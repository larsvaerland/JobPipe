from __future__ import annotations

import re
from typing import Any


def _clean_line(value: str) -> str:
    return value.strip().strip("\ufeff")


def _markdown_sections(text: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current_h2: dict[str, Any] | None = None
    current_h3: dict[str, Any] | None = None

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            current_h2 = {"title": line[3:].strip(), "lines": [], "subsections": []}
            sections.append(current_h2)
            current_h3 = None
            continue
        if line.startswith("### "):
            if current_h2 is None:
                continue
            current_h3 = {"title": line[4:].strip(), "lines": []}
            current_h2["subsections"].append(current_h3)
            continue
        if current_h3 is not None:
            current_h3["lines"].append(line)
        elif current_h2 is not None:
            current_h2["lines"].append(line)

    return sections


def _bullet_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        stripped = _clean_line(line)
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def _parse_label_value_bullets(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        out[key.strip().lower()] = value.strip()
    return out


def parse_profile_pack(profile_text: str) -> dict[str, Any]:
    sections = _markdown_sections(profile_text)
    parsed: dict[str, Any] = {
        "sections": [],
        "snapshot": {},
        "strategic_direction": "",
        "target_roles": {"primary": [], "secondary": [], "hard_no": []},
        "constraints": {"location_ok": [], "remote_hybrid": ""},
        "geo_whitelist_prefixes": [],
        "hard_no_roles": [],
        "keyword_signals": {"tier_a": [], "tier_b": []},
        "negative_keywords": [],
        "evidence_sections": [],
        "education": [],
    }

    for section in sections:
        title = section["title"]
        title_lower = title.lower()
        bullets = _bullet_items(section["lines"])
        section_record: dict[str, Any] = {
            "title": title,
            "body": "\n".join([line for line in section["lines"] if _clean_line(line)]).strip(),
            "bullets": bullets,
            "subsections": [],
        }

        for subsection in section["subsections"]:
            sub_bullets = _bullet_items(subsection["lines"])
            section_record["subsections"].append(
                {
                    "title": subsection["title"],
                    "body": "\n".join([line for line in subsection["lines"] if _clean_line(line)]).strip(),
                    "bullets": sub_bullets,
                }
            )

        parsed["sections"].append(section_record)

        if "candidate snapshot" in title_lower:
            snapshot = _parse_label_value_bullets(bullets)
            parsed["snapshot"] = {
                "name": snapshot.get("name", ""),
                "base": snapshot.get("base", ""),
                "languages": snapshot.get("languages", ""),
                "level": snapshot.get("level", ""),
                "positioning": snapshot.get("positioning", ""),
            }
            for subsection in section["subsections"]:
                if "strategic direction" in subsection["title"].lower():
                    body = "\n".join([line for line in subsection["lines"] if _clean_line(line)]).strip()
                    parsed["strategic_direction"] = body

        elif "target roles" in title_lower:
            for subsection in section["subsections"]:
                sub_title = subsection["title"].lower()
                items = _bullet_items(subsection["lines"])
                if "primary" in sub_title:
                    parsed["target_roles"]["primary"] = items
                elif "secondary" in sub_title:
                    parsed["target_roles"]["secondary"] = items
                elif "hard no" in sub_title:
                    parsed["target_roles"]["hard_no"] = items

        elif "must-haves" in title_lower:
            for subsection in section["subsections"]:
                sub_title = subsection["title"].lower()
                body = "\n".join([line for line in subsection["lines"] if _clean_line(line)]).strip()
                items = _bullet_items(subsection["lines"])
                if "location" in sub_title:
                    parsed["constraints"]["location_ok"] = items
                    parsed["constraints"]["remote_hybrid"] = body

        elif "geo whitelist" in title_lower:
            prefixes: list[str] = []
            for item in bullets:
                match = re.search(r'"([^"]+)"', item)
                if match:
                    prefixes.append(match.group(1))
                    continue
                prefixes.append(item.split()[0])
            parsed["geo_whitelist_prefixes"] = prefixes

        elif "hard no" in title_lower:
            parsed["hard_no_roles"] = bullets

        elif "keyword signals" in title_lower:
            for subsection in section["subsections"]:
                sub_title = subsection["title"].lower()
                items = _bullet_items(subsection["lines"])
                if "tier a" in sub_title:
                    parsed["keyword_signals"]["tier_a"] = items
                elif "tier b" in sub_title:
                    parsed["keyword_signals"]["tier_b"] = items

        elif "negative keywords" in title_lower:
            parsed["negative_keywords"] = bullets

        elif "evidence bullets" in title_lower:
            evidence_sections: list[dict[str, Any]] = []
            for subsection in section["subsections"]:
                evidence_sections.append(
                    {
                        "label": subsection["title"],
                        "bullets": _bullet_items(subsection["lines"]),
                    }
                )
            parsed["evidence_sections"] = evidence_sections

        elif title_lower.startswith("8)") or "education" in title_lower:
            parsed["education"] = bullets

    return parsed


__all__ = ["parse_profile_pack"]
