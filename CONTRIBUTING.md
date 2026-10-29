# Contributing

Thanks for looking. ASSAY is a final-year project at TUS Athlone, so it isn't
open to contributions until it has been graded (around May 2027). Pull
requests from others won't be allowed before then.

## Before you start

- ASSAY is licensed under the [MIT License with an added clause](LICENSE)
  that limits use to improving the safety and security of AI systems.
- AgentHarm tasks are harmful by design. Never commit benchmark data, `.eval`
  logs, results or model output, and don't paste harmful model output into
  issues. CI fails if any of these are tracked.

## Set up

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```text
uv sync
uv run pytest
uv run ruff check
uv run ruff format --check
```

## How changes are made

Once contributions open, this is the process. Until then it's how I work.

1. Open an issue first for anything bigger than a small fix, so I can check
   it against the [spec](docs/spec.md).
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
