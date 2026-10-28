import { useState } from "react";
import type { Report } from "../api/types";
import { type Gate, GATES, METRICS } from "../labels";
import MetricsTable from "./MetricsTable";
import PassVsCcAsrPlot from "./PassVsCcAsrPlot";
import VerdictTable from "./VerdictTable";

export default function Overview({ report }: { report: Report }) {
  const [gate, setGate] = useState<Gate>(report.headline_gate);
  const { configurations } = report;
  return (
    <>
      <p className="gate">
        <label htmlFor="gate">Capability gate</label>{" "}
        <select id="gate" value={gate} onChange={(event) => setGate(event.target.value as Gate)}>
          {GATES.map(({ name, label }) => (
            <option key={name} value={name}>
              {name === report.headline_gate ? `${label} (headline)` : label}
            </option>
          ))}
        </select>
      </p>

      <section>
        <h2>Metrics</h2>
        <MetricsTable configurations={configurations} gate={gate} />
      </section>

      <section>
        <h2>Benign pass rate against ccASR</h2>
        <PassVsCcAsrPlot configurations={configurations} gate={gate} />
      </section>

      <section>
        <h2>Verdicts</h2>
        <VerdictTable configurations={configurations} gate={gate} />
      </section>

      <section>
        <h2>Definitions</h2>
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
          comes from report.json; the dashboard computes none of them.
        </p>
      </section>
    </>
  );
}
