"""The PDF report: the report rendered to HTML with Jinja2, then to PDF with WeasyPrint.

Needs the pdf extra. Every number comes from the report; the template adds only
fixed headings and the limitations list.
"""

import io
from collections import defaultdict
from pathlib import Path

from assay.errors import ConfigError
from assay.outcomes import POLICY_LABELS, Verdict
from assay.report import (
    GATES,
    METRIC_LABELS,
    VERDICT_LABELS,
    format_limits,
    format_rate,
    format_refs,
)
from assay.report_schema import GateResult, Report

INSTALL = "The PDF report needs the pdf extra: pip install 'agent-safety-assay[pdf]'."
GATE_LABELS = {
    "structural": "Structural (executed calls)",
    "structural_attempted": "Structural (attempted calls)",
    "semantic": "Semantic",
}

# The safety palette (docs/presentation.md): colour, symbol and word always together.
TONES = {
    "harm": ("#B42318", "✗"),
    "safe": ("#1A7F37", "✓"),
    "gap": ("#B54708", "◐"),
    "none": ("#667085", "–"),
    "neutral": ("#0F6E6A", "●"),
}
VERDICT_TONES = {
    Verdict.COMPLIED: "harm",
    Verdict.REFUSED_WHEN_CAPABLE: "safe",
    Verdict.FAILED_WHEN_CAPABLE: "gap",
    Verdict.CAPABILITY_ANOMALY: "gap",
    Verdict.REFUSED_UNTESTED: "none",
    Verdict.NO_SIGNAL: "none",
}
# The plain questions from the Demo 1 slides, conditioned metrics first.
METRIC_CARDS = [
    ("cc_asr", "harm", "If it can do the task, does it?"),
    ("cc_rr", "safe", "If it can do the task, how often does it say no?"),
    ("cgr", "gap", "How much of the \u201csafety\u201d is really inability?"),
    ("asr", "harm", "How often was the harmful task done, out of every pair?"),
    ("benign_pass_rate", "neutral", "How often could it do the benign twin?"),
]
DEFINITIONS = {
    "cc_asr": "Harmful tasks done, out of the pairs whose benign twin passed.",
    "cc_rr": "Refusals, out of refused or done, on the pairs whose benign twin passed.",
    "cgr": "Harmful tasks not done whose benign twin also failed, out of all not done.",
    "asr": "Harmful tasks done, out of all pairs.",
    "benign_pass_rate": "Benign twins that passed the gate, out of all pairs.",
}
# Harm on the left and safe-with-evidence on the right, so red and green never touch.
BAR_ORDER = [
    Verdict.COMPLIED,
    Verdict.CAPABILITY_ANOMALY,
    Verdict.FAILED_WHEN_CAPABLE,
    Verdict.NO_SIGNAL,
    Verdict.REFUSED_UNTESTED,
    Verdict.REFUSED_WHEN_CAPABLE,
]
# The 2x3 grid: rows by benign twin, columns by harmful outcome.
GRID = [
    (Verdict.COMPLIED, Verdict.REFUSED_WHEN_CAPABLE, Verdict.FAILED_WHEN_CAPABLE),
    (Verdict.CAPABILITY_ANOMALY, Verdict.REFUSED_UNTESTED, Verdict.NO_SIGNAL),
]


def _times(count: int) -> str:
    return "1 time" if count == 1 else f"{count} times"


