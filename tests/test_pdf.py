import re
import shutil
import sys
from pathlib import Path

import pytest

import assay
from assay import pdf
from assay.cli import main
from assay.report import GATES, format_rate, load_report, read_report
from assay.report_schema import PairRef

DEMO = Path(assay.__file__).parent / "demo"


@pytest.fixture
def results(tmp_path):
    for name in ("evidence.jsonl", "run_config.json"):
        shutil.copy(DEMO / name, tmp_path / name)
    assert main(["report", str(tmp_path)]) == 0
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


def test_unjudged_pairs_are_listed_by_key_and_repeat(results):
    report = read_report(results / "report.json")
    configuration = report.configurations[0]
    configuration.repeats = 2
    configuration.unjudged = [PairRef(repeat=2, key="test_public/9-1")]

    appendix = section(pdf.render_html(report), "appendix")

    assert "Unjudged, left out: test_public/9-1 r2" in appendix


def test_without_the_pdf_extra_assay_pdf_says_how_to_install_it(results, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "weasyprint", None)

    assert main(["pdf", str(results)]) == 3
    assert "pip install 'agent-safety-assay[pdf]'" in capsys.readouterr().err


def test_assay_pdf_outside_a_results_directory_says_so(tmp_path, capsys):
    assert main(["pdf", str(tmp_path)]) == 5
    assert "Is it a results directory?" in capsys.readouterr().err


def test_assay_pdf_follows_the_evidence_not_an_older_report(results, monkeypatch):
    # report.json is only rebuilt by assay report, so after a rejudge it can be stale.
    (results / "report.json").write_text("{}")
    rendered = []
    monkeypatch.setattr(pdf, "write_pdf", lambda report, path: rendered.append(report))

    assert main(["pdf", str(results)]) == 0

    assert rendered[0].configurations == load_report(results).configurations


def test_assay_pdf_writes_a_pdf(results):
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        pytest.skip("WeasyPrint or its system libraries are not installed")

    assert main(["pdf", str(results)]) == 0
    assert (results / "report.pdf").read_bytes().startswith(b"%PDF")


def test_the_title_page_names_the_run_and_how_it_was_read(results):
    report = read_report(results / "report.json")

    title = section(pdf.render_html(report), "title")

    for text in [
        report.runs[0].run_id,
        report.runs[0].judge,
        "demo-small/off",
        "demo-small/on",
        "Structural (executed calls)",
        "execution first",
        report.assay_version,
    ]:
        assert text in title


def test_the_summary_says_each_result_in_plain_words(results):
    html = pdf.render_html(read_report(results / "report.json"))

    assert (
        "On the 20 tasks it showed it could do, it did the harmful version 12 times, refused "
        "5 times and failed 3 times. Of the 17 harmful tasks it didn&#39;t do, 9 had a benign "
        "twin that also failed, so they show inability, not safety."
    ) in section(html, "summary")


def test_every_page_has_a_footer_with_the_page_count_and_run(results):
    report = read_report(results / "report.json")

    html = pdf.render_html(report)

    assert "counter(page)" in html and "counter(pages)" in html
    assert f'"Run {report.runs[0].run_id}"' in html


def test_table_rows_never_split_across_pages(results):
    html = pdf.render_html(read_report(results / "report.json"))

    assert re.search(r"tr\s*\{[^}]*break-inside:\s*avoid", html)


def test_verdicts_carry_their_safety_colour_symbol_and_word(results):
    results_html = section(pdf.render_html(read_report(results / "report.json")), "results")

    assert re.search(r'class="[^"]*tone-harm[^"]*"[^>]*>\s*✗ Complied', results_html)
    assert re.search(r'class="[^"]*tone-safe[^"]*"[^>]*>\s*✓ Refused when capable', results_html)
    assert "#B42318" in pdf.render_html(read_report(results / "report.json"))


def test_sensitivity_readings_set_each_gate_beside_the_headline(results):
    report = read_report(results / "report.json")

    table = section(pdf.render_html(report), "sensitivity")

    configuration = report.configurations[0]
    row = table.split(f'<th scope="row">{configuration.name}, ccASR</th>', 1)[1]
    row = row.split("</tr>", 1)[0]
    for gate in GATES:
        assert format_rate(configuration.gates[gate].metrics.cc_asr).strip() in row


def test_other_counts_name_the_capped_pairs(results):
    report = read_report(results / "report.json")
    configuration = report.configurations[0]
    [capped] = configuration.limits["harmful"].capped

    html = pdf.render_html(report)

    other = html.split("Other counts", 1)[1]
    row = other.split(f'<th scope="row">{configuration.name}</th>', 1)[1]
    assert capped.key in row.split("</tr>", 1)[0]
