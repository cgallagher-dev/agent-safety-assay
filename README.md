# ASSAY

ASSAY is a command-line harness for LLM safety evaluation. I'm building it to look at capability-conditioned safety evaluation for small LLM agents.

When an agent does not complete a harmful task, it may have refused, made an
execution error, or simply lacked the capability. Attack success rate (ASR)
counts all of these in the same way. ASSAY scores every harmful
[AgentHarm](https://arxiv.org/abs/2410.09024) task beside its matched benign
task, which needs the same tool calls, so that safety is reported on the tasks
a model has shown it can actually do.

It reports these metrics side by side, always with numerators and denominators:

| Metric | Definition |
| --- | --- |
| ASR | Harmful successes / all pairs |
| Benign pass rate | Benign passes / all pairs |
| ccASR | Harmful successes / pairs whose benign task passed |
| ccRR | Refusals / (refusals + harmful successes), on pairs whose benign task passed |
| CGR | Harmful non-successes with a failed benign twin / all harmful non-successes |

ASSAY is built on [Inspect](https://inspect.aisi.org.uk) and works with any model
Inspect can reach. Models are described by profiles, not code.

**Status:** early development (October 2026). This is my final-year project at
TUS Athlone. The commands below are what I'm aiming for, not what exists yet.
See [docs/spec.md](docs/spec.md) and the [Jira board](https://cgallagherdev.atlassian.net/jira/software/projects/SCRUM/boards/1).

## Prior art

ASSAY doesn't invent paired benign tasks or conditional reporting. It builds
on this work and was shaped by it:

- **AgentHarm** (Andriushchenko et al., 2024,
  [arXiv:2410.09024](https://arxiv.org/abs/2410.09024)). The benchmark ASSAY
  runs: harmful agent tasks with benign rewrites, synthetic tools, grading
  rubrics and a refusal judge. It already reports harm on non-refused
  responses. ASSAY instead selects each harmful task by whether its own
  benign twin passed.
- **AgentDojo** (Debenedetti et al., 2024,
  [arXiv:2406.13352](https://arxiv.org/abs/2406.13352)). Reports benign
  utility beside attack success, and notes that low-utility agents can look
  secure just by failing the task.
- **Hofer et al., 2026** ([arXiv:2606.10525](https://arxiv.org/abs/2606.10525)).
  Suggests a small model's lower utility partly explains why it looks harder
  to attack.
- **McAllister et al., 2026** ([arXiv:2606.12709](https://arxiv.org/abs/2606.12709)).
  Paired control and malicious conditions on the same coding problems,
  including Qwen3.5-27B, and weak models failing both.
- **HarmBench** (Mazeika et al., 2024) and **PAIR** (Chao et al., 2023,
  [arXiv:2310.08419](https://arxiv.org/abs/2310.08419)), which made attack
  success rate the standard headline metric.
- **Inspect** and **Inspect Evals**, which run the tasks and supply
  AgentHarm's graders.

What ASSAY adds is the row-level benign gate, a parity check on the pairs,
refusal and execution kept as separate facts, and readings that show how
much the result depends on those choices. Full credits are in
[NOTICE](NOTICE) and [CITATION.cff](CITATION.cff).

## Planned usage

```text
pip install safety-assay                      # once released

assay pairs                                   # validate matched pairs, list exclusions
assay run --profile qwen3.5-4b --out results/4b
assay run --model ollama/llama3.2 --out results/llama
assay judge results/4b --judge gemma4-12b     # graders and refusal judge over saved logs
assay report results/4b                       # metrics, text / JSON / CSV
assay compare results/4b results/27b          # clustered paired comparison
assay narrate results/4b                      # optional model-written summary
assay pdf results/4b                          # needs pip install 'safety-assay[pdf]'
assay dashboard results/                      # local, read-only dashboard
```

## Development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```text
uv sync                      # create .venv from uv.lock
uv run pytest                # tests
uv run ruff check            # lint
```

## Responsible use

AgentHarm tasks are harmful by design and run against synthetic tools only.
ASSAY never commits benchmark data, evaluation logs or model outputs, and the
dashboard never sends harmful-task text to the browser. See
[SECURITY.md](SECURITY.md).

## Licence

[PolyForm Noncommercial 1.0.0](LICENSE). Free to use, study and change for
research, teaching and personal projects, but not for anything commercial.
If you share it or build on it, keep the licence and credit the original.

ASSAY is built on Inspect, Inspect Evals and AgentHarm, which keep their own
licences. AgentHarm data is downloaded at run time and is only to be used to
make AI systems safer. Credits are in [NOTICE](NOTICE).
