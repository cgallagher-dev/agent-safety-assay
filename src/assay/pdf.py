"""The PDF report: report.json rendered to HTML with Jinja2, then to PDF with WeasyPrint.

Needs the pdf extra. Every number comes from the report; the template adds only
fixed headings and the limitations list.
"""

import io
from collections import defaultdict
from pathlib import Path

from assay.errors import ConfigError
from assay.report import GATES, METRIC_LABELS, VERDICT_LABELS, Report, format_rate

INSTALL = "The PDF report needs the pdf extra: pip install 'safety-assay[pdf]'."
GATE_LABELS = {
    "structural": "Structural (executed calls)",
    "structural_attempted": "Structural (attempted calls)",
    "semantic": "Semantic",
}


def write_pdf(report: Report, path: Path) -> None:
    try:
        import weasyprint
    except ImportError:
        raise ConfigError(INSTALL) from None
    except OSError as error:
        raise ConfigError(
            "WeasyPrint could not load Pango. Install it as described at "
            "https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
        ) from error
    weasyprint.HTML(string=render_html(report)).write_pdf(path)


def render_html(report: Report) -> str:
    try:
        import jinja2
        from markupsafe import Markup
    except ImportError:
        raise ConfigError(INSTALL) from None
    environment = jinja2.Environment(loader=jinja2.PackageLoader("assay"), autoescape=True)
    environment.filters["rate"] = lambda rate: format_rate(rate).strip()
    return environment.get_template("report.html").render(
        report=report,
        gates=GATES,
        gate_labels=GATE_LABELS,
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
    figure = Figure(figsize=(5, 3.6))
    axes = figure.subplots()
    for configuration in report.configurations:
        metrics = configuration.gates[report.headline_gate].metrics
        if metrics.cc_asr.value is None:
            continue
        point = (metrics.benign_pass_rate.value, metrics.cc_asr.value)
        axes.scatter(*point, color="#0969da")
        axes.annotate(
            configuration.name, point, xytext=(5, 5), textcoords="offset points", fontsize=8
        )
    axes.set(xlim=(0, 1), ylim=(0, 1), xlabel="Benign pass rate", ylabel="ccASR")
    axes.xaxis.set_major_formatter(PercentFormatter(1.0))
    axes.yaxis.set_major_formatter(PercentFormatter(1.0))
    figure.tight_layout()
    buffer = io.StringIO()
    figure.savefig(buffer, format="svg", metadata={"Date": None})
    svg = buffer.getvalue()
    return svg[svg.index("<svg") :]


def _verdict_cells(report: Report) -> dict[tuple[str, str, str], list[str]]:
    """(configuration, gate, verdict) -> the pair keys counted in that cell."""
    repeats = {c.name: c.repeats for c in report.configurations}
    cells = defaultdict(list)
    for pair in report.pairs:
        label = pair.key if repeats[pair.configuration] == 1 else f"{pair.key} (r{pair.repeat})"
        for gate, result in pair.gates.items():
            cells[(pair.configuration, gate, result.verdict)].append(label)
    return cells
