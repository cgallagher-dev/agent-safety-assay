import json

import httpx
import pytest

from assay.errors import RunError
from assay.preflight import check_ollama, check_server, server_root
from assay.profiles import load_profile

PROFILE = load_profile("qwen3.5-4b")
NAME = "qwen3.5:4b-q4_K_M"
DIGEST = "sha256:2a6f1e"


def server(
    capabilities=("completion", "tools", "thinking"), context=32768, pulled=True, listed=NAME
):
    """A fake Ollama server; records the requests it gets."""
    seen = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        body = json.loads(request.content) if request.content else {}
        match request.url.path:
            case "/api/version":
                return httpx.Response(200, json={"version": "0.40.15"})
            case "/api/show" if pulled:
                return httpx.Response(
                    200,
                    json={
                        "capabilities": list(capabilities),
                        "parameters": "temperature 1\ntop_k 20\ntop_p 0.95\npresence_penalty 1.5",
                    },
                )
            case "/api/show":
                return httpx.Response(404, json={"error": f"model '{body['model']}' not found"})
            case "/api/tags":
                return httpx.Response(200, json={"models": [{"name": listed, "digest": DIGEST}]})
            case "/api/generate":
                return httpx.Response(200, json={"done": True})
            case "/api/ps":
                models = [{"name": listed, "context_length": context}]
                return httpx.Response(200, json={"models": models})
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(answer), base_url="http://ollama"), seen


def test_a_ready_server_is_recorded():
    client, _ = server()

    check = check_ollama(PROFILE, client)

    assert check.version == "0.40.15"
    assert check.model == NAME
    assert check.digest == DIGEST
    assert check.sampling == {
        "temperature": "1",
        "top_k": "20",
        "top_p": "0.95",
        "presence_penalty": "1.5",
    }
    assert check.context == 32768


def test_a_model_without_tool_support_stops_before_loading_it():
    client, seen = server(capabilities=("completion",))

    with pytest.raises(RunError, match=f"{NAME} doesn't advertise tool support"):
        check_ollama(PROFILE, client)
    assert "/api/generate" not in seen


def test_a_served_context_below_the_profile_minimum_stops_the_run():
    client, _ = server(context=4096)

    with pytest.raises(RunError, match="with 4096 tokens of context, but qwen3.5-4b needs 32768"):
        check_ollama(PROFILE, client)


def test_a_model_that_is_not_pulled_says_how_to_get_it():
    client, _ = server(pulled=False)

    with pytest.raises(RunError, match=f"ollama pull {NAME}"):
        check_ollama(PROFILE, client)


def test_no_server_says_to_start_one():
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.Client(transport=httpx.MockTransport(refuse), base_url="http://ollama")

    with pytest.raises(RunError, match="Start it with ollama serve"):
        check_ollama(PROFILE, client)


def test_a_model_named_without_a_tag_matches_ollamas_latest():
    client, _ = server(listed="qwen3.5:latest")
    untagged = PROFILE.model_copy(update={"model": "ollama/qwen3.5"})

    check = check_ollama(untagged, client)

    assert check.digest == DIGEST
    assert check.context == 32768


@pytest.mark.parametrize(
    ("base_url", "env", "root"),
    [
        (None, None, "http://localhost:11434"),
        (None, "http://10.0.0.5:11434/v1", "http://10.0.0.5:11434"),
        ("http://box:11434/v1/", "http://10.0.0.5:11434/v1", "http://box:11434"),
    ],
)
def test_the_server_is_looked_for_where_inspect_sends_requests(monkeypatch, base_url, env, root):
    if env:
        monkeypatch.setenv("OLLAMA_BASE_URL", env)
    else:
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    assert server_root(PROFILE.model_copy(update={"base_url": base_url})) == root


def test_a_model_not_on_ollama_has_no_server_to_check():
    hosted = PROFILE.model_copy(update={"model": "openai/gpt-5"})

    assert check_server(hosted) is None
