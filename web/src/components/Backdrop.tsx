import { useEffect, useRef } from "react";
import { decode, drawFrame, phases } from "../graph/backdrop";

/**
 * The hero backdrop. Phase 7 step 3.
 *
 * **Four rules, and each one is a test in `Backdrop.test.tsx`** rather than an intention, because
 * every one of them is a thing that quietly stops being true.
 *
 *   1. `prefers-reduced-motion: reduce` draws ONE frame and never starts a loop. Not "slower".
 *   2. A hidden tab stops the loop. `visibilitychange`, not a timer.
 *   3. A run in flight stops it and it does not come back. See `paused` below.
 *   4. A still backdrop is DRAWN, never blank. A layer that renders nothing is indistinguishable from
 *      a loop that threw on frame one, which is a failure this project has already shipped once --
 *      see `web/previews/check-5.mjs`.
 *
 * **On rule 1 and what it is for.** Honoring the query does not dim anything for anyone who has not
 * switched it on. sjtroxel's requirement, 2026-09-08, verbatim: *"i want most users to have the
 * full-motion experience. only those who have gone out of their way to select their accessibility for
 * reduced-motion should have the lesser one."* That is exactly what a media query does, and there is
 * deliberately no toggle in the UI offering a third state.
 *
 * **The data is inlined, not fetched**, so this component makes no network request and `App.test.tsx`'s
 * "makes no network request on load" -- phase 5 DoD 5 -- stays literally true. See
 * `src/musical_mycelium/graph/backdrop.py` for why that was the choice rather than relaxing DoD 5.
 */
export function Backdrop({ paused }: { paused: boolean }): React.JSX.Element {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    // jsdom has no canvas, and a deployed browser with 2D disabled is the same shape of nothing. The
    // page must still render; the backdrop is the one part of it allowed to be absent.
    const ctx = canvas?.getContext?.("2d");
    if (!canvas || !ctx) return;

    const graph = decode();
    const phase = phases(graph.nodeCount);
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
    let frame = 0;

    const resize = () => {
      // Cap the device pixel ratio at 2. A decorative layer is the last thing that should pay for a
      // 3x retina buffer over 1,465 nodes and 5,058 edges.
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(window.innerWidth * dpr);
      canvas.height = Math.round(window.innerHeight * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const paint = (t: number) =>
      drawFrame(ctx, graph, phase, {
        t,
        width: window.innerWidth,
        height: window.innerHeight,
        animated: !reduced,
      });

    const loop = (t: number) => {
      paint(t);
      frame = requestAnimationFrame(loop);
    };

    const still = reduced || paused;
    resize();
    // Rule 4: the still case still paints. `paint(0)` rather than an early return.
    paint(0);
    if (!still) frame = requestAnimationFrame(loop);

    const onVisibility = () => {
      cancelAnimationFrame(frame);
      if (!still && !document.hidden) frame = requestAnimationFrame(loop);
    };
    const onResize = () => {
      resize();
      // Repaint immediately: a resized canvas is a cleared canvas, and a still backdrop that is never
      // asked to redraw would go blank on a window drag -- rule 4 failing in a way only a person
      // resizing a window would ever see.
      paint(0);
    };

    window.addEventListener("resize", onResize);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [paused]);

  return <canvas ref={ref} className="backdrop" aria-hidden="true" />;
}
