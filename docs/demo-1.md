# Demo 1

Two paths through the whole tool, before `assay run` exists: the synthetic
fixture, which needs no model, and a small real run made with Inspect
directly. Commands run from the repository root.

## Before the demo

- `uv sync --extra pdf`. The PDF also needs Pango (`brew install pango` on
  macOS).
- Build the dashboard once: `cd frontend && npm ci && npm run build`.
- Ollama running, with `qwen3.5:4b-q4_K_M` (the agent) and
  `gemma4:12b-it-qat` (the judge) pulled.
- Run path 2 before the session. Generation and judging take too long to
  show live, so the demo starts from the judged results.

## Path 1: the fixture

The fixture is invented: made-up behaviours and tool names, no AgentHarm
text.

```sh
rm -rf results/demo-fixture && cp -r src/assay/demo results/demo-fixture
uv run assay report results/demo-fixture
uv run assay pdf results/demo-fixture
uv run assay dashboard results/demo-fixture
```

Then open <http://127.0.0.1:8000>, or add `--port` if something else is
already using 8000. Things to show:

- Each metric with its fraction, and ccASR shown as undefined, never zero,
  when no benign task passed.
- The gate selector moving every number to the attempted or semantic gate.
- A verdict count, the pair list behind it, and one pair: both arms' tool
  calls side by side, and the harmful trace as structure only.
- `report.pdf`, whose appendix lists the pairs behind every count.

## Path 2: a small real run

Ten pairs, the first prompt variant of ten base behaviours across seven
categories, run with Qwen3.5 4B with thinking on. No AgentHarm patch,
tool-description difference or order asymmetry touches these pairs, because
patches only apply inside the ASSAY runner.

1. Run both arms with Inspect. Scoring is off because AgentHarm's default
   judges are hosted models; ASSAY's scoring pass replaces them. The two
   judge options only stop the task building OpenAI clients it never uses.

   ```sh
   IDS=46-1,38-1,61-1,49-1,9-1,58-1,28-1,17-1,24-1,36-1
   for arm in benign harmful; do
     task=agentharm; [ $arm = benign ] && task=agentharm_benign
     uv run inspect eval inspect_evals/$task -T split=test_public \
       -T refusal_judge=ollama/gemma4:12b-it-qat \
       -T semantic_judge=ollama/gemma4:12b-it-qat \
       --sample-id $IDS --model ollama/qwen3.5:4b-q4_K_M \
       --temperature 1.0 --top-p 0.95 --presence-penalty 1.5 --seed 1 \
       --max-connections 1 --no-score \
       --log-dir results/demo-1/logs/qwen3.5-4b-on/$arm/repeat-1
   done
   ```

   The sampling settings are the `qwen3.5-4b` profile's. Logs go under
   `logs/<profile>-<mode>/<arm>/repeat-<n>/`, the layout `assay judge` reads.

2. Write `run_config.json`, which `assay run` will write itself:

   ```sh
   cat > results/demo-1/run_config.json <<JSON
   {
     "run_id": "$(uv run python -c 'from assay.logs import new_run_id; print(new_run_id())')",
     "configurations": {"qwen3.5-4b/on": {"profile": "qwen3.5-4b", "mode": "on"}},
     "versions": {"inspect_ai": "0.3.277", "inspect_evals": "0.23.0", "agentharm": "8-B"},
     "judge": "ollama/gemma4:12b-it-qat",
     "sampling": {"temperature": 1.0, "top_p": 0.95, "presence_penalty": 1.5},
     "repeats": [{"repeat": 1, "seed": 1}],
     "message_limit": 20,
     "splits": ["test_public"],
     "exclusions": []
   }
   JSON
   ```

3. Score the logs and write the evidence, then report:

   ```sh
   uv run assay judge results/demo-1 --judge gemma4-12b
   uv run assay report results/demo-1
   uv run assay pdf results/demo-1
   uv run assay dashboard results/demo-1
   ```

   On a pair page the benign transcript is shown in full; the harmful trace
   still shows only roles, tool names and tool errors.

## Timings

Path 2 on an Apple M1 Pro with 32 GB of memory and Ollama 0.31.1, with both
models already pulled:

| Step | Samples | Time |
|---|---|---|
| Benign arm | 10 | 9 min 55 s |
| Harmful arm | 10 | 6 min 38 s |
| `assay judge` | 20 | about 14 min |

The generation times come from the start and end stamps in the logs. The
scoring time is the sum of two attempts. The first stopped partway through
the harmful arm on a grader that sent the judge an empty message, which the
judge wrapper now fails without asking. The second skipped the ten benign
samples already scored and took 5 min 56 s. A clean pass should take a little
under the total, so allow about half an hour for path 2.
