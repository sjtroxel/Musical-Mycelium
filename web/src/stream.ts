import type { Frame } from "./types";

/**
 * The SSE client.
 *
 * **`EventSource` is deliberately not used, and the reason is money rather than taste.** `EventSource`
 * reconnects automatically when the server closes the stream — which is exactly what happens at the end
 * of every successful `/lineage` run. On a one-shot query that reconnect re-runs the whole agent loop,
 * forever, on a public URL nobody is watching. `.claude/rules/aws-and-cost.md` puts the per-visitor
 * ceiling in the token budget, and an auto-reconnecting client multiplies that ceiling by however long a
 * tab stays open. `fetch` plus a `ReadableStream` gives a one-shot stream and an `AbortController`.
 *
 * The parser is split out from the transport so it can be tested without a network: a stream arrives in
 * arbitrary chunks, and the bug this shape prevents is a frame split across two reads.
 */

const FRAME_SEPARATOR = /\r\n\r\n|\n\n|\r\r/;

/** Accumulates chunks and yields whole frames. One instance per request. */
export class SseParser {
  private buffer = "";

  /**
   * Feed one chunk of decoded text. Returns every frame that is now complete.
   *
   * Anything unparseable is dropped rather than thrown. A malformed frame mid-stream should cost the
   * visitor that frame, not the answer.
   */
  push(chunk: string): Frame[] {
    this.buffer += chunk;
    const frames: Frame[] = [];

    for (;;) {
      const match = FRAME_SEPARATOR.exec(this.buffer);
      if (match === null) break;

      const raw = this.buffer.slice(0, match.index);
      this.buffer = this.buffer.slice(match.index + match[0].length);

      const frame = parseFrame(raw);
      if (frame !== null) frames.push(frame);
    }

    return frames;
  }
}

/**
 * One raw frame to a typed one, or `null`.
 *
 * Per the SSE spec, `data:` may appear on several lines and they join with a newline. `api/app.py`
 * emits JSON via `json.dumps`, which escapes newlines, so in practice there is always exactly one —
 * but a parser that assumes that breaks silently the day it stops being true.
 */
export function parseFrame(raw: string): Frame | null {
  let event = "";
  const data: string[] = [];

  for (const line of raw.split(/\r\n|\n|\r/)) {
    if (line === "" || line.startsWith(":")) continue;

    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    // "If value starts with a U+0020 SPACE, remove it" — the spec's rule, and `sse()` emits that space.
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);

    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }

  if (event === "" || data.length === 0) return null;

  try {
    const payload = JSON.parse(data.join("\n")) as Record<string, unknown>;
    return { ...payload, type: event } as Frame;
  } catch {
    return null;
  }
}

/**
 * Where the API lives. Empty in dev, where Vite proxies `/api` to a local uvicorn; the deployed
 * Function URL at build time. Trailing slash normalised so `${base}/lineage` cannot become a double
 * slash, which a Function URL answers with a redirect that drops the query string.
 */
export const API_BASE: string = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/+$/, "");

export interface StreamOptions {
  signal?: AbortSignal;
  onFrame: (frame: Frame) => void;
}

/**
 * Run one query, calling `onFrame` as frames arrive.
 *
 * Resolves when the stream ends. Rejects on a transport failure, on a non-2xx, or on abort — the
 * caller decides what any of that looks like on screen, because this module owns no presentation.
 */
export async function streamLineage(query: string, options: StreamOptions): Promise<void> {
  const url = `${API_BASE}/lineage?q=${encodeURIComponent(query)}`;
  // `Accept` is a CORS-safelisted request header, so this stays a *simple* request and never
  // preflights. That matters: the Function URL's `allow_headers` is `["content-type"]` only. Adding any
  // non-safelisted header here — an `X-Request-Id`, an auth token — turns this into a preflighted
  // request that the deployed CORS config will reject, and it will work perfectly in `npm run dev`
  // because the Vite proxy makes it same-origin. Verified live 2026-08-26.
  const init: RequestInit = { headers: { Accept: "text/event-stream" } };
  if (options.signal) init.signal = options.signal;

  const response = await fetch(url, init);

  if (!response.ok) {
    throw new Error(`the server answered ${response.status}`);
  }
  if (response.body === null) {
    throw new Error("the server sent no body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      // `stream: true` matters: a multi-byte character can straddle two chunks, and decoding each
      // chunk independently turns it into replacement characters. The corpus has plenty of them.
      for (const frame of parser.push(decoder.decode(value, { stream: true }))) {
        options.onFrame(frame);
      }
    }
    for (const frame of parser.push(decoder.decode())) {
      options.onFrame(frame);
    }
  } finally {
    reader.releaseLock();
  }
}
