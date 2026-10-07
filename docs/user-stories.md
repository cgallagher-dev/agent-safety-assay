# User stories

Personas are defined in [spec.md](spec.md#users). Priority uses MoSCoW.
Each story lists the milestone it is planned for and the requirements it
covers. Implementation issues on GitHub reference these ids.

## A. Pairs and runs

### US-01 Validate pairs before a run
As an evaluator, I want ASSAY to check that each harmful task and its benign
twin expect the same tool calls before anything runs, so that every comparison
is like for like.
- Pairs are keyed by split and sample id, never bare id.
- Pairs whose declared target-function sequences differ in content, length or
  order are excluded and listed with the reason.
- The kept count and excluded list are printed and recorded in the run.
- Kept pairs whose tools show a different description or schema on the two
  arms are listed, as is the kept share per category.

Must, M1. FR1.

### US-02 Run any model from a profile
As an evaluator, I want to run a model by naming it or a profile, so that I can
test a new model without changing code.
- `assay run --profile <name|path>` accepts a built-in name or a TOML file.
- `assay run --model <inspect model>` runs with a default single-mode profile.
- A profile gives the Inspect model string, connection settings, max
  connections, a minimum context length, and reasoning modes, each with its
  request parameters and sampling settings.
- API keys come from environment variables, never from the profile.
- An invalid profile fails before any model call with a message naming the
  field.

Must, M2. FR2.

### US-03 Reasoning mode is verified
As an evaluator, I want a run to stop if "thinking off" is not actually off, so
that a silently ignored setting cannot corrupt a configuration.
- The mode's parameters are checked in the built request before the run.
- The run stops if an "off" mode shows any reasoning in its first samples, or
  an "on" mode shows none.

Must, M2. FR5.

### US-04 Resume an interrupted run
As an evaluator, I want a stopped run to continue where it left off, so that a
long 27B run is not lost to one interruption.
- Re-running the same command skips completed samples.
- Benign runs before harmful for each configuration and repeat.
- Each sample starts with fresh agent and tool state.

Must, M2. FR2, FR4.

### US-05 Score after generation
As an evaluator with limited memory, I want grading and refusal judging to run
after the agent model has finished, so that a large target and the judge never
need to fit in memory together and every model is scored the same way.
- Generation never calls the judge.
- `assay judge <results>` runs AgentHarm's graders and the refusal judge over
  every unscored sample on both arms, and checkpoints.

Must, M1 (saved logs) and M2 (runner integration). FR11.

### US-06 Catch serving problems before a run
As an evaluator, I want ASSAY to check the model server first, so that a
misconfigured server fails in seconds rather than after hours.
- For Ollama: server version, tool-calling capability and served context are
  checked, and the server's default sampling parameters are recorded.

Should, M2. FR6.

## B. Grading and judging

### US-07 Capability gates for both arms
As a researcher, I want structural, attempted-call and semantic gate readings for
every sample, so that I can see how the gate choice changes results.
- Ordering rules follow each grader, including the graders that differ
  between arms.
- Readings are cross-checked against AgentHarm's own breakdown and
  disagreements are reported.
- A missing or malformed breakdown is an error.

Must, M1. FR7, FR8.

### US-08 Execution and refusal recorded separately
As a researcher, I want tool execution and refusal stored as separate facts,
so that a trace that both refuses and executes is not hidden.
- Each harmful sample has `executed` per gate and `refusal`.
- Refusal is judged on the benign arm too, and benign refusals are reported
  apart from other benign failures.
- The derived outcome uses refusal first, and the overlap count is reported.
- The judge sees reasoning, text and rendered tool calls.

Must, M1. FR9, FR13.

### US-09 Re-judge without re-running agents
As a researcher, I want to re-judge saved logs, so that a judge fix does not
cost a new agent run.
- Re-judging writes a new verdict under the judge's score key and leaves agent
  output and the original scores untouched.

Must, M1. FR11.

### US-10 The judge fails loudly
As a researcher, I want any judge failure to stop the run, so that an error is
never counted as "did not refuse".
- Judge exceptions, unparseable verdicts and a missing reasoning switch raise.
- A sample with nothing to judge is marked unjudged.

Must, M1. FR10.

## C. Metrics and statistics

### US-11 Metrics with visible denominators
As a researcher or engineer, I want ASR, benign pass rate, ccASR, ccRR and CGR
with numerators and denominators, so that I can see what each rate rests on.
- Definitions match spec section 6.4.
- An empty denominator shows as undefined with a reason, never zero.

Must, M1. FR12.

### US-12 Verdicts and anomalies
As a researcher, I want each pair placed in one of the six verdict cells, so
that I can see where safety is demonstrated and where it was never tested.
- Verdict counts per configuration and gate.
- Capability anomalies are listed by key.
- Benign refusals are counted, and the share of CGR whose benign twin was
  refused is shown, so over-refusal is not read as incapability.
- Duplicate, one-sided or unjudged evidence stops the report.

Must, M1. FR13, FR14.

### US-13 Uncertainty by base behaviour
As a researcher, I want intervals that treat prompt variants of one behaviour
as one unit, so that I do not overstate precision.
- Cluster bootstrap over base behaviours, seed and resample count recorded.

Must, M2. FR15.

### US-14 Compare configurations
As an engineer, I want to compare two configurations on the same pairs, so
that I can pick between models on evidence.
- Differences with bootstrap intervals and cluster-level randomisation
  p-values, Holm-adjusted within the call.
- A common-subset view on pairs that passed benign in every configuration.

Must, M2. FR16, FR17.

### US-15 Sensitivity readings
As a researcher, I want to see how results move with the gate and the outcome
policy, so that I can answer RQ2.
- Structural, attempted-call and semantic gates side by side.
- Refusal-first and execution-first policies side by side.

Must, M2. FR18.

### US-16 Repeated runs
As a researcher, I want repeats of a configuration combined and their spread
shown, so that run-to-run variation is separated from task variation.
- Per-repeat metrics, mean and range; intervals resample clusters with all
  their repeats.

Must, M2. FR15, FR18.

## D. Reports and dashboard

### US-17 Report in terminal, JSON and CSV
As any user, I want one command to give me the results in the format I need.
- `assay report` prints the pair table and metrics and writes `report.json`,
  `pairs.csv` and `metrics.csv`.
- A test checks that all outputs carry identical numbers.
- `report.json` validates against the versioned schema.

Must, M1. FR19, FR20.

### US-18 PDF report
As an engineer, I want a PDF I can attach to a model decision.
- Rendered from `report.json` only, including the benign pass versus ccASR
  plot, denominators and limitations.
- An appendix lists the pair keys in each verdict cell.

Must, M1. FR21.

### US-19 Dashboard overview
As an engineer or demo audience, I want a browser view of all configurations,
so that the main result is readable at a glance.
- `assay dashboard <results>` opens a local read-only dashboard.
- Metrics with numerators, denominators and intervals; the benign pass versus
  ccASR plot; verdict breakdown; gate selector.
- The browser renders backend numbers and never computes a metric.

Must, M1. FR23, FR24.

### US-20 Trace a number back to its pairs
As a researcher, I want to click from a metric to the pairs behind it and on
to each pair's traces, so that every number can be checked.
- Pair explorer filtered by verdict, category and configuration.
- Pair detail with declared, observed and executed tool sequences for both
  arms, the judge verdict and the benign transcript.

Must, M1 (detail) and M3 (filters). FR22, FR25.

### US-21 Harmful text never reaches the browser
As the project owner, I want harmful-arm text kept on the backend, so that a
demo or shared screen cannot expose it.
- Harmful traces show tool names, execution status and verdicts only.
- A sentinel test covers every API endpoint.
- `assay show` redacts harmful text unless asked explicitly.

Must, M1. FR22, FR26.

### US-22 Compare and sensitivity in the dashboard
As an engineer, I want the comparison and sensitivity results in the
dashboard, so that I can explore them without the CLI.

Should, M3. FR27.

### US-23 Live run progress
As a demo audience, I want to watch a run progress, so that the pipeline is
visible and not just its end result.
- Samples appear as they finish with provisional, backend-computed metrics.

Could, M3. FR28.

## E. Trust and reproducibility

### US-24 Runs record what produced them
As a researcher, I want every run to record its versions, model digest,
profile, judge and settings, so that results can be reproduced and are never
mixed by accident.
- `run_config.json` with a fingerprint; reports refuse to combine mismatched
  fingerprints and name the differing fields.
- The sampling settings in force and each repeat's seed are recorded; API keys
  never are.

Must, M2. FR3, NFR1.

### US-25 Judge agreement with human labels
As a researcher, I want the judge checked against my own labels, so that I can
state how far refusal readings can be trusted.
- A blinded labelling sheet from a stratified sample; agreement and Cohen's
  kappa reported with the direction of errors.

Must, M3. Evaluation plan.

### US-26 Clean install
As any user, I want to install and run ASSAY on a fresh machine with
documented steps, so that the tool works outside my laptop.
- `pip install safety-assay` from PyPI.
- Clean machine or VM: install, run the fixture report, open the dashboard,
  render the PDF.

Must, M3. NFR5, NFR13.

### US-27 Offline demonstration fixture
As any user, I want a synthetic example that runs with no model, so that I can
see what ASSAY produces in a minute.
- Invented behaviours and tools only, no AgentHarm text.
- Produces a report, PDF and dashboard.

Must, M1. FR29.

### US-28 Model-written summary
As an engineer or demo audience, I want a short written summary of the
results, so that I can understand them without reading every table.
- `assay narrate <results>` writes `narrative.md` from `report.json`.
- The prose contains no digits; numbers appear only through placeholders
  filled from `report.json`.
- The PDF and dashboard show it under a "model-written" label, and work
  without it.

Should, M3. FR30.

### US-29 Clear failures and a run log
As an evaluator running long jobs unattended, I want failures to stop with a
clear message and every run to leave a log, so that I can see what happened
and fix it.
- Each error names what failed and what to do; no traceback unless `--debug`.
- Exit codes differ by error type.
- Every run writes `assay.log` tagged with its run id; no harmful text is
  logged.

Must, M1. NFR11, NFR12.
