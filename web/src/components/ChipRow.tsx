import chipData from "../chips.json";

export interface ChipStep {
  query: string;
  kind: string;
  expect: "answer" | "refusal";
}

export interface Chip {
  id: string;
  label: string;
  blurb: string;
  steps: ChipStep[];
}

/**
 * The canonical chips, from the file `tests/test_chips.py` validates against the pinned artifact.
 *
 * Imported as JSON rather than restated here so there is exactly one definition. A chip list that lived
 * in TypeScript could not be checked by a Python test, and an unchecked chip is a demo that 404s in
 * front of a recruiter after the next re-ingest.
 */
export const CHIPS: Chip[] = (chipData.chips as Chip[]).map((chip) => ({
  id: chip.id,
  label: chip.label,
  blurb: chip.blurb,
  steps: chip.steps,
}));

interface Props {
  disabled: boolean;
  activeId: string | null;
  onPick: (chip: Chip) => void;
}

export function ChipRow({ disabled, activeId, onPick }: Props) {
  return (
    <div className="chips" role="group" aria-label="Example questions">
      {CHIPS.map((chip) => (
        <button
          key={chip.id}
          type="button"
          className={`chip${activeId === chip.id ? " chip--active" : ""}`}
          disabled={disabled}
          onClick={() => onPick(chip)}
        >
          <span className="chip__label">{chip.label}</span>
          <span className="chip__blurb">{chip.blurb}</span>
        </button>
      ))}
    </div>
  );
}
