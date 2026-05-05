from __future__ import annotations

from jobpipe.cli.mark_status import normalize_shared_status


def test_normalize_shared_status_collapses_internal_stages() -> None:
    assert normalize_shared_status({"stages": ["shortlisted"]}) == "draft"
    assert normalize_shared_status({"stages": ["shortlisted", "called"]}) == "draft"
    assert normalize_shared_status({"stages": ["applied"]}) == "applied"
    assert normalize_shared_status({"stages": ["applied", "interview", "second_interview"]}) == "interview"


def test_normalize_shared_status_collapses_outcomes() -> None:
    assert normalize_shared_status({"outcome": "accepted"}) == "offer"
    assert normalize_shared_status({"outcome": "rejected"}) == "rejected"
    assert normalize_shared_status({"outcome": "dismissed"}) == "dismissed"


def test_normalize_shared_status_migrates_legacy_entries() -> None:
    assert normalize_shared_status({"status": "interview"}) == "interview"
    assert normalize_shared_status({"status": "shortlisted"}) == "draft"
