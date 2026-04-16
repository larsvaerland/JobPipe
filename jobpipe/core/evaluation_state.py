from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _rows_as_dicts(
    sqlite_path: Path,
    sql: str,
    params: Iterable[Any] = (),
) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, list(params))]
    finally:
        conn.close()


def load_job_catalog(
    *,
    primary_db_path: Optional[Path],
    candidate_id: str,
) -> List[Dict[str, Any]]:
    """Load the latest job catalog from the primary DB."""
    if primary_db_path and primary_db_path.exists():
        try:
            rows = _rows_as_dicts(
                primary_db_path,
                """
                SELECT job_id, title, employer, work_city, final_decision
                FROM job_evaluations
                WHERE candidate_id = ?
                """,
                [candidate_id],
            )
            if rows:
                return rows
        except Exception:
            pass

    return []


def load_processed_job_ids(
    *,
    primary_db_path: Optional[Path],
    candidate_id: str,
) -> set[str]:
    """Return known job_ids from the primary DB."""
    return {
        str(row.get("job_id") or "").strip()
        for row in load_job_catalog(
            primary_db_path=primary_db_path,
            candidate_id=candidate_id,
        )
        if str(row.get("job_id") or "").strip()
    }
