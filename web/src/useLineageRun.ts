import { useCallback, useEffect, useRef, useState } from "react";
import { nodeIdsInArguments } from "./graph/subgraph";
import { streamLineage } from "./stream";
import type { Claim, CorpusSummary, DoneFrame, Frame, PathFrame, RefusedFrame } from "./types";

/**
 * One query's worth of state, built up frame by frame.
 *
 * `claims` fills *before* `prose` starts, and that ordering is not a rendering accident — it is the
 * claims-first invariant made visible. The gate approves claims, and only then does synthesis write
 * prose from the approved set. A visitor watching the citation list populate ahead of the sentences is
 * watching the grounding actually happen. See `.claude/rules/grounding-and-claims.md`.
 */
export interface StepState {
  query: string;
  phase: "queued" | "running" | "settled" | "failed";
  outcome: "answer" | "refusal" | null;
  prose: string;
  claims: Claim[];
  rejectionCount: number;
  path: PathFrame | null;
  /**
   * Node ids the run's tool calls named, in the order they were called.
   *
   * **Navigation only, and the distinction is load-bearing.** These are model-proposed tool arguments
   * that no gate ever saw, so they may put a node on the map and may never put a claim in the list.
   * They exist because a refusal has no other id in it: `kate-bush-refusal.sse` carries an empty
   * `path` and a `refused` frame holding only a reason and the query string, so without this the
   * refusal has nothing to draw a neighbourhood around.
   */
  toolNodeIds: string[];
  refusal: RefusedFrame | null;
  done: DoneFrame | null;
  error: string | null;
}

export interface RunStep {
  query: string;
}

function emptyStep(query: string): StepState {
  return {
    query,
    phase: "queued",
    outcome: null,
    prose: "",
    claims: [],
    rejectionCount: 0,
    path: null,
    toolNodeIds: [],
    refusal: null,
    done: null,
    error: null,
  };
}

/** Apply one frame to one step. Pure, so the frame-to-state mapping is testable without a network. */
export function applyFrame(step: StepState, frame: Frame): StepState {
  switch (frame.type) {
    case "claim":
      return { ...step, claims: [...step.claims, frame.claim] };
    case "rejected":
      return { ...step, rejectionCount: step.rejectionCount + 1 };
    case "token":
      return { ...step, prose: step.prose + frame.text };
    case "path":
      return { ...step, path: frame };
    case "refused":
      // Outcome is set the moment the frame arrives rather than at `done`, so the panel can commit to
      // the refusal presentation without a flash of empty answer.
      return { ...step, refusal: frame, outcome: "refusal" };
    case "done":
      return {
        ...step,
        done: frame,
        phase: "settled",
        outcome: step.outcome ?? "answer",
      };
    case "tool": {
      // Step 2 stored nothing from a tool frame. Step 4 takes exactly one thing: the node ids in the
      // arguments, so the map knows where in the corpus to look. Everything else about the machinery
      // is still dropped; surfacing the loop itself remains a later step's call.
      const fresh = nodeIdsInArguments(frame.arguments).filter(
        (id) => !step.toolNodeIds.includes(id),
      );
      return fresh.length === 0 ? step : { ...step, toolNodeIds: [...step.toolNodeIds, ...fresh] };
    }
    // `plan` is consumed but not stored.
    case "plan":
      return step;
  }
}

export interface RunState {
  steps: StepState[];
  corpus: CorpusSummary | null;
  busy: boolean;
  label: string | null;
}

const IDLE: RunState = { steps: [], corpus: null, busy: false, label: null };

