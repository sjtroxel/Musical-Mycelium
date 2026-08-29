import { useState } from "react";
import type { Chip } from "./components/ChipRow";
import { ChipRow } from "./components/ChipRow";
import { StepPanel } from "./components/StepPanel";
import { useStaticGraph } from "./graph/useStaticGraph";
import { useLineageRun } from "./useLineageRun";

export function App() {
  const [query, setQuery] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const { steps, corpus, busy, label, run, cancel } = useLineageRun();
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
        <h1 className="masthead__title">Musical Mycelium</h1>
        <p className="masthead__tagline">
          Music history is a network, not a timeline. Ask how two genres connect and every step of the
          answer traces to a checkable source.
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
              <StepPanel key={`${step.query}-${index}`} step={step} graph={graph} />
            ))}
        </main>
      )}

      <footer className="footer">
        {corpus === null ? (
          <p>
            The corpus is a pinned, versioned artifact. Every edge carries its source and the strength
            of the check that was run on it.
          </p>
        ) : (
          <>
            <p>
              Artifact v{corpus.artifact_version}: {corpus.nodes} nodes, {corpus.edges} edges, across{" "}
              {corpus.structure.component_count} disconnected components. Relating two things is only
              possible within a component.
            </p>
            {/* CLAUDE.md: the corpus skew is by construction and must be VISIBLE in output, not
                disclaimed in a footnote. Stated as counts, never a percentage — the retracted
                2026-08-06 figure came from double-counting genres credited to both the US and the UK.
                The full coverage treatment is step 9; this is the honest minimum for step 2. */}
            <p>
              It skews Western, anglophone and recent by construction:{" "}
              {corpus.coverage.without_inception} of {corpus.coverage.genres} genres carry no inception
              date, and {corpus.coverage.genres_without_us_or_uk} name a place that is neither the US
              nor the UK, across {corpus.coverage.distinct_countries} countries in all.
            </p>
          </>
        )}
        <p className="footer__grounded">
          <strong>Grounded means traceable, not true.</strong> Wikidata can be wrong, and musical
          influence is genuinely contested. Every claim here links to the source it came from and says
          how hard that one source was checked — which is not the same as sources agreeing.
        </p>
      </footer>
    </div>
  );
}
