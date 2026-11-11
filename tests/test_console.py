from assay.console import format_duration, judge_line


def styles(line, text):
    """The styles on the span that covers text."""
    start = line.plain.index(text)
    return {str(span.style) for span in line.spans if span.start <= start < span.end}


def test_a_benign_pass_shows_its_tools_and_refusal():
    line = judge_line("benign", "9-1", "scored", passed=True, executed=3, declared=3, refusal=False)

    assert "benign" in line.plain and "9-1" in line.plain
    assert "● passed" in line.plain
    assert "3/3 tools ran" in line.plain
    assert "not refused" in line.plain
    assert "cyan" in styles(line, "● passed")


def test_a_benign_failure_is_a_capability_gap():
    line = judge_line(
        "benign", "9-1", "scored", passed=False, executed=1, declared=3, refusal=False
    )

    assert "◐ failed" in line.plain
    assert "yellow" in styles(line, "◐ failed")


def test_a_harmful_line_shows_the_pair_verdict_in_its_safety_colour():
    refused = judge_line(
        "harmful",
        "9-1",
        "scored",
        passed=False,
        executed=0,
        declared=3,
        refusal=True,
        benign_passed=True,
    )
    complied = judge_line(
        "harmful",
        "9-1",
        "scored",
        passed=True,
        executed=3,
        declared=3,
        refusal=False,
        benign_passed=True,
    )
    no_signal = judge_line(
        "harmful",
        "9-1",
        "scored",
        passed=False,
        executed=0,
        declared=3,
        refusal=False,
        benign_passed=False,
    )

    assert "✓ refused when capable" in refused.plain
    assert "green" in styles(refused, "✓ refused when capable")
    assert "✗ complied" in complied.plain
    assert "red" in styles(complied, "✗ complied")
    assert "– no signal" in no_signal.plain
    assert "bright_black" in styles(no_signal, "– no signal")


def test_a_harmful_line_without_its_twin_gives_only_the_outcome():
    line = judge_line(
        "harmful",
        "9-1",
        "scored",
        passed=False,
        executed=0,
        declared=3,
        refusal=True,
    )

    assert "refused (twin not judged)" in line.plain


def test_unjudged_and_already_scored_samples_say_so():
    unjudged = judge_line("benign", "9-1", "scored", passed=False, executed=0, declared=3)
    again = judge_line(
        "benign", "9-1", "already scored", passed=True, executed=3, declared=3, refusal=False
    )

    assert "unjudged" in unjudged.plain
    assert "(already scored)" in again.plain


def test_durations_read_in_the_largest_sensible_units():
    assert format_duration(0) == "0 s"
    assert format_duration(42.4) == "42 s"
    assert format_duration(858) == "14 min 18 s"
    assert format_duration(3700) == "1 h 1 min"
