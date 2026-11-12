import type { GateResult } from "../api/types";

function times(count: number): string {
  return count === 1 ? "1 time" : `${count} times`;
}

function tasks(count: number): string {
  return count === 1 ? "1 harmful task" : `${count} harmful tasks`;
}

// Counts read straight from the report; the sentence adds words, never a new number.
export function summary(result: GateResult): string {
  const { cc_asr, cgr } = result.metrics;
  const capable = cc_asr.denominator;
  const parts = [`did the harmful version ${times(result.verdicts.complied)}`];
  parts.push(`refused ${times(result.verdicts.refused_when_capable)}`);
  if (result.verdicts.failed_when_capable > 0) {
    parts.push(`failed ${times(result.verdicts.failed_when_capable)}`);
  }
  const sentences = [
    capable === 0
      ? "It passed no benign task on this gate, so nothing here shows it refusing a task it could do."
      : `On the ${capable === 1 ? "1 task" : `${capable} tasks`} it showed it could do, it ` +
        `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}.`,
  ];
  if (cgr.denominator > 0) {
    sentences.push(
      `Of the ${tasks(cgr.denominator)} it didn't do, ${cgr.numerator} had a benign twin that ` +
        "also failed, so they show inability, not safety.",
    );
  }
  return sentences.join(" ");
}

export default function Summary({ result }: { result: GateResult }) {
  return <p className="summary">{summary(result)}</p>;
}
