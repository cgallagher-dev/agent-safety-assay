from pathlib import Path

from fastapi.testclient import TestClient
from inspect_ai.log import EvalConfig, EvalDataset, EvalLog, EvalSample, EvalSpec, write_eval_log
from inspect_ai.model import (
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageTool,
    ChatMessageUser,
    ContentReasoning,
    ContentText,
)
from inspect_ai.tool import ToolCall, ToolCallError

import assay
from assay.server import create_app
from helpers import record_fields, write_results

DEMO = Path(assay.__file__).parent / "demo"
HARMFUL = "HARMFUL-SENTINEL"
BENIGN = "BENIGN-MARKER"
PAIR = {"configuration": "demo-small/off", "repeat": 1, "key": "test_public/2-1"}


def write_log(path, uuid, marker):
    """A one-sample .eval log with the marker in every text field."""
    made_up = f"{marker}_tool"
    messages = [
        ChatMessageSystem(content=f"{marker} system"),
        ChatMessageUser(content=f"{marker} prompt"),
        ChatMessageAssistant(
            content=[
                ContentReasoning(reasoning=f"{marker} reasoning"),
                ContentText(text=f"{marker} reply"),
            ],
            tool_calls=[
                ToolCall(id="1", function="demo_search", arguments={"query": f"{marker} argument"}),
                ToolCall(id="2", function=made_up, arguments={}),
            ],
        ),
        ChatMessageTool(content=f"{marker} result", tool_call_id="1", function="demo_search"),
        ChatMessageTool(
            content="",
            tool_call_id="2",
            function=made_up,
            error=ToolCallError("unknown", f"{marker} error"),
        ),
    ]
    sample = EvalSample(
        id="2-1",
        epoch=1,
        uuid=uuid,
        input=f"{marker} input",
        target=f"{marker} target",
        messages=messages,
        metadata={"note": f"{marker} metadata"},
    )
    spec = EvalSpec(
        created="2026-11-12T21:30:00+00:00",
        task="demo",
        dataset=EvalDataset(),
        model="demo/model",
        config=EvalConfig(),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    write_eval_log(EvalLog(eval=spec, samples=[sample]), path)


def results_with_logs(path, benign_log="logs/benign.eval#b"):
    write_log(path / "logs/benign.eval", "b", BENIGN)
    write_log(path / "logs/harmful.eval", "h", HARMFUL)
    write_results(
        path,
        [
            record_fields(arm="benign", log=benign_log),
            record_fields(arm="harmful", log="logs/harmful.eval#h"),
        ],
    )
    return path


def test_harmful_text_never_reaches_a_response(tmp_path):
    app = create_app(results_with_logs(tmp_path))
    client = TestClient(app)
    params = {"/api/report": {}, "/api/pairs": {}, "/api/pair": PAIR}

    responses = [client.get(url, params=query) for url, query in params.items()]

    assert {r.path for r in app.routes if r.path.startswith("/api")} == set(params)
    assert [r.status_code for r in responses] == [200, 200, 200]
    body = "".join(r.text for r in responses)
    assert HARMFUL not in body
    assert BENIGN in body


def test_a_log_path_outside_the_results_directory_is_rejected(tmp_path):
    results = tmp_path / "results"
    write_log(tmp_path / "outside.eval", "x", BENIGN)
    client = TestClient(create_app(results_with_logs(results, benign_log="../outside.eval#x")))

    response = client.get("/api/pair", params=PAIR)

    assert response.status_code == 400
    assert BENIGN not in response.text


def test_the_api_only_reads():
    app = create_app(DEMO)

    assert {m for route in app.routes for m in getattr(route, "methods", ())} <= {"GET", "HEAD"}


def test_demo_pairs_show_structure_without_logs():
    client = TestClient(create_app(DEMO))

    detail = client.get("/api/pair", params=PAIR).json()

    assert detail["harmful"]["transcript"] is None
    assert detail["harmful"]["evidence"]["declared_tools"]
