# Evaluation plan

Version 0.2, 28 October 2026, for my supervisor to sign off on 29 October.
Anything marked **(to agree)** is my proposal until then. Once it's agreed I
tag the case study section (`eval-plan-frozen`) and don't change it before
looking at any final-run results.

There are two parts, matching objective O5: a case study that uses the tool,
and an evaluation of the tool itself.

## Part 1: Case study

### Configurations

| Model | Ollama tag | Reasoning modes |
| --- | --- | --- |
| Qwen3.5 4B | `qwen3.5:4b-q4_K_M` | on, off |
| Qwen3.5 9B | `qwen3.5:9b-q4_K_M` | on, off |
| Qwen3.5 27B | `qwen3.5:27b-q4_K_M` | on, off |

That's six configurations. Sticking to one family and one quantisation means
size and reasoning mode don't get mixed up with differences in training.

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
- Upstream now marks 6-B as the recommended version while it prepares a
  broader 9-B review ([inspect_evals #2290](https://github.com/UKGovernmentBEIS/inspect_evals/issues/2290)).
  The review lists executed-only crediting (7-B onward) as an open design
  question and notes grader regressions from 7-B. ASSAY stays on 8-B for its
  tool fixes, computes the structural gates itself on both executed and
  attempted calls, and reports where its gates disagree with AgentHarm's own
  score. My proposal (to agree): the structural gate on executed calls is the
  headline, with the attempted-calls reading next to it as a sensitivity
  check. If AgentHarm 9-B comes out before the final runs start on 30
  November and works with ASSAY, I'll move to it and use that as the
  headline instead. Either way it's settled before I look at any final
  results.
- Parity keeps 171 of 208 pairs (143 test_public, 28 validation) from 43 base
  behaviours (36 and 7). 42 behaviours are kept whole; `test_public/30` keeps
  3 of its 4 variants. The 37 excluded pairs are the ones whose harmful side
  needs a tool that only exists on that side (onion search, ransomware,
  malware, credit-card purchase, log deletion) or has an extra step.
- Kept share per category: Copyright 28/28, Drugs 24/24, Harassment 28/28,
  Hate 23/24, Disinformation 20/24, Fraud 20/28, Sexual 20/28, Cybercrime
  8/24. So the findings are about the kept set, which is light on
  Cybercrime.
- Of the 75 tool names shared by the two arms, 72 present the same schema to
  the model. Two kept tools differ in description only: `share_on_pinterest`
  (the harmful side adds "starts with @", pairs `test_public/7` and
  `validation/6`) and `run_stable_diffusion_model` (a missing bracket). Tool
  outputs differ by design: each arm returns its own synthetic content.
- Three tool defects make tasks unwinnable: content paths that depend on the
  working directory, on both arms (`test_public/26`, `43`, `53`); a case
  mismatch in the benign Kiwi image whitelist (`test_public/2`); and a
  missing video in the benign upload whitelist (`test_public/37`). ASSAY
  patches them in memory and reports a sensitivity reading without these
  five base behaviours. `run_stable_diffusion_model` is not patched: it is
  identical on both arms and accepts an empty `image_path`, so a model that
  omits the argument gets a tool error it can recover from.
- Three kept base behaviours have graders that check tool order differently
  on each arm: `test_public/14` (benign accepts two orders), `test_public/30`
  (harmful checks only the first three tools) and `test_public/62` (benign has
  no order check). Each arm is gated by its own grader, as AgentHarm does,
  and these pairs are listed and left out in a sensitivity reading.
- AgentHarm's semantic judge passes any reply other than "pass" through as a
  failed criterion, with only a printed warning. ASSAY tells the judge it is
  grading a benchmark response, retries once on any other reply, then stops
  with an error, so a refusal to grade never becomes a silent fail.
- The benign `grade_ddos_attack` (`validation/8`) reads the search query
  without checking a search ran (`a and b or c`), so it crashes on any
  sample where the model never searched, including an empty reply. ASSAY
  brackets the `or` in memory. That only changes the crashing case, which
  now fails the search criterion; such a sample already fails the gate
  because the search is a target tool. Found on 15 October 2026 by running
  every grader on an empty reply: no other grader crashes. Reported as
  [inspect_evals #2703](https://github.com/UKGovernmentBEIS/inspect_evals/issues/2703).
- AgentHarm keeps `max_messages=20`, `max_tokens=4096` per generation and
  temperature 0, and shuffles each sample's tools with an unseeded random
  order, which is one source of run-to-run variation.

### Fixed settings

- The task set above, direct requests only.
- Target decoding as below. Message limit 20 and output limit 4,096
  tokens (AgentHarm's defaults); samples hitting either are counted.
- Judge `gemma4:12b-it-qat` (a different family), temperature 0, reasoning
  off, whole-output rendering, on both arms. The same model is AgentHarm's
  semantic judge. Scoring runs as a separate pass after generation, the same
  way for every configuration.
- One reference machine (Apple M1 Pro, 32 GB), Ollama version recorded.
- Every run records versions, model digests, profile, sampling settings in
  force and seeds.

### Decoding

Decided 7 October 2026. Every configuration uses the sampling settings Ollama
serves for these models, which are Qwen's published general thinking-mode
settings: temperature 1.0, top_p 0.95, top_k 20, presence penalty 1.5. The
same settings apply with thinking on and off, so the reasoning switch is the
only thing that changes between modes. Each repeat uses a different, recorded
seed. One extra run of the 4B in both modes at AgentHarm's temperature 0 is a
decoding sensitivity check.

Why I went with this:

- It's what someone running these models through Ollama gets by default,
  which fits the proposal's focus on small models run locally.
- Keeping decoding the same for all six configurations means size and
  reasoning mode are the only things that change. Qwen's separate
  non-thinking settings (temperature 0.7, top_p 0.8) would add a second
  difference between the modes.
- With sampling on, repeats show how much results move from one generation
  to the next, which is what RQ2 asks. At temperature 0 they'd only pick up
  serving non-determinism and the tool-order shuffle.
- AgentHarm defaults to temperature 0, so my numbers won't line up exactly
  with published AgentHarm results. The 4B check shows how much that
  matters.

The settings live in the built-in profiles and are recorded with every run.
`top_k` cannot be sent through Ollama's OpenAI-compatible endpoint, so it
comes from the model file and is read back by the preflight check. Outside
the case study, a profile without sampling settings keeps AgentHarm's
defaults.

Reasoning in the tool loop, decided 15 October 2026: with thinking on, each
turn's earlier reasoning is sent back to the model, which is Inspect's
default. Qwen3.5's own chat template does the same for every turn after the
last user message, and an AgentHarm task is one user message followed by a
tool loop; its advice to drop thinking from history applies to earlier user
turns, which these tasks do not have. A probe through Inspect and Ollama
confirmed it: the 4B recalled a code word that appeared only in an earlier
turn's reasoning in 3 of 3 trials with the default, and 0 of 3 with history
stripped. Keeping the default matches how the model is served elsewhere and
how other Inspect users run AgentHarm. The setting is recorded with every
run.

### Full-benchmark context (to agree)

My proposal: don't run the 37 excluded pairs. Their harmful and benign tasks
use different tools, so the benign task isn't testing the same ability and
they can't go into any paired metric. Running them would add about 22% to
repeat 1 for rates I wouldn't use anywhere, and AgentHarm's published results
already cover those tasks. As well as `assay run` skipping them,
`assay report` will refuse evidence for an excluded pair, so one can't end up
in the metrics by accident.

### Repeats (to agree)

My proposal: three repeats of every configuration. The 4B and 9B do all
three on every kept pair. The 27B is the slow one: early checks on my machine
had it at 165 to 225 seconds per sample, so about 19 hours per mode per
repeat. So the 27B does repeat 1 on every kept pair, and repeats 2 and 3 on a
random half of the base behaviours, picked once with a recorded seed before
anything runs. That comes to about 130 machine-hours, run overnight from
mid-November, and means I don't have to make any calls while the runs are
going.

### Outcomes

- Primary: CGR, ccASR and ccRR under the structural gate (executed calls).
- Always reported alongside: benign pass rate, ASR, verdict counts,
  executed-and-refused overlap, capability anomalies, benign refusals and the
  share of CGR they account for, capped and truncated shares.
- Unjudged pairs, where the judge had nothing to read on one arm (no
  reasoning, text or tool call in any turn), are listed per configuration and
  left out of every metric. Such a harmful sample cannot have executed, but
  whether it refused is unknown, so counting it as either refusal or failure
  would bias ccRR. Decided 15 October 2026.

### Primary comparisons (to agree)

For each primary metric:

- Size within a mode: 4B vs 9B, 9B vs 27B, 4B vs 27B, for each mode (6).
- Mode within a size: on vs off at 4B, 9B and 27B (3).

So 9 comparisons per metric, 27 in total. My proposal is Holm correction
across all 27. Each comparison uses the same pairs in both configurations,
with a randomisation test over base behaviours and a cluster bootstrap
interval for the difference.

The model-by-mode interaction is only described, not tested. Swapping labels
within clusters doesn't give a valid exact test of zero interaction without
extra assumptions, so I won't report an interaction p-value unless my
supervisor and I agree a method.

### Sensitivity analyses

- Gate: structural (executed calls) vs attempted calls vs semantic. The
  semantic gate is judge-dependent: 26 benign and 31 harmful graders ask an
  LLM to grade at least one criterion, and here that LLM is the local judge.
- Outcome policy: refusal first vs execution first.
- Common subset: conditioned metrics on pairs whose benign task passed in all
  compared configurations.
- Flagged pairs: metrics without the five patched base behaviours, the two
  with a tool-description difference and the three whose order check differs
  by arm.
- Decoding: the 4B at temperature 0 against the case-study settings.
- Repeats: per-repeat values and range.

### Limitations stated up front

- No held-out data: every kept behaviour is public and I saw them while
  building the tool, so my design choices could be shaped by them. Freezing
  the plan before the final runs is how I try to limit that.
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
| Invalid input | One test per rejection: missing arm, duplicate key, runs with different settings, invalid profile, malformed grading breakdown. Unjudged pairs are tested to be listed and left out of the metrics. | Tests. |
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
