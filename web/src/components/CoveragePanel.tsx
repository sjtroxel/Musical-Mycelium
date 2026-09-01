import facts from "../corpus-facts.json";

/**
 * What this corpus covers, drawn rather than disclaimed.
 *
 * **Phase 5 DoD 7: coverage is visible in the interface, not disclaimed in a footnote.** Until step 9
 * it was exactly a footnote -- two sentences in `App.tsx`'s footer, commented at the time as "the
 * honest minimum for step 2". This panel replaces them, and the point of drawing the figures instead
 * of writing them is that a bar with nothing in it is harder to skip than a clause.
 *
 * **The framing rule this panel exists under, and it cuts both ways: CONCENTRATION IS NOT ABSENCE.**
 * The corpus is dense in post-war anglophone material and thin elsewhere. Collapsing that into "it is
 * only recent Western music" is the same overclaiming failure as hiding the skew -- it just errs
 * toward false modesty, and it is false about a corpus holding medieval music dated 500, samba,
 * kuduro, Anatolian rock and 43 genres that name neither the US nor the UK. So every concentration
 * figure here renders next to its counterweight, in the same block, and
 * `tests/test_corpus_facts.py::test_the_skew_cannot_be_rendered_without_its_counterweight` fails if a
 * future corpus makes that counterweight a fig leaf.
 *
 * **Counts, never percentages.** A published percentage was retracted on 2026-08-07 because it added
 * the US and UK totals and double-counted every genre credited to both. Rates are how that happened;
 * counts are what replaced it.
 *
 * **Bars are `--ink-soft`, never `--accent`.** Step 6 decided the accent means gate-approved. Nothing
 * on this panel has been approved by anything -- these are properties of the corpus, not findings
 * about music -- and the standing trap is that the four `verification` tiers must never appear on a
 * colour ramp. This panel is counts and must not drift into looking like that.
 *
 * All figures come from `corpus-facts.json`, which `tests/test_corpus_facts.py` asserts against the
 * pinned artifact whole. Nothing here is typed into the markup.
 */

const { coverage, density } = facts;

/** How many places get their own bar before the tail is drawn as marks instead. */
export const NAMED_PLACES = 8;

/** The era buckets in time order, with `unknown` deliberately last and deliberately present. */
const ERA_ORDER = [
  "pre-1900",
  "1900-1949",
  "1950-1969",
  "1970-1989",
  "1990-2009",
  "2010-",
] as const;

const ERA_LABEL: Record<string, string> = {
  "pre-1900": "before 1900",
  "1900-1949": "1900-1949",
  "1950-1969": "1950-1969",
  "1970-1989": "1970-1989",
  "1990-2009": "1990-2009",
  "2010-": "2010 onwards",
};

function Bar({
  label,
  count,
  max,
  muted = false,
}: {
  label: string;
  count: number;
  max: number;
  muted?: boolean;
}) {
  return (
    <div className={`cov__row${muted ? " cov__row--muted" : ""}`}>
      <span className="cov__rowLabel">{label}</span>
      <span className="cov__track">
        {/* `aria-hidden`: the bar is a redrawing of the number beside it, and a screen reader
            announcing both would read every row twice. The count is the accessible value. */}
        <span
          className="cov__bar"
          aria-hidden="true"
          style={{ inlineSize: `${max === 0 ? 0 : (count / max) * 100}%` }}
        />
      </span>
      <span className="cov__rowCount">{count}</span>
    </div>
  );
}

function When() {
  const eras = coverage.eras as Record<string, number>;
  const max = Math.max(...Object.values(eras));

  return (
    <section className="cov__axis">
      <h3 className="cov__axisTitle">When</h3>
      <div className="cov__rows">
        {ERA_ORDER.map((era) => (
          <Bar key={era} label={ERA_LABEL[era] ?? era} count={eras[era] ?? 0} max={max} />
        ))}
        {/* Drawn as a bar, not dropped to make the histogram sum to a tidier number. The absences
            ARE the measurement, which is why `Coverage` carries an explicit `unknown` bucket at all
            rather than reporting 141 dated genres and stopping. Muted because it is not a period --
            it sits on the time axis without being a point on it. */}
        <Bar label="no date recorded" count={eras.unknown ?? 0} max={max} muted />
      </div>
      <p className="cov__note">
        {coverage.coarser_than_year} are dated to a decade or a century, not a year. The earliest
        are dated 500.
      </p>
    </section>
  );
}

