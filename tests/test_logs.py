import logging
from datetime import UTC, datetime

from assay.logs import new_run_id, run_log


def test_run_ids_sort_by_creation_time():
    earlier = new_run_id(datetime(2026, 11, 12, 21, 30, tzinfo=UTC))
    later = new_run_id(datetime(2026, 11, 12, 21, 31, tzinfo=UTC))

    assert earlier.startswith("20261112T2130Z-")
    assert sorted([later, earlier]) == [earlier, later]


def test_run_log_tags_every_line_with_the_run_id(tmp_path):
    log = logging.getLogger("assay.example")

    with run_log(tmp_path, "20261112T2130Z-7f3a"):
        log.debug("loaded 171 pairs")
        log.warning("judge retried sample 12")
    log.warning("after the run")

    lines = (tmp_path / "assay.log").read_text().splitlines()
    assert len(lines) == 2
    assert all("20261112T2130Z-7f3a" in line for line in lines)
