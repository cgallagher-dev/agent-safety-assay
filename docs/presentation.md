# Presentation

This page sets out how the CLI, the PDF report and the dashboard look and
what each one shows. I settled it on 28 October 2026. The requirements are in
the spec (FR19 to FR30, NFR7, NFR14), and the work is tracked in SCRUM-52
(CLI), SCRUM-53 (dashboard) and SCRUM-54 (PDF).

## Shared rules

- One palette across the CLI, the PDF, the dashboard and the slides. A colour
  says what something means for safety, never just which thing it is, and it
  always comes with a symbol and a word, so nothing relies on colour alone.
  (Changed on 11 November 2026: green used to mean "complied", which reads as
  good on a harmful task.)

  | Colour | Hex | Symbol | Means | Used for |
  | --- | --- | --- | --- | --- |
  | Red | `#B42318` | ✗ | Harm happened | complied, ASR, ccASR, harmful text and logs |
  | Green | `#1A7F37` | ✓ | Safe, with evidence | refused when capable, ccRR |
  | Amber | `#B54708` | ◐ | Capability gap, a warning | failed when capable, capability anomaly, CGR |
  | Grey | `#667085` | – | No evidence either way | refused with capability untested, no signal, undefined rates |
  | Teal | `#0F6E6A` | ● | Neutral: the benign side, structure, the brand | benign pass rate, headers, progress |

  In a terminal, these map to rich's `red`, `green`, `yellow`, `bright_black`
  and `cyan`, so they follow the user's terminal theme.

- A rate is always shown as `42% (21/50) [CI 30–55]`. Undefined shows its
  reason, never zero (NFR7).
- Every view starts with the same header: run id, date, configurations, gate,
  and the ASSAY, Inspect and AgentHarm versions.
- Harmful-arm text never appears, only its structure (FR26).
- Light theme only.

## CLI

Built on `rich`. Colour is dropped when output is not a terminal, when
`NO_COLOR` is set, or with `--no-color`.

| Command | Shows |
| --- | --- |
| `assay pairs` | Kept and excluded counts, exclusion reasons, kept share per category. |
| `assay run` | Preflight checklist (✓ or ✗ per check), then a progress bar per arm, mode and repeat with samples done, time left and errors. Ends with the run id. |
| `assay judge` | Progress bar, plus one line per sample as it finishes: arm, sample id, tools run out of those declared, and the refusal verdict. A harmful line also shows its pair's verdict, since its benign twin is judged first. Then the checkpoint state and unjudged count. |
| `assay report` | Header panel, metrics table per configuration, verdict counts, anomalies, then the files written. |
| `assay show`, `assay ls` | One pair with both arms side by side; a summary of a results directory. |
| `assay compare` | Differences with intervals and Holm-adjusted p-values; significant rows highlighted. |
| `assay narrate` | Accepted or rejected, with the reason for each rejection. |

- Every command ends with a `next:` line suggesting the usual next command,
  for example `next: assay judge results/<run id>`. `-q` hides it.
- Errors print as a red panel: what failed, then what to do next. No
  traceback unless `--debug` (NFR11).
- Long steps show progress, and `-q` hides it.

## PDF report

1. Title page: run id, date, configurations, gate, versions.
2. Summary: the narrative, if one exists, under a "model-written" label,
   followed by a fixed table of the five metrics per configuration.
3. Method: pairs kept and excluded, gate, judge and settings, generated from
   `run_config.json`.
4. Results: metrics table, benign pass rate versus ccASR plot, verdict
   breakdown.
5. Comparisons and sensitivity, when `assay compare` output exists.
6. Limitations: fixed text plus this run's anomalies, unjudged samples and
   message-limit hits.
7. Appendix: pair keys in each verdict cell, so every count traces to its
   pairs (FR21).

Footer on every page: run id and page number. Charts use the shared palette
and stay readable in greyscale. Table rows never split across pages.

## Dashboard

| Page | Shows |
| --- | --- |
| Overview | Narrative panel (model-written, if present), metric cards per configuration, benign pass rate versus ccASR plot, verdict breakdown, gate selector. |
| Pair explorer | Table filtered by verdict, category, configuration and repeat, with verdict badges. Filters live in the URL. |
| Pair detail | Declared, observed and executed tool sequences for both arms side by side, the judge verdict, the benign transcript, harmful-arm structure only. |
| Compare and sensitivity (M3) | Difference plot with intervals, common-subset toggle, gate and policy sensitivity tables. |
| Live run (Could) | Provisional progress during a run. |

Every page has loading, empty and error states, works by keyboard with
visible focus, and meets WCAG AA contrast (NFR14).

## Narrative

The judge model writes it by default (D13, FR30). It never writes a digit.
Numbers, configuration names, model names and pair keys all come in through
placeholders that are filled from `report.json`, for example
`{metric:ccASR:qwen3.5-4b/on}` or `{config:qwen3.5-4b/on}`. Output with a
digit or an unresolved placeholder is rejected. The narrative appears at the
top of the PDF and as a panel on the dashboard overview, always labelled
"model-written".
