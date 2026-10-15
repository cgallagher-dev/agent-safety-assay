# Contributing

Thanks for looking. ASSAY is a final-year project at TUS Athlone, so I'm the
main developer until it's assessed (around May 2027), but bug reports and
small fixes are welcome.

## Before you start

- ASSAY is licensed under [PolyForm Noncommercial 1.0.0](LICENSE).
  Contributions are accepted under the same licence.
- AgentHarm tasks are harmful by design. Never commit benchmark data, `.eval`
  logs, results or model output, and don't paste harmful model output into
  issues or pull requests. CI fails if any of these are tracked.

## Set up

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```text
uv sync
uv run pytest
uv run ruff check
uv run ruff format --check
```

## Making a change

1. Open an issue first for anything bigger than a small fix, so we can agree
   it fits the [spec](docs/spec.md).
2. Write the test first for anything touching pairing, grading, outcomes,
   metrics or redaction. Tests use synthetic fixtures and need no model or
   network.
3. Keep each pull request to one change, with a short description of what
   changed and why.
4. CI has to pass (lint, tests on Python 3.12 and 3.14, and the containment
   check).

## Reporting a bug

Use the bug template. Include the command you ran, the `assay` version and
the error line. Run it again with `--debug` if you can. Leave out any model
output from harmful tasks.

For anything security related, see [SECURITY.md](SECURITY.md).
