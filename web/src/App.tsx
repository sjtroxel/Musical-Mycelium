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
            {/* **The sentence and the number both moved at phase 6 step 8.** The count is computed
                from the `done` frame, so it self-corrected from 169 to 7 without an edit — but the
                sentence around it was written for 169 islands and said something different there.
                At 7 components, with the largest holding almost everything, "disconnected
                components" would read as a caveat about a graph that is now mostly connected.

                **What connects it is the amended thesis from step 1, and this is where it has to
                appear on screen.** The organism is connected through the PEOPLE WHO PLAY ACROSS IT
                — artist-to-genre membership — not through an unbroken chain of genre-to-genre
                influence. The second clause is doing real work: wording that lets membership read
                as derivation is the failure `CLAUDE.md` names, and it is as easy to commit in a
                footer as on a canvas. */}
            <p>
              Artifact v{corpus.artifact_version}: {corpus.nodes} nodes, {corpus.edges} edges, in{" "}
              {corpus.structure.component_count}{" "}
              {corpus.structure.component_count === 1 ? "component" : "components"}. Relating two
              things is only possible within a component.
            </p>
            <p>
              What holds it together is the musicians who worked across it: an artist is recorded as
              playing a genre, which is not a claim that either came out of the other. Influence and
              membership are different statements here, and the map draws them differently.
            </p>
          </>
        )}
        <p className="footer__grounded">
          <strong>Grounded means traceable, not true.</strong> Wikidata can be wrong, and musical
          influence is genuinely contested. Every claim here links to the source it came from and
          says how hard that one source was checked — which is not the same as sources agreeing.
        </p>
        {/* **CC BY-SA attribution, phase 6 step 8, and it is an obligation rather than a courtesy.**
            `DATA-LICENSES.md` records that from artifact v0.7.0 the corpus is a MIXTURE of licences:
            Wikidata is CC0 and imposes nothing, DBpedia's `dbo:stylisticOrigin` edges are CC BY-SA
            3.0, and the `cultural_origins` infobox values parsed from Wikipedia are CC BY-SA 4.0.
            Both BY-SA versions are named because they are different licences, not one rounded off.

            `.claude/rules/graph-semantics.md` requires this be DISPLAYED and "not in a buried
            credits page", which is why it is here, in the footer of the page that renders the data,
            rather than in an About route. The per-row half of the obligation is already met
            structurally: every DBpedia edge carries a resolvable resource URI as its `source_id`,
            so the link back travels with the data. This is the visible half. */}
        <p className="footer__licences">
          Corpus data:{" "}
          <a href="https://www.wikidata.org/" target="_blank" rel="noreferrer">
            Wikidata
          </a>{" "}
          under{" "}
          <a
            href="https://creativecommons.org/publicdomain/zero/1.0/"
            target="_blank"
            rel="noreferrer"
          >
            CC0 1.0
          </a>
          ;{" "}
          <a href="https://www.dbpedia.org/" target="_blank" rel="noreferrer">
            DBpedia
          </a>{" "}
          under{" "}
          <a
            href="https://creativecommons.org/licenses/by-sa/3.0/"
            target="_blank"
            rel="noreferrer"
          >
            CC BY-SA 3.0
          </a>
          ; and origin details parsed from{" "}
          <a href="https://en.wikipedia.org/" target="_blank" rel="noreferrer">
            English Wikipedia
          </a>{" "}
          under{" "}
          <a
            href="https://creativecommons.org/licenses/by-sa/4.0/"
            target="_blank"
            rel="noreferrer"
          >
            CC BY-SA 4.0
          </a>
          . Every edge carries a link back to the source it came from.
        </p>
      </footer>
    </div>
  );
}
