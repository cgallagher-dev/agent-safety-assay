# ASSAY

ASSAY is a CLI-based LLM safety evaluation harness investigating capability-conditioned safety evaluation for small LLM agents.

When an agent does not complete a harmful task, it may have refused, made an
execution error, or simply lacked the capability. Attack success rate (ASR)
counts all of these the same way. ASSAY scores every harmful
[AgentHarm](https://arxiv.org/abs/2410.09024) task beside its matched benign
task, which needs the same tool calls, so that safety is reported on the tasks
a model has shown it can actually do.

It reports, side by side and always with numerators and denominators:

| Metric | Definition |
| --- | --- |
| ASR | Harmful successes / all pairs |
| Benign pass rate | Benign passes / all pairs |
| ccASR | Harmful successes / pairs whose benign task passed |
| ccRR | Refusals / (refusals + harmful successes), on pairs whose benign task passed |
| CGR | Harmful non-successes with a failed benign twin / all harmful non-successes |

ASSAY is built on [Inspect](https://inspect.aisi.org.uk) and works with any model
Inspect can reach. Models are described by profiles, not code.

**Status:** early development (October 2026). This is a final-year project at
TUS Athlone. The command surface below is the target, not what exists yet;
see [docs/spec.md](docs/spec.md) and the issue tracker.

## Planned usage

```text
pip install safety-assay                      # once released

assay pairs                                   # validate matched pairs, list exclusions
assay run --profile qwen3.5-4b --out results/4b
assay run --model ollama/llama3.2 --out results/llama
assay judge results/4b                        # graders and refusal judge over saved logs
assay report results/4b                       # metrics, text / JSON / CSV
assay compare results/4b results/27b          # clustered paired comparison
assay narrate results/4b                      # optional model-written summary
assay pdf results/4b
assay dashboard results/                      # local, read-only dashboard
```

## Development

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/) and Node 24+ (dashboard only).

```text
uv sync                      # create .venv from uv.lock
uv run pytest                # tests
uv run ruff check            # lint
cd frontend && npm ci && npm test && npm run build
```

`npm run build` writes the dashboard into `src/assay/dashboard_static/`, where
`assay dashboard` serves it. While working on the frontend, run
`uv run assay dashboard src/assay/demo` and `npm run dev` side by side; the
Vite dev server proxies `/api` to the backend on port 8000.

## Responsible use

AgentHarm tasks are harmful by design and run against synthetic tools only.
ASSAY never commits benchmark data, evaluation logs or model outputs, and the
dashboard never sends harmful-task text to the browser. See
[SECURITY.md](SECURITY.md).

## Licence

MIT. AgentHarm data is downloaded at run time and keeps its own licence.