function Where() {
  const countries = coverage.countries as Record<string, number>;
  const ranked = Object.entries(countries).sort(
    (left, right) => right[1] - left[1] || left[0].localeCompare(right[0]),
  );
  const named = ranked.slice(0, NAMED_PLACES);
  const tail = ranked.slice(NAMED_PLACES);
  const max = named[0]?.[1] ?? 0;
  // Computed, not typed, so the sentence cannot go stale against a re-ingest.
  const tailMax = tail.length === 0 ? 0 : Math.max(...tail.map(([, count]) => count));

  return (
    <section className="cov__axis cov__axis--tall">
      <h3 className="cov__axisTitle">Where</h3>
      <div className="cov__rows">
        {named.map(([place, count]) => (
          <Bar key={place} label={place} count={count} max={max} />
        ))}
      </div>
      {tail.length > 0 && (
        <div className="cov__tail">
          {/* The long tail drawn as marks rather than as 21 more labelled rows. The concentration is
              already obvious from the two bars above it; what needs to be equally visible is that
              the tail exists and is long, which a row of marks says in the space of a sentence. */}
          <span className="cov__ticks" aria-hidden="true">
            {tail.map(([place]) => (
              <span key={place} className="cov__tick" />
            ))}
          </span>
          <span className="cov__tailLabel">
            and {tail.length} further places, {tailMax} genres or fewer each:{" "}
            {tail.map(([place]) => place).join(", ")}
          </span>
        </div>
      )}
      {/* The counterweight, in the same block as the figure it counterweighs and not in a footnote
          below it. Reading the two bars at the top alone gives "this is a US and UK corpus", which
          is false: it is a corpus concentrated there and genuinely spread across 29 places. */}
      <p className="cov__note">
        {coverage.genres_without_us_or_uk} of the {coverage.genres} genres name a place that is
        neither the US nor the UK, across {coverage.distinct_countries} in all, and{" "}
        {coverage.without_country} name no place at all. &ldquo;Place&rdquo; is Wikidata&rsquo;s
        label, not a guarantee &mdash; hence Brixton and Scandinavia beside countries.
      </p>
    </section>
  );
}

function HowDensely() {
  const connections = density.connections as Record<string, number>;
  const buckets = Object.entries(connections).sort(
    (left, right) => Number(left[0]) - Number(right[0]),
  );
  const max = Math.max(...buckets.map(([, count]) => count));

  return (
    <section className="cov__axis">
      <h3 className="cov__axisTitle">How densely</h3>
      <div className="cov__rows">
        {buckets.map(([connections_, count]) => (
          <Bar
            key={connections_}
            label={`${connections_} ${connections_ === "1" ? "connection" : "connections"}`}
            count={count}
            max={max}
          />
        ))}
      </div>
      {/* The direction sentence. `subject influenced_by object`, so a genre that is never a subject
          is one the corpus records no ORIGIN for -- not one that influenced nothing. Getting this
          backwards would invert the claim, and it is this project's named failure mode. */}
      <p className="cov__note">
        {density.genres_without_recorded_origins} of the {coverage.genres} genres have no recorded
        origin at all &mdash; the corpus holds nothing about where they came from. That is the state
        of the sources, not a finding about the music.
      </p>
    </section>
  );
}

export function CoveragePanel({ answeredVersion }: { answeredVersion: string | null }) {
  // The same guard `StepPanel` puts in front of the map, for the same reason. These figures are
  // baked at build time from the pinned artifact; the answer comes from whatever corpus the backend
  // loaded. If those differ, this panel is describing a corpus the answer did not run against, which
  // is a quieter version of drawing a graph that was never walked. Say so rather than let the two
  // sit next to each other looking consistent.
  const mismatched = answeredVersion !== null && answeredVersion !== facts.artifact_version;

  return (
    /* Open by default, and that is the DoD-7 decision rather than a styling default: a collapsed
       disclosure labelled "what this corpus covers" is a footnote wearing a different hat. It
       collapses because a visitor running a second query has already read it, not so it starts out
       of sight. */
    <details className="cov" open>
      <summary className="cov__summary">
        What this corpus covers
        <span className="cov__summaryHint">
          {coverage.genres} genres, {coverage.distinct_countries} places, unevenly
        </span>
      </summary>

      <div className="cov__body">
        {mismatched && (
          <p className="cov__mismatch">
            These figures describe corpus v{facts.artifact_version}, and the answer above came from
            v{answeredVersion}. Read them as a description of the pinned corpus, not of the one that
            was walked.
          </p>
        )}
        <p className="cov__lede">
          Measured from the pinned artifact, not asserted. These describe its {coverage.genres}{" "}
          genres; the {facts.nodes - coverage.genres} artist nodes are deliberately unmeasured,
          because date and place are genre properties in Wikidata.
        </p>

        <div className="cov__axes">
          <When />
          <Where />
          <HowDensely />
        </div>
      </div>
    </details>
  );
}
