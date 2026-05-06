"""Normalize Reactive Resume JSON export to JSON Resume-compatible shape."""
from __future__ import annotations

import re
from typing import Any

_MONTH_MAP: dict[str, str] = {
    # Norwegian
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "mai": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "okt": "10", "nov": "11", "des": "12",
    # English
    "may": "05", "oct": "10", "dec": "12",
}


def normalize_rr_to_jsonresume(
    data: dict[str, Any],
    *,
    include_hidden_work: bool = False,
) -> dict[str, Any]:
    """
    If data already has a top-level 'work' key, return as-is (JSON Resume).
    If data has 'sections', convert Reactive Resume format to JSON Resume shape.
    Always returns a dict safe to pass to derive_candidate_evidence_units().

    include_hidden_work:
        When False (default), hidden work/experience items are dropped — safe
        for CV rendering and evidence derivation.
        When True, hidden work items are included but tagged with
        ``"_rr_hidden": True`` so callers can treat them differently (e.g. the
        profile-layer builder creates RoleRecords for career context but skips
        evidence-atom generation, preventing off-target roles from polluting the
        triage/semantic-filter embedding).
        Skills and projects are always filtered to visible-only regardless of
        this flag — hidden skills/projects are typically off-target or stale.
    """
    if data.get("work") is not None:
        return data
    sections = data.get("sections")
    if not sections:
        return data
    result = dict(data)
    result["work"] = _rr_experience_to_work(
        sections.get("experience") or {},
        include_hidden=include_hidden_work,
    )
    result["education"] = _rr_education(sections.get("education") or {})
    result["skills"] = _rr_skills(sections.get("skills") or {})
    result["projects"] = _rr_projects(sections.get("projects") or {})
    return result


def _rr_experience_to_work(
    section: dict[str, Any],
    *,
    include_hidden: bool = False,
) -> list[dict[str, Any]]:
    result = []
    for item in section.get("items", []) or []:
        is_hidden = bool(item.get("hidden"))
        if is_hidden and not include_hidden:
            continue
        company = str(item.get("company") or "").strip()
        position = str(item.get("position") or "").strip()
        start_date, end_date = _parse_period(str(item.get("period") or ""))
        description_html = str(item.get("description") or "")
        summary = _strip_html(description_html)[:200]
        highlights = _extract_li_items(description_html)
        entry: dict[str, Any] = {
            "name": company,
            "company": company,
            "position": position,
            "startDate": start_date,
            "endDate": end_date,
            "summary": summary,
            "highlights": highlights,
        }
        if item.get("location"):
            entry["location"] = str(item["location"]).strip()
        if is_hidden:
            entry["_rr_hidden"] = True
        result.append(entry)
    return result


def _parse_period(period: str) -> tuple[str, str]:
    if not period.strip():
        return ("", "")
    parts = re.split(r"\s*[-–]\s*", period.strip(), maxsplit=1)
    start_date = _parse_month_year(parts[0].strip()) if parts else ""
    end_date = ""
    if len(parts) > 1:
        right = parts[1].strip().lower()
        if right in ("present", "nå", ""):
            end_date = ""
        else:
            end_date = _parse_month_year(parts[1].strip())
    return (start_date, end_date)


def _parse_month_year(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    tokens = text.split()
    month_num = ""
    year = ""
    for token in tokens:
        lower = token.lower()
        if lower in _MONTH_MAP:
            month_num = _MONTH_MAP[lower]
        elif re.fullmatch(r"\d{4}", token):
            year = token
    if year and month_num:
        return f"{year}-{month_num}"
    if year:
        return year
    return ""


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def _extract_li_items(html: str) -> list[str]:
    items = re.findall(r"<li[^>]*>(.*?)</li>", html, re.DOTALL | re.IGNORECASE)
    result = []
    for item in items:
        text = _strip_html(item).strip()
        if text:
            result.append(text)
    return result


def _rr_education(section: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for item in section.get("items", []) or []:
        if item.get("hidden"):
            continue
        result.append({
            "institution": str(item.get("institution") or "").strip(),
            "studyType": str(item.get("degree") or "").strip(),
            "area": str(item.get("area") or "").strip(),
            "endDate": str(item.get("date") or "").strip(),
        })
    return result


def _rr_skills(section: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for item in section.get("items", []) or []:
        if item.get("hidden"):
            continue
        keywords = item.get("keywords") or []
        result.append({
            "name": str(item.get("name") or "").strip(),
            "keywords": [str(k) for k in keywords if k],
        })
    return result


def _rr_projects(section: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for item in section.get("items", []) or []:
        if item.get("hidden"):
            continue
        result.append({
            "name": str(item.get("name") or "").strip(),
            "description": _strip_html(str(item.get("description") or "")),
        })
    return result
