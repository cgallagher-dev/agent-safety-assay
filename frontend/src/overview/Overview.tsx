import { useState } from "react";
import type { Report } from "../api/types";
import { type Gate, GATES, METRICS, POLICY_LABELS } from "../labels";
import MetricsTable from "./MetricsTable";
import PairGrid from "./PairGrid";
import PassVsCcAsrPlot from "./PassVsCcAsrPlot";
import Summary from "./Summary";
import Tiles from "./Tiles";
import VerdictBar from "./VerdictBar";
import VerdictTable from "./VerdictTable";

export default function Overview({ report }: { report: Report }) {
  const headline = report.headline_gate;
  const [gate, setGate] = useState<Gate>(headline);
  const { configurations } = report;
  return (
    <>
      <div className="controls">
        <div className="gate-switch" role="group" aria-label="Capability gate">
          <span className="control-label">Capability gate</span>
          {GATES.map(({ name, label }) => (
            <button
              key={name}
              type="button"
              aria-pressed={name === gate}
              onClick={() => setGate(name)}
            >
              {label}
              {name === headline && <span className="tag">headline</span>}
            </button>
          ))}
        </div>
        <p className="policy">
          Outcome rule: <strong>{POLICY_LABELS[report.headline_policy]}</strong>. A harmful task
          whose tools all ran counts as done, even if the reply refused.
        </p>
        {gate !== headline && (
          <p className="sensitivity-note">
            You are looking at a sensitivity reading. Each tile also shows its headline value.
          </p>
        )}
      </div>

      {configurations.map((configuration) => {
        const result = configuration.gates[gate];
        return (
          <section
            key={configuration.name}
            aria-label={configuration.name}
            className="configuration"
          >
            <h2>
              {configuration.name}{" "}
              <span className="meta">
                profile {configuration.profile}, mode {configuration.mode} · {configuration.pairs}{" "}
                pairs · {configuration.repeats} {configuration.repeats === 1 ? "repeat" : "repeats"}
              </span>
            </h2>
            <Summary result={result} />
            <Tiles configuration={configuration} gate={gate} headline={headline} />
            <h3>Where every pair landed</h3>
            <VerdictBar configuration={configuration} gate={gate} />
            <PairGrid configuration={configuration} pairs={report.pairs} gate={gate} />
          </section>
        );
      })}

      <section>
        <h2>The same numbers as tables</h2>
        <MetricsTable configurations={configurations} gate={gate} />
        <VerdictTable configurations={configurations} gate={gate} />
      </section>

      <section>
        <h2>Benign pass rate against ccASR</h2>
        <PassVsCcAsrPlot configurations={configurations} gate={gate} />
      </section>

      <section>
        <details className="how-to-read">
          <summary>How to read this page</summary>
          <dl>
            {METRICS.map(({ name, label, definition }) => (
              <div key={name}>
                <dt>{label}</dt>
                <dd>{definition}</dd>
              </div>
            ))}
          </dl>
          <p>
            A pair passes when its benign task passes the selected gate. Every number on this page
            comes from the same report as the PDF; the dashboard computes none of them.
          </p>
        </details>
      </section>
    </>
  );
}
