import facts from "../corpus-facts.json";
import type { StepState } from "../useLineageRun";
import { ClaimList } from "./ClaimList";

/**
 * One query's panel — the answer *and* the refusal.
 *
 * **The refusal deliberately shares this component with the answer rather than having its own.** DoD 10
 * requires no error chrome, ever: same card, same typography, same weight. Two components drift, and the
 * drift always goes the same way — the refusal picks up a warning colour, an icon, a lighter weight —
 * and by then the visitor has read "broken" before reading a word. One component makes that structural.
 *
 * A refusal is styled by a modifier that changes the *heading wording only*. If you find yourself
 * adding a colour here, re-read IMPLEMENTATION 4.5.
 */

function labelMap(step: StepState): Map<string, string> {
  const labels = new Map<string, string>();
  const path = step.path;
  if (path === null) return labels;
  path.node_ids.forEach((id, i) => {
    const label = path.labels[i];
    if (label !== undefined) labels.set(id, label);
  });
  path.chain.forEach((id, i) => {
    const label = path.chain_labels[i];
    if (label !== undefined) labels.set(id, label);
  });
  return labels;
}

function Chain({ step, labels }: { step: StepState; labels: Map<string, string> }) {
  const chain = step.path?.chain ?? [];
  // Empty for an origins query, and empty when a hop was rejected — a broken chain is not displayed
  // as a chain. `loop.py:PathWalked` is explicit that visit order is NOT descent order, so this reads
  // `chain`, never `node_ids`. Drawing an arrow down the visit order narrates false history.
  if (chain.length < 2) return null;

  return (
    <p className="chain" aria-label="Line of descent">
      {chain.map((id, index) => (
        <span key={id}>
          {index > 0 && <span className="chain__arrow"> came out of </span>}
          <span className="chain__node">{labels.get(id) ?? id}</span>
        </span>
      ))}
    </p>
  );
}

function Status({ step }: { step: StepState }) {
  if (step.phase === "failed") {
    return (
      <p className="status status--failed">
        The request did not complete: {step.error}. This is a transport problem, not an answer about
        the sources.
      </p>
    );
  }
  if (step.phase !== "running") return null;
  if (step.prose.length > 0) return null;

  return (
    <p className="status" aria-live="polite">
      {step.claims.length === 0
        ? "Checking the graph for sourced edges…"
        : `${step.claims.length} claim${step.claims.length === 1 ? "" : "s"} approved. Writing the answer…`}
    </p>
  );
}

function Truncation({ step }: { step: StepState }) {
  const reason = step.done?.stop_reason;
  if (reason === undefined || reason === "complete") return null;

  // A truncated answer must never be presented as a complete one. `loop.py:Done` exists partly to make
  // this distinguishable, and silently dropping it would waste that.
  return (
    <p className="truncation">
      This traversal stopped early ({reason === "max_turns" ? "turn limit" : "token budget"}), so it may
      be missing a hop. What is shown is still gated and cited; it is just not necessarily everything.
    </p>
  );
}

export function StepPanel({ step }: { step: StepState }) {
  const labels = labelMap(step);
  const refused = step.outcome === "refusal";

  return (
    <article className="panel">
      <h2 className="panel__query">{step.query}</h2>

      <Status step={step} />
      <Chain step={step} labels={labels} />

      {step.prose && <p className="panel__prose">{step.prose}</p>}

      {refused && (
        <div className="panel__context">
          {/* Requirement 5: never a negative claim. The corpus cannot support "nobody influenced X",
              and this figure is why — it is checked by tests/test_corpus_facts.py. */}
          <p>
            A missing edge is not evidence of a missing influence.{" "}
            {facts.nodes_without_recorded_influences} of the corpus&rsquo;s {facts.nodes} nodes record
            no influences at all, so silence here is the state of the sources rather than a finding
            about the music.
          </p>
        </div>
      )}

      <ClaimList claims={step.claims} labels={labels} />

      {step.rejectionCount > 0 && (
        <p className="rejections">
          {step.rejectionCount} proposed{" "}
          {step.rejectionCount === 1 ? "claim was" : "claims were"} rejected by the gate and left out.
        </p>
      )}

      <Truncation step={step} />

      {step.done && (
        <p className="panel__meta">
          {step.done.elapsed_seconds.toFixed(1)}s · artifact v{step.done.artifact_version} ·{" "}
          {step.done.claim_count} approved, {step.done.rejection_count} rejected
        </p>
      )}
    </article>
  );
}
