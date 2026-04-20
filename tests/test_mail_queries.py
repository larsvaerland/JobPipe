from __future__ import annotations

from jobpipe.connectors.mail.status import build_status_queries
from jobpipe.connectors.mail.suggestions import detect_suggestion_platform


def test_build_status_queries_contains_expected_patterns():
    queries = build_status_queries("2026/04/01")

    assert any('label:"Jobb/Jobbsøk/Status jobbsøknad"' in query for query in queries)
    assert any("subject:intervju" in query for query in queries)
    assert any("from:jobbnorge.no" in query for query in queries)


def test_detect_suggestion_platform_recognizes_finn_and_linkedin():
    assert detect_suggestion_platform("Varsler <jobbvarsel@finn.no>", "Ledige stillinger for deg") == "finn"
    assert detect_suggestion_platform("LinkedIn Jobs <jobs-noreply@linkedin.com>", "New jobs for you") == "linkedin"
    assert detect_suggestion_platform("Example AS <jobs@example.com>", "Interview invitation") is None
