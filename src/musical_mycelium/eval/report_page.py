"""The published eval report, as one static page. Phase 7.5 step 1.

``make report`` writes ``web/public/report/index.html``. Vite copies ``public/`` into the build
unchanged, so the page ships with no JavaScript, no router and no second copy of any metric. Every
number on it is read from a committed file or computed by the code the suite already scores with, and
``tests/test_report_page.py`` fails when the committed page disagrees with this generator -- a stale
report fails ``make check`` rather than a reader. Decided by sjtroxel 2026-09-10, option A of three.

**Where each section comes from, and why none of them invents its own rule.**

- **Live gates** come from the verdict ``eval-live`` stored in its own result file at run time
  (``live.gate_record``). The page never re-derives a verdict from bounds: that would be a second
  implementation of ``thresholds.py``, and the day the two disagreed the page would be the copy
  nobody checked. A run that stored no verdict against the live set is not shown as gated, however
  complete it looks.
- **Scripted gates** are computed here by ``run_gold_suite`` and ``gate``: deterministic, free, 0.2 s.
- **The noise floor** is ``eval/noise_floor.json`` as written, and per-run values go through
  ``noise.METRICS``, the extractors the floor itself was computed with.
- **Judged numbers** come from the newest tier 2 file, and one without its agreement range is refused
  with ``NoAgreement`` -- the rule ``report.render_judged`` already enforces in the terminal.
- **The held-out result** is read for aggregates only: counts, the pin, the date. It is written through
  an allowlist that admits no query and no prose (``heldout_run.redact``), and nothing here prints a
  case from it.

**The sentences on this page are a DRAFT and they are his to rewrite.** ``COPY`` holds every sentence
that is not a number or a label, in one place, for exactly that reason: ``CLAUDE.md``'s watermark rule
and phase 7.5 §6. Rewriting them changes the page and fails the drift test until ``make report`` runs,
which is the intended order of events.
"""

from __future__ import annotations

import html
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from musical_mycelium.eval import noise
from musical_mycelium.eval.live import gate_record
from musical_mycelium.eval.published import corpus_figures
from musical_mycelium.eval.slices import SPARSE_SLICE
from musical_mycelium.eval.suite import run_gold_suite
from musical_mycelium.eval.thresholds import FAIL, NOT_APPLICABLE, PASS, THRESHOLDS_PATH, gate
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.schema import Artifact

Json = dict[str, Any]

EVAL_DIR = Path(__file__).parent
RESULTS_DIR = EVAL_DIR / "results"
NOISE_FLOOR = EVAL_DIR / "noise_floor.json"
PAGE = EVAL_DIR.parents[2] / "web" / "public" / "report" / "index.html"

#: The threshold set whose verdicts the live section shows. Matched by ``applies_to`` rather than by
#: name so a renamed set is still found, and a second live set is an error rather than a silent pick.
LIVE = {"dataset": "live", "provider": "bedrock"}

#: What each verdict reads as. **N/A says in words that it is not a pass**, because the failure this
#: page exists to avoid is a table where two untested gates sit in a column of green.
VERDICT_LABEL = {PASS: "pass", FAIL: "FAIL", NOT_APPLICABLE: "N/A: not tested, and not a pass"}

