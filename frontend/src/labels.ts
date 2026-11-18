import type { MetricSet, PairRef, Report, Verdict } from "./api/types";
import shown from "./labels.json";

export type Gate = Report["headline_gate"];

export const GATES = shown.gates as { name: Gate; label: string }[];

// A gate read from a link, which may be stale or hand-edited.
export function gateParam(params: URLSearchParams, fallback: Gate): Gate {
  const value = params.get("gate");
  return GATES.find(({ name }) => name === value)?.name ?? fallback;
}

// What a colour means for safety (docs/presentation.md); always shown with a symbol and a word.
export type Tone = keyof typeof shown.tones;

export const SYMBOLS = Object.fromEntries(
  Object.entries(shown.tones).map(([tone, { symbol }]) => [tone, symbol]),
) as Record<Tone, string>;

// The palette lives in labels.json with the console's and the PDF's, not in the stylesheet.
export function paintPalette(root: HTMLElement): void {
  for (const [tone, { colour }] of Object.entries(shown.tones)) {
    root.style.setProperty(`--${tone}`, colour);
  }
}

type Metric = {
  name: keyof MetricSet;
  label: string;
  title: string;
  question: string;
  definition: string;
  tone: Tone;
};

export const METRICS = shown.metrics as Metric[];

// The tiles, conditioned metrics first, with the plain questions from the Demo 1 slides.
export const TILES = shown.card_order.map((name) =>
  METRICS.find((m) => m.name === name)!,
);

export type HarmfulOutcome = "done" | "refused" | "not done";

const CELLS: Record<
  Verdict,
  { benignPassed: boolean; outcome: HarmfulOutcome }
> = {
  complied: { benignPassed: true, outcome: "done" },
  refused_when_capable: { benignPassed: true, outcome: "refused" },
  failed_when_capable: { benignPassed: true, outcome: "not done" },
  refused_untested: { benignPassed: false, outcome: "refused" },
  no_signal: { benignPassed: false, outcome: "not done" },
  capability_anomaly: { benignPassed: false, outcome: "done" },
};

// The six cells of benign pass/fail by harmful outcome, in report order.
export const VERDICTS = shown.verdicts.map(({ name, label, tone }) => ({
  name: name as Verdict,
  label: label[0].toUpperCase() + label.slice(1),
  tone: tone as Tone,
  ...CELLS[name as Verdict],
}));

// Harm on the left and safe-with-evidence on the right, so red and green never touch.
export const BAR_ORDER = shown.bar_order as Verdict[];

export const POLICY_LABELS = shown.policies as Record<
  Report["headline_policy"],
  string
>;

export const VERDICT_LABELS = Object.fromEntries(
  VERDICTS.map(({ name, label }) => [name, label]),
) as Record<Verdict, string>;

// A pair key, with its repeat when the configuration has more than one.
export function pairRefs(refs: PairRef[], repeats: number): string {
  return refs
    .map(({ key, repeat }) => (repeats === 1 ? key : `${key} r${repeat}`))
    .join(", ");
}
