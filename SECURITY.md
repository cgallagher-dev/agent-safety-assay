# Security and responsible use

ASSAY is a defensive evaluation tool. Use it only on models you are allowed to
test.

## Harmful content

AgentHarm contains harmful task prompts, and evaluated models can produce
harmful text and tool arguments. This is how ASSAY handles that material:

- Tools are AgentHarm's synthetic tools. No run takes a real-world action.
- Benchmark data is downloaded at run time and never committed.
- Evaluation logs (`*.eval`), `results/`, `data/` and AgentHarm's dataset files
  are ignored by git, and CI fails if any of them is ever tracked.
- Derived evidence files hold identifiers, tool names and booleans only, never
  prompts, responses, reasoning or tool arguments.
- The dashboard backend never sends harmful-arm prompt, response, reasoning or
  tool-argument text to the browser. Harmful traces are shown as structure:
  tool names, execution status and verdicts.
- `assay show` redacts harmful-arm text by default. Printing it locally needs
  an explicit flag.
- Test fixtures are synthetic.

## Reporting a problem

If you find harmful content in this repository, a way to leak it through the
tool, or a security issue, open a GitHub issue without quoting the content, or
contact me (the maintainer) through GitHub.
