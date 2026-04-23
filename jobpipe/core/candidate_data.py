from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from jobpipe.core.profile_pack import parse_profile_pack
from jobpipe.runtime.paths import primary_db_path, profile_dir, profile_pack_path, resume_json_path


# Marker used to detect already-stitched profile_pack blobs so we don't
# double-append siblings on repeat loads.
_SIBLINGS_MARKER = "<!-- PROFILE_SIBLINGS_APPLIED -->"

# Sibling files stitched onto profile_pack.md at load time.
# Order matters for prompt readability: constraints first, motivation second.
_PROFILE_SIBLINGS: tuple[tuple[str, str], ...] = (
    ("constraints.md", "Constraints (profile/constraints.md)"),
    ("motivation.md", "Motivation (profile/motivation.md)"),
)


def _apply_profile_siblings(base: str) -> str:
    """
    Append sibling files from profile_dir() (constraints.md, motivation.md)
    onto the profile_pack.md blob so triage + authoring see the full contract.

    Idempotent: returns base unchanged if already stitched (marker detected).
    No-op if siblings don't exist on disk.
    """
    if not base:
        return base
    if _SIBLINGS_MARKER in base:
        return base

    try:
        dir_ = profile_dir()
    except Exception:
        return base
    if not dir_.exists() or not dir_.is_dir():
        return base

    addenda: list[str] = []
    for fname, heading in _PROFILE_SIBLINGS:
        sibling = dir_ / fname
        if not sibling.exists():
            continue
        try:
            content = sibling.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if not content:
            continue
        addenda.append(f"\n\n---\n\n## {heading}\n\n{content}")

    if not addenda:
        return base

    return f"{base.rstrip()}\n{_SIBLINGS_MARKER}{''.join(addenda)}\n"


def default_candidate_id() -> str:
    return (os.environ.get("JOBPIPE_CANDIDATE_ID") or "default").strip() or "default"


def _normalize_path(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    text = str(path).strip()
    if not text:
        return None
    return Path(text)


def _load_active_profile_row(
    db_path: str | Path | None = None,
    candidate_id: str | None = None,
) -> dict[str, Any] | None:
    resolved_db = _normalize_path(db_path) or primary_db_path()
    resolved_candidate = (candidate_id or default_candidate_id()).strip() or "default"
    if not resolved_db.exists():
        return None

    try:
        conn = sqlite3.connect(str(resolved_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT profile_pack_md, profile_json, resume_json, updated_at
            FROM candidate_profiles
            WHERE candidate_id = ? AND is_active = 1
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            [resolved_candidate],
        ).fetchone()
        conn.close()
    except Exception:
        return None

    return dict(row) if row else None


def load_candidate_profile_pack(
    profile_path: str | Path | None = None,
    *,
    candidate_id: str | None = None,
    db_path: str | Path | None = None,
) -> str:
    """
    Resolve the candidate's profile_pack.md and stitch in sibling files
    (constraints.md, motivation.md) from profile_dir() at the bottom.

    Stitching is idempotent — a marker comment prevents double-append on
    repeat loads whether the base came from an explicit path, the primary
    DB, or the default disk fallback.
    """
    explicit_path = _normalize_path(profile_path)
    if explicit_path is not None:
        return _apply_profile_siblings(explicit_path.read_text(encoding="utf-8"))

    row = _load_active_profile_row(db_path=db_path, candidate_id=candidate_id)
    if row and str(row.get("profile_pack_md") or "").strip():
        return _apply_profile_siblings(str(row["profile_pack_md"]))

    fallback = profile_pack_path()
    if fallback.exists():
        return _apply_profile_siblings(fallback.read_text(encoding="utf-8"))

    raise FileNotFoundError(
        "No candidate profile found in the primary DB or at the default profile_pack.md path."
    )


def load_candidate_resume_json(
    resume_path: str | Path | None = None,
    *,
    candidate_id: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    explicit_path = _normalize_path(resume_path)
    if explicit_path is not None:
        return json.loads(explicit_path.read_text(encoding="utf-8"))

    row = _load_active_profile_row(db_path=db_path, candidate_id=candidate_id)
    if row:
        try:
            raw = str(row.get("resume_json") or "").strip()
            if raw:
                return json.loads(raw)
        except Exception:
            pass

    fallback = resume_json_path()
    if fallback.exists():
        try:
            return json.loads(fallback.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def load_candidate_profile_json(
    profile_path: str | Path | None = None,
    *,
    candidate_id: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    explicit_path = _normalize_path(profile_path)
    if explicit_path is not None:
        return parse_profile_pack(explicit_path.read_text(encoding="utf-8"))

    row = _load_active_profile_row(db_path=db_path, candidate_id=candidate_id)
    if row:
        try:
            raw = str(row.get("profile_json") or "").strip()
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
        except Exception:
            pass

        profile_pack_md = str(row.get("profile_pack_md") or "").strip()
        if profile_pack_md:
            return parse_profile_pack(profile_pack_md)

    fallback = profile_pack_path()
    if fallback.exists():
        return parse_profile_pack(fallback.read_text(encoding="utf-8"))

    return {}
