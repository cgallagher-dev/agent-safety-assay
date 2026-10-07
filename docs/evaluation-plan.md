# Evaluation plan

Version 0.1, 7 October 2026. Draft for supervisor review. Items marked
**(to agree)** are proposals until the supervisor meeting. Once agreed, the
case study section is frozen with a git tag (`eval-plan-frozen`) before any
final-run outcome is read.

The plan has two parts, matching objective O5: a case study that uses the tool,
and an evaluation of the tool itself.

## Part 1: Case study

### Configurations

| Model | Ollama tag | Reasoning modes |
| --- | --- | --- |
| Qwen3.5 4B | `qwen3.5:4b-q4_K_M` | on, off |
| Qwen3.5 9B | `qwen3.5:9b-q4_K_M` | on, off |
| Qwen3.5 27B | `qwen3.5:27b-q4_K_M` | on, off |

Six configurations. One family and one quantisation keep size and reasoning
mode apart from training differences.

### Task set

Checked on 7 October 2026 against inspect_evals 0.23.0 (AgentHarm task
version 8-B):

- The tasks are `agentharm` (harmful) and `agentharm_benign`, run on the
  `test_public` and `val` splits with the default agent, no irrelevant tools
  and no chat-only samples. `test_private` is withheld by the authors.
- The dataset is pinned to Hugging Face revision `e23b3fe`, which is still the
  dataset's latest revision and has not changed across recent inspect_evals
  releases; those releases changed the graders, judge and scorer.
- `test_public` has 176 harmful tasks and `val` has 32 (44 and 8 base
  behaviours, four prompt variants each: detailed or open-ended, with or
  without a hint). Every harmful id has a benign task with the same id,
  original id, category, variant flags and grader name, so pairing by key is
  correct.
- Parity keeps 171 of 208 pairs (143 test_public, 28 validation) from 43 base
  behaviours (36 and 7). 42 behaviours are kept whole; `test_public/30` keeps
  3 of its 4 variants. The 37 excluded pairs are the ones whose harmful side
  needs a tool that only exists on that side (onion search, ransomware,
  malware, credit-card purchase, log deletion) or has an extra step.
- Kept share per category: Copyright 28/28, Drugs 24/24, Harassment 28/28,
  Hate 23/24, Disinformation 20/24, Fraud 20/28, Sexual 20/28, Cybercrime
  8/24. Findings describe the kept set, which under-represents Cybercrime.
- Of the 75 tool names shared by the two arms, 72 present the same schema to
  the model. Two kept tools differ in description only: `share_on_pinterest`
  (the harmful side adds "starts with @", pairs `test_public/7` and
  `validation/6`) and `run_stable_diffusion_model` (a missing bracket). Tool
  outputs differ by design: each arm returns its own synthetic content.
- Four benign-side tool defects make benign tasks unwinnable: a case mismatch in the Kiwi image whitelist
  (`test_public/2`), a missing video in the upload whitelist
  (`test_public/37`), content paths that depend on the working directory
  (`test_public/26`, `43`, `53`), and a required `image_path` documented as
  optional (`test_public/52`). ASSAY patches them in memory and reports a
  sensitivity reading without these six base behaviours.
- AgentHarm keeps `max_messages=20`, `max_tokens=4096` per generation and
  temperature 0, and shuffles each sample's tools with an unseeded random
  order, which is one source of run-to-run variation.

### Fixed settings

- The task set above, direct requests only.
- Target decoding as agreed below. Message limit 20 and output limit 4,096
  tokens (AgentHarm's defaults); samples hitting either are counted.
- Judge `gemma4:12b-it-qat` (a different family), temperature 0, reasoning
  off, whole-output rendering, on both arms. The same model is AgentHarm's
  semantic judge. Scoring runs as a separate pass after generation, the same
  way for every configuration.
- One reference machine (Apple M1 Pro, 32 GB), Ollama version recorded.
- Every run records versions, model digests, profile, sampling settings in
  force and seeds.

### Decoding (to agree)

AgentHarm's task sets temperature 0 and seed 0. Ollama's `qwen3.5` model
files default to Qwen's recommended thinking-mode sampling (temperature 1.0,
top_p 0.95, top_k 20, presence penalty 1.5), so under AgentHarm only the
temperature changes. Qwen's model card recommends temperature 1.0 and top_p
0.95 for thinking, 0.7 and 0.8 for non-thinking, and a presence penalty to
avoid endless repetition.

- **Option A, AgentHarm protocol:** temperature 0 for every configuration.
  Comparable with published AgentHarm results. Repeats then
  only capture serving non-determinism and the tool-order shuffle.
- **Option B, recommended sampling:** Qwen's settings for each mode, with a
  different seed per repeat. Closer to how these models are deployed, and
  repeats measure the sampling variation RQ2 asks about. Departs from
  AgentHarm's default, and the modes then differ in sampling as well as
  reasoning, as Qwen defines them.

