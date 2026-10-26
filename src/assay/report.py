"""Report schema and builder.

report.json is the one numeric source: the text table, the CSV files, the PDF
and the dashboard all render it. Its shape follows spec section 8.
"""

import csv
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from assay import __version__
from assay.errors import EvidenceError, validation_problems
from assay.evidence import EvidenceRecord, key_order, read_evidence
from assay.metrics import Rate, summarise
from assay.outcomes import (
    VERDICTS,
    Gate,
    PairKey,
    PairOutcome,
    Verdict,
    pair_outcomes,
    unjudged_pairs,
)

SCHEMA_VERSION = 1
HEADLINE_GATE: Gate = "structural"
GATES: tuple[Gate, ...] = ("structural", "structural_attempted", "semantic")
ARMS = ("benign", "harmful")

METRIC_LABELS = {
    "benign_pass_rate": "Benign pass rate",
    "asr": "ASR",
    "cc_asr": "ccASR",
    "cc_rr": "ccRR",
    "cgr": "CGR",
}
VERDICT_LABELS = {
    Verdict.COMPLIED: "complied",
    Verdict.REFUSED_WHEN_CAPABLE: "refused when capable",
    Verdict.FAILED_WHEN_CAPABLE: "failed when capable",
    Verdict.REFUSED_UNTESTED: "refused with capability untested",
    Verdict.NO_SIGNAL: "no signal",
    Verdict.CAPABILITY_ANOMALY: "capability anomaly",
}


class ReportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReportRate(ReportModel):
    numerator: int
    denominator: int
    value: float | None
    undefined_reason: str | None

    @classmethod
    def of(cls, rate: Rate) -> "ReportRate":
        return cls(
            numerator=rate.numerator,
            denominator=rate.denominator,
            value=rate.value,
            undefined_reason=rate.undefined_reason,
        )


class MetricSet(ReportModel):
    benign_pass_rate: ReportRate
    asr: ReportRate
    cc_asr: ReportRate
    cc_rr: ReportRate
    cgr: ReportRate


class GateResult(ReportModel):
    metrics: MetricSet
    verdicts: dict[Verdict, int]
    overlap: int
    anomalies: list[str]
    benign_refusals: int
    cgr_benign_refused: ReportRate


class LimitCounts(ReportModel):
    capped: int
    truncated: int


class ConfigurationResult(ReportModel):
    name: str
    profile: str
    mode: str
    repeats: int
    pairs: int
    # Pairs left out of every metric because the judge had nothing to read on one arm.
    unjudged: list[str]
    gates: dict[Gate, GateResult]
    limits: dict[Literal["benign", "harmful"], LimitCounts]


class Exclusion(ReportModel):
    key: str
    reason: str


class RunInfo(ReportModel):
    run_id: str
    versions: dict[str, str]
    judge: str
    sampling: dict[str, int | float]
    message_limit: int
    splits: list[str]
    exclusions: list[Exclusion]


class PairGate(ReportModel):
    benign_passed: bool
    executed: bool
    verdict: Verdict


class PairRow(ReportModel):
    configuration: str
    repeat: int
    key: str
    base_behaviour: str
    category: str
    refused: bool
    benign_refused: bool
    gates: dict[Gate, PairGate]


class Report(ReportModel):
    schema_version: Literal[1]
    assay_version: str
    created_at: datetime
    headline_gate: Gate
    runs: list[RunInfo]
    configurations: list[ConfigurationResult]
    pairs: list[PairRow]


class ConfiguredMode(BaseModel):
    profile: str
    mode: str


class RunConfig(RunInfo):
    """The parts of run_config.json that a report reads."""

    model_config = ConfigDict(extra="ignore")

    configurations: dict[str, ConfiguredMode]


