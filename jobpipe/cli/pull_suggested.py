"""Fetch full job content for platform-suggested jobs queued by scan_gmail --scan-suggestions.

Reads reports/suggested_jobs.jsonl, fetches each job's full content from FINN.no
(using BeautifulSoup4 to parse JSON-LD structured data), normalizes to pipeline
JSONL format, and appends to the suggested-lead connector staging file with
suggested_by_platform=true.

The pipeline triage stage treats suggested_by_platform=true as a calibration signal:
  - Semantic filter will not kill platform-suggested jobs (let the LLM decide)
  - signal 'platform_suggested' is recorded in triage output

IMPORTANT — anti-bot time guard:
  FINN flags unusual overnight request patterns. This script only runs between
  09:00 and 19:00 Oslo time. Random delays (3–10 seconds) between fetches.
  Max 20 jobs per run. Use --force-daytime to bypass during testing.

LinkedIn suggestions are queued but not yet auto-fetched (different scraping
approach needed). They appear in the output as not-yet-fetched entries.

Usage:
    python -m jobpipe.cli.pull_suggested                        # up to 20 FINN jobs
    python -m jobpipe.cli.pull_suggested --max 5 --dry-run      # preview only
    python -m jobpipe.cli.pull_suggested --force-daytime        # skip time guard
    python -m jobpipe.cli.pull_suggested --max 5 --verbose      # verbose + small batch
"""
from __future__ import annotations

import argparse
import io
import json
import random
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from jobpipe.core.lead_intake import append_leads
from jobpipe.core.paths import bootstrap_private_data, get_jobpipe_paths

def _fix_windows_stdout() -> None:
    """Wrap stdout with UTF-8 encoding on Windows to avoid cp1252 encode errors.

    Called from main() only — not at module level so that pytest capture works.
    """
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# BeautifulSoup4 (required — in requirements.txt)
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# Norwegian timezone — requires the `tzdata` package on Windows (pip install tzdata)
try:
    from zoneinfo import ZoneInfo
    _OSLO_TZ: Any = ZoneInfo("Europe/Oslo")
except Exception:
    # Fallback: CET (UTC+1). Off by 1h during CEST (summer) — close enough for time guard.
    _OSLO_TZ = timezone(timedelta(hours=1))

_DEFAULT_PATHS = get_jobpipe_paths()
DEFAULT_SUGGESTED_PATH = _DEFAULT_PATHS.suggested_jobs_path
DEFAULT_OUT_PATH = _DEFAULT_PATHS.leads_connector_path
DEFAULT_LEDGER_PATH = _DEFAULT_PATHS.ledger_sqlite_path

_DAYTIME_START = 9   # 09:00 Oslo — start of allowed window
_DAYTIME_END = 19    # 19:00 Oslo — end of allowed window

# Browser-like User-Agent to avoid easy bot detection
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# --- Time guard ---

def _is_daytime() -> bool:
    """Return True only between _DAYTIME_START and _DAYTIME_END Oslo time."""
    now = datetime.now(_OSLO_TZ)
    return _DAYTIME_START <= now.hour < _DAYTIME_END


def _oslo_time_str() -> str:
    return datetime.now(_OSLO_TZ).strftime("%H:%M")


# --- FINN job fetching ---

