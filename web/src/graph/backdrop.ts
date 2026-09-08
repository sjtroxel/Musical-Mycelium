/**
 * The hero backdrop: the real corpus, drifting, behind the page.
 *
 * **Everything here is a pure function of elapsed milliseconds.** That split is the same one
 * `graph/motion.ts` makes and for the same reason: jsdom has no canvas, so anything computed inside a
 * render loop cannot be tested at all. The timing and the geometry are checkable here even though the
 * pixels are not, and `Backdrop.tsx` is left with nothing but `ctx` calls and lifecycle.
 *
 * **The scheme is S4 "lit edges", decided by sjtroxel on 2026-09-08** from four rendered candidates in
 * `web/previews/palette7.html`. Nodes go quiet and the connections carry the accent, because the
 * project's claim is that music history is a network and this is the scheme that draws the network
 * rather than the nodes. The as-built record with every measurement is
 * `docs/phases/phase-7-cinematic-surface-IMPLEMENTATION.md` §3.1.
 *
 * **The node colors are dark on purpose and it is not a taste decision.** They were `--ink-soft` and
 * `--ink-faint`; measured across the drift the title never cleared its 3.0 large-text contrast bar and
 * fell to 2.35:1 at full brightness. The bright pixels in this scheme are the NODES, not the accent
 * edges -- halving edge alpha moved the number by 0.00 -- so the nodes came down instead. Title
 * measured 10.90:1 after. Raising these values re-opens a contrast failure; if they change, re-measure
 * rather than eyeball.
 */

import { BACKDROP } from "./backdropData";

/** Rose on the edges, near-black on the nodes. Every value is a token from `styles.css`. */
export const SCHEME = {
  genre: "#8b81a6",
  artist: "#4a4160",
  edge: "#ff5cae",
  genreAlpha: 0.62,
  artistAlpha: 0.45,
  edgeAlpha: 0.16,
} as const;

/** Positions live on a 0..65535 grid: forty times finer than a pixel at render size, and half the bytes. */
const QUANT = 65535;

export interface BackdropGraph {
  /** x then y, unit box, one pair per node. */
  readonly xy: Float32Array;
  /** 0 genre, 1 artist. */
  readonly kinds: Uint8Array;
  /** subject then object index, one pair per edge. */
  readonly edges: Uint16Array;
  /** Edge count per node, derived rather than shipped. */
  readonly degree: Uint16Array;
  readonly nodeCount: number;
  readonly edgeCount: number;
}

function bytes(b64: string): Uint8Array {
  const raw = atob(b64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

/**
 * Unpack the generated module into typed arrays.
 *
 * Degree is computed here rather than shipped: it is one pass over the edge list, and 1,465 more bytes
 * for something derivable is exactly what the asset budget exists to catch.
 */
export function decode(data: typeof BACKDROP = BACKDROP): BackdropGraph {
  const xyBytes = bytes(data.xy);
  const xyRaw = new Uint16Array(xyBytes.buffer, xyBytes.byteOffset, xyBytes.length / 2);
  const xy = new Float32Array(xyRaw.length);
  for (let i = 0; i < xyRaw.length; i++) xy[i] = (xyRaw[i] ?? 0) / QUANT;

  const kindBits = bytes(data.kinds);
  const kinds = new Uint8Array(data.nodeCount);
  for (let i = 0; i < data.nodeCount; i++) {
    kinds[i] = ((kindBits[i >> 3] ?? 0) >> (i & 7)) & 1;
  }

  const edgeBytes = bytes(data.edges);
  const edges = new Uint16Array(edgeBytes.buffer, edgeBytes.byteOffset, edgeBytes.length / 2);

  const degree = new Uint16Array(data.nodeCount);
  for (let i = 0; i < edges.length; i += 2) {
    const a = edges[i] ?? 0;
    const b = edges[i + 1] ?? 0;
    degree[a] = (degree[a] ?? 0) + 1;
    degree[b] = (degree[b] ?? 0) + 1;
  }

  return { xy, kinds, edges, degree, nodeCount: data.nodeCount, edgeCount: data.edgeCount };
}

/**
 * Where the camera is at time `t`.
 *
 * Three periods that do not divide into each other -- 17s, 21s, 23s -- so the drift never visibly
 * repeats. A loop a visitor can spot is worse than no motion, because once seen it is all they see.
 */
export function camera(t: number, width: number, height: number) {
  const zoom = 1.06 + Math.sin(t / 21000) * 0.06;
  const scale = Math.max(width, height) * zoom;
  return {
    scale,
    originX: width / 2 - (0.5 + Math.sin(t / 17000) * 0.045) * scale,
    originY: height / 2 - (0.5 + Math.cos(t / 23000) * 0.035) * scale,
  };
}

/** Deterministic per-node twinkle phase. Seeded so two loads draw the same picture. */
export function phases(count: number, seed: number = BACKDROP.seed): Float32Array {
  let s = (seed * 977) >>> 0;
  const out = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    s = (s + 0x6d2b79f5) >>> 0;
    let r = Math.imul(s ^ (s >>> 15), 1 | s);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    out[i] = (((r ^ (r >>> 14)) >>> 0) / 4294967296) * Math.PI * 2;
  }
  return out;
}

/** Node radius from its edge count, capped so one hub does not become a blob. */
export function radiusOf(degree: number): number {
  return 0.9 + Math.min(degree, 40) * 0.07;
}

/** Alpha for one node at one instant. Exported so the twinkle's range is testable without a canvas. */
export function nodeAlpha(t: number, phase: number, isGenre: boolean, animated: boolean): number {
  const twinkle = animated ? 0.55 + 0.45 * Math.sin(t / 2600 + phase) : 1;
  return (isGenre ? SCHEME.genreAlpha : SCHEME.artistAlpha) * twinkle;
}

/** One frame. Keeps nothing; everything it needs is an argument. */
export function drawFrame(
  ctx: CanvasRenderingContext2D,
  graph: BackdropGraph,
  phase: Float32Array,
  options: { t: number; width: number; height: number; animated: boolean },
): void {
  const { t, width, height, animated } = options;
  const { scale, originX, originY } = camera(t, width, height);
  const px = (i: number) => originX + (graph.xy[i * 2] ?? 0) * scale;
  const py = (i: number) => originY + (graph.xy[i * 2 + 1] ?? 0) * scale;

  ctx.clearRect(0, 0, width, height);

  // Edges first and as one path: a single `stroke()` means overlapping hairlines do not compound their
  // alpha, which is what keeps a dense cluster from burning out into a solid patch.
  ctx.lineWidth = 1;
  ctx.strokeStyle = SCHEME.edge;
  ctx.globalAlpha = SCHEME.edgeAlpha;
  ctx.beginPath();
  for (let i = 0; i < graph.edges.length; i += 2) {
    const a = graph.edges[i] ?? 0;
    const b = graph.edges[i + 1] ?? 0;
    ctx.moveTo(px(a), py(a));
    ctx.lineTo(px(b), py(b));
  }
  ctx.stroke();

  for (let i = 0; i < graph.nodeCount; i++) {
    const x = px(i);
    const y = py(i);
    if (x < -20 || y < -20 || x > width + 20 || y > height + 20) continue;
    const isGenre = graph.kinds[i] === 0;
    ctx.globalAlpha = nodeAlpha(t, phase[i] ?? 0, isGenre, animated);
    ctx.fillStyle = isGenre ? SCHEME.genre : SCHEME.artist;
    ctx.beginPath();
    ctx.arc(x, y, radiusOf(graph.degree[i] ?? 0), 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}
