import type { ConfigurationResult, PairRow } from "../api/types";
import { type Gate, type HarmfulOutcome, SYMBOLS, VERDICTS } from "../labels";
import { href } from "../route";

interface Props {
  configuration: ConfigurationResult;
  pairs: PairRow[];
  gate: Gate;
}

const OUTCOMES: { outcome: HarmfulOutcome; label: string }[] = [
  { outcome: "done", label: "Harmful task done" },
  { outcome: "refused", label: "Refused" },
  { outcome: "not done", label: "Not done" },
];

// The six verdicts as the 2×3 grid from the slides, with every pair drawn as a square.
export default function PairGrid({ configuration, pairs, gate }: Props) {
  const own = pairs.filter((pair) => pair.configuration === configuration.name);
  return (
    <table className="pair-grid" aria-label="Pairs by verdict">
      <thead>
        <tr>
          <td />
          {OUTCOMES.map(({ outcome, label }) => (
            <th scope="col" key={outcome}>
              {label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {[true, false].map((passed) => (
          <tr key={String(passed)}>
            <th scope="row">{passed ? "Benign twin passed" : "Benign twin failed"}</th>
            {OUTCOMES.map(({ outcome }) => {
              const verdict = VERDICTS.find(
                (v) => v.benignPassed === passed && v.outcome === outcome,
              )!;
              const inCell = own.filter((pair) => pair.gates[gate].verdict === verdict.name);
              return (
                <td key={outcome} className={`cell tone-${verdict.tone}`}>
                  <span className="cell-label">
                    <span aria-hidden="true">{SYMBOLS[verdict.tone]}</span> {verdict.label}{" "}
                    <strong>{inCell.length}</strong>
                  </span>
                  <span className="squares">
                    {inCell.map((pair) => {
                      const name =
                        configuration.repeats === 1 ? pair.key : `${pair.key} r${pair.repeat}`;
                      return (
                        <a
                          key={`${pair.repeat} ${pair.key}`}
                          className="square"
                          aria-label={name}
                          title={`${name}, ${pair.category}`}
                          href={href("pair", {
                            configuration: pair.configuration,
                            repeat: pair.repeat,
                            key: pair.key,
                            gate,
                          })}
                        />
                      );
                    })}
                  </span>
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
