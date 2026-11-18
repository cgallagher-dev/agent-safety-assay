import json
from pathlib import Path

from assay import labels

DASHBOARD_LABELS = Path(__file__).parents[1] / "frontend" / "src" / "labels.json"


def test_the_dashboard_shows_the_same_words_symbols_and_colours():
    written = json.loads(DASHBOARD_LABELS.read_text(encoding="utf-8"))

    # Regenerate with: uv run python scripts/labels.py > frontend/src/labels.json
    assert written == labels.as_json()


def test_every_verdict_and_metric_has_a_label_and_a_known_tone():
    shown = labels.as_json()

    assert {v["tone"] for v in shown["verdicts"]} <= shown["tones"].keys()
    assert {m["tone"] for m in shown["metrics"]} <= shown["tones"].keys()
    assert sorted(shown["bar_order"]) == sorted(v["name"] for v in shown["verdicts"])
