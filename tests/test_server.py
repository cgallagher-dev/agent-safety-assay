import logging
import socket
from pathlib import Path

import pytest
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
from assay import server
from assay.cli import main
from assay.server import create_app
from helpers import record_fields, write_results

DEMO = Path(assay.__file__).parent / "demo"
HARMFUL = "HARMFUL-SENTINEL"
BENIGN = "BENIGN-MARKER"
PAIR = {"configuration": "demo-small/off", "repeat": 1, "key": "test_public/2-1"}


def local(app):
    return TestClient(app, base_url="http://127.0.0.1:8000")


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
    client = local(app)
    params = {"/api/report": {}, "/api/pair": PAIR}

    responses = [client.get(url, params=query) for url, query in params.items()]

    assert {r.path for r in app.routes if r.path.startswith("/api")} == set(params)
    assert [r.status_code for r in responses] == [200, 200]
    body = "".join(r.text for r in responses)
    assert HARMFUL not in body
    assert BENIGN in body


def test_a_log_path_outside_the_results_directory_is_rejected(tmp_path):
    results = tmp_path / "results"
    write_log(tmp_path / "outside.eval", "x", BENIGN)
    client = local(create_app(results_with_logs(results, benign_log="../outside.eval#x")))

    response = client.get("/api/pair", params=PAIR)

    assert response.status_code == 400
    assert BENIGN not in response.text


@pytest.mark.parametrize(
    "benign_log",
    [
        pytest.param("logs/benign.eval#missing", id="no such sample"),
        pytest.param("logs/broken.eval#b", id="corrupt log"),
    ],
)
def test_an_unreadable_log_is_reported_not_crashed(tmp_path, benign_log):
    results = results_with_logs(tmp_path, benign_log=benign_log)
    (results / "logs/broken.eval").write_bytes(b"not a zip file")
    client = local(create_app(results))

    response = client.get("/api/pair", params=PAIR)

    assert response.status_code == 400
    assert "Could not read the benign log for test_public/2-1" in response.json()["detail"]


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:5173"])
def test_local_hosts_are_served(host):
    response = local(create_app(DEMO)).get("/api/report", headers={"host": host})

    assert response.status_code == 200


def test_another_host_name_is_refused():
    # A page on another site that rebinds its name to 127.0.0.1 still sends its own Host.
    response = local(create_app(DEMO)).get("/api/report", headers={"host": "attacker.example"})

    assert response.status_code == 400


def test_an_unbuilt_dashboard_says_how_to_build_it(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(server, "STATIC", tmp_path / "missing")
    monkeypatch.setattr(logging.getLogger("assay"), "propagate", True)

    create_app(DEMO)

    assert "npm run build" in caplog.text


def test_the_api_only_reads():
    app = create_app(DEMO)

    assert {m for route in app.routes for m in getattr(route, "methods", ())} <= {"GET", "HEAD"}


def test_a_stale_report_json_is_not_served(tmp_path):
    results = results_with_logs(tmp_path)
    (results / "report.json").write_text('{"stale": true}')
    client = local(create_app(results))

    report = client.get("/api/report").json()

    assert [p["key"] for p in report["pairs"]] == [PAIR["key"]]


def test_an_unknown_pair_is_not_found(tmp_path):
    client = local(create_app(results_with_logs(tmp_path)))

    response = client.get("/api/pair", params={**PAIR, "key": "test_public/9-9"})

    assert response.status_code == 404


def test_a_transcript_is_read_once(tmp_path, monkeypatch):
    reads = []
    real = server.read_eval_log_sample

    def counted(*args, **kwargs):
        reads.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(server, "read_eval_log_sample", counted)
    client = local(create_app(results_with_logs(tmp_path)))

    first, second = (client.get("/api/pair", params=PAIR).json() for _ in range(2))

    assert first == second
    assert len(reads) == 2


def test_demo_pairs_show_structure_without_logs():
    client = local(create_app(DEMO))

    detail = client.get("/api/pair", params=PAIR).json()

    assert detail["harmful"]["transcript"] is None
    assert detail["harmful"]["evidence"]["declared_tools"]


def test_a_busy_port_is_reported_before_the_url(capsys):
    with socket.create_server((server.HOST, 0)) as taken:
        port = taken.getsockname()[1]

        assert main(["dashboard", str(DEMO), "--port", str(port)]) == 3

    err = capsys.readouterr().err
    assert f"{server.HOST}:{port}" in err and "--port" in err
    assert "http://" not in err