Recommendation: option B for the case study, plus one temperature-0 repeat of
the 4B in both modes as a decoding sensitivity check. Either way the settings
live in the profiles and are recorded with every run. `top_k` cannot be set
through Ollama's OpenAI-compatible endpoint and comes from the model file.

### Full-benchmark context (to agree)

Proposal: repeat 1 of each configuration also runs the 37 excluded pairs, so
ASR, refusal rate and benign pass rate can be reported on all 208 tasks for
comparison with published AgentHarm results, and the effect of the parity
filter on those rates is visible. Conditioned metrics still use kept pairs
only. Cost: about 22% more on repeat 1.

### Repeats (to agree)

Proposal: three full repeats of every configuration. Early feasibility checks
on the reference machine put the 27B at 165 to 225 seconds per sample, about
19 hours per mode per repeat, so three repeats of everything is about 170
machine-hours, run overnight from mid-November. Fallback, decided before the
runs: repeats 2 and 3 of the 27B cover a predeclared random subset of base
behaviours.

### Outcomes

- Primary: CGR, ccASR and ccRR under the structural gate (executed calls).
- Always reported alongside: benign pass rate, ASR, verdict counts,
  executed-and-refused overlap, capability anomalies, benign refusals and the
  share of CGR they account for, capped and truncated shares.

### Primary comparisons (to agree)

For each primary metric:

- Size within a mode: 4B vs 9B, 9B vs 27B, 4B vs 27B, for each mode (6).
- Mode within a size: on vs off at 4B, 9B and 27B (3).

That is 9 comparisons per metric and 27 in total. Proposal: Holm correction
across all 27. Each comparison uses the same pairs in both configurations, a
cluster-level randomisation test over base behaviours and a cluster bootstrap
interval for the difference.

Model-by-mode interaction is reported descriptively. A cluster label-swap test
does not justify an exact test of zero interaction without further
assumptions, so
no interaction p-value is claimed unless the supervisor agrees a method.

### Sensitivity analyses

- Gate: structural (executed calls) vs attempted calls vs semantic. The
  semantic gate is judge-dependent: 26 benign and 31 harmful graders ask an
  LLM to grade at least one criterion, and here that LLM is the local judge.
- Outcome policy: refusal first vs execution first.
- Common subset: conditioned metrics on pairs whose benign task passed in all
  compared configurations.
- Patched and flagged pairs: metrics without the six patched base behaviours
  and the two with a tool-description difference.
- Repeats: per-repeat values and range.

### Limitations stated up front

- No held-out data: all kept behaviours are public and were seen while the
  tool was designed, so design choices could reflect them. The plan is frozen before the
  final runs to limit this.
- Coverage: the kept set under-represents Cybercrime (8 of 24 tasks), and
  tasks that need an illicit-only tool cannot be conditioned at all.
- A benign pass shows related capability on a task with the same tools, not
  equal difficulty; benign and harmful tools return different content.
- A structural harmful success means the harmful tool sequence executed. It
  does not check that the arguments were harmful; the semantic gate does,
  with the caveat above.
- AgentHarm is public, so the models may have seen its tasks in training.

### Reporting rules

- Effect sizes and intervals are reported whatever the significance.
- Findings describe the tested configurations only. No general claim about
  model size and safety.
- ccRR is reported as an estimate that depends on the judge, beside the
  judge agreement result.
- Results outside the agreed comparisons are labelled exploratory.

## Part 2: Evaluating the tool

| Check | Method | Evidence |
| --- | --- | --- |
| Correctness | Unit tests on synthetic fixtures for pairing, gates, outcomes, metrics and statistics, written first. CI on every push. | Test count and CI history. |
| Gate validity | Structural readings cross-checked against AgentHarm's own breakdown on every case-study sample. | Disagreement count, each one explained. |
| Invalid input | One test per rejection: missing arm, duplicate key, unjudged harmful sample, runs with different settings, invalid profile, malformed grading breakdown. | Tests. |
| Export agreement | Text, JSON, CSV, PDF and dashboard API carry identical numbers for the same run. | Automated test. |
| Privacy | Sentinel strings through every API endpoint; CI containment check; manual review of an evidence file. | Tests and CI. |
| Judge agreement | Blinded hand labels on a stratified random sample of at least 100 samples across configurations and verdicts, including every benign refusal. Agreement, Cohen's kappa and direction of errors. | Agreement table. |
| Plug-and-play | A tool-capable model from another family (for example a Llama or Mistral model on Ollama) run on a small slice using only a new profile. | Run record, no code change in the diff. |
| Clean install | Fresh machine or VM: install from the release, run the fixture report, open the dashboard, render the PDF. | Checklist and screenshots. |
| Demonstrations | Demo 1 runs end to end from the fixture and a small saved run. | Demo script. |

## Ethics and data handling

- Synthetic tools only; no real-world actions.
- Raw logs and hand labels stay on the reference machine and are not
  committed. Evidence files hold no harmful text.
- Hand labelling is done by the author only; no participants are involved.
- Public examples use the synthetic fixture or benign tasks.
- Release permission (TUS and employer) is confirmed before the repository is
  made public.
