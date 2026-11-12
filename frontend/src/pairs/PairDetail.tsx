import { useEffect, useState } from "react";
import { fetchPair } from "../api/client";
import type { EvidenceRecord, PairDetail, Report } from "../api/types";
import { GATES, gateParam, SYMBOLS, VERDICT_LABELS, VERDICTS } from "../labels";
import Status, { loadError } from "../Status";
import { Transcript, TraceStructure } from "./Transcript";

function judged(arm: string, evidence: EvidenceRecord): string {
  const verdicts = {
    true: "refused",
    false: "did not refuse",
    null: "unjudged, nothing to judge",
  };
  return `${arm}: ${verdicts[String(evidence.refusal) as keyof typeof verdicts]} (judge ${evidence.judge})`;
}

function sequence(tools: string[]): string {
  return tools.length > 0 ? tools.join(" → ") : "none";
}

function ran(evidence: EvidenceRecord): string {
  const declared = new Set(evidence.declared_tools);
  const done = new Set(evidence.executed_tools.filter((tool) => declared.has(tool)));
  return `${done.size} of ${declared.size} declared tools ran`;
}

function step(evidence: EvidenceRecord, tool: string): { text: string; tone: string } {
  if (evidence.executed_tools.includes(tool)) {
    return { text: `${SYMBOLS.safe} ran`, tone: "ran" };
  }
  if (evidence.observed_tools.includes(tool)) {
    return { text: `${SYMBOLS.gap} called, failed`, tone: "failed" };
  }
  return { text: `${SYMBOLS.none} not called`, tone: "not-called" };
}

const NO_LOG =
  "The log for this sample is not in the results directory, so only its evidence is shown.";

export default function PairDetailPage({
  report,
  params,
}: {
  report: Report;
  params: URLSearchParams;
}) {
  const configuration = params.get("configuration") ?? "";
  const repeat = Number(params.get("repeat"));
  const key = params.get("key") ?? "";
  const gate = gateParam(params, report.headline_gate);
  const [detail, setDetail] = useState<PairDetail | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const known = report.pairs.some(
    (pair) => pair.configuration === configuration && pair.repeat === repeat && pair.key === key,
  );

  useEffect(() => {
    if (known) {
      fetchPair(configuration, repeat, key).then(setDetail, setError);
    }
  }, [known, configuration, repeat, key]);

  if (!known) {
    return (
      <Status kind="empty" title={`No pair ${key || "(none given)"} in this run`}>
        <p>
          The link may be from another run, or the pair was left out as unjudged.{" "}
          <a href="#/">Back to the overview</a>
        </p>
      </Status>
    );
  }
  if (error) {
    return (
      <Status kind="error" title={`Couldn't load the pair ${key}`}>
        {loadError(error)}
        <p>
          <a href="#/">Back to the overview</a>
        </p>
      </Status>
    );
  }
  if (!detail) {
    return <Status kind="loading" title={`Loading the pair ${key}…`} />;
  }
  const { pair, benign, harmful } = detail;
  const reading = pair.gates[gate];
  const verdict = VERDICTS.find(({ name }) => name === reading.verdict)!;
  // Declared tools in task order, then anything else either arm called.
  const tools = [
    ...new Set([
      ...benign.evidence.declared_tools,
      ...benign.evidence.observed_tools,
      ...harmful.evidence.observed_tools,
    ]),
  ];
  const rows: {
    label: string;
    field: "declared_tools" | "observed_tools" | "executed_tools";
  }[] = [
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

      <section aria-label="Verdict" className={`verdict-banner tone-${verdict.tone}`}>
        <p>
          Benign twin: {reading.benign_passed ? "passed" : "failed"}, {ran(benign.evidence)}.
        </p>
        <p>
          Harmful task: {harmful.evidence.refusal ? "refused" : "did not refuse"},{" "}
          {ran(harmful.evidence)}.
        </p>
        <p className="verdict-line">
          Verdict on {GATES.find(({ name }) => name === gate)!.label}:{" "}
          <strong>
            {SYMBOLS[verdict.tone]} {verdict.label}
          </strong>
        </p>
      </section>

      <section>
        <h3>Tool steps</h3>
        <table aria-label="Tool steps" className="steps">
          <thead>
            <tr>
              <th scope="col">Tool</th>
              <th scope="col">Benign twin</th>
              <th scope="col">Harmful task</th>
            </tr>
          </thead>
          <tbody>
            {tools.map((tool) => (
              <tr key={tool}>
                <th scope="row">
                  {tool}
                  {!benign.evidence.declared_tools.includes(tool) && (
                    <span className="undeclared"> (not one of the task's tools)</span>
                  )}
                </th>
                {[benign.evidence, harmful.evidence].map((evidence) => {
                  const { text, tone } = step(evidence, tool);
                  return (
                    <td key={evidence.arm} className={`step-${tone}`}>
                      {text}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

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
        <h3>Call order</h3>
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
