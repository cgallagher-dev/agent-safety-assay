import type { ConfigurationResult } from "../api/types";
import { BAR_ORDER, type Gate, SYMBOLS, VERDICTS } from "../labels";
import { href } from "../route";

interface Props {
  configuration: ConfigurationResult;
  gate: Gate;
}

export default function VerdictBar({ configuration, gate }: Props) {
  const counts = configuration.gates[gate].verdicts;
  const total = BAR_ORDER.reduce((sum, name) => sum + counts[name], 0);
  const verdicts = BAR_ORDER.map((name) => VERDICTS.find((verdict) => verdict.name === name)!);
  const link = (name: string) =>
    href("pairs", { configuration: configuration.name, verdict: name, gate });
  return (
    <div className="verdict-bar">
      <div className="bar" aria-hidden="true">
        {verdicts
          .filter(({ name }) => counts[name] > 0)
          .map(({ name, tone }) => (
            <a
              key={name}
              href={link(name)}
              tabIndex={-1}
              className={`segment tone-${tone}`}
              style={{ flexGrow: counts[name] }}
            >
              {counts[name] / total >= 0.08 && `${SYMBOLS[tone]} ${counts[name]}`}
            </a>
          ))}
      </div>
      <ul className="legend" aria-label="Verdicts">
        {verdicts.map(({ name, label, tone }) => (
          <li key={name} className={counts[name] === 0 ? "zero" : undefined}>
            <a href={link(name)} aria-label={`${SYMBOLS[tone]} ${label}: ${counts[name]}`}>
              <span className={`swatch tone-${tone}`} aria-hidden="true">
                {SYMBOLS[tone]}
              </span>{" "}
              {label} <strong>{counts[name]}</strong>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
