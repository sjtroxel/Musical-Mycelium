import { useEffect, useRef, useState } from "react";
import type { StaticGraph } from "./staticGraph";
import { loadStaticGraph } from "./staticGraph";

/**
 * Load the pinned corpus, lazily, exactly once.
 *
 * **`enabled` is what keeps DoD 5 true.** The artifact is **2.6 MB (201 KB over the wire)** and fetching
 * it on mount would put it in front of first paint, which is precisely what DoD 5 forbids and what
 * `App.test.tsx`'s "makes no network request on load" is standing guard over. The caller turns this on
 * when a run starts, so the corpus downloads alongside the stream and is ready well before an agent
 * that takes twenty seconds to think has finished.
 *
 * *(The numbers read "640 KB (55 KB over the wire)" until 2026-09-08. Both were measured honestly at
 * artifact v0.5.0 and were stale from the moment phase 6 re-pinned to v0.7.1 -- the corpus grew 4x and
 * a comment stating a measurement does not re-measure itself. Re-measured at v0.7.1 by the phase 7
 * step 0 asset budget, which exists to make exactly this class of drift fail a build instead of
 * sitting in a docstring. **The argument the comment makes is stronger at the new number, not weaker**,
 * which is why the paragraph needed a new figure rather than a rewrite.)*
 *
 * A failure is returned, not thrown. The map is an enhancement over an answer that is already fully
 * legible without it: the claim list, the citations and the chain do not depend on this file.
 */
export function useStaticGraph(enabled: boolean): {
  graph: StaticGraph | null;
  error: string | null;
} {
  const [graph, setGraph] = useState<StaticGraph | null>(null);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (!enabled || started.current) return;
    started.current = true;

    let live = true;
    loadStaticGraph()
      .then((loaded) => {
        if (live) setGraph(loaded);
      })
      .catch((reason: unknown) => {
        if (live) setError(reason instanceof Error ? reason.message : String(reason));
      });

    return () => {
      live = false;
    };
  }, [enabled]);

  return { graph, error };
}
