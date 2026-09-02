import { useState } from "react";
import { Mark } from "./components/Mark";
import type { Chip } from "./components/ChipRow";
import { ChipRow } from "./components/ChipRow";
import { CoveragePanel } from "./components/CoveragePanel";
import { StepPanel } from "./components/StepPanel";
import { useStaticGraph } from "./graph/useStaticGraph";
import { useLineageRun } from "./useLineageRun";

export function App() {
  const [query, setQuery] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const { steps, corpus, busy, label, run, annotate, cancel } = useLineageRun();
  // The corpus downloads alongside the first run, never before one. DoD 5 forbids putting a 640 KB
  // fetch in front of first paint, and `App.test.tsx` asserts that loading the page requests nothing.
  const { graph } = useStaticGraph(steps.length > 0);

  const pickChip = (chip: Chip) => {
    setActiveId(chip.id);
    setQuery("");
    void run(
      chip.label,
      chip.steps.map((step) => step.query),
    );
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (trimmed === "" || busy) return;
    setActiveId(null);
    void run(trimmed, [trimmed]);
  };

  return (
    <div className="app">
      <header className="masthead">
        <div className="masthead__lockup">
          <Mark />
          <h1 className="masthead__title">Musical Mycelium</h1>
        </div>
        <p className="masthead__tagline">
          Music history is a network, not a timeline. Ask how two genres connect and every step of
          the answer traces to a checkable source.
        </p>
      </header>

      <form className="ask" onSubmit={submit}>
        <label className="ask__label" htmlFor="query">
          Ask about a genre or an artist
        </label>
        <div className="ask__row">
          <input
            id="query"
            className="ask__input"
            type="text"
            value={query}
            placeholder="Where did trip hop come from?"
            onChange={(event) => setQuery(event.target.value)}
            autoComplete="off"
          />
          <button className="ask__submit" type="submit" disabled={busy || query.trim() === ""}>
            Trace it
          </button>
        </div>
      </form>

      <ChipRow disabled={busy} activeId={activeId} onPick={pickChip} />

      {busy && (
        <button className="cancel" type="button" onClick={cancel}>
          Stop
        </button>
      )}

      {steps.length > 0 && (
        <main className="results" aria-live="polite" aria-busy={busy}>
          {label !== null && <p className="results__label">{label}</p>}
          {steps
            .filter((step) => step.phase !== "queued")
            .map((step, index) => (
              <StepPanel
                key={`${step.query}-${index}`}
                step={step}
                graph={graph}
                busy={busy}
                onAnnotate={(query) => void annotate(query)}
              />
            ))}
        </main>
      )}

      {/* Step 9, DoD 7. **Below the results, always, and that placement is a correction.**
          It was above them at first, on the reasoning that coverage is the frame an answer is read
          through. sjtroxel ran it and the reasoning collapsed: the panel is a screen tall, so
          clicking a chip looked like nothing had happened, and by the time you scrolled past it the
          streaming answer had already finished. A frame nobody sees the answer inside is not a
          frame.

          There is no positional switch here and deliberately so. With no run yet `results` is empty,
          so this still lands directly under the chips and is the first screen's content; once an
          answer exists it takes that slot and this follows it down. One rule, and nothing jumps.

          Still not a footnote, which is what DoD 7 actually forbids: it is a drawn section with a
          heading, open on arrival, above the footer rather than inside it. It reads
          `corpus-facts.json`, so it renders at first paint and never waits on the `done` frame's
          `corpus.coverage` -- DoD 5 keeps the 640 KB artifact fetch off first paint and this must
          not smuggle one in. */}
      <CoveragePanel answeredVersion={corpus?.artifact_version ?? null} />

      <footer className="footer">
        {corpus === null ? (
          <p>
            The corpus is a pinned, versioned artifact. Every edge carries its source and the
            strength of the check that was run on it.
          </p>
        ) : (
          <>
            <p>
              Artifact v{corpus.artifact_version}: {corpus.nodes} nodes, {corpus.edges} edges,
              across {corpus.structure.component_count} disconnected components. Relating two things
              is only possible within a component.
            </p>
          </>
        )}
        <p className="footer__grounded">
          <strong>Grounded means traceable, not true.</strong> Wikidata can be wrong, and musical
          influence is genuinely contested. Every claim here links to the source it came from and
          says how hard that one source was checked — which is not the same as sources agreeing.
        </p>
      </footer>
    </div>
  );
}