#: Every sentence that is not a number or a label. DRAFT -- see the module docstring.
COPY: dict[str, str] = {
    "intro": (
        "Every number on this page is generated from files committed to the repository, by the same "
        "code the evaluation suite runs with. None of it is typed by hand, and the build fails if the "
        "page falls out of date."
    ),
    "grounded": (
        "Grounded means traceable to a checkable source, not true. The gates below prove the first. "
        "Nothing on this page claims the second."
    ),
    "live_gates": (
        "Six correctness properties block a release. They are judged against a real model, with bounds "
        "measured over identical runs before any bound was set."
    ),
    "live_gates_missing": (
        "No stored live run records its gate verdicts yet: runs began recording them on 2026-09-10. "
        "This section fills in from the next full live run."
    ),
    "scripted_gates": (
        "The free run on every commit. Its model is scripted, so it can decide some properties and "
        "marks the rest not applicable rather than passing them."
    ),
    "metrics": (
        "Tracked metrics beside the spread measured across identical runs. A movement inside the spread "
        "is noise, not a result."
    ),
    "slices": (
        "Cases answered correctly, sliced. The corpus skews Western, anglophone and recent, and an "
        "aggregate that looks healthy can hide a thin slice. Slices under five cases are marked."
    ),
    "judged": (
        "Judged by a model from a different family than the one being judged, on a sample. Tracked, "
        "never gated. Every judged number carries its measured agreement with a human."
    ),
    "judge_self": (
        "The judge also disagrees with itself. The same 30 items, judged three times, scored {runs} "
        "supported."
    ),
    "heldout": (
        "Ten cases drawn from the corpus by a seed only the author holds, sealed, and never read during "
        "development."
    ),
    "heldout_caveat": (
        "One run of ten cases, {refusals} of them refusals, so one flip moves refusal accuracy by "
        "{swing} points. It is an observation, not a rate, and it cannot be re-run for an error bar "
        "without spending the property the set exists to have."
    ),
    "cause:gold_v0_1_020": (
        'The model types "fentanyl" for the artist femtanyl, so the lookup finds nothing. Not a graph '
        "or tool defect: typed correctly, the graph answers it in one call."
    ),
    "orbison": (
        "A failure no metric here can catch. Joy Orbison and Roy Orbison are one edit apart and both "
        "are in the corpus. A model that typed one for the other would resolve cleanly, cite correctly, "
        "and answer about the wrong person at 100% groundedness. The adversarial case that asserts one's "
        "influences about the other (adv_019) is refused, but only because that premise is false. The "
        "substitution itself is invisible."
    ),
    "single_source": (
        "{single} of {influence} influence edges have one source. A second source speaks on "
        "{corroborated}, and {contested} pairs are contested. Everywhere else the page can say how "
        "strongly one source was checked, not whether another agrees."
    ),
}


class NoAgreement(ValueError):
    """A judged number arrived without a measured judge-human agreement range.

    Refused rather than printed, for the reason ``.claude/rules/evals.md`` gives: an LLM-judge score
    with no measured agreement is decoration, and decoration is quotable where a crash is not.
    """


# --- reading ----------------------------------------------------------------------------------------


def _load(path: Path) -> Json:
    payload: Json = json.loads(path.read_text(encoding="utf-8"))
    return payload


def results(suffix: str, directory: Path = RESULTS_DIR) -> list[tuple[str, Json]]:
    """``(stamp, payload)`` for every result file with this suffix, oldest first.

    The stamp is the filename's, not ``written_at``: three early runs predate that field (§4)."""
    return [
        (path.name.split("-", 1)[0], _load(path))
        for path in sorted(directory.glob(f"*-{suffix}.json"))
    ]


def live_set(path: Path = THRESHOLDS_PATH) -> Json:
    matching: list[Json] = [entry for entry in _load(path)["sets"] if entry["applies_to"] == LIVE]
    if len(matching) != 1:
        raise LookupError(f"expected exactly one live Bedrock threshold set, found {len(matching)}")
    return matching[0]


def gated_live_run(set_name: str, runs: Sequence[tuple[str, Json]]) -> tuple[str, Json] | None:
    """The newest run whose own stored verdict was made against ``set_name``.

    This is the gate's judgement of comparability, reused rather than restated: ``thresholds.gate``
    already refuses a subset, an incomplete run, a moved case count and a mismatched pin, and a refused
    run stores ``set: None``. So the only question asked here is "did the gate judge this run against
    the live bounds", and the answer was written down when the run happened.
    """
    for stamp, run in reversed(runs):
        record = run.get("gates")
        if isinstance(record, dict) and record.get("set") == set_name:
            return stamp, run
    return None


# --- formatting -------------------------------------------------------------------------------------


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _fmt(unit: str, value: float | None) -> str:
    if value is None:
        return "undefined"
    return f"{value * 100:.1f}%" if unit == "rate" else f"{round(value):,}"


def _when(stamp: str) -> str:
    """``20260907T230821Z`` as ``2026-09-07 23:08 UTC``."""
    return f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]} {stamp[9:11]}:{stamp[11:13]} UTC"


def _p(text: str, css: str = "") -> str:
    attribute = f' class="{css}"' if css else ""
    return f"<p{attribute}>{_e(text)}</p>"