def build_report(
    run_config: RunConfig, records: list[EvidenceRecord], created_at: datetime | None = None
) -> Report:
    evidence_names = {r.configuration for r in records}
    if evidence_names != set(run_config.configurations):
        raise EvidenceError(
            f"The evidence covers {sorted(evidence_names)} but run_config.json lists "
            f"{sorted(run_config.configurations)}. Regenerate the evidence for this run."
        )
    outcomes = {gate: pair_outcomes(records, gate) for gate in GATES}
    unjudged = unjudged_pairs(records)
    configurations = [
        _configuration_result(name, mode, records, outcomes, unjudged)
        for name, mode in run_config.configurations.items()
    ]
    return Report(
        schema_version=SCHEMA_VERSION,
        assay_version=__version__,
        created_at=created_at or datetime.now(UTC),
        headline_gate=HEADLINE_GATE,
        runs=[RunInfo(**run_config.model_dump(exclude={"configurations"}))],
        configurations=configurations,
        pairs=_pair_rows(outcomes, list(run_config.configurations)),
    )


def _configuration_result(
    name: str,
    configured: ConfiguredMode,
    records: list[EvidenceRecord],
    outcomes: dict[Gate, list[PairOutcome]],
    unjudged: list[PairKey],
) -> ConfigurationResult:
    mine = [r for r in records if r.configuration == name]
    # Repeats are pooled here; per-repeat readings come with the statistics.
    return ConfigurationResult(
        name=name,
        profile=configured.profile,
        mode=configured.mode,
        repeats=len({r.repeat for r in mine}),
        pairs=len({r.key for r in mine}),
        unjudged=[
            key
            for _, _, key in sorted(
                (p for p in unjudged if p[0] == name), key=lambda p: (p[1], key_order(p[2]))
            )
        ],
        gates={
            gate: _gate_result([o for o in outcomes[gate] if o.configuration == name])
            for gate in GATES
        },
        limits={
            arm: LimitCounts(
                capped=sum(r.capped for r in mine if r.arm == arm),
                truncated=sum(r.truncated for r in mine if r.arm == arm),
            )
            for arm in ARMS
        },
    )


def _gate_result(outcomes: list[PairOutcome]) -> GateResult:
    summary = summarise(outcomes)
    return GateResult(
        metrics=MetricSet(
            **{name: ReportRate.of(rate) for name, rate in vars(summary.metrics).items()}
        ),
        verdicts=summary.verdicts,
        overlap=summary.overlap,
        anomalies=summary.anomalies,
        benign_refusals=summary.benign_refusals,
        cgr_benign_refused=ReportRate.of(summary.cgr_benign_refused),
    )


def _pair_rows(outcomes: dict[Gate, list[PairOutcome]], names: list[str]) -> list[PairRow]:
    by_pair: dict[tuple[str, int, str], dict[Gate, PairOutcome]] = defaultdict(dict)
    for gate in GATES:
        for outcome in outcomes[gate]:
            by_pair[(outcome.configuration, outcome.repeat, outcome.key)][gate] = outcome
    ordered = sorted(by_pair, key=lambda p: (names.index(p[0]), p[1], key_order(p[2])))
    rows = []
    for configuration, repeat, key in ordered:
        gates = by_pair[(configuration, repeat, key)]
        headline = gates[HEADLINE_GATE]
        rows.append(
            PairRow(
                configuration=configuration,
                repeat=repeat,
                key=key,
                base_behaviour=headline.base_behaviour,
                category=headline.category,
                refused=headline.refused,
                benign_refused=headline.benign_refused,
                gates={
                    gate: PairGate(
                        benign_passed=o.benign_passed, executed=o.executed, verdict=o.verdict
                    )
                    for gate, o in gates.items()
                },
            )
        )
    return rows


def load_report(results: Path) -> Report:
    """Build a report from a results directory's run_config.json and evidence.jsonl."""
    return build_report(read_run_config(results), read_evidence(results / "evidence.jsonl"))


def read_run_config(results: Path) -> RunConfig:
    path = results / "run_config.json"
    if not path.is_file():
        raise EvidenceError(f"No run_config.json in {results}. Is it a results directory?")
    try:
        return RunConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise EvidenceError(f"{path}: {validation_problems(error)}.") from None


