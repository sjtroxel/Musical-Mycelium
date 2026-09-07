import type { ContestedFrame } from "../types";

/**
 * Where two sources disagree about a pair this answer crossed.
 *
 * **The one thing this component must never do is pick a side.** The corpus records a disagreement, not
 * a verdict: Wikidata says one direction, DBpedia says the other, and nothing in this project knows
 * which is right. Both rows are rendered with equal weight for that reason — a layout that made one the
 * heading and the other a footnote would be a judgement the data does not support.
 *
 * **It must also never collapse into a badge next to a verification tier.** `verification` says how
 * strongly ONE source was checked; this says a SECOND source contradicts it. They are different
 * guarantees and this repo has already corrected three files for blurring them. So this is a block of
 * its own, above the claim list, and it never decorates a claim row.
 *
 * **Contested is not the same as reciprocal.** At artifact v0.7.1 six pairs point both ways and only two
 * are contested; the other four are a single source describing mutual influence, which between genres is
 * frequently a real claim. This component only ever receives the contested two, because
 * `graph/corroboration.py` compares sources before the frame is ever emitted.
 */
interface Props {
  contested: ContestedFrame[];
}

export function ContestedNotice({ contested }: Props) {
  if (contested.length === 0) return null;

  return (
    <section className="contested" aria-label="Where the sources disagree">
      <h3 className="contested__heading">
        {contested.length === 1
          ? "The sources disagree about one pair here"
          : `The sources disagree about ${contested.length} pairs here`}
      </h3>
      <ul className="contested__list">
        {contested.map((frame) => (
          <li className="contested__pair" key={`${frame.pair.a}-${frame.pair.b}`}>
            <p className="contested__direction">
              <span className="contested__source">{frame.pair.a_from_b.source}</span> records{" "}
              <span className="contested__node">{frame.a_label}</span> as influenced by{" "}
              <span className="contested__node">{frame.b_label}</span>.
            </p>
            <p className="contested__direction">
              <span className="contested__source">{frame.pair.b_from_a.source}</span> records{" "}
              <span className="contested__node">{frame.b_label}</span> as influenced by{" "}
              <span className="contested__node">{frame.a_label}</span>.
            </p>
            <p className="contested__note">
              Both are cited. This graph does not resolve which is right, and neither direction is
              presented as the answer.
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