def summary(result: GateResult) -> str:
    """The result in plain words, built from the report's counts (the dashboard says the same)."""
    capable = result.metrics.cc_asr.denominator
    verdicts = result.verdicts
    parts = [
        f"did the harmful version {_times(verdicts[Verdict.COMPLIED])}",
        f"refused {_times(verdicts[Verdict.REFUSED_WHEN_CAPABLE])}",
    ]
    if verdicts[Verdict.FAILED_WHEN_CAPABLE]:
        parts.append(f"failed {_times(verdicts[Verdict.FAILED_WHEN_CAPABLE])}")
    if capable == 0:
        text = (
            "It passed no benign task on this gate, so nothing here shows it refusing a task "
            "it could do."
        )
    else:
        tasks = "1 task" if capable == 1 else f"{capable} tasks"
        text = f"On the {tasks} it showed it could do, it {', '.join(parts[:-1])} and {parts[-1]}."
    cgr = result.metrics.cgr
    if cgr.denominator:
        harmful = "1 harmful task" if cgr.denominator == 1 else f"{cgr.denominator} harmful tasks"
        text += (
            f" Of the {harmful} it didn't do, {cgr.numerator} had a benign twin that also "
            "failed, so they show inability, not safety."
        )
    return text


def write_pdf(report: Report, path: Path) -> None:
    try:
        import weasyprint
    except ImportError:
        raise ConfigError(INSTALL) from None
    except OSError as error:
        raise ConfigError(
            "WeasyPrint could not load Pango. Install it as described at "
            "https://doc.courtbouillon.org/weasyprint/stable/first_steps.html, then rerun."
        ) from error
    html = render_html(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    weasyprint.HTML(string=html).write_pdf(path)


def render_html(report: Report) -> str:
    try:
        import jinja2
        from markupsafe import Markup
    except ImportError:
        raise ConfigError(INSTALL) from None
    environment = jinja2.Environment(loader=jinja2.PackageLoader("assay"), autoescape=True)
    environment.filters["rate"] = lambda rate: format_rate(rate).strip()
    environment.filters["refs"] = format_refs
    return environment.get_template("report.html").render(
        report=report,
        gates=GATES,
        gate_labels=GATE_LABELS,
        policy_label=POLICY_LABELS[report.headline_policy],
        summary=summary,
        limits=format_limits,
        tones=TONES,
        verdict_tones=VERDICT_TONES,
        metric_cards=METRIC_CARDS,
        definitions=DEFINITIONS,
        bar_order=BAR_ORDER,
        grid=GRID,
        metric_labels=METRIC_LABELS,
        verdict_labels=VERDICT_LABELS,
        plot=Markup(_plot_svg(report)),
        cells=_verdict_cells(report),
    )


def _plot_svg(report: Report) -> str:
    """Benign pass rate against ccASR on the headline gate, one point per configuration."""
    try:
        from matplotlib.figure import Figure
        from matplotlib.ticker import PercentFormatter
    except ImportError:
        raise ConfigError(INSTALL) from None
    figure = Figure(figsize=(4.2, 3.2))
    axes = figure.subplots()
    for configuration in report.configurations:
        metrics = configuration.gates[report.headline_gate].metrics
        if metrics.cc_asr.value is None:
            continue
        point = (metrics.benign_pass_rate.value, metrics.cc_asr.value)
        axes.scatter(*point, color=TONES["neutral"][0], s=40, zorder=3)
        axes.annotate(
            configuration.name, point, xytext=(6, 6), textcoords="offset points", fontsize=9
        )
    axes.set(xlim=(0, 1), ylim=(0, 1), xlabel="Benign pass rate", ylabel="ccASR")
    axes.xaxis.set_major_formatter(PercentFormatter(1.0))
    axes.yaxis.set_major_formatter(PercentFormatter(1.0))
    figure.tight_layout()
    buffer = io.StringIO()
    # No date in the metadata, so the same report always gives the same SVG.
    figure.savefig(buffer, format="svg", metadata={"Date": None})
    svg = buffer.getvalue()
    return svg[svg.index("<svg") :]


def _verdict_cells(report: Report) -> dict[tuple[str, str, str], list[str]]:
    """(configuration, gate, verdict) -> the pair keys counted in that cell."""
    repeats = {c.name: c.repeats for c in report.configurations}
    cells = defaultdict(list)
    for pair in report.pairs:
        label = pair.key if repeats[pair.configuration] == 1 else f"{pair.key} r{pair.repeat}"
        for gate, result in pair.gates.items():
            cells[(pair.configuration, gate, result.verdict)].append(label)
    return cells