def _table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    """Cells arrive as HTML already escaped by the caller; headers are escaped here."""
    head = "".join(f"<th>{_e(header)}</th>" for header in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def gate_rows(gates: Iterable[Mapping[str, str]]) -> list[list[str]]:
    rows = []
    for entry in gates:
        verdict = entry["verdict"]
        css = {PASS: "v-pass", FAIL: "v-fail"}.get(verdict, "v-na")
        expected = _e(entry["expected"])
        if entry.get("note"):
            expected += f'<div class="note">{_e(entry["note"])}</div>'
        rows.append(
            [
                f"<code>{_e(entry['name'])}</code>",
                f'<span class="{css}">{_e(VERDICT_LABEL.get(verdict, verdict))}</span>',
                _e(entry["observed"]),
                expected,
            ]
        )
    return rows


def tally(gates: Sequence[Mapping[str, str]]) -> str:
    """Passed, failed and not applicable as three counts, never one. An all-N/A run must not read green."""
    count = {verdict: sum(1 for g in gates if g["verdict"] == verdict) for verdict in VERDICT_LABEL}
    return (
        f"{count[PASS]} passed, {count[FAIL]} failed, {count[NOT_APPLICABLE]} not applicable, "
        f"of {len(gates)}"
    )


def agreement_line(metric: Mapping[str, Any]) -> str:
    agreement = metric.get("agreement")
    if not isinstance(agreement, Mapping) or agreement.get("kappa_low") is None:
        raise NoAgreement(f"judged metric without a measured agreement range: {dict(metric)}")
    low, high = agreement["kappa_low"], agreement["kappa_high"]
    kappa = f"{low:.2f}" if round(low, 2) == round(high, 2) else f"{low:.2f} to {high:.2f}"
    exact = f"{agreement['exact_low']:.0%} to {agreement['exact_high']:.0%}"
    bands = ", ".join(agreement.get("kappa_bands", ()))
    line = (
        f"judge-human agreement: {agreement['kappa_kind']} kappa {kappa} ({bands}), exact agreement "
        f"{exact}, over {agreement['validation_runs']} validation runs of n={agreement['n_low']}"
    )
    if agreement.get("single_run_caveat"):
        line += f". {agreement['single_run_caveat']}"
    return _e(line)


# --- sections ---------------------------------------------------------------------------------------


def live_gates_section(live: Json, gated: tuple[str, Json] | None) -> str:
    derived = live["derived_from"]
    out = '<h2 id="live-gates">Correctness gates: a real model</h2>' + _p(COPY["live_gates"])
    out += _p(
        f"Bounds measured over {derived['run_count']} identical runs of the {live['case_count']}-case "
        f"set at artifact {derived['artifact_version']}, decided {derived['decided']}, model "
        f"{derived['model_id']}."
    )
    if gated is None:
        return out + _p(COPY["live_gates_missing"], "note")
    stamp, run = gated
    gates = run["gates"]["gates"]
    out += (
        f"<p>Run of {_e(_when(stamp))}, revision <code>{_e(run.get('code_revision', '?'))}</code>, "
        f"{run['cases_run']} cases: <strong>{_e(tally(gates))}</strong>.</p>"
    )
    return out + _table(["gate", "verdict", "observed", "required"], gate_rows(gates))


def scripted_gates_section(gates: Sequence[Mapping[str, str]]) -> str:
    return (
        '<h2 id="scripted-gates">Correctness gates: every commit, free</h2>'
        + _p(COPY["scripted_gates"])
        + f"<p><strong>{_e(tally(gates))}</strong>.</p>"
        + _table(["gate", "verdict", "observed", "required"], gate_rows(gates))
    )


def metrics_section(label: str, run: Json, floor: Json) -> str:
    spreads = {spread["metric"]: spread for spread in floor["spreads"]}
    rows = []
    for name, unit, extract in noise.METRICS:
        spread = spreads.get(name)
        measured = (
            f"{_fmt(unit, spread['low'])} to {_fmt(unit, spread['high'])}"
            if spread
            else "not measured"
        )
        rows.append([f"<code>{_e(name)}</code>", _e(_fmt(unit, extract(run))), _e(measured)])
    return (
        '<h2 id="metrics">Metrics and the noise floor</h2>'
        + _p(COPY["metrics"])
        + _p(
            f"Values from {label}. The floor is {floor['run_count']} identical runs at artifact "
            f"{floor['artifact_version']}, revision {floor['code_revision']}."
        )
        + _table(["metric", "this run", f"range over {floor['run_count']} runs"], rows)
    )


def slices_section(run: Json) -> str:
    rows = []
    for dimension, values in run.get("slices", {}).items():
        for value, rate in values.items():
            count = f"{rate['numerator']} of {rate['denominator']}"
            if rate["denominator"] < SPARSE_SLICE:
                count += f" (n&lt;{SPARSE_SLICE})"
            rows.append([_e(dimension), _e(value), count])
    return (
        '<h2 id="slices">By era, region, density and query type</h2>'
        + _p(COPY["slices"])
        + _table(["dimension", "slice", "correct"], rows)
    )


def judged_section(tier2: tuple[str, Json], judges: Sequence[tuple[str, Json]]) -> str:
    stamp, run = tier2
    metrics = run["metrics"]
    support, quality = metrics["citation_support"], metrics["narrative_quality"]
    rows = [
        [
            "<code>citation_support</code>",
            _e(f"{support['supported']} of {support['scored']} supported"),
            agreement_line(support),
        ],
        [
            "<code>narrative_quality</code>",
            _e(f"mean {quality['mean']:.2f} over {quality['scored']}"),
            agreement_line(quality),
        ],
    ]
    source = run["sources"][0] if run.get("sources") else {}
    self_runs = ", then ".join(
        f"{judge['citation_support_supported']} of {judge['citation_support_scored']}"
        for _, judge in judges
    )
    return (
        '<h2 id="judged">Judged quality, tier 2</h2>'
        + _p(COPY["judged"])
        + _p(
            f"Judged {_when(stamp)} by {run['judge_model_id']}, a sample of {run['sample_size']} "
            f"from the live run of {_when(source.get('written_at', '00000000T0000Z'))}."
        )
        + _table(["metric", "score", "agreement"], rows)
        + _p(COPY["judge_self"].format(runs=self_runs))
    )


def heldout_section(runs: Sequence[tuple[str, Json]], current_artifact: str) -> str:
    out = '<h2 id="heldout">The sealed held-out set</h2>' + _p(COPY["heldout"])
    if not runs:
        return out + _p("It has not been run.")
    stamp, run = runs[-1]
    refusals = sum(1 for case in run.get("per_case", []) if case.get("expected_refusal"))
    out += (
        f"<p><strong>{run['cases_correct']} of {run['cases_run']} correct</strong>, run "
        f"{len(runs)} {'time' if len(runs) == 1 else 'times'} in total, on {_e(_when(stamp))} at "
        f"artifact {_e(run['artifact_version'])}. The corpus is now {_e(current_artifact)}.</p>"
    )
    if refusals:
        out += _p(COPY["heldout_caveat"].format(refusals=refusals, swing=round(100 / refusals)))
    return out


def did_not_work_section(
    floor: Json,
    live: Json,
    scripted: Sequence[Mapping[str, str]],
    figures: Mapping[str, int | str],
    heldout: Sequence[tuple[str, Json]],
    current_artifact: str,
) -> str:
    bounds = live["bounds"]
    items = []
    for case_id in floor["reproducible_failure_ids"]:
        excluded = [
            name
            for name in ("refusal_accuracy", "traversal_recall")
            if case_id in bounds.get(name, {}).get("excluded", ())
        ]
        text = f"<code>{_e(case_id)}</code> fails the same way in every run. "
        text += _e(COPY.get(f"cause:{case_id}", "Its cause is not yet recorded here."))
        if excluded:
            text += _e(
                f" Excluded from {' and '.join(excluded)} with its cause recorded, and still in the "
                "dataset and still scored."
            )
        items.append(text)
    unstable = floor["unstable_case_ids"]
    if unstable:
        items.append(
            _e(f"{len(unstable)} cases changed verdict between identical runs: ")
            + ", ".join(f"<code>{_e(case_id)}</code>" for case_id in unstable)
            + _e(
                ". Five runs is the floor for that reason: three would have recorded a coin flip as a defect."
            )
        )
    for entry in scripted:
        if entry["verdict"] == NOT_APPLICABLE:
            items.append(
                f"<code>{_e(entry['name'])}</code> is not tested by the free run: "
                + _e(entry["note"] or "no reason recorded")
                + _e(". It is reported as not applicable, never as a pass.")
            )
    items.append(_e(COPY["orbison"]))
    items.append(
        _e(
            COPY["single_source"].format(
                single=f"{figures['single_source']:,}",
                influence=f"{figures['influence_edges']:,}",
                corroborated=figures["corroborated"],
                contested=figures["contested_pairs"],
            )
        )
    )
    if heldout and heldout[-1][1].get("artifact_version") != current_artifact:
        items.append(
            _e(
                f"The held-out set was run at artifact {heldout[-1][1]['artifact_version']}. The "
                f"corpus is now {current_artifact}, so generalization is untested on it, not passed."
            )
        )
    return (
        '<h2 id="did-not-work">What did not work</h2><ul>'
        + "".join(f"<li>{item}</li>" for item in items)
        + "</ul>"
    )


# --- the page ---------------------------------------------------------------------------------------

STYLE = """
:root{color-scheme:dark;--ink:#f3effa;--ink-soft:#bab0cf;--ink-faint:#8b81a6;--ground:#0d0a14;
--card:#171327;--rule:#2b2440;--accent:#ff5cae;--contested:#5cd8ff}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);line-height:1.55;
font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
-webkit-font-smoothing:antialiased}
main{max-width:54rem;margin:0 auto;padding-block:2.5rem 4rem;padding-inline:1rem}
h1{font-size:1.9rem;line-height:1.2;margin:0 0 .75rem}
h2{font-size:1.2rem;margin:2.75rem 0 .75rem;padding-top:1.25rem;border-top:1px solid var(--rule)}
p{color:var(--ink-soft);max-width:42rem}
a{color:var(--contested)}
code{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,monospace;font-size:.85em;color:var(--ink)}
.scroll{overflow-x:auto;margin:.5rem 0 1rem;background:var(--card);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:.9rem;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:.5rem .75rem;border-bottom:1px solid var(--rule);vertical-align:top}
th{color:var(--ink-faint);font-weight:600}
tr:last-child td{border-bottom:0}
.note{color:var(--ink-faint);font-size:.85rem}
.v-pass{color:var(--ink)}
.v-fail{color:var(--accent);font-weight:700}
.v-na{color:var(--contested)}
ul{padding-left:1.25rem}
li{color:var(--ink-soft);margin:.6rem 0;max-width:42rem}
.lede{font-size:1.05rem}
"""


def render() -> str:
    """The exact bytes the committed page should hold."""
    store = InMemoryGraphStore.from_directory(artifact_directory())
    figures = corpus_figures(store, Artifact.load(artifact_directory()))
    current = store.artifact_version

    live = live_set()
    floor = _load(NOISE_FLOOR)
    gated = gated_live_run(live["name"], results("bedrock"))
    if gated is not None:
        label, run = f"the gated run of {_when(gated[0])}", gated[1]
    else:
        newest = floor["runs"][-1]
        label = f"the newest baseline run, {_when(newest.split('-', 1)[0])}"
        run = _load(RESULTS_DIR / newest)

    outcome = gate(run_gold_suite(store))
    if outcome.report is None:
        raise LookupError("the scripted run matched no threshold set; there is nothing to publish")
    scripted = gate_record(outcome)["gates"]

    tier2 = results("tier2")
    heldout = results("heldout")
    sections = [
        "<h1>How Musical Mycelium is evaluated</h1>",
        _p(COPY["intro"], "lede"),
        _p(COPY["grounded"]),
        f'<p><a href="/">Back to the app</a> · artifact {_e(current)}</p>',
        live_gates_section(live, gated),
        scripted_gates_section(scripted),
        metrics_section(label, run, floor),
        slices_section(run),
        judged_section(tier2[-1], results("judge")) if tier2 else "",
        heldout_section(heldout, current),
        did_not_work_section(floor, live, scripted, figures, heldout, current),
    ]
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Musical Mycelium: evaluation report</title>\n"
        f"<style>{STYLE}</style>\n</head>\n<body>\n<main>\n"
        + "\n".join(section for section in sections if section)
        + "\n</main>\n</body>\n</html>\n"
    )


def main() -> None:
    page = render()
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(page, encoding="utf-8")
    print(f"wrote {PAGE.relative_to(Path.cwd())}: {len(page.encode('utf-8')):,} bytes")


if __name__ == "__main__":
    main()
