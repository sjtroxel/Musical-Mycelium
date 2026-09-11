import { useState } from "react";
import { enterDelay } from "./graph/motion";
import { Backdrop } from "./components/Backdrop";
import { Mark } from "./components/Mark";
import type { Chip } from "./components/ChipRow";
import { ChipRow } from "./components/ChipRow";
import { CoveragePanel } from "./components/CoveragePanel";
import { StepPanel } from "./components/StepPanel";
import { useStaticGraph } from "./graph/useStaticGraph";
import { TOUR_QUERY, useTour } from "./graph/useTour";
import { useLineageRun } from "./useLineageRun";

export function App() {
  const [query, setQuery] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [touring, setTouring] = useState(false);
  const { steps, corpus, busy, label, run, annotate, cancel } = useLineageRun();
  // The tour replays a recording, so it spends nothing and needs no network. See `useTour.ts`.
  const tour = useTour(touring);
  // The corpus downloads alongside the first run, never before one. DoD 5 forbids putting a 640 KB
  // fetch in front of first paint, and `App.test.tsx` asserts that loading the page requests nothing.
  const { graph } = useStaticGraph(steps.length > 0 || touring);

  const pickChip = (chip: Chip) => {
    setActiveId(chip.id);
    setQuery("");
    setTouring(false);
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
    setTouring(false);
    void run(trimmed, [trimmed]);
  };

  return (
    <>
      {/* Phase 7 step 3, amended step 8. `touring` was missing here until the phase's DoD audit, and the
          omission is the interesting part: the tour is a *replayed* run, so it never touches `steps`, and
          the backdrop went on drifting behind the most semantic motion on the page. DoD 9 is explicit --
          ambient motion yields to semantic motion -- and a replay is a run for that purpose.

          `paused` is `steps.length > 0` and NOT "a run is in flight": once the visitor
          has asked something, the page is a working surface and the ambient layer stays still for the
          rest of the visit. Restarting the drift after every answer would put motion behind the claims
          exactly when the claims are the thing to look at, and it would flicker. The backdrop's job is
          the first three seconds. */}
      <Backdrop paused={steps.length > 0 || touring} />
      <div className="app">
        <header className="masthead">
          {/* Phase 7 step 4. Three beats, and the indices are the whole of the choreography: the
              delay comes from `staggerDelay` so it is a number a test can read, and the duration and
              curve live in `styles.css`. The backdrop is drifting behind all three. */}
          <div className="masthead__lockup enter" style={enterDelay(0) as React.CSSProperties}>
            <Mark />
            <h1 className="masthead__title">Musical Mycelium</h1>
          </div>
          <p className="masthead__tagline enter" style={enterDelay(1) as React.CSSProperties}>
            Music history is a network, not a timeline. Ask how two genres connect and every step of
            the answer traces to a checkable source.
          </p>
        </header>

        <form className="ask enter" style={enterDelay(2) as React.CSSProperties} onSubmit={submit}>
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

        {/* Phase 7 step 6, surface C. The tour replays a recorded run rather than calling the model:
            a live tour would bill a Bedrock run per page view from visitors who never asked anything,
            and `.claude/rules/aws-and-cost.md` is explicit that an abandoned stream still bills the
            full duration. Narration and map are two readings of ONE `StepState` from `timeline.ts`,
            which is what makes DoD 2's "desynchronization impossible by construction" structural
            rather than promised. */}
        <button
          className="tour"
          type="button"
          disabled={busy}
          onClick={() => {
            setActiveId(null);
            setTouring(true);
          }}
        >
          Take the guided tour
        </button>

        {touring && (
          <main className="results" aria-live="polite" aria-busy={!tour.done}>
            <p className="results__label">
              A recorded walk through the corpus. Every claim is checked against the pinned
              artifact.
            </p>
            <StepPanel key={TOUR_QUERY} step={tour.state} graph={graph} busy={!tour.done} />
          </main>
        )}

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
        <div className="enter" style={enterDelay(3) as React.CSSProperties}>
          <CoveragePanel answeredVersion={corpus?.artifact_version ?? null} />
        </div>

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
                What holds it together is the musicians who worked across it: an artist is recorded
                as playing a genre, which is not a claim that either came out of the other.
                Influence and membership are different statements here, and the map draws them
                differently.
              </p>
            </>
          )}
          <p className="footer__grounded">
            <strong>Grounded means traceable, not true.</strong> Wikidata can be wrong, and musical
            influence is genuinely contested. Every claim here links to the source it came from and
            says how hard that one source was checked — which is not the same as sources agreeing.
          </p>
          {/* Phase 7.5 step 1. `/report/index.html` rather than `/report/`: CloudFront's default root
            object applies to the site root only, so a bare directory path may not resolve through
            the S3 origin. Step 3's deploy is where that gets checked against the real distribution. */}
          <p className="footer__report">
            <a href="/report/index.html">How this is evaluated</a>: every gate, the measured noise
            floor, and what did not work.
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
          {/* Phase 7.5 step 4. The copyright line every one of his apps ends with -- Patchwork, Heritage
            Odyssey, Wildlife Sentinel, Poster Pilot -- matched to theirs, including the Octicon path.
            The icon is also the site's only link to the repo, the third stop on the recruiter path. */}
          <p className="footer__copyright">
            © 2026 sjtroxel
            <a
              href="https://github.com/sjtroxel/Musical-Mycelium"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="GitHub repository (opens in new tab)"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="currentColor"
                aria-hidden="true"
              >
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755-1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12z" />
              </svg>
            </a>
            . All rights reserved.
          </p>
        </footer>
      </div>
    </>
  );
}
