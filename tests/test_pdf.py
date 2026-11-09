import re
from pathlib import Path

import pytest

import assay
from assay import pdf
from assay.cli import main
from assay.report import GATES, format_rate, read_report
from assay.report_schema import PairRef

DEMO = Path(assay.__file__).parent / "demo"


@pytest.fixture
def results(tmp_path):
    assert main(["report", str(DEMO), "--out", str(tmp_path)]) == 0
    return tmp_path


def section(html, name):
    return html.split(f'id="{name}"', 1)[1].split("</section>", 1)[0]


def test_every_metric_in_the_report_appears_in_the_html(results):
    report = read_report(results / "report.json")

    html = pdf.render_html(report)

    for gate in GATES:
        table = section(html, f"metrics-{gate}")
        for configuration in report.configurations:
            row = table.split(f'<th scope="row">{configuration.name}</th>', 1)[1]
            row = row.split("</tr>", 1)[0]
            for _, rate in configuration.gates[gate].metrics:
                assert format_rate(rate).strip() in row
    assert "<svg" in section(html, "plot")


def test_the_appendix_lists_the_pairs_behind_every_verdict_count(results):
    report = read_report(results / "report.json")

    html = pdf.render_html(report)

    cells = dict(re.findall(r'data-cell="([^"]+)">([^<]*)<', section(html, "appendix")))
    for configuration in report.configurations:
        for gate in GATES:
            for verdict, count in configuration.gates[gate].verdicts.items():
                text = cells[f"{configuration.name} {gate} {verdict}"]
                assert len(text.split(", ") if text != "none" else []) == count
    pair = report.pairs[0]
    verdict = pair.gates[report.headline_gate].verdict
    cell = cells[f"{pair.configuration} {report.headline_gate} {verdict}"]
    assert pair.key in cell.split(", ")


def test_unjudged_pairs_and_anomalies_are_listed_by_key_and_repeat(results):
    report = read_report(results / "report.json")
    configuration = report.configurations[0]
    configuration.repeats = 2
    configuration.unjudged = [PairRef(repeat=2, key="test_public/9-1")]
    anomalies = configuration.gates[report.headline_gate].anomalies

    appendix = section(pdf.render_html(report), "appendix")

    assert "Unjudged, left out: test_public/9-1 r2" in appendix
    assert f"{anomalies[0].key} r{anomalies[0].repeat}" in appendix
