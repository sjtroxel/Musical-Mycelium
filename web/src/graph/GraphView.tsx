import { useEffect, useRef } from "react";
import { layout, tallestColumn } from "./layout";
import {
  edgeKey,
  frameAt,
  graphSignature,
  lerp,
  lerpView,
  prefersReducedMotion,
  resolveMotionMode,
  type MotionFrame,
  type MotionMode,
  type View,
} from "./motion";
import type { RenderEdge, RenderGraph, RenderNode } from "./subgraph";

/**
 * The map. Canvas 2D, laid out by `layout.ts`.
 *
 * The engine was decided at step 3 with reasons recorded in the phase 5 IMPLEMENTATION doc: WebGL's
 * only argument here was scale, and the measured scale is 458 nodes at the very worst with the demo
 * surfaces at 3 and 31. What canvas charges is hit-testing and label placement by hand, and what it
 * buys is that steps 5, 6 and 7 are then just drawing.
 *
 * **Layout is step 5's decision and it lives in `layout.ts`.** x is influence depth, y is year within
 * the column, and there is no simulation at all — see that file for why a chronological axis cannot
 * be drawn on this corpus. This file draws; it does not decide where anything goes.
 *
 * Pan, zoom, drag and follow-an-edge are step 8; the palette is step 6; motion is step 7. The phase's
 * fence is engine, then layout, then palette, then motion, and reaching forward from here is how the
 * fence stops meaning anything.
 *
 * Every colour is read from the CSS custom properties in `styles.css` so step 6 has one place to
 * change rather than twenty.
 *
 * **Motion is step 7 and it lives in `motion.ts`.** The sentence that stood here — *"`prefers-reduced-motion`
 * needs no special case any more: a deterministic layout has no settling animation to suppress"* — was
 * true about the *simulation* and wrong about the map. Removing the simulation removed the settling,
 * not the movement: this component redraws on every claim frame, and step 7 measured the result. The
 * acid jazz subject reflows vertically four times while the answer streams and a claim edge appears
 * fully formed the instant the gate approves it, both as hard cuts. `motion.ts` carries the numbers.
 */

interface SimNode extends RenderNode {
  /** Where `layout()` says this node belongs. */
  x: number;
  y: number;
  /** Where it was last drawn, which is the same as `x`/`y` unless the layout just moved it. */
  fromX: number;
  fromY: number;
  /** True when this node was not on screen at all in the previous draw. */
  entering: boolean;
}

/** A record of one drawn picture: where its nodes sat, what it had approved, and where the camera was. */
interface Painted {
  signature: string;
  positions: Map<string, { x: number; y: number }>;
  claimed: Set<string>;
  view: View | null;
}

interface SimLink {
  source: SimNode;
  target: SimNode;
  kind: RenderEdge["kind"];
  order: number | null;
  /** True when the gate approved this edge since the last draw. Only ever true for a claimed edge. */
  entering: boolean;
}

/**
 * The map is as tall as its busiest column needs, between these two bounds.
 *
 * A fixed height was right when a simulation spread nodes in two dimensions. A column layout only
 * has the vertical, so eleven nodes in one column at 300px became a stack of dots a few pixels
 * apart. The upper bound is there because the map must not push the cited claims below the fold —
 * the claims are the answer and the picture is the illustration, never the other way round.
 */
const MIN_HEIGHT = 260;
const MAX_HEIGHT = 460;
const ROW_PITCH = 30;
const FALLBACK_WIDTH = 640;

function palette(root: Element): Record<string, string> {
  const style = getComputedStyle(root);
  const token = (name: string, fallback: string) =>
    style.getPropertyValue(name).trim() || fallback;
  return {
    ink: token("--ink", "#16161a"),
    inkSoft: token("--ink-soft", "#55555f"),
    inkFaint: token("--ink-faint", "#7c7c88"),
    rule: token("--rule", "#e3e3de"),
    // The map's context edges read `--edge-context`, not `--rule`. Same colour until step 6; two
    // different jobs, and only one of them is content the caption counts out loud.
    edgeContext: token("--edge-context", "#b0b0a7"),
    card: token("--card", "#ffffff"),
    accent: token("--accent", "#3d5a45"),
  };
}

