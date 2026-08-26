import { describe, expect, it } from "vitest";
import { SseParser, parseFrame } from "./stream";

/**
 * Frontend tests are thin on purpose (IMPLEMENTATION 7): the stream parser and the claim/prose
 * separation, not component snapshots. The frontend is a two-way door and over-testing something
 * designed to be thrown away twice is waste.
 *
 * The parser earns its tests because a stream arrives in arbitrary chunks and the failure mode — a
 * frame split across two reads — is invisible locally and shows up only over a real network.
 */

const CLAIM = 'event: claim\ndata: {"claim":{"subject_id":"Q1","object_id":"Q2"}}\n\n';
const TOKEN = 'event: token\ndata: {"text":"hello"}\n\n';

describe("parseFrame", () => {
  it("reads the event name onto the payload as a discriminator", () => {
    const frame = parseFrame('event: token\ndata: {"text":"hi"}');
    expect(frame).toEqual({ type: "token", text: "hi" });
  });

  it("strips exactly one leading space from a field value, per the SSE spec", () => {
    // `sse()` in api/app.py emits "data: {...}". A parser that keeps the space still parses, because
    // JSON tolerates leading whitespace — but one that strips *all* whitespace would corrupt a token
    // frame whose text legitimately begins with a space, and prose is full of those.
    const frame = parseFrame('event: token\ndata:  {"text":" leading"}');
    expect(frame).toEqual({ type: "token", text: " leading" });
  });

  it("joins multi-line data with a newline", () => {
    const frame = parseFrame('event: token\ndata: {"text":\ndata: "split"}');
    expect(frame).toEqual({ type: "token", text: "split" });
  });

  it("ignores comment lines", () => {
    const frame = parseFrame(': keep-alive\nevent: token\ndata: {"text":"x"}');
    expect(frame).toEqual({ type: "token", text: "x" });
  });

  it("returns null rather than throwing on malformed JSON", () => {
    // A bad frame mid-stream should cost the visitor that frame, not the answer.
    expect(parseFrame("event: token\ndata: {oops")).toBeNull();
  });

  it("returns null when there is no event name", () => {
    expect(parseFrame('data: {"text":"x"}')).toBeNull();
  });
});

describe("SseParser", () => {
  it("yields whole frames from one chunk", () => {
    const parser = new SseParser();
    expect(parser.push(CLAIM + TOKEN)).toHaveLength(2);
  });

  it("reassembles a frame split across chunks", () => {
    const parser = new SseParser();
    const split = 20;
    expect(parser.push(TOKEN.slice(0, split))).toHaveLength(0);
    expect(parser.push(TOKEN.slice(split))).toEqual([{ type: "token", text: "hello" }]);
  });

  it("reassembles a frame split one character at a time", () => {
    const parser = new SseParser();
    const frames = [...TOKEN].flatMap((char) => parser.push(char));
    expect(frames).toEqual([{ type: "token", text: "hello" }]);
  });

  it("holds an incomplete trailing frame rather than emitting a partial one", () => {
    const parser = new SseParser();
    expect(parser.push(TOKEN + "event: claim\ndata: {")).toHaveLength(1);
  });

  it("handles CRLF separators", () => {
    const parser = new SseParser();
    expect(parser.push('event: token\r\ndata: {"text":"x"}\r\n\r\n')).toEqual([
      { type: "token", text: "x" },
    ]);
  });
});
