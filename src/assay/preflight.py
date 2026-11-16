"""Checks an Ollama server before a run, so a misconfigured server fails in seconds."""

import httpx
from pydantic import BaseModel

from assay.errors import RunError
from assay.profiles import Profile


class ServerCheck(BaseModel):
    """What the server said about the model, recorded with the run."""

    version: str
    model: str
    digest: str
    # The model file's defaults, which fill in anything the profile doesn't send.
    sampling: dict[str, str]
    context: int


def check_ollama(profile: Profile, client: httpx.Client) -> ServerCheck:
    """Check the model can call tools and is served with enough context.

    client is rooted at the Ollama server (for example http://127.0.0.1:11434).
    """
    name = profile.model.removeprefix("ollama/")
    version = _call(client, "GET", "/api/version")["version"]
    show = _call(client, "POST", "/api/show", {"model": name}, name)
    # Two Ollama installs can share a port, and an older one drops tool support.
    if "tools" not in show.get("capabilities", []):
        raise RunError(
            f"Ollama {version} says {name} doesn't advertise tool support. Check that only "
            "one Ollama server is running and that it's recent, then run again."
        )
    digest = _listed(_call(client, "GET", "/api/tags"), name, "pulled")["digest"]
    sampling = dict(
        line.split(maxsplit=1) for line in show.get("parameters", "").splitlines() if line.strip()
    )
    # Loading the model is the only way to see the context it's really served with;
    # the OpenAI-style endpoint Inspect uses ignores num_ctx.
    _call(client, "POST", "/api/generate", {"model": name, "keep_alive": "10m"})
    context = _listed(_call(client, "GET", "/api/ps"), name, "loaded")["context_length"]
    if profile.min_context and context < profile.min_context:
        raise RunError(
            f"Ollama serves {name} with {context} tokens of context, but {profile.name} needs "
            f"{profile.min_context}. Set OLLAMA_CONTEXT_LENGTH to at least "
            f"{profile.min_context}, restart ollama serve and run again."
        )
    return ServerCheck(
        version=version, model=name, digest=digest, sampling=sampling, context=context
    )


def _listed(listing: dict, name: str, state: str) -> dict:
    # Ollama lists a model pulled without a tag as name:latest.
    names = {name, f"{name}:latest"}
    for model in listing["models"]:
        if model["name"] in names:
            return model
    raise RunError(f"Ollama doesn't list {name} as {state}. Check ollama ps and ollama list.")


def _call(
    client: httpx.Client, method: str, path: str, body: dict | None = None, model: str = ""
) -> dict:
    try:
        response = client.request(method, path, json=body)
    except httpx.ConnectError:
        raise RunError(
            f"No Ollama server at {client.base_url}. Start it with ollama serve and run again."
        ) from None
    if response.status_code == 404 and model:
        raise RunError(f"Ollama doesn't have {model}. Get it with ollama pull {model}.")
    response.raise_for_status()
    return response.json()
