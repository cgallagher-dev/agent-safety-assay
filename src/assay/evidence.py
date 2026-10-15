"""Evidence record: one line of evidence.jsonl per sample.

Ids, tool names, booleans and counts only. No prompt, response, reasoning,
tool argument or judge explanation is stored, so the file can be shared.
"""

from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from assay.errors import EvidenceError, validation_problems

ToolName = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]


class Gates(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    structural: bool
    structural_attempted: bool
    semantic: bool


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    run_id: str
    configuration: str
    repeat: int = Field(ge=1)
    arm: Literal["benign", "harmful"]
    split: Literal["test_public", "validation"]
    sample_id: str = Field(pattern=r"^\d+-\d+$")
    key: str
    base_behaviour: str
    category: str
    detailed: bool
    hint: bool
    declared_tools: list[ToolName]
    observed_tools: list[ToolName]
    executed_tools: list[ToolName]
    gates: Gates
    benchmark_score: float = Field(ge=0, le=1)
    refusal: bool | None
    judge: str | None
    messages: int = Field(ge=0)
    capped: bool
    truncated: bool
    log: str

    @model_validator(mode="after")
    def _key_matches_sample(self) -> "EvidenceRecord":
        if self.key != f"{self.split}/{self.sample_id}":
            raise ValueError("key must be the split and sample id joined by '/'")
        if self.base_behaviour != f"{self.split}/{self.sample_id.split('-')[0]}":
            raise ValueError("base_behaviour must be the key without its variant suffix")
        return self


def write_evidence(path: Path, records: Iterable[EvidenceRecord]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(record.model_dump_json() + "\n")


def read_evidence(path: Path) -> list[EvidenceRecord]:
    if not path.is_file():
        raise EvidenceError(f"No evidence file at {path}. Run assay judge on the results first.")
    records = []
    with path.open(encoding="utf-8") as file:
        for number, line in enumerate(file, start=1):
            try:
                records.append(EvidenceRecord.model_validate_json(line))
            except ValidationError as error:
                raise EvidenceError(
                    f"{path}, line {number}: {validation_problems(error)}. "
                    "Regenerate it with assay judge."
                ) from None
    return records
