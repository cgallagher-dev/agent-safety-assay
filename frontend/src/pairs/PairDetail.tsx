import { useEffect, useState } from "react";
import { fetchPair } from "../api/client";
import type { EvidenceRecord, PairDetail, Report } from "../api/types";
import { type Gate, GATES, VERDICT_LABELS } from "../labels";
import { Transcript, TraceStructure } from "./Transcript";

function judged(arm: string, evidence: EvidenceRecord): string {
  const verdicts = { true: "refused", false: "did not refuse", null: "unjudged, nothing to judge" };
  return `${arm}: ${verdicts[String(evidence.refusal) as keyof typeof verdicts]} (judge ${evidence.judge})`;
}

function sequence(tools: string[]): string {
  return tools.length > 0 ? tools.join(" → ") : "none";
}

const NO_LOG = "The log for this sample is not in the results directory, so only its evidence is shown.";

export default function PairDetailPage({ report, params }: { report: Report; params: URLSearchParams }) {
  const configuration = params.get("configuration") ?? "";
  const repeat = Number(params.get("repeat"));
  const key = params.get("key") ?? "";
  const gate = (params.get("gate") ?? report.headline_gate) as Gate;
  const [detail, setDetail] = useState<PairDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPair(configuration, repeat, key).then(setDetail, (reason: Error) => setError(reason.message));
  }, [configuration, repeat, key]);

  if (error) {
    return <p role="alert">Could not load the pair: {error}.</p>;
  }
  if (!detail) {
    return <p>Loading the pair...</p>;
  }
  const { pair, benign, harmful } = detail;
  const rows: { label: string; field: "declared_tools" | "observed_tools" | "executed_tools" }[] = [
    { label: "Declared", field: "declared_tools" },
    { label: "Observed (attempted)", field: "observed_tools" },
    { label: "Executed (no tool error)", field: "executed_tools" },
  ];

  return (
    <>
      <h2>{pair.key}</h2>
      <p>
        {pair.category}, {pair.configuration}, repeat {pair.repeat}
      </p>

      <section>
        <h3>Verdicts</h3>
        <table aria-label="Verdict by gate">
          <thead>
            <tr>
              <th scope="col">Capability gate</th>
              <th scope="col">Benign task passed</th>
              <th scope="col">Harmful task executed</th>
              <th scope="col">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {GATES.map(({ name, label }) => (
              <tr key={name} className={name === gate ? "selected" : undefined}>
                <th scope="row">{label}</th>
                <td>{pair.gates[name].benign_passed ? "yes" : "no"}</td>
                <td>{pair.gates[name].executed ? "yes" : "no"}</td>
                <td>{VERDICT_LABELS[pair.gates[name].verdict]}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <ul>
          <li>{judged("Harmful arm", harmful.evidence)}</li>
          <li>{judged("Benign arm", benign.evidence)}</li>
        </ul>
      </section>

      <section>
        <h3>Tool calls</h3>
        <table aria-label="Tool calls">
          <thead>
            <tr>
              <th scope="col">Calls</th>
              <th scope="col">Benign arm</th>
              <th scope="col">Harmful arm</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ label, field }) => (
              <tr key={field}>
                <th scope="row">{label}</th>
                <td>{sequence(benign.evidence[field])}</td>
                <td>{sequence(harmful.evidence[field])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <div className="arms">
        <section aria-label="Benign transcript">
          <h3>Benign transcript</h3>
          {benign.transcript ? <Transcript turns={benign.transcript} /> : <p>{NO_LOG}</p>}
        </section>
        <section aria-label="Harmful trace">
          <h3>Harmful trace</h3>
          <p className="withheld">
            Content withheld: the harmful arm's prompt, replies, reasoning and tool arguments never
            leave the backend. Only roles, tool names and tool errors are shown.
          </p>
          {harmful.transcript ? <TraceStructure turns={harmful.transcript} /> : <p>{NO_LOG}</p>}
        </section>
      </div>
    </>
  );
}
