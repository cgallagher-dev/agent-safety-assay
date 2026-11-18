import type { GateResult } from "../api/types";

export default function Summary({ result }: { result: GateResult }) {
  return <p className="summary">{result.summary}</p>;
}
