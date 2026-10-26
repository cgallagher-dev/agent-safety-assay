from fractions import Fraction
from itertools import combinations_with_replacement
from pathlib import Path

import assay
from assay.evidence import read_evidence
from assay.metrics import compute_metrics, summarise
from assay.outcomes import VERDICTS, Outcome, PairOutcome, Verdict, pair_outcomes

DEMO = Path(assay.__file__).parent / "demo"
CELLS = [(passed, outcome) for passed in (True, False) for outcome in Outcome]


def pair(benign_passed, outcome, number=1):
    return PairOutcome(
        configuration="demo-small/off",
        repeat=1,
        key=f"test_public/{number}-1",
        base_behaviour=f"test_public/{number}",
        category="Fraud",
        benign_passed=benign_passed,
        benign_refused=False,
        executed=outcome is Outcome.SUCCESS,
        refused=outcome is Outcome.REFUSAL,
        outcome=outcome,
        verdict=VERDICTS[(benign_passed, outcome)],
    )


def test_empty_denominators_are_undefined_not_zero():
    metrics = compute_metrics([pair(False, Outcome.FAILURE, 1), pair(False, Outcome.FAILURE, 2)])

    assert (metrics.benign_pass_rate.numerator, metrics.benign_pass_rate.denominator) == (0, 2)
    assert metrics.benign_pass_rate.value == 0
    assert metrics.cc_asr.value is None and metrics.cc_asr.undefined_reason
    assert metrics.cc_rr.value is None and metrics.cc_rr.undefined_reason
    assert metrics.cgr.value == 1


def test_cc_asr_falls_below_asr_only_with_an_anomaly():
    for size in range(1, 5):
        for cells in combinations_with_replacement(CELLS, size):
            outcomes = [pair(passed, outcome, n) for n, (passed, outcome) in enumerate(cells)]
            metrics = compute_metrics(outcomes)
            if metrics.cc_asr.value is None:
                continue
            below = Fraction(metrics.cc_asr.numerator, metrics.cc_asr.denominator) < Fraction(
                metrics.asr.numerator, metrics.asr.denominator
            )
            if below:
                assert (False, Outcome.SUCCESS) in cells, cells


def test_demo_fixture_matches_hand_computed_metrics():
    records = read_evidence(DEMO / "evidence.jsonl")
    outcomes = [o for o in pair_outcomes(records) if o.configuration == "demo-small/off"]

    summary = summarise(outcomes)

    rates = {
        name: (metric.numerator, metric.denominator)
        for name, metric in vars(summary.metrics).items()
    }
    assert rates == {
        "benign_pass_rate": (20, 30),
        "asr": (12, 30),
        "cc_asr": (11, 20),
        "cc_rr": (6, 17),
        "cgr": (9, 18),
    }
    assert summary.verdicts == {
        Verdict.COMPLIED: 11,
        Verdict.REFUSED_WHEN_CAPABLE: 6,
        Verdict.FAILED_WHEN_CAPABLE: 3,
        Verdict.REFUSED_UNTESTED: 3,
        Verdict.NO_SIGNAL: 6,
        Verdict.CAPABILITY_ANOMALY: 1,
    }
    assert summary.overlap == 1
    assert len(summary.anomalies) == 1
    assert summary.benign_refusals == 2
    assert (summary.cgr_benign_refused.numerator, summary.cgr_benign_refused.denominator) == (2, 9)
