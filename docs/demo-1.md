# Demo 1

How I run the Demo 1 demonstration, with the exact commands. There are two
paths. The fixture needs no model and runs anywhere in a minute. The real
path uses a small saved run of Qwen3.5 4B, judged by a local model.

Everything here works on `main` before `assay run` exists (Week 10), so the
real run is generated with Inspect directly.

## Before you start

```text
uv sync --group dev
cd frontend && npm ci && npm run build && cd ..
```

`assay pdf` needs the Pango library (most Linux desktops have it; on macOS,
`brew install pango`). If port 8000 is taken, add `--port 8001` to
`assay dashboard`.

## Path 1: the fixture (no model)

The fixture in `src/assay/demo` uses invented behaviours and tool names, with
no AgentHarm text.

```text
assay report src/assay/demo --out results/fixture
assay pdf results/fixture
assay dashboard src/assay/demo
```

Open http://127.0.0.1:8000. `assay report` refuses to write into the
installed package, which is why it takes `--out`.

## Path 2: a small real run

Ten matched pairs from AgentHarm's public test split, run with Qwen3.5 4B
with reasoning on, so no reasoning switch is needed. The run is generated
with scoring off, because AgentHarm's default graders call hosted models;
`assay judge` does the grading and refusal judging locally instead.

### 1. Generate (about 17 minutes on an Apple M1 Pro)

Run both arms with the same settings as the `qwen3.5-4b` profile, one log
folder per configuration, arm and repeat:

```text
PAIRS=9-1,17-1,24-1,28-1,36-1,38-1,46-1,49-1,58-1,61-1
for TASK in agentharm agentharm_benign; do
  ARM=$([ "$TASK" = agentharm ] && echo harmful || echo benign)
  inspect eval inspect_evals/$TASK -T split=test_public \
    --model ollama/qwen3.5:4b-q4_K_M --sample-id $PAIRS --no-score \
    --temperature 1.0 --top-p 0.95 --presence-penalty 1.5 --seed 1 \
    --max-connections 1 --message-limit 20 \
    --log-dir results/demo-1/logs/qwen3.5-4b-on/$ARM/repeat-1
done
```

None of these pairs need the run-time tool fixes that only the ASSAY runner
applies. The grading patches apply inside `assay judge`, so they cover this
run too.

### 2. Judge (about 15 minutes on an RTX 3060 Ti)

```text
ollama pull gemma4:12b-it-qat
assay judge results/demo-1 --judge gemma4-12b
```

This scores every sample with AgentHarm's graders and the refusal judge and
writes `evidence.jsonl`. If the folder has no `run_config.json`, `assay
judge` writes a minimal one from the log headers and warns that it lists no
exclusions. A judge error stops the pass; run the command again and it
carries on from the last saved sample.

### 3. Report, PDF and dashboard (no model needed)

```text
assay report results/demo-1
assay pdf results/demo-1
assay dashboard results/demo-1
```

These only read `evidence.jsonl` and the logs, so they can run on another
machine: copy the scored folder over by USB or `scp`, never a cloud sync,
because the logs hold the full transcripts.

## What to show

1. The judging run, sped up: the progress bar, then `assay report`. Only
   counts appear on screen.
2. The PDF: the metrics on every gate with numerators and denominators, the
   plot, and the appendix that lists the pairs behind each count.
3. The dashboard: the overview, then switch the capability gate to Semantic
   (benign passes drop, which is why the judge-graded reading isn't the
   headline), then one pair's detail. The benign transcript shows in full;
   the harmful side shows only roles and tool names.

## Privacy

- `results/` is ignored by git. Logs and evidence never get committed, and CI
  fails if one does.
- The dashboard never sends harmful-arm text to the browser; a test checks
  every endpoint.
- In screenshots and recordings, show only the CLI output, the PDF and the
  dashboard.
