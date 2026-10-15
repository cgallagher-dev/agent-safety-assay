import type { GateResult, Report, ReportRate } from "../api/types";

function rate(numerator: number, denominator: number): ReportRate {
  return { numerator, denominator, value: numerator / denominator, undefined_reason: null };
}

function undefinedRate(reason: string): ReportRate {
  return { numerator: 0, denominator: 0, value: null, undefined_reason: reason };
}

function gate(metrics: GateResult["metrics"], verdicts: number[]): GateResult {
  const names = [
    "complied",
    "refused_when_capable",
    "failed_when_capable",
    "refused_untested",
    "no_signal",
    "capability_anomaly",
  ];
  return {
    metrics,
    verdicts: Object.fromEntries(names.map((name, i) => [name, verdicts[i]])),
    overlap: 1,
    anomalies: [],
    benign_refusals: 0,
    cgr_benign_refused: rate(0, 9),
  };
}

const capable = gate(
  {
    benign_pass_rate: rate(20, 30),
    asr: rate(12, 30),
    cc_asr: rate(11, 20),
    cc_rr: rate(6, 17),
    cgr: rate(9, 18),
  },
  [11, 6, 3, 3, 6, 1],
);

const stricter = gate(
  {
    benign_pass_rate: rate(15, 30),
    asr: rate(8, 30),
    cc_asr: rate(7, 15),
    cc_rr: rate(6, 13),
    cgr: rate(14, 22),
  },
  [7, 6, 2, 3, 11, 1],
);

const incapable = gate(
  {
    benign_pass_rate: rate(0, 30),
    asr: rate(0, 30),
    cc_asr: undefinedRate("no benign task passed"),
    cc_rr: undefinedRate("no pair with a passed benign task was refused or succeeded"),
    cgr: rate(30, 30),
  },
  [0, 0, 0, 4, 26, 0],
);

const limits = { benign: { capped: 0, truncated: 0 }, harmful: { capped: 1, truncated: 0 } };

export const report: Report = {
  schema_version: 1,
  assay_version: "0.1.0",
  created_at: "2026-11-12T21:30:00Z",
  headline_gate: "structural",
  runs: [
    {
      run_id: "20261112T2130Z-7f3a",
      versions: {},
      judge: "demo/judge",
      sampling: { temperature: 1 },
      message_limit: 20,
      splits: ["test_public"],
      exclusions: [],
    },
  ],
  configurations: [
    {
      name: "small/off",
      profile: "small",
      mode: "off",
      repeats: 1,
      pairs: 30,
      gates: { structural: capable, structural_attempted: capable, semantic: stricter },
      limits,
    },
    {
      name: "tiny/off",
      profile: "tiny",
      mode: "off",
      repeats: 1,
      pairs: 30,
      gates: { structural: incapable, structural_attempted: incapable, semantic: incapable },
      limits,
    },
  ],
  pairs: [],
};
