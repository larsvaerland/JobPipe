from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from jobpipe.core.paths import primary_db_path, profile_pack_path, resume_json_path


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
    explicit_path = _normalize_path(profile_path)
    if explicit_path is not None:
        return explicit_path.read_text(encoding="utf-8")

    row = _load_active_profile_row(db_path=db_path, candidate_id=candidate_id)
    if row and str(row.get("profile_pack_md") or "").strip():
        return str(row["profile_pack_md"])

    fallback = profile_pack_path()
    if fallback.exists():
        return fallback.read_text(encoding="utf-8")

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
