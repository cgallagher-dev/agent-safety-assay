"""How results look in a terminal: the safety palette, the coloured report and
the per-sample lines that assay judge prints while it works.

Colours follow docs/presentation.md: each one says what a result means for
safety, and always comes with a symbol and a word.
"""

import re
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from assay.outcomes import HEADLINE_POLICY, VERDICTS, Verdict, harmful_outcome
from assay.report import METRIC_LABELS, VERDICT_LABELS

HARM, SAFE, GAP, NO_EVIDENCE, NEUTRAL = "red", "green", "yellow", "bright_black", "cyan"
VERDICT_STYLES = {
    Verdict.COMPLIED: HARM,
    Verdict.REFUSED_WHEN_CAPABLE: SAFE,
    Verdict.FAILED_WHEN_CAPABLE: GAP,
    Verdict.CAPABILITY_ANOMALY: GAP,
    Verdict.REFUSED_UNTESTED: NO_EVIDENCE,
    Verdict.NO_SIGNAL: NO_EVIDENCE,
}
VERDICT_SYMBOLS = {HARM: "✗", SAFE: "✓", GAP: "◐", NO_EVIDENCE: "–"}
METRIC_STYLES = {
    "benign_pass_rate": NEUTRAL,
    "asr": HARM,
    "cc_asr": HARM,
    "cc_rr": SAFE,
    "cgr": GAP,
}
OUTCOME_WORDS = {"refusal": "refused", "success": "done", "failure": "not done"}
# Wide enough for the longest verdict, "– refused with capability untested".
VERDICT_WIDTH = 2 + max(len(label) for label in VERDICT_LABELS.values())


# Set once per command from --no-color; NO_COLOR and non-terminals are checked per console.
colour = True


def styled_console(stderr: bool = False) -> Console | None:
    """A rich console when output is a colour terminal, else None for plain text."""
    console = Console(stderr=stderr, highlight=False)
    return console if colour and console.is_terminal and not console.no_color else None


def print_error(message: str) -> None:
    """An error on stderr: a red panel on a colour terminal, else the plain line."""
    terminal = styled_console(stderr=True)
    if terminal is None:
        print(f"assay: error: {message}", file=sys.stderr)
    else:
        terminal.print(
            Panel(Text(message), title="✗ error", title_align="left", border_style=HARM),
            style=HARM,
        )


def styled_report(text: str) -> Text:
    """The plain report with colour added; the text itself is unchanged."""
    styled = Text(text)
    styled.highlight_regex(re.compile(r"\ARun [^\n]*"), "dim")
    styled.highlight_regex(
        re.compile(r"^[^\s(]+ \(profile [^\n]*$", re.MULTILINE), f"bold {NEUTRAL}"
    )
    styled.highlight_regex(re.compile(r"^Pairs \([^\n]*\)$", re.MULTILINE), f"bold {NEUTRAL}")
    styled.highlight_regex(re.compile(r"^key +category[^\n]*$", re.MULTILINE), "dim")
    for metric, label in METRIC_LABELS.items():
        pattern = re.compile(rf"^  {re.escape(label)}\b", re.MULTILINE)
        styled.highlight_regex(pattern, f"bold {METRIC_STYLES[metric]}")
    for verdict, style in VERDICT_STYLES.items():
        styled.highlight_regex(rf"\b{re.escape(VERDICT_LABELS[verdict])}\b", style)
    styled.highlight_regex(r"undefined \([^)]*\)", NO_EVIDENCE)
    return styled


def format_duration(seconds: float) -> str:
    """A duration in the two largest units that matter: "14 min 18 s", "1 h 1 min"."""
    total = round(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours} h {minutes} min"
    if minutes:
        return f"{minutes} min {secs} s"
    return f"{secs} s"


def judge_line(
    arm: str,
    sample_id: str,
    status: str,
    *,
    category: str = "",
    passed: bool = False,
    executed: int = 0,
    declared: int = 0,
    refusal: bool | None = None,
    benign_passed: bool | None = None,
) -> Text:
    """One finished sample: ids, tool counts and verdict words, never task text."""
    # 16 fits AgentHarm's longest category, "Disinformation".
    line = Text(f"  {arm:<9}{sample_id:<8}{category:<16}")
    if refusal is None:
        word, style = "– unjudged", NO_EVIDENCE
    elif arm == "benign":
        word, style = ("● passed", NEUTRAL) if passed else ("◐ failed", GAP)
    else:
        outcome = harmful_outcome(passed, refusal, HEADLINE_POLICY)
        if benign_passed is None:
            word, style = f"{OUTCOME_WORDS[outcome]} (twin not judged)", NO_EVIDENCE
        else:
            verdict = VERDICTS[(benign_passed, outcome)]
            style = VERDICT_STYLES[verdict]
            word = f"{VERDICT_SYMBOLS[style]} {VERDICT_LABELS[verdict]}"
    line.append(word, style)
    line.append(" " * (VERDICT_WIDTH - len(word)))
    line.append(f"   {executed}/{declared} tools ran")
    if refusal is not None:
        # A benign refusal is over-refusal; on the harmful arm the verdict carries the colour.
        warn = GAP if refusal and arm == "benign" else ""
        line.append("   refused" if refusal else "   not refused", warn)
    if status == "already scored":
        line.append("   (already scored)", NO_EVIDENCE)
    return line


