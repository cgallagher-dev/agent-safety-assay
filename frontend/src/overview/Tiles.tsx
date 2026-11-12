import type { ConfigurationResult } from "../api/types";
import { type Gate, SYMBOLS, TILES } from "../labels";
import Rate from "./Rate";

interface Props {
  configuration: ConfigurationResult;
  gate: Gate;
  headline: Gate;
}

export default function Tiles({ configuration, gate, headline }: Props) {
  return (
    <div className="tiles">
      {TILES.map(({ name, label, title, question, tone }) => {
        const rate = configuration.gates[gate].metrics[name];
        return (
          <article key={name} className={`tile tone-${tone}`} aria-label={label}>
            <h4 title={title}>
              <span className="symbol" aria-hidden="true">
                {SYMBOLS[tone]}
              </span>{" "}
              {label}
            </h4>
            <p className="question">{question}</p>
            <p className="value">
              <Rate rate={rate} />
            </p>
            <div className="meter" aria-hidden="true">
              <div style={{ width: `${(rate.value ?? 0) * 100}%` }} />
            </div>
            {gate !== headline && (
              <p className="headline-value">
                headline <Rate rate={configuration.gates[headline].metrics[name]} />
              </p>
            )}
          </article>
        );
      })}
    </div>
  );
}
