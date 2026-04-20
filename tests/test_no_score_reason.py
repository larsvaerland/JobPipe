from __future__ import annotations

from jobpipe.core.no_score_reason import derive_no_score_reason, format_no_score_reason


def test_derive_no_score_reason_for_triage_skip_before_scoring() -> None:
    reason = derive_no_score_reason(
        {
            "fit_score": None,
            "pivot_score": None,
            "skip_reason": "triage_llm",
            "triage_decision": "SKIP",
        }
    )
    assert reason == "triage_skip_before_scoring"
    assert format_no_score_reason(reason) == "skipped at triage before fit and pivot scoring"


def test_derive_no_score_reason_for_geo_filter_before_scoring() -> None:
    reason = derive_no_score_reason(
        {
            "fit_score": None,
            "pivot_score": None,
            "skip_reason": "geo",
            "triage_decision": "",
        }
    )
    assert reason == "geo_filtered_before_scoring"


def test_derive_no_score_reason_is_empty_when_score_is_present() -> None:
    reason = derive_no_score_reason(
        {
            "fit_score": 55,
            "pivot_score": None,
            "skip_reason": "triage_llm",
            "triage_decision": "SKIP",
        }
    )
    assert reason == ""
