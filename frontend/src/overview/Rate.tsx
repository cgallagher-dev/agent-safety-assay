import type { ReportRate } from "../api/types";

// Formats a rate from the report; an empty denominator is never shown as zero.
export default function Rate({ rate }: { rate: ReportRate }) {
  if (rate.value === null) {
    return <span className="undefined">undefined ({rate.undefined_reason})</span>;
  }
  return (
    <span className="rate">
      <span>{(rate.value * 100).toFixed(1)}%</span>{" "}
      <span className="fraction">{`(${rate.numerator}/${rate.denominator})`}</span>
    </span>
  );
}