export function useLineageRun() {
  const [state, setState] = useState<RunState>(IDLE);
  const abortRef = useRef<AbortController | null>(null);

  /**
   * How many steps exist, mirrored outside React state.
   *
   * `annotate` appends a step and then has to stream into it by index. Reading `prev.steps.length`
   * from inside a `setState` updater would work exactly once: updaters must be pure, React calls
   * them twice under StrictMode, and an index captured as a side effect of one would be wrong on the
   * second call. A ref is the honest way to know the index before the append happens.
   */
  const stepCount = useRef(0);

  /** Whether a stream is in flight, for the same reason: a callback cannot read current state. */
  const busyRef = useRef(false);

  // A run in flight when the component goes away is a Lambda still being billed for a stream nobody
  // will read. AWS bills the full function duration on a streamed response even after the client
  // disconnects, so aborting is the polite half of a cost control, not just tidiness.
  useEffect(() => () => abortRef.current?.abort(), []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    busyRef.current = false;
    setState((prev) => ({ ...prev, busy: false }));
  }, []);

  /**
   * Stream one query into one existing step. Returns false when the step did not complete.
   *
   * Extracted at step 8b so `run` and `annotate` cannot drift. They differ only in how the step gets
   * there — a fresh list of them, or one appended to what is already on screen.
   */
  const streamStep = useCallback(
    async (index: number, query: string, controller: AbortController): Promise<boolean> => {
      setState((prev) => ({
        ...prev,
        steps: prev.steps.map((step, i) => (i === index ? { ...step, phase: "running" } : step)),
      }));

      try {
        await streamLineage(query, {
          signal: controller.signal,
          onFrame: (frame) => {
            setState((prev) => {
              const next = {
                ...prev,
                steps: prev.steps.map((step, i) => (i === index ? applyFrame(step, frame) : step)),
              };
              return frame.type === "done" ? { ...next, corpus: frame.corpus } : next;
            });
          },
        });
        return true;
      } catch (error) {
        if (controller.signal.aborted) return false;
        const message = error instanceof Error ? error.message : String(error);
        setState((prev) => ({
          ...prev,
          steps: prev.steps.map((step, i) =>
            i === index ? { ...step, phase: "failed", error: message } : step,
          ),
        }));
        return false;
      }
    },
    [],
  );

  const run = useCallback(
    async (label: string, queries: string[]) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      stepCount.current = queries.length;
      busyRef.current = true;
      setState({
        steps: queries.map(emptyStep),
        corpus: null,
        busy: true,
        label,
      });

      for (const [index, query] of queries.entries()) {
        if (controller.signal.aborted) return;
        // Stop the sequence on a failure. A paired chip whose first half failed must not run its
        // second half as though the first had merely refused — that would present a transport
        // failure as evidence.
        if (!(await streamStep(index, query, controller))) break;
      }

      if (!controller.signal.aborted) {
        busyRef.current = false;
        setState((prev) => ({ ...prev, busy: false }));
      }
    },
    [streamStep],
  );

  /**
   * Ask the agent about one node, appending the answer below what is already on screen.
   *
   * **DoD 4's "request an annotation", and it goes through `/lineage` and the gate like everything
   * else.** The static corpus in the browser is for navigation only; the moment a visitor asks a
   * question about what they found, it is a real query, a real traversal and a real set of gated
   * claims. Rendering an edge from the static file is not narrating it — IMPLEMENTATION 4.2.
   *
   * It APPENDS rather than replacing, which is the whole difference from `run`. Replacing would
   * throw away the answer the visitor was reading in order to answer a question about it.
   *
   * Refused while a stream is in flight. Aborting one mid-answer would leave that step stuck showing
   * "running" forever, since nothing would ever deliver its `done` frame.
   */
  const annotate = useCallback(
    async (query: string) => {
      if (busyRef.current) return;

      const controller = new AbortController();
      abortRef.current = controller;

      const index = stepCount.current;
      stepCount.current += 1;
      busyRef.current = true;
      setState((prev) => ({
        ...prev,
        steps: [...prev.steps, emptyStep(query)],
        busy: true,
      }));

      await streamStep(index, query, controller);

      if (!controller.signal.aborted) {
        busyRef.current = false;
        setState((prev) => ({ ...prev, busy: false }));
      }
    },
    [streamStep],
  );

  return { ...state, run, annotate, cancel };
}