def _fetch_html(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch URL with browser-like headers. Returns HTML string or None on error."""
    headers = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "no-NO,no;q=0.9,en-US;q=0.8,en;q=0.7",
        # No Accept-Encoding — urlopen doesn't auto-decompress; omit for plain HTML.
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        "DNT": "1",
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            # Handle gzip/br by letting urllib decode (it doesn't auto-decode br,
            # but gzip is handled. For br we fall back gracefully.)
            try:
                return raw.decode("utf-8", errors="replace")
            except Exception:
                return raw.decode("latin-1", errors="replace")
    except (URLError, HTTPError, OSError, TimeoutError) as e:
        return None


def _extract_finn_ld(soup: "BeautifulSoup") -> Optional[dict]:
    """Extract JobPosting from JSON-LD <script> tags."""
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
            # FINN wraps JSON-LD in {"script:ld+json": {...}} — unwrap if present
            if isinstance(data, dict) and "script:ld+json" in data:
                data = data["script:ld+json"]
            # Handle array of LD objects
            entries = data if isinstance(data, list) else [data]
            for entry in entries:
                if isinstance(entry, dict) and entry.get("@type") == "JobPosting":
                    return entry
        except (json.JSONDecodeError, AttributeError):
            continue
    return None


def _extract_finn_next_data(soup: "BeautifulSoup") -> Optional[dict]:
    """Extract job data from Next.js __NEXT_DATA__ blob."""
    tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if not tag:
        return None
    try:
        next_data = json.loads(tag.string or "")
        props = next_data.get("props", {}).get("pageProps", {})
        # Try multiple known key patterns FINN has used
        for key in ("adData", "ad", "jobAd", "initialState", "data"):
            val = props.get(key)
            if val and isinstance(val, dict):
                return val
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def _iso_date(s: str) -> str:
    """Extract YYYY-MM-DD from ISO datetime string. Returns '' on failure."""
    if not s:
        return ""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(s))
    return m.group(1) if m else ""


def _normalize_ld(ld: dict, finnkode: str, source_url: str) -> dict:
    """Normalize a JSON-LD JobPosting object to pipeline format."""
    org = ld.get("hiringOrganization") or {}
    if isinstance(org, str):
        org = {"name": org}

    location = ld.get("jobLocation") or {}
    if isinstance(location, list):
        location = location[0] if location else {}
    address = location.get("address") if isinstance(location, dict) else {}
    if isinstance(address, str):
        city = address
        postal = ""
    elif isinstance(address, dict):
        city = address.get("addressLocality") or address.get("addressRegion") or ""
        postal = address.get("postalCode") or ""
    else:
        city = ""
        postal = ""

    return {
        "job_id": f"finn_{finnkode}",
        "title": ld.get("title") or "",
        "employer_name": org.get("name") or "",
        "description_html": ld.get("description") or "",
        "applicationDue": _iso_date(ld.get("validThrough") or ""),
        "work_city": city,
        "work_postalCode": postal,
        "sourceurl": ld.get("url") or source_url,
        "source": "finn_suggestion",
        "suggested_by_platform": True,
        "parse_method": "json_ld",
    }


def _normalize_next_data(ad: dict, finnkode: str, source_url: str) -> dict:
    """Normalize a FINN Next.js adData blob to pipeline format."""
    # Various key shapes seen in FINN's Next.js pages
    employer = ad.get("employer") or ad.get("company") or {}
    if isinstance(employer, str):
        employer_name = employer
    elif isinstance(employer, dict):
        employer_name = employer.get("name") or employer.get("companyName") or ""
    else:
        employer_name = ""

    location = ad.get("location") or ad.get("workPlace") or ""
    if isinstance(location, dict):
        city = location.get("city") or location.get("municipality") or ""
        postal = location.get("postalCode") or ""
    else:
        city = str(location)
        postal = ""

    return {
        "job_id": f"finn_{finnkode}",
        "title": ad.get("title") or ad.get("heading") or "",
        "employer_name": employer_name,
        "description_html": ad.get("description") or ad.get("body") or "",
        "applicationDue": _iso_date(ad.get("applicationDeadline") or ad.get("deadline") or ""),
        "work_city": city,
        "work_postalCode": postal,
        "sourceurl": source_url,
        "source": "finn_suggestion",
        "suggested_by_platform": True,
        "parse_method": "next_data",
    }


def _normalize_html_fallback(soup: "BeautifulSoup", finnkode: str, source_url: str) -> Optional[dict]:
    """Last-resort: extract title and employer from page title + meta tags."""
    title_tag = soup.find("title")
    raw_title = title_tag.get_text(strip=True) if title_tag else ""

    # FINN title format: "JOB TITLE - EMPLOYER | FINN.no"
    raw_title = re.sub(r"\s*\|\s*finn\.no\s*$", "", raw_title, flags=re.IGNORECASE).strip()
    employer = ""
    title = raw_title
    if " - " in raw_title:
        parts = raw_title.split(" - ", 1)
        title, employer = parts[0].strip(), parts[1].strip()

    if not title:
        return None

    # Meta description
    meta_desc = soup.find("meta", {"name": "description"})
    description = ""
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"]

    return {
        "job_id": f"finn_{finnkode}",
        "title": title,
        "employer_name": employer,
        "description_html": f"<p>{description}</p>" if description else "",
        "sourceurl": source_url,
        "source": "finn_suggestion",
        "suggested_by_platform": True,
        "parse_method": "html_fallback",
    }


_FINN_FINNKODE_RE = re.compile(r"[?&]finnkode=(\d+)")
_FINN_AD_PATH_RE = re.compile(r"/job/(?:fulltime|parttime|management)/ad\.html")


def _extract_finn_related_finnkodes(soup: "BeautifulSoup", current_finnkode: str) -> List[str]:
    """Extract finnkodes from the 'also suggested' / similar-jobs sidebar on a FINN job page.

    FINN renders related job links as standard anchor tags pointing to
    /job/fulltime/ad.html?finnkode=XXXXXX. They also appear in the Next.js
    __NEXT_DATA__ blob under keys like 'recommendations', 'similarAds', or 'relatedAds'.

    Returns a deduplicated list of finnkodes (excluding current_finnkode).
    """
    found: set[str] = set()

    # --- Strategy A: scan all <a href> for FINN job ad URLs ---
    for tag in soup.find_all("a", href=True):
        href = str(tag.get("href") or "")
        if _FINN_AD_PATH_RE.search(href):
            m = _FINN_FINNKODE_RE.search(href)
            if m:
                found.add(m.group(1))

    # --- Strategy B: Next.js __NEXT_DATA__ recommendations blob ---
    script = soup.find("script", {"id": "__NEXT_DATA__"})
    if script:
        try:
            next_data = json.loads(script.string or "")
            # Walk the whole pageProps dict looking for recommendation-like keys
            props = next_data.get("props", {}).get("pageProps", {})
            for key in ("recommendations", "similarAds", "relatedAds", "moreAds", "suggestedAds"):
                items = props.get(key)
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            # Accept both 'finnkode' and 'id' as fallback
                            fk = str(item.get("finnkode") or item.get("id") or "").strip()
                            if fk.isdigit():
                                found.add(fk)
        except (json.JSONDecodeError, AttributeError):
            pass

    found.discard(current_finnkode)
    return sorted(found)


def fetch_finn_job(
    finnkode: str,
    delay: float,
    verbose: bool = False,
    capture_related: bool = True,
) -> tuple[Optional[dict], List[str]]:
    """Fetch a FINN job ad. Returns (normalized pipeline dict or None, related finnkodes).

    Tries extraction in order: JSON-LD → Next.js __NEXT_DATA__ → HTML title fallback.
    If capture_related=True, also extracts related/similar job finnkodes from the page.
    """
    url = f"https://www.finn.no/job/fulltime/ad.html?finnkode={finnkode}"

    if verbose:
        print(f"    Sleeping {delay:.1f}s before fetch...")
    time.sleep(delay)

    html = _fetch_html(url)
    if html is None:
        return None, []

    soup = BeautifulSoup(html, "lxml")

    job: Optional[dict] = None

    # Strategy 1: JSON-LD structured data (most reliable)
    ld = _extract_finn_ld(soup)
    if ld:
        candidate = _normalize_ld(ld, finnkode, url)
        if candidate.get("title"):
            if verbose:
                print(f"    Parsed via JSON-LD")
            job = candidate

    # Strategy 2: Next.js __NEXT_DATA__ (used by newer FINN pages)
    if not job:
        ad_data = _extract_finn_next_data(soup)
        if ad_data:
            candidate = _normalize_next_data(ad_data, finnkode, url)
            if candidate.get("title"):
                if verbose:
                    print(f"    Parsed via Next.js data")
                job = candidate

    # Strategy 3: HTML title + meta fallback (minimal but better than nothing)
    if not job:
        candidate = _normalize_html_fallback(soup, finnkode, url)
        if candidate:
            if verbose:
                print(f"    Parsed via HTML fallback (minimal data)")
            job = candidate

    related: List[str] = []
    if capture_related:
        related = _extract_finn_related_finnkodes(soup, finnkode)
        if verbose and related:
            print(f"    Found {len(related)} related finnkodes: {related[:5]}")

    return job, related


# --- Ledger helpers ---

def _load_ledger_ids(ledger_path: Path) -> set:
    if not ledger_path.exists():
        return set()
    try:
        conn = sqlite3.connect(str(ledger_path))
        rows = conn.execute("SELECT job_id FROM ledger").fetchall()
        conn.close()
        return {r[0] for r in rows}
    except Exception as e:
        print(f"Warning: could not read ledger ({e}).", file=sys.stderr)
        return set()


def process_suggested_queue(
    *,
    suggested_path: Path,
    out_path: Path,
    ledger_path: Path,
    max_jobs: int = 20,
    min_delay: float = 3.0,
    max_delay: float = 9.0,
    force_daytime: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    if not BS4_AVAILABLE:
        raise RuntimeError(
            "beautifulsoup4 not installed. Run: pip install beautifulsoup4 lxml --break-system-packages"
        )

    if not force_daytime and not dry_run and not _is_daytime():
        return {
            "status": "blocked_by_time_guard",
            "oslo_time": _oslo_time_str(),
            "fetched": 0,
            "failed": 0,
            "remaining": 0,
        }

    if not suggested_path.exists():
        return {
            "status": "missing_queue",
            "fetched": 0,
            "failed": 0,
            "remaining": 0,
        }

    queue: List[dict] = []
    for line in suggested_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                queue.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    ledger_ids = _load_ledger_ids(ledger_path)
    finn_pending = [
        j for j in queue
        if j.get("platform") == "finn"
        and not j.get("fetched_at")
        and f"finn_{j.get('finnkode', '')}" not in ledger_ids
        and j.get("finnkode")
    ]
    linkedin_pending = [
        j for j in queue
        if j.get("platform") == "linkedin"
        and not j.get("fetched_at")
    ]

    if not finn_pending:
        return {
            "status": "queue_empty",
            "fetched": 0,
            "failed": 0,
            "remaining": 0,
            "linkedin_pending": len(linkedin_pending),
        }

    batch = finn_pending[:max_jobs]
    remaining_after = len(finn_pending) - len(batch)

    if dry_run:
        return {
            "status": "dry_run",
            "fetched": 0,
            "failed": 0,
            "remaining": remaining_after,
            "planned": len(batch),
            "linkedin_pending": len(linkedin_pending),
        }

    fetched: List[dict] = []
    fetched_finnkodes: set = set()
    failed_finnkodes: set = set()
    # Track all known finnkodes (queue + ledger) to avoid queuing duplicates as related
    known_finnkodes: set = {str(j.get("finnkode", "")) for j in queue} | {
        fk.replace("finn_", "") for fk in ledger_ids if fk.startswith("finn_")
    }
    related_queued: int = 0

    for suggestion in batch:
        finnkode = suggestion["finnkode"]
        delay = random.uniform(min_delay, max_delay)
        job, related_fks = fetch_finn_job(finnkode, delay=delay, verbose=verbose)
        if job:
            job["suggested_at"] = suggestion.get("suggested_at", "")
            job["email_subject"] = suggestion.get("email_subject", "")
            fetched.append(job)
            fetched_finnkodes.add(finnkode)
        else:
            failed_finnkodes.add(finnkode)

        # Queue related/similar finnkodes found on the page (deduplicated)
        if related_fks:
            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            new_related = [fk for fk in related_fks if fk not in known_finnkodes]
            if new_related:
                related_lines = [
                    json.dumps({
                        "platform": "finn",
                        "finnkode": fk,
                        "source": "finn_related",
                        "parent_finnkode": finnkode,
                        "suggested_at": now_iso,
                        "email_subject": "",
                    }, ensure_ascii=False)
                    for fk in new_related
                ]
                suggested_path.parent.mkdir(parents=True, exist_ok=True)
                with suggested_path.open("a", encoding="utf-8") as fh:
                    fh.write("\n".join(related_lines) + "\n")
                for fk in new_related:
                    known_finnkodes.add(fk)
                related_queued += len(new_related)
                if verbose:
                    print(f"    Queued {len(new_related)} related finnkodes from {finnkode}")

    appended = append_leads(
        out_path,
        fetched,
        intake_channel="gmail_recommendation_email",
        connector_source="finn_suggested",
        pretriage_policy="suggested_lead",
    )

    if fetched_finnkodes:
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        updated_lines: List[str] = []
        for line in suggested_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("finnkode") in fetched_finnkodes:
                    entry["fetched_at"] = now_iso
                updated_lines.append(json.dumps(entry, ensure_ascii=False))
            except json.JSONDecodeError:
                updated_lines.append(line)
        suggested_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

    return {
        "status": "ok",
        "fetched": len(appended),
        "failed": len(failed_finnkodes),
        "remaining": remaining_after,
        "related_queued": related_queued,
        "linkedin_pending": len(linkedin_pending),
    }


# --- Main ---

def main(argv: Optional[List[str]] = None) -> None:
    _fix_windows_stdout()
    ap = argparse.ArgumentParser(
        description=(
            "Fetch full job content for platform-suggested FINN jobs. "
            "Only runs 09:00-19:00 Oslo time to avoid bot-detection flags."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--data-root",
        default="",
        help=f"JobPipe user data root (default: {_DEFAULT_PATHS.data_root})",
    )
    ap.add_argument(
        "--suggested",
        default="",
        help=f"Path to suggested_jobs.jsonl (default: {DEFAULT_SUGGESTED_PATH})",
    )
    ap.add_argument(
        "--out",
        default="",
        help=f"Output JSONL path to append fetched jobs to (default: {DEFAULT_OUT_PATH})",
    )
    ap.add_argument(
        "--ledger",
        default="",
        help=f"Ledger SQLite for deduplication (default: {DEFAULT_LEDGER_PATH})",
    )
    ap.add_argument(
        "--max",
        type=int,
        default=20,
        help="Max FINN jobs to fetch per run (default: 20). Keeps daily volume low.",
    )
    ap.add_argument(
        "--min-delay",
        type=float,
        default=3.0,
        help="Min seconds between requests (default: 3.0)",
    )
    ap.add_argument(
        "--max-delay",
        type=float,
        default=9.0,
        help="Max seconds between requests (default: 9.0)",
    )
    ap.add_argument(
        "--force-daytime",
        action="store_true",
        help="Skip the Oslo time-of-day guard (for testing only)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview queue without fetching or writing",
    )
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args(argv)
    paths = get_jobpipe_paths(args.data_root or None)
    bootstrap_private_data(paths, include_artifacts=False)
    suggested_path = Path(args.suggested) if args.suggested else paths.suggested_jobs_path
    out_path = Path(args.out) if args.out else paths.leads_connector_path
    ledger_path = Path(args.ledger) if args.ledger else paths.ledger_sqlite_path

    try:
        result = process_suggested_queue(
            suggested_path=suggested_path,
            out_path=out_path,
            ledger_path=ledger_path,
            max_jobs=args.max,
            min_delay=args.min_delay,
            max_delay=args.max_delay,
            force_daytime=args.force_daytime,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if result["status"] == "blocked_by_time_guard":
        print(
            f"[time-guard] Current Oslo time: {result['oslo_time']}.\n"
            f"FINN scraping is only allowed between {_DAYTIME_START:02d}:00 and "
            f"{_DAYTIME_END:02d}:00 Oslo time to avoid bot-detection flags.\n"
            f"Run during the day or use --force-daytime to bypass (testing only)."
        )
        sys.exit(0)

    if result["status"] == "missing_queue":
        print(
            f"No suggestion queue found at {suggested_path}.\n"
            "Run:  python -m jobpipe.cli.scan_gmail --scan-suggestions"
        )
        sys.exit(0)

    if result["status"] == "queue_empty":
        print("No FINN jobs pending. Queue is up to date.")
        if result.get("linkedin_pending"):
            print(
                f"\n{result['linkedin_pending']} LinkedIn jobs are queued but require jobspy:\n"
                f"  python -m jobpipe.cli.pull_linkedin  (not yet implemented)\n"
                "  Or update the jobspy scraper manually and pipe output through pull_finn_ext.py"
            )
        sys.exit(0)

    if result["status"] == "dry_run":
        print(
            f"[DRY RUN] Mailbox recommendation flow is ready: "
            f"{result['planned']} FINN leads would enter suggested-lead connector staging, "
            f"{result['remaining']} would remain queued after this batch."
        )
        sys.exit(0)

    related_queued = result.get("related_queued", 0)
    print(
        f"\nSummary:\n"
        f"  Fetched:         {result['fetched']}\n"
        f"  Failed:          {result['failed']}\n"
        f"  Related queued:  {related_queued}  (similar jobs found on FINN pages, added to queue)\n"
        f"  Remaining in queue: {result['remaining']}\n"
    )
    if result["fetched"]:
        print(
            "Leads were appended to connector staging and will merge before filters/triage.\n"
            "Next step: run pipeline to process fetched suggestions:\n"
            "  .\\go.ps1 -DryRun   (test 2 jobs first)\n"
            "  .\\go.ps1           (full run)"
        )


if __name__ == "__main__":
    main()
