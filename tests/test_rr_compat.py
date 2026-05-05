from __future__ import annotations

from jobpipe.core.rr_compat import (
    _extract_li_items,
    _parse_period,
    _strip_html,
    normalize_rr_to_jsonresume,
)
from jobpipe.decision import derive_candidate_evidence_units


def test_normalize_passthrough_for_jsonresume_format() -> None:
    data = {
        "work": [{"name": "Acme", "position": "PM", "highlights": ["Led roadmap."]}],
        "education": [],
        "skills": [],
    }
    result = normalize_rr_to_jsonresume(data)
    assert result is data


def test_normalize_rr_experience_to_work() -> None:
    data = {
        "sections": {
            "experience": {
                "items": [
                    {
                        "company": "Acme Corp",
                        "position": "Product Manager",
                        "period": "Jan 2020 - Jan 2023",
                        "description": "<ul><li>Led roadmap prioritization.</li><li>Improved delivery by 30%.</li></ul>",
                        "hidden": False,
                    },
                    {
                        "company": "Hidden Corp",
                        "position": "Intern",
                        "period": "Jan 2019 - Jan 2020",
                        "description": "<ul><li>Should not appear.</li></ul>",
                        "hidden": True,
                    },
                ]
            }
        }
    }
    result = normalize_rr_to_jsonresume(data)
    work = result["work"]
    assert len(work) == 1
    entry = work[0]
    assert entry["name"] == "Acme Corp"
    assert entry["position"] == "Product Manager"
    assert "Led roadmap prioritization." in entry["highlights"]
    assert "Improved delivery by 30%." in entry["highlights"]
    assert len(entry["highlights"]) == 2


def test_strip_html_removes_tags_and_entities() -> None:
    html = "<p>Hello &amp; <b>world</b>&nbsp;here</p>"
    assert _strip_html(html) == "Hello & world here"


def test_parse_period_norwegian_months() -> None:
    start, end = _parse_period("Mai 2015 - Jan 2022")
    assert start == "2015-05"
    assert end == "2022-01"


def test_parse_period_present() -> None:
    start, end = _parse_period("Jan 2024 - present")
    assert start == "2024-01"
    assert end == ""


def test_derive_evidence_units_with_rr_format() -> None:
    rr_data = {
        "sections": {
            "experience": {
                "items": [
                    {
                        "company": "TechCo",
                        "position": "Senior Product Manager",
                        "period": "Feb 2020 - present",
                        "description": (
                            "<ul>"
                            "<li>Led roadmap prioritization across 3 teams.</li>"
                            "<li>Improved delivery predictability by 25%.</li>"
                            "</ul>"
                        ),
                        "hidden": False,
                    }
                ]
            },
            "skills": {
                "items": [
                    {"name": "Product Strategy", "keywords": ["roadmap", "OKR"], "hidden": False}
                ]
            },
            "education": {
                "items": [
                    {"institution": "BI", "degree": "Master", "area": "Management", "hidden": False}
                ]
            },
            "projects": {"items": []},
        }
    }
    units = derive_candidate_evidence_units(rr_data, candidate_id="test-rr")
    assert len(units) >= 1
    assert any(u.source_type == "work_highlight" for u in units)
