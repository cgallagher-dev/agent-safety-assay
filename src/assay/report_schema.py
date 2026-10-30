"""The report.json schema (spec section 8), validated on write and read.

The text table, CSV files, PDF and dashboard API all render these models.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from assay.metrics import Rate
from assay.outcomes import Gate, Verdict

SCHEMA_VERSION = 1


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


class PairRef(ReportModel):
    repeat: int
    key: str


class GateResult(ReportModel):
    metrics: MetricSet
    verdicts: dict[Verdict, int]
    overlap: int
    anomalies: list[PairRef]
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
    unjudged: list[PairRef]
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