class SampleLines:
    """Prints a line for each sample assay judge finishes, pairing harmful with benign."""

    def __init__(self, console: Console, results: Path) -> None:
        self.console = console
        self.results = results
        self.benign: dict[tuple[str, str, str], bool] = {}

    def __call__(self, path: Path, arm: str, sample, status: str) -> None:
        # Imported here because Inspect adds seconds to every other command.
        from assay.grading import LOG_PATH, grade_sample

        match = LOG_PATH.search(path.relative_to(self.results).as_posix())
        configuration, repeat = (match.group(1), match.group(3)) if match else ("", "")
        pair = (configuration, repeat, str(sample.id))
        grade = grade_sample(sample, arm)
        passed = grade.gates.structural
        if arm == "benign":
            self.benign[pair] = passed
        self.console.print(
            judge_line(
                arm,
                str(sample.id),
                status,
                category=sample.metadata["category"],
                passed=passed,
                executed=len(set(grade.executed) & set(sample.metadata["target_functions"])),
                declared=len(set(sample.metadata["target_functions"])),
                refusal=grade.refusal,
                benign_passed=self.benign.get(pair) if arm == "harmful" else None,
            )
        )


def styled_pairs(text: str) -> Text:
    """The plain pairs check with colour added; the text itself is unchanged."""
    styled = Text(text)
    styled.highlight_regex(re.compile(r"\AAgentHarm dataset[^\n]*"), "dim")
    styled.highlight_regex(re.compile(r"^Kept \d+ of \d+ pairs[^\n]*$", re.MULTILINE), "bold")
    styled.highlight_regex(re.compile(r"^[A-Z][^\n]*:$", re.MULTILINE), f"bold {NEUTRAL}")
    return styled


def print_task(terminal: Console | None, key, category, declared, orders, twin, task, show) -> None:
    """One AgentHarm pair: its expected calls, its order rule and its prompts."""
    if orders["harmful"] == orders["benign"]:
        order_lines = [f"Order: {orders['harmful']}"]
    else:
        order_lines = [
            f"Order on the harmful task: {orders['harmful']}",
            f"Order on the benign twin: {orders['benign']}",
        ]
    steps = [f"  {step}. {tool}" for step, tool in enumerate(declared, 1)]
    withheld = "Harmful task: withheld. Add --show-harmful to print it, under a content warning."
    warning = "Content warning: AgentHarm's harmful task text, shown for research and supervision."
    if terminal is None:
        print(f"{key}  {category}", "Expected tool calls:", *steps, *order_lines, sep="\n")
        print(f"\nBenign twin: {twin.name}\n{twin.prompt}\n")
        print(f"{warning}\nHarmful task: {task.name}\n{task.prompt}" if show else withheld)
        return
    terminal.print(Text.assemble((key, f"bold {NEUTRAL}"), "  ", (category, "bold")))
    terminal.print(Text("Expected tool calls", style="bold"))
    for line in steps:
        number, tool = line.split(". ", 1)
        terminal.print(Text.assemble((f"{number}.", NEUTRAL), " ", tool))
    for line in order_lines:
        terminal.print(Text(line, style="dim"))
    width = min(terminal.width, 100)
    terminal.print()
    terminal.print(
        Panel(
            Text(twin.prompt),
            title=f"Benign twin: {twin.name}",
            title_align="left",
            border_style=NEUTRAL,
            width=width,
        )
    )
    if not show:
        terminal.print(Text(withheld, style=NO_EVIDENCE))
        return
    terminal.print(Text(f"{VERDICT_SYMBOLS[HARM]} {warning}", style=f"bold {HARM}"))
    terminal.print(
        Panel(
            Text(task.prompt),
            title=f"Harmful task: {task.name}",
            title_align="left",
            border_style=HARM,
            width=width,
        )
    )
