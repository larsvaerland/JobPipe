from __future__ import annotations

import base64
import hashlib
import re
from typing import Any
from urllib.parse import unquote


_FINN_FINNKODE_RE = re.compile(
    r"finnkode(?:=|%3D|%253D)+(\d{7,10})",
    re.IGNORECASE,
)
_FINN_URL_RE = re.compile(
    r"finn\.no(?:/|%2F)(?:job|stillinger)(?:[^\"'\s]*?)(?:/|%2F)(?:ad\.html[?%]|annonse(?:/|%2F))(?:[^\"'\s]*?finnkode(?:=|%3D|%253D)+)?(\d{7,10})",
    re.IGNORECASE,
)
_LINKEDIN_URL_RE = re.compile(
    r"linkedin\.com(?:/|%2F)(?:comm(?:/|%2F))?jobs(?:/|%2F)view(?:/|%2F)(\d{6,15})",
    re.IGNORECASE,
)
_FINN_ALERT_SENDER_RE = re.compile(r"(?:@|\.)\bfinn\.no\b", re.IGNORECASE)
_FINN_ALERT_SUBJECT_RE = re.compile(
    r"ledige\s+stillinger|jobbvarsel|nye\s+jobber|stillinger\s+som\s+(kan\s+)?pass|"
    r"jobb.*anbefal|anbefal.*jobb|ny.*stilling.*for\s+deg",
    re.IGNORECASE,
)
_LINKEDIN_ALERT_SENDER_RE = re.compile(r"linkedin\.com", re.IGNORECASE)
_LINKEDIN_ALERT_SUBJECT_RE = re.compile(
    r"jobs?\s+(you\s+may|matching|for\s+you|we\s+think)|new\s+jobs?\s+matching|"
    r"job\s+alert|\d+\s+new\s+jobs?|recommended\s+jobs?|jobber\s+(for\s+deg|som\s+passer)|"
    r"jobs?\s+in\s+your\s+network",
    re.IGNORECASE,
)


def suggestion_external_id(entry: dict[str, Any]) -> str:
    return str(entry.get("finnkode") or entry.get("linkedin_job_id") or entry.get("external_id") or "").strip()


def suggestion_key(platform: str, external_id: str) -> str:
    return f"{platform}:{external_id}"


def suggestion_id(candidate_id: str, platform: str, external_id: str) -> str:
    raw = f"{candidate_id}|{platform}|{external_id}"
    return "suggestion_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def catalog_placeholder_job(
    platform: str,
    external_id: str,
    job_url: str,
    email_subject: str,
    suggested_at: str,
) -> dict[str, Any]:
    job_id = f"{platform}_{external_id}"
    return {
        "job_id": job_id,
        "title": "",
        "normalized_title": "",
        "employer_name": "",
        "description_html": "",
        "sourceurl": job_url,
        "link": job_url,
        "applicationUrl": "",
        "applicationDue": "",
        "work_city": "",
        "work_county": "",
        "work_postalCode": "",
        "sector": "",
        "status": "ACTIVE",
        "suggested_by_platform": True,
        "email_subject": email_subject,
        "suggested_at": suggested_at,
        "external_id": external_id,
        "finnkode": external_id if platform == "finn" else "",
        "linkedin_job_id": external_id if platform == "linkedin" else "",
    }


def status_source_refs(raw: dict[str, Any]) -> list[tuple[str, str]]:
    payload = raw.get("payload", {}) if isinstance(raw, dict) else {}
    urls = extract_job_urls_from_payload(payload)
    refs: list[tuple[str, str]] = []
    for item in extract_suggestion_jobs(urls):
        platform = str(item.get("platform") or "").strip()
        external_id = suggestion_external_id(item)
        if platform and external_id:
            refs.append((platform, external_id))
    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            deduped.append(ref)
    return deduped


def build_suggestion_queries(after_str: str) -> list[str]:
    return [
        f"from:finn.no after:{after_str}",
        f"from:jobbvarsel@finn.no after:{after_str}",
        f"from:varsler@finn.no after:{after_str}",
        f"from:jobalerts-noreply@linkedin.com after:{after_str}",
        f"from:jobs-noreply@linkedin.com after:{after_str}",
        f"from:linkedin.com (jobs OR stillinger OR job) after:{after_str}",
    ]


def detect_suggestion_platform(sender: str, subject: str) -> str | None:
    from_finn = _FINN_ALERT_SENDER_RE.search(sender)
    from_linkedin = _LINKEDIN_ALERT_SENDER_RE.search(sender)

    if not (from_finn or from_linkedin):
        return None
    if from_finn and _FINN_ALERT_SUBJECT_RE.search(subject):
        return "finn"
    if from_linkedin and _LINKEDIN_ALERT_SUBJECT_RE.search(subject):
        return "linkedin"
    if from_finn:
        return "finn"
    if from_linkedin:
        return "linkedin"
    return None


def extract_job_urls_from_payload(payload: dict[str, Any]) -> list[str]:
    urls: list[str] = []

    def _walk(part: dict[str, Any]) -> None:
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data", "")
        if data and mime in ("text/html", "text/plain"):
            try:
                text = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
                for match in re.finditer(r'href=["\']([^"\'>\s]+)', text, re.IGNORECASE):
                    urls.append(match.group(1))
                for match in re.finditer(r"https?://[^\s\"'<>\]]+", text):
                    urls.append(match.group(0))
            except Exception:
                pass
        for sub in part.get("parts", []):
            _walk(sub)

    _walk(payload)
    return urls


def extract_suggestion_jobs(urls: list[str]) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}

    for url in urls:
        try:
            url_decoded = unquote(url)
        except Exception:
            url_decoded = url

        for candidate in (url, url_decoded):
            for match in _FINN_FINNKODE_RE.finditer(candidate):
                fk = match.group(1)
                key = f"finn:{fk}"
                if key not in found:
                    found[key] = {
                        "platform": "finn",
                        "finnkode": fk,
                        "job_url": f"https://www.finn.no/job/fulltime/ad.html?finnkode={fk}",
                        "job_id_hint": f"finn_{fk}",
                    }

            for match in _FINN_URL_RE.finditer(candidate):
                if match.group(1):
                    fk = match.group(1)
                    key = f"finn:{fk}"
                    if key not in found:
                        found[key] = {
                            "platform": "finn",
                            "finnkode": fk,
                            "job_url": f"https://www.finn.no/job/fulltime/ad.html?finnkode={fk}",
                            "job_id_hint": f"finn_{fk}",
                        }

            for match in _LINKEDIN_URL_RE.finditer(candidate):
                lid = match.group(1)
                key = f"linkedin:{lid}"
                if key not in found:
                    found[key] = {
                        "platform": "linkedin",
                        "linkedin_job_id": lid,
                        "job_url": f"https://www.linkedin.com/jobs/view/{lid}",
                        "job_id_hint": f"linkedin_{lid}",
                    }

    return list(found.values())


__all__ = [
    "build_suggestion_queries",
    "catalog_placeholder_job",
    "detect_suggestion_platform",
    "extract_job_urls_from_payload",
    "extract_suggestion_jobs",
    "status_source_refs",
    "suggestion_external_id",
    "suggestion_id",
    "suggestion_key",
]