/** A short triangle at the target end, so the direction of influence is readable without a legend. */
function arrowhead(
  ctx: CanvasRenderingContext2D,
  [fromX, fromY]: [number, number],
  [toX, toY]: [number, number],
  radius: number,
): void {
  const dx = toX - fromX;
  const dy = toY - fromY;
  const length = Math.hypot(dx, dy);
  if (length < 1) return;

  const ux = dx / length;
  const uy = dy / length;
  const tipX = toX - ux * radius;
  const tipY = toY - uy * radius;
  const size = 7;

  ctx.beginPath();
  ctx.moveTo(tipX, tipY);
  ctx.lineTo(tipX - ux * size + -uy * size * 0.5, tipY - uy * size + ux * size * 0.5);
  ctx.lineTo(tipX - ux * size - -uy * size * 0.5, tipY - uy * size - ux * size * 0.5);
  ctx.closePath();
  ctx.fill();
}

export function GraphView({ graph, motion }: { graph: RenderGraph; motion?: MotionMode }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  /**
   * What the map last put on screen, so the next draw can tell what actually changed.
   *
   * The position cache is back, and for the opposite reason it was removed. It existed to stop a
   * *simulation* settling somewhere new on every run; `layout()` is pure, so that problem is gone.
   * What these hold is the previous DRAW, which is what tells a node that just moved from one that
   * did not, and a claim edge the gate approved a moment ago from one already on screen.
   *
   * **Two slots, not one, and that is the whole StrictMode fix.** `main.tsx` mounts the app inside
   * `StrictMode`, so React runs this effect TWICE on mount. One slot meant the first pass recorded
   * every edge as drawn and the second pass found nothing new and painted the finished picture
   * instantly — all three motion modes looked identical in the browser while every unit test passed,
   * because the tests rendered this component bare and the app never does. `shown` describes the
   * picture on screen now; `before` describes the one prior to it. A repeat invocation of the same
   * picture animates from `before`, so running the effect twice is indistinguishable from running it
   * once.
   */
  const shown = useRef<Painted>({
    signature: "",
    positions: new Map(),
    claimed: new Set(),
    view: null,
  });
  const before = useRef<Painted>({
    signature: "",
    positions: new Map(),
    claimed: new Set(),
    view: null,
  });

  /**
   * When the current animation began, held across renders on purpose.
   *
   * Reset only when the picture's content changes. An unrelated re-render mid-animation — a prose
   * token, most often — re-enters this effect, and restarting the clock there would make the edge
   * begin drawing itself again from nothing on every token.
   */
  const startedAt = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas === null) return;

    // jsdom returns null here, which is the whole reason the selection logic lives in `subgraph.ts`
    // and not in this file. The tests assert the structure and the caption; the pixels are checked in
    // a real browser instead.
    const ctx = canvas.getContext("2d");
    if (ctx === null) return;

    const width = canvas.parentElement?.clientWidth || FALLBACK_WIDTH;
    const height = Math.min(
      MAX_HEIGHT,
      Math.max(MIN_HEIGHT, tallestColumn(graph) * ROW_PITCH + 60),
    );
    const dpr = window.devicePixelRatio || 1;
    canvas.style.width = "100%";
    // Narrowing does not survive into the draw closure, so the non-null element is captured once.
    const surface: HTMLCanvasElement = canvas;
    // The backing store is sized per FRAME, not here. The canvas box itself grows as the map gains
    // rows, and a box that jumps height is a layout shift no amount of in-canvas tweening can hide.

    const colors = palette(document.documentElement);

    // The mode is resolved per draw rather than once, so a visitor who turns reduced motion on
    // mid-answer gets it honoured on the next claim instead of at the next page load.
    const mode = motion ?? resolveMotionMode(prefersReducedMotion());

    // Keyed on what the picture CONTAINS, never on the `RenderGraph` object — see `graphSignature`.
    const signature = graphSignature(graph);
    const isNewPicture = signature !== shown.current.signature;
    // On a repeat invocation of the same picture, `shown` already describes it, so the state to
    // animate away from is the one before it. That is what makes the StrictMode double-invoke and a
    // mid-answer re-render both behave like a single mount.
    const from = isNewPicture ? shown.current : before.current;
    const previous = from.positions;
    const seenEdges = from.claimed;
    const previousView = from.view;

    const placed = layout(graph);
    const nodes: SimNode[] = graph.nodes.map((node) => {
      const target = placed.get(node.id) ?? { x: 0, y: 0 };
      const was = previous.get(node.id);
      return {
        ...node,
        ...target,
        fromX: was?.x ?? target.x,
        fromY: was?.y ?? target.y,
        entering: was === undefined,
      };
    });
    const byId = new Map(nodes.map((node) => [node.id, node]));

    const links: SimLink[] = graph.edges.flatMap((edge) => {
      const source = byId.get(edge.from);
      const target = byId.get(edge.to);
      if (source === undefined || target === undefined) return [];
      return [
        {
          source,
          target,
          kind: edge.kind,
          order: edge.order,
          // Only a claimed edge can enter. A context edge appearing is a side effect of the
          // neighbourhood growing, not a thing the gate decided, and animating it would give the
          // corpus's unwalked lines the same arrival as an approved claim.
          entering: edge.kind === "claimed" && !seenEdges.has(edgeKey(edge.from, edge.to)),
        },
      ];
    });

    const radius = (node: SimNode) => (node.role === "walked" ? 6 : 3.5);

    // Which nodes sit next to which, used only to decide which side a label goes on.
    const neighbours = new Map<string, SimNode[]>();
    for (const link of links) {
      const source = link.source as SimNode;
      const target = link.target as SimNode;
      neighbours.set(source.id, [...(neighbours.get(source.id) ?? []), target]);
      neighbours.set(target.id, [...(neighbours.get(target.id) ?? []), source]);
    }

    const font = '12px ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif';

    /**
     * Fit the laid-out positions into the box.
     *
     * Not cosmetic. The headline chip's entire component is three nodes (measured at step 3), and a
     * force layout of three nodes occupies a fraction of a 650x300 canvas, so without this the
     * signature demo draws a tiny cluster in the middle with its labels on top of each other. Rather
     * than scaling the canvas transform, this projects positions and leaves radii and type at a fixed
     * size, which is the thing canvas makes easy and a point-sprite renderer makes hard.
     *
     * Right padding is measured from the widest label, because labels are drawn to the right of their
     * node and would otherwise run off the edge. That is the by-hand label placement canvas charges
     * for, and step 3 took that trade knowingly.
     */
    function viewFor(): View {
      if (ctx === null || nodes.length === 0) {
        return { k: 1, cx: 0, cy: 0, originX: 0, height };
      }
      ctx.font = font;
      const widest = nodes
        .filter((node) => node.role === "walked")
        .reduce((wide, node) => Math.max(wide, ctx.measureText(node.label).width), 0);

      const padY = 26;
      const padLeft = 20;
      const padRight = 20 + Math.min(widest + 10, width * 0.35);

      const xs = nodes.map((node) => node.x);
      const ys = nodes.map((node) => node.y);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);

      // A cap, so two nodes are not blown up until the map reads as a diagram of nothing.
      const k = Math.min(
        (width - padLeft - padRight) / Math.max(maxX - minX, 1),
        (height - padY * 2) / Math.max(maxY - minY, 1),
        2.2,
      );
      const cx = (minX + maxX) / 2;
      const cy = (minY + maxY) / 2;
      const originX = padLeft + (width - padLeft - padRight) / 2;

      return { k, cx, cy, originX, height };
    }

    // Hoisted out of `draw` because it depends only on the *target* layout, which does not change
    // while a frame animates, and because it measures text — not free to redo sixty times a second.
    const targetView = viewFor();

    function draw(frame: MotionFrame) {
      if (ctx === null) return;

      // The camera for THIS frame. In `none` and `reveal`, `positionT` is always 1 and this is
      // exactly `targetView` — the cut step 6 committed. Only `full` moves the camera, and moving it
      // is most of what `full` is: the nodes barely travel by comparison.
      const view =
        previousView === null || frame.positionT >= 1
          ? targetView
          : lerpView(previousView, targetView, frame.positionT);

      // Resized per frame so the element grows with the picture instead of snapping to its final
      // height on the first one. Reallocating a 640x460 backing store twenty-five times over 420ms
      // is not a cost worth optimising at this scale.
      const frameHeight = Math.round(view.height);
      surface.width = width * dpr;
      surface.height = frameHeight * dpr;
      surface.style.height = `${frameHeight}px`;

      const at = (x: number, y: number): [number, number] => [
        (x - view.cx) * view.k + view.originX,
        (y - view.cy) * view.k + view.height / 2,
      ];
      const px = (node: SimNode): [number, number] =>
        at(lerp(node.fromX, node.x, frame.positionT), lerp(node.fromY, node.y, frame.positionT));

      ctx.save();
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, frameHeight);

      // Context first, so an unclaimed corpus edge can never be drawn over an approved one.
      for (const link of links) {
        const source = link.source as SimNode;
        const target = link.target as SimNode;
        if (link.kind !== "context") continue;
        const [sx, sy] = px(source);
        const [tx, ty] = px(target);
        ctx.strokeStyle = colors.edgeContext ?? "#b0b0a7";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(tx, ty);
        ctx.stroke();
      }

      for (const link of links) {
        const source = link.source as SimNode;
        const target = link.target as SimNode;
        if (link.kind !== "claimed") continue;
        const [sx, sy] = px(source);
        const [tx, ty] = px(target);

        // The one motion in this file that means something. The line grows from the object toward
        // the subject — the direction influence actually runs, per `RenderEdge.from` — so watching it
        // is watching the gate approve a claim. An edge already on screen is drawn whole; `t` is 1
        // for it and every expression below collapses to what step 6 committed.
        const t = link.entering ? frame.edgeT : 1;
        const hx = lerp(sx, tx, t);
        const hy = lerp(sy, ty, t);

        ctx.strokeStyle = colors.accent ?? "#3d5a45";
        ctx.fillStyle = colors.accent ?? "#3d5a45";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(hx, hy);
        ctx.stroke();
        // The arrowhead only lands once the line has arrived. A head travelling ahead of its own
        // line reads as a cursor rather than as a connection being made.
        if (t >= 1) arrowhead(ctx, [sx, sy], [tx, ty], radius(target) + 3);
      }

      for (const node of nodes) {
        const [nx, ny] = px(node);
        // A node that was not on screen before fades in rather than blinking on. Nodes already
        // drawn are untouched, so a growing neighbourhood does not re-enter itself on every claim.
        ctx.globalAlpha = node.entering ? frame.edgeT : 1;
        ctx.beginPath();
        ctx.arc(nx, ny, radius(node), 0, Math.PI * 2);
        ctx.fillStyle =
          node.role === "walked" ? (colors.accent ?? "#3d5a45") : (colors.card ?? "#ffffff");
        ctx.fill();
        ctx.strokeStyle =
          node.role === "walked" ? (colors.accent ?? "#3d5a45") : (colors.inkFaint ?? "#7c7c88");
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      // Only walked nodes are labelled. A context node is there to show the answer sits in a
      // neighbourhood, not to be read, and labelling forty of them would say otherwise.
      ctx.font = font;
      ctx.textBaseline = "middle";
      for (const node of nodes) {
        if (node.role !== "walked") continue;
        const [nx, ny] = px(node);

        // Put the label on the emptier side. An origins answer aims every edge at one node, so a
        // label fixed to the right lands across the arrows about half the time — which is what
        // happened to "acid jazz" the first time this was rendered. Choosing a side per node is six
        // lines; real label placement is step 5's problem, not this step's.
        const around = neighbours.get(node.id) ?? [];
        const lean =
          around.reduce((sum, other) => sum + (px(other)[0] - nx), 0) / (around.length || 1);
        const onLeft = lean > 0;
        const lx = nx + (onLeft ? -(radius(node) + 5) : radius(node) + 5);
        ctx.textAlign = onLeft ? "right" : "left";

        ctx.lineWidth = 3;
        ctx.strokeStyle = colors.card ?? "#ffffff";
        ctx.strokeText(node.label, lx, ny);
        ctx.fillStyle = colors.ink ?? "#16161a";
        ctx.fillText(node.label, lx, ny);
      }
      ctx.textAlign = "left";
      // The approval ordinal on each claimed edge. This is DoD 3's "in the order it was walked" made
      // readable on a still image rather than only as a thing that happened while you were watching
      // the stream.
      //
      // Drawn last, so the label halo cannot eat the digit. Drawing these first was tried and made
      // the ordinals look scratched out, which is why the overlap is solved by placing them rather
      // than by stacking them.
      for (const link of links) {
        if (link.kind !== "claimed" || link.order === null) continue;
        // The badge waits for its own line. Numbering an edge before the edge exists puts the
        // ordinal in empty space, and the ordinal is the thing that says what order the gate
        // approved these in.
        if (link.entering && frame.edgeT < 1) continue;
        const source = link.source as SimNode;
        const target = link.target as SimNode;
        const [sx, sy] = px(source);
        const [tx, ty] = px(target);
        // Nudged off the line, perpendicular to it. On the headline chip the badge lands exactly on
        // the "blues rock" label otherwise, and that chip is the one a visitor sees first.
        // A third of the way from the source, nudged off the line, rather than at the midpoint.
        // An origins answer aims every arrow at one node, so midpoints crowd that node's label —
        // which on the acid jazz chip is the subject itself, the label a visitor most needs. Pushed
        // back toward the parents, the ordinals sit in empty space, and the parents' own labels have
        // already been placed on their outward side.
        const len = Math.max(Math.hypot(tx - sx, ty - sy), 1);
        const mx = sx + (tx - sx) * 0.33 - ((ty - sy) / len) * 10;
        const my = sy + (ty - sy) * 0.33 + ((tx - sx) / len) * 10;
        ctx.beginPath();
        ctx.arc(mx, my, 8, 0, Math.PI * 2);
        ctx.fillStyle = colors.card ?? "#ffffff";
        ctx.fill();
        ctx.strokeStyle = colors.accent ?? "#3d5a45";
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.fillStyle = colors.accent ?? "#3d5a45";
        ctx.textAlign = "center";
        ctx.fillText(String(link.order), mx, my + 0.5);
        ctx.textAlign = "left";
      }

      ctx.restore();
    }

    // Record what this picture puts on screen, and start its clock — but only when the picture is
    // genuinely a new one. Doing this unconditionally is precisely the bug that made all three modes
    // look the same.
    if (isNewPicture) {
      before.current = shown.current;
      shown.current = {
        signature,
        positions: new Map(nodes.map((node) => [node.id, { x: node.x, y: node.y }])),
        claimed: new Set(
          graph.edges
            .filter((edge) => edge.kind === "claimed")
            .map((edge) => edgeKey(edge.from, edge.to)),
        ),
        view: targetView,
      };
      startedAt.current = null;
    }

    // `none` — which is what `prefers-reduced-motion: reduce` resolves to — is a single draw with no
    // loop started at all, identical to what step 6 committed. Not a loop that runs at zero duration:
    // reduced motion should mean no animation happened, not an animation nobody could see.
    if (mode === "none") {
      draw({ positionT: 1, edgeT: 1, done: true });
      return;
    }

    let raf = 0;
    const tick = (now: number) => {
      startedAt.current ??= now;
      const frame = frameAt(mode, now - startedAt.current);
      draw(frame);
      if (!frame.done) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    // Cancelled on unmount and before every re-run. A claim landing mid-animation replaces the loop
    // rather than racing a second one against it — two loops drawing the same canvas is a flicker
    // that only appears under a fast stream, which is exactly when a visitor is watching.
    return () => cancelAnimationFrame(raf);
  }, [graph, motion]);

  const walked = graph.nodes.filter((node) => node.role === "walked").length;

  return (
    <figure className="map">
      <canvas
        className="map__canvas"
        ref={canvasRef}
        role="img"
        aria-label={
          `A map of ${walked} ${walked === 1 ? "node" : "nodes"} this answer reached, ` +
          `${graph.claimed} approved ${graph.claimed === 1 ? "connection" : "connections"} ` +
          `numbered in the order they were approved, and ${graph.context} nearby ` +
          `${graph.context === 1 ? "connection" : "connections"} from the corpus that were not walked. ` +
          `The claims themselves are listed below in text.`
        }
      />
      <figcaption className="map__caption">
        {/* The claimed/context distinction stated in words. Without this sentence the map implies the
            faint edges are part of the answer, which is the exact slide from "traceable" to "asserted"
            that `.claude/rules/grounding-and-claims.md` forbids. */}
        <strong>{graph.claimed}</strong> cited{" "}
        {graph.claimed === 1 ? "connection" : "connections"}, numbered in the order the gate approved
        them. The faint lines are <strong>{graph.context}</strong> further{" "}
        {graph.context === 1 ? "connection" : "connections"} the corpus holds around them, shown for
        bearings and <em>not</em> part of this answer.
        {graph.truncated && " The neighbourhood is larger than what is drawn here."}
      </figcaption>
    </figure>
  );
}
