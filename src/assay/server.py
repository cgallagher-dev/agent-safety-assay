"""Read-only dashboard API, served by `assay dashboard`.

Responses come from a report built from evidence.jsonl at start-up and, for
pair detail, the sample's .eval log. Harmful-arm transcripts are rebuilt from structure only
(roles, tool names, error flags), so their text never leaves this module.
"""

import re
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from inspect_ai.log import read_eval_log_sample
from inspect_ai.model import ChatMessage, ChatMessageAssistant, ChatMessageTool, ContentReasoning
from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema, models_json_schema

from assay.errors import AssayError, EvidenceError
from assay.evidence import EvidenceRecord, read_evidence
from assay.outcomes import Gate, Verdict
from assay.report import PairRow, Report, load_report

HOST = "127.0.0.1"
STATIC = Path(__file__).parent / "dashboard_static"
TOOL_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")


class ToolCallView(BaseModel):
    function: str
    arguments: dict[str, object] | None


class Turn(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    text: str | None
    reasoning: str | None
    tool_calls: list[ToolCallView]
    function: str | None
    tool_error: bool | None


class ArmDetail(BaseModel):
    evidence: EvidenceRecord
    transcript: list[Turn] | None


class PairDetail(BaseModel):
    pair: PairRow
    benign: ArmDetail
    harmful: ArmDetail


class _ModelTitlesOnly(GenerateJsonSchema):
    # json2ts makes a type alias for every titled field; model names are enough.
    def field_title_should_be_set(self, schema) -> bool:
        return False


def api_schema() -> dict:
    """JSON Schema for every response body, used to generate the frontend types."""
    _, schema = models_json_schema(
        [(Report, "serialization"), (PairDetail, "serialization")],
        title="ASSAY dashboard API",
        schema_generator=_ModelTitlesOnly,
    )
    return schema


def create_app(results: Path) -> FastAPI:
    # Built from the evidence, not report.json, which can be older than it.
    report = load_report(results)
    pairs = {(p.configuration, p.repeat, p.key): p for p in report.pairs}
    evidence = {
        (r.configuration, r.repeat, r.key, r.arm): r
        for r in read_evidence(results / "evidence.jsonl")
    }
    app = FastAPI(title="ASSAY dashboard", openapi_url=None)

    @app.exception_handler(AssayError)
    def assay_error(request: Request, error: AssayError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @app.get("/api/report")
    def get_report() -> Report:
        return report

    @app.get("/api/pairs")
    def get_pairs(
        configuration: str | None = None,
        category: str | None = None,
        verdict: Verdict | None = None,
        gate: Gate = report.headline_gate,
    ) -> list[PairRow]:
        return [
            pair
            for pair in report.pairs
            if configuration in (None, pair.configuration)
            and category in (None, pair.category)
            and verdict in (None, pair.gates[gate].verdict)
        ]

    @app.get("/api/pair")
    def get_pair(configuration: str, repeat: int, key: str) -> PairDetail:
        row = pairs.get((configuration, repeat, key))
        if row is None:
            raise HTTPException(status_code=404, detail="No such pair in this report.")
        arms = {arm: evidence[(configuration, repeat, key, arm)] for arm in ("benign", "harmful")}
        return PairDetail(
            pair=row,
            **{
                arm: ArmDetail(evidence=record, transcript=_transcript(results, record))
                for arm, record in arms.items()
            },
        )

    if STATIC.is_dir():
        app.mount("/", StaticFiles(directory=STATIC, html=True))
    return app


def serve(app: FastAPI, port: int) -> None:
    uvicorn.run(app, host=HOST, port=port, log_level="warning")


def _transcript(results: Path, record: EvidenceRecord) -> list[Turn] | None:
    """The sample's messages, or None when its log is not in the results directory."""
    log_path, _, uuid = record.log.partition("#")
    path = (results / log_path).resolve()
    if not path.is_relative_to(results.resolve()):
        raise EvidenceError(f"The log for {record.key} points outside the results directory.")
    if not path.is_file():
        return None
    sample = read_eval_log_sample(path, uuid=uuid, resolve_attachments=True)
    return [_turn(message, harmful=record.arm == "harmful") for message in sample.messages]


def _turn(message: ChatMessage, harmful: bool) -> Turn:
    calls = (message.tool_calls or []) if isinstance(message, ChatMessageAssistant) else []
    is_tool = isinstance(message, ChatMessageTool)
    if harmful:
        return Turn(
            role=message.role,
            text=None,
            reasoning=None,
            tool_calls=[ToolCallView(function=_name(c.function), arguments=None) for c in calls],
            function=_name(message.function or "") if is_tool else None,
            tool_error=message.error is not None if is_tool else None,
        )
    reasoning = (
        [c.reasoning for c in message.content if isinstance(c, ContentReasoning)]
        if isinstance(message.content, list)
        else []
    )
    return Turn(
        role=message.role,
        text=message.text,
        reasoning="\n\n".join(reasoning) or None,
        tool_calls=[ToolCallView(function=c.function, arguments=c.arguments) for c in calls],
        function=message.function if is_tool else None,
        tool_error=message.error is not None if is_tool else None,
    )


def _name(function: str) -> str:
    # Tool names come from the model, so a made-up one could carry text.
    return function if TOOL_NAME.fullmatch(function) else "(invalid tool name)"