def read_report(path: Path) -> Report:
    try:
        return Report.model_validate_json(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise EvidenceError(f"No report at {path}. Build it with assay report.") from None
    except ValidationError as error:
        raise EvidenceError(
            f"{path}: {validation_problems(error)}. Rebuild it with assay report."
        ) from None


def write_report(report: Report, out: Path) -> None:
    """Write report.json, metrics.csv and pairs.csv to out."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    with (out / "metrics.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "configuration",
                "gate",
                "metric",
                "numerator",
                "denominator",
                "value",
                "undefined_reason",
            ]
        )
        for configuration in report.configurations:
            for gate, result in configuration.gates.items():
                for metric, rate in result.metrics:
                    writer.writerow(
                        [
                            configuration.name,
                            gate,
                            metric,
                            rate.numerator,
                            rate.denominator,
                            "" if rate.value is None else rate.value,
                            rate.undefined_reason or "",
                        ]
                    )
    with (out / "pairs.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["configuration", "repeat", "key", "base_behaviour", "category", *GATES])
        for pair in report.pairs:
            writer.writerow(
                [
                    pair.configuration,
                    pair.repeat,
                    pair.key,
                    pair.base_behaviour,
                    pair.category,
                    *(pair.gates[gate].verdict for gate in GATES),
                ]
            )


def format_rate(rate: ReportRate) -> str:
    if rate.value is None:
        return f"undefined ({rate.undefined_reason})"
    return f"{rate.value:6.1%} ({rate.numerator}/{rate.denominator})"


def format_report(report: Report) -> str:
    """The metrics per configuration and the pair table, on the headline gate."""
    gate = report.headline_gate
    lines = [
        ", ".join(f"Run {run.run_id}, judge {run.judge}" for run in report.runs)
        + f". Gate: {gate}. Outcomes: refusal first."
    ]
    for configuration in report.configurations:
        result = configuration.gates[gate]
        repeats = "repeat" if configuration.repeats == 1 else "repeats"
        lines += [
            "",
            f"{configuration.name} (profile {configuration.profile}, mode {configuration.mode}, "
            f"{configuration.pairs} pairs, {configuration.repeats} {repeats})",
        ]
        lines += [
            f"  {METRIC_LABELS[metric]:<22}{format_rate(rate)}" for metric, rate in result.metrics
        ]
        lines += [
            f"  {'Benign ' + ('passed' if passed else 'failed'):<22}"
            + ", ".join(
                f"{VERDICT_LABELS[verdict]} {result.verdicts[verdict]}"
                for (benign_passed, _), verdict in VERDICTS.items()
                if benign_passed == passed
            )
            for passed in (True, False)
        ]
        limits = configuration.limits
        lines += [
            f"  {'Executed and refused':<22}{result.overlap}",
            f"  {'Capability anomalies':<22}{', '.join(result.anomalies) or 'none'}",
            f"  {'Unjudged, left out':<22}{', '.join(configuration.unjudged) or 'none'}",
            f"  {'Benign refusals':<22}{result.benign_refusals}, "
            f"{format_rate(result.cgr_benign_refused).strip()} of the CGR numerator",
            f"  {'Capped':<22}benign {limits['benign'].capped}, harmful {limits['harmful'].capped}",
            f"  {'Truncated':<22}benign {limits['benign'].truncated}, "
            f"harmful {limits['harmful'].truncated}",
        ]
    lines += ["", f"Pairs ({gate} gate)", *_pair_table(report)]
    return "\n".join(lines)


def _pair_table(report: Report) -> list[str]:
    repeats = {c.name: c.repeats for c in report.configurations}
    columns = list(dict.fromkeys((p.configuration, p.repeat) for p in report.pairs))
    headers = [name if repeats[name] == 1 else f"{name} r{repeat}" for name, repeat in columns]
    cells: dict[str, dict[tuple[str, int], str]] = defaultdict(dict)
    categories = {}
    for pair in report.pairs:
        cells[pair.key][(pair.configuration, pair.repeat)] = VERDICT_LABELS[
            pair.gates[report.headline_gate].verdict
        ]
        categories[pair.key] = pair.category
    rows = [
        [key, categories[key], *(cells[key].get(column, "-") for column in columns)]
        for key in sorted(cells, key=key_order)
    ]
    table = [["key", "category", *headers], *rows]
    widths = [max(len(row[i]) for row in table) for i in range(len(table[0]))]
    return [
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip()
        for row in table
    ]
