import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
} from "d3-force";
import type { SimulationLinkDatum, SimulationNodeDatum } from "d3-force";
import { useEffect, useRef } from "react";
import type { RenderEdge, RenderGraph, RenderNode } from "./subgraph";

/**
 * The map. Canvas 2D, laid out by `d3-force`.
 *
 * The engine was decided at step 3 with reasons recorded in the phase 5 IMPLEMENTATION doc: WebGL's
 * only argument here was scale, and the measured scale is 458 nodes at the very worst with the demo
 * surfaces at 3 and 31. What canvas charges is hit-testing and label placement by hand, and what it
 * buys is that steps 5, 6 and 7 are then just drawing.
 *
 * **This step deliberately stops at drawing.** Pan, zoom, drag and follow-an-edge are step 8; the
 * palette is step 6; motion is step 7. The phase's fence is engine, then layout, then palette, then
 * motion, and reaching forward from here is how the fence stops meaning anything. What is here is the
 * first honest render and nothing else.
 *
 * Two things it does do now rather than later, because both are cheaper now than as a retrofit:
 * `prefers-reduced-motion` settles the layout without animating it, and every colour is read from the
 * CSS custom properties in `styles.css` so step 6 has one place to change rather than twenty.
 */

interface SimNode extends SimulationNodeDatum, RenderNode {}

interface SimLink extends SimulationLinkDatum<SimNode> {
  kind: RenderEdge["kind"];
  order: number | null;
}

const HEIGHT = 300;
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
    card: token("--card", "#ffffff"),
    accent: token("--accent", "#3d5a45"),
  };
}

function prefersReducedMotion(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
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

export function GraphView({ graph }: { graph: RenderGraph }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // Positions survive a re-render so a claim arriving mid-stream extends the map instead of shuffling
  // it. Watching the layout reshuffle on every frame would read as the answer changing its mind.
  const positions = useRef(new Map<string, { x: number; y: number }>());

  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas === null) return;

    // jsdom returns null here, which is the whole reason the selection logic lives in `subgraph.ts`
    // and not in this file. The tests assert the structure and the caption; the pixels are checked in
    // a real browser instead.
    const ctx = canvas.getContext("2d");
    if (ctx === null) return;

    const width = canvas.parentElement?.clientWidth || FALLBACK_WIDTH;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = HEIGHT * dpr;
    canvas.style.width = "100%";
    canvas.style.height = `${HEIGHT}px`;

    const colors = palette(document.documentElement);

    const nodes: SimNode[] = graph.nodes.map((node) => {
      const seen = positions.current.get(node.id);
      return seen === undefined ? { ...node } : { ...node, x: seen.x, y: seen.y };
    });
    const byId = new Map(nodes.map((node) => [node.id, node]));

    const links: SimLink[] = graph.edges.flatMap((edge) => {
      const source = byId.get(edge.from);
      const target = byId.get(edge.to);
      if (source === undefined || target === undefined) return [];
      return [{ source, target, kind: edge.kind, order: edge.order }];
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

    const simulation = forceSimulation(nodes)
      .force("link", forceLink<SimNode, SimLink>(links).id((node) => node.id).distance(70))
      .force("charge", forceManyBody().strength(-220))
      .force("collide", forceCollide<SimNode>((node) => radius(node) + 12))
      // forceX/forceY toward the centre rather than forceCenter: the corpus is 169 disjoint islands
      // (measured at step 3) and a disconnected component under forceCenter drifts off screen
      // forever, because nothing is pulling it back.
      .force("x", forceX(width / 2).strength(0.06))
      .force("y", forceY(HEIGHT / 2).strength(0.09));

    const font = '12px ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif';

    /**
     * Fit whatever the simulation settled on into the box.
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
    function project(): (x: number, y: number) => [number, number] {
      if (ctx === null || nodes.length === 0) return (x, y) => [x, y];
      ctx.font = font;
      const widest = nodes
        .filter((node) => node.role === "walked")
        .reduce((wide, node) => Math.max(wide, ctx.measureText(node.label).width), 0);

      const padY = 26;
      const padLeft = 20;
      const padRight = 20 + Math.min(widest + 10, width * 0.35);

      const xs = nodes.map((node) => node.x ?? 0);
      const ys = nodes.map((node) => node.y ?? 0);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);

      // A cap, so two nodes are not blown up until the map reads as a diagram of nothing.
      const k = Math.min(
        (width - padLeft - padRight) / Math.max(maxX - minX, 1),
        (HEIGHT - padY * 2) / Math.max(maxY - minY, 1),
        2.2,
      );
      const cx = (minX + maxX) / 2;
      const cy = (minY + maxY) / 2;
      const originX = padLeft + (width - padLeft - padRight) / 2;

      return (x, y) => [(x - cx) * k + originX, (y - cy) * k + HEIGHT / 2];
    }

    function draw() {
      if (ctx === null) return;
      const at = project();
      const px = (node: SimNode): [number, number] => at(node.x ?? 0, node.y ?? 0);

      ctx.save();
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, HEIGHT);

      // Context first, so an unclaimed corpus edge can never be drawn over an approved one.
      for (const link of links) {
        const source = link.source as SimNode;
        const target = link.target as SimNode;
        if (link.kind !== "context") continue;
        const [sx, sy] = px(source);
        const [tx, ty] = px(target);
        ctx.strokeStyle = colors.rule ?? "#e3e3de";
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
        ctx.strokeStyle = colors.accent ?? "#3d5a45";
        ctx.fillStyle = colors.accent ?? "#3d5a45";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(tx, ty);
        ctx.stroke();
        arrowhead(ctx, [sx, sy], [tx, ty], radius(target) + 3);
      }

      for (const node of nodes) {
        const [nx, ny] = px(node);
        ctx.beginPath();
        ctx.arc(nx, ny, radius(node), 0, Math.PI * 2);
        ctx.fillStyle =
          node.role === "walked" ? (colors.accent ?? "#3d5a45") : (colors.card ?? "#ffffff");
        ctx.fill();
        ctx.strokeStyle =
          node.role === "walked" ? (colors.accent ?? "#3d5a45") : (colors.inkFaint ?? "#7c7c88");
        ctx.lineWidth = 1.5;
        ctx.stroke();
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

    if (prefersReducedMotion()) {
      // Settle the layout without animating it. DoD 6 lands properly at step 7; this is the honest
      // minimum, and it is three lines rather than a retrofit.
      simulation.stop();
      for (let i = 0; i < 240; i += 1) simulation.tick();
      draw();
    } else {
      simulation.on("tick", draw);
    }

    return () => {
      simulation.stop();
      for (const node of nodes) {
        if (node.x !== undefined && node.y !== undefined) {
          positions.current.set(node.id, { x: node.x, y: node.y });
        }
      }
    };
  }, [graph]);

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
