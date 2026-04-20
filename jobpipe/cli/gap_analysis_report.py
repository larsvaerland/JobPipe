from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jobpipe.core.io import load_env_file

load_env_file(".env")

from jobpipe.runtime.paths import exports_root, primary_db_path
from jobpipe.core.primary_db import (
    connect_primary_db,
    ensure_candidate,
    insert_gap_evidence,
    replace_candidate_gap_state,
    upsert_capability_gap,
    upsert_gap_assessment,
)


DEFAULT_CANDIDATE_ID = (os.environ.get("JOBPIPE_CANDIDATE_ID") or "default").strip() or "default"
RELEVANT_DECISIONS = {"REVIEW_HIGH", "REVIEW_LOW"}

_LEADING_PATTERNS = [
    r"^(manglende erfaring med)\s+",
    r"^(manglende kunnskap om)\s+",
    r"^(manglende kompetanse innen)\s+",
    r"^(ingen dokumentert erfaring med)\s+",
    r"^(ingen spesifikk erfaring med)\s+",
    r"^(manglende)\s+",
    r"^(mangler)\s+",
    r"^(ingen)\s+",
    r"^(uten)\s+",
    r"^(experience with)\s+",
    r"^(experience in)\s+",
    r"^(knowledge of)\s+",
    r"^(expertise in)\s+",
    r"^(missing)\s+",
    r"^(lack of)\s+",
    r"^(no)\s+",
]


def _configure_stdout() -> None:
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _connect(path: Path) -> sqlite3.Connection:
    conn = connect_primary_db(path)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_json(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _clean_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip()).strip(" .,:;")


def _normalize_gap_text(text: str) -> str:
    normalized = _clean_text(text).lower()
    if not normalized:
        return ""
    for pattern in _LEADING_PATTERNS:
        normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized).strip(" .,:;")
    return normalized


def _gap_label(text: str) -> str:
    normalized = _normalize_gap_text(text)
    if not normalized:
        return ""
    return normalized[0].upper() + normalized[1:]


def _gap_key(text: str) -> str:
    normalized = _normalize_gap_text(text)
    if not normalized:
        return ""
    ascii_text = (
        unicodedata.normalize("NFKD", normalized)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    key = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
    return key or "gap"


def _gap_type(label: str) -> str:
    text = label.lower()
    if any(token in text for token in ["sertif", "certif", "license", "lisens"]):
        return "credential"
    if any(token in text for token in ["master", "degree", "utdanning", "education", "mba"]):
        return "education"
    if any(token in text for token in ["portfolio", "proof", "dokumentert", "evidence", "case"]):
        return "evidence"
    if any(token in text for token in ["domain", "sektor", "public sector", "procurement", "forsvar", "helse"]):
        return "domain"
    if any(token in text for token in ["ledelse", "leadership", "people leadership", "senior", "strategisk", "ownership"]):
        return "experience"
    return "skill"


def _time_to_close(gap_type: str, label: str) -> str:
    text = label.lower()
    if gap_type in {"credential", "evidence"}:
        return "low"
    if gap_type == "education":
        return "high"
    if gap_type == "experience":
        return "high"
    if any(token in text for token in ["ledelse", "leadership", "people", "senior", "strategisk"]):
        return "high"
    if gap_type == "domain":
        return "medium"
    return "medium"


def _severity_score(severity: str) -> float:
    return {
        "nice_to_have": 0.3,
        "meaningful_gap": 0.6,
        "material_blocker": 0.9,
    }.get(severity, 0.5)


def _decision_quality(decision: str, fit_score: Any) -> float:
    decision_weight = {
        "APPLY_STRONGLY": 0.95,
        "APPLY": 0.8,
        "REVIEW_HIGH": 0.65,
        "REVIEW_LOW": 0.4,
    }.get(str(decision or "").strip(), 0.1)
    try:
        fit_component = max(0.0, min(float(fit_score or 0) / 100.0, 1.0))
    except Exception:
        fit_component = 0.0
    return max(decision_weight, fit_component)


def _gap_id(candidate_id: str, gap_key: str) -> str:
    return f"gap_{hashlib.sha1(f'{candidate_id}|{gap_key}'.encode('utf-8')).hexdigest()[:20]}"


def _gap_evidence_id(candidate_id: str, gap_key: str, job_id: str, source: str, text: str) -> str:
    raw = f"{candidate_id}|{gap_key}|{job_id}|{source}|{_normalize_gap_text(text)}"
    return f"gap_ev_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:20]}"


def _extract_gap_candidates(row: dict[str, Any]) -> list[dict[str, Any]]:
    match = _safe_json(row.get("raw_match_json"))
    out: list[dict[str, Any]] = []

    for raw_text in match.get("gaps", []) or []:
        label = _gap_label(str(raw_text))
        key = _gap_key(str(raw_text))
        if not label or not key:
            continue
        out.append(
            {
                "gap_key": key,
                "label": label,
                "gap_type": _gap_type(label),
                "severity": "meaningful_gap",
                "evidence_source": "raw_match_json.gaps",
                "evidence_text": _clean_text(raw_text),
            }
        )

    for raw_text in match.get("hard_blockers", []) or []:
        label = _gap_label(str(raw_text))
        key = _gap_key(str(raw_text))
        if not label or not key:
            continue
        out.append(
            {
                "gap_key": key,
                "label": label,
                "gap_type": _gap_type(label),
                "severity": "material_blocker",
                "evidence_source": "raw_match_json.hard_blockers",
                "evidence_text": _clean_text(raw_text),
            }
        )

    return out


def _load_relevant_evaluations(conn: sqlite3.Connection, candidate_id: str, min_fit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT candidate_id, job_id, run_id, title, employer, fit_score, pivot_score,
               final_decision, recommendation_reason, raw_match_json, raw_pivot_json, updated_at
        FROM job_evaluations
        WHERE candidate_id = ?
          AND final_decision IN ('REVIEW_HIGH', 'REVIEW_LOW')
          AND COALESCE(fit_score, 0) >= ?
          AND COALESCE(closed_at, '') = ''
        ORDER BY fit_score DESC, updated_at DESC, job_id ASC
        """,
        [candidate_id, int(min_fit)],
    ).fetchall()
    return [dict(row) for row in rows]


def _priority(
    *,
    frequency_jobs: int,
    severity_score: float,
    unlock_score: float,
    opportunity_quality_score: float,
    confidence_score: float,
) -> str:
    if opportunity_quality_score < 0.35 or unlock_score < 0.25:
        return "ignore"
    if (
        frequency_jobs >= 2
        and severity_score >= 0.55
        and unlock_score >= 0.45
        and confidence_score >= 0.55
    ):
        return "close_now"
    return "monitor"


def build_gap_analysis_payload(
    db_path: Path,
    candidate_id: str,
    *,
    min_fit: int = 40,
) -> dict[str, Any]:
    conn = _connect(db_path)
    try:
        evaluations = _load_relevant_evaluations(conn, candidate_id, min_fit)
    finally:
        conn.close()

    grouped: dict[str, dict[str, Any]] = {}
    jobs_with_evidence: set[str] = set()

    for row in evaluations:
        evidence_items = _extract_gap_candidates(row)
        if evidence_items:
            jobs_with_evidence.add(str(row.get("job_id") or "").strip())
        for item in evidence_items:
            bucket = grouped.setdefault(
                item["gap_key"],
                {
                    "gap_key": item["gap_key"],
                    "label": item["label"],
                    "gap_type": item["gap_type"],
                    "evidence": [],
                },
            )
            bucket["evidence"].append(
                {
                    **item,
                    "job_id": str(row.get("job_id") or "").strip(),
                    "run_id": str(row.get("run_id") or "").strip(),
                    "evaluation_id": f"{row.get('run_id') or ''}:{row.get('job_id') or ''}",
                    "title": str(row.get("title") or "").strip(),
                    "employer": str(row.get("employer") or "").strip(),
                    "fit_score": row.get("fit_score"),
                    "pivot_score": row.get("pivot_score"),
                    "final_decision": str(row.get("final_decision") or "").strip(),
                    "recommendation_reason": str(row.get("recommendation_reason") or "").strip(),
                    "updated_at": str(row.get("updated_at") or "").strip(),
                }
            )

    gaps: list[dict[str, Any]] = []
    for gap_key, bucket in grouped.items():
        evidence = bucket["evidence"]
        unique_jobs = {str(e["job_id"]) for e in evidence if str(e["job_id"]).strip()}
        unique_sources = {str(e["evidence_source"]) for e in evidence if str(e["evidence_source"]).strip()}
        severity_values = [_severity_score(str(e["severity"])) for e in evidence]
        quality_values = [_decision_quality(str(e["final_decision"]), e.get("fit_score")) for e in evidence]

        frequency_jobs = len(unique_jobs)
        frequency_score = min(1.0, frequency_jobs / 5.0)
        severity_score_value = sum(severity_values) / max(len(severity_values), 1)
        opportunity_quality_score = sum(quality_values) / max(len(quality_values), 1)
        unlock_score = min(
            1.0,
            opportunity_quality_score * min(1.5, max(1.0, frequency_jobs / 2.0)),
        )
        confidence_score = min(
            0.95,
            0.2
            + min(0.35, 0.12 * frequency_jobs)
            + (0.25 * severity_score_value)
            + min(0.15, 0.05 * len(unique_sources)),
        )
        time_to_close = _time_to_close(bucket["gap_type"], bucket["label"])
        priority = _priority(
            frequency_jobs=frequency_jobs,
            severity_score=severity_score_value,
            unlock_score=unlock_score,
            opportunity_quality_score=opportunity_quality_score,
            confidence_score=confidence_score,
        )

        sample_jobs = [
            {
                "job_id": e["job_id"],
                "title": e["title"],
                "employer": e["employer"],
                "fit_score": e["fit_score"],
                "final_decision": e["final_decision"],
            }
            for e in sorted(
                evidence,
                key=lambda item: (
                    -float(item.get("fit_score") or 0),
                    str(item.get("title") or ""),
                    str(item.get("job_id") or ""),
                ),
            )[:5]
        ]

        gaps.append(
            {
                "gap_key": gap_key,
                "label": bucket["label"],
                "gap_type": bucket["gap_type"],
                "frequency_jobs": frequency_jobs,
                "frequency_score": round(frequency_score, 3),
                "severity_score": round(severity_score_value, 3),
                "unlock_score": round(unlock_score, 3),
                "opportunity_quality_score": round(opportunity_quality_score, 3),
                "time_to_close": time_to_close,
                "confidence_score": round(confidence_score, 3),
                "priority": priority,
                "sample_jobs": sample_jobs,
                "evidence": evidence,
            }
        )

    priority_rank = {"close_now": 0, "monitor": 1, "ignore": 2}
    gaps.sort(
        key=lambda item: (
            priority_rank.get(str(item.get("priority") or ""), 9),
            -float(item.get("unlock_score") or 0),
            -float(item.get("confidence_score") or 0),
            -int(item.get("frequency_jobs") or 0),
            str(item.get("label") or ""),
        )
    )

    return {
        "candidate_id": candidate_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "jobs_considered": len(evaluations),
        "jobs_with_gap_evidence": len(jobs_with_evidence),
        "gap_count": len(gaps),
        "gaps": gaps,
    }


def persist_gap_analysis(db_path: Path, payload: dict[str, Any]) -> None:
    candidate_id = str(payload.get("candidate_id") or "").strip()
    conn = _connect(db_path)
    try:
        ensure_candidate(conn, candidate_id=candidate_id)
        replace_candidate_gap_state(conn, candidate_id)
        updated_at = str(payload.get("generated_at") or datetime.now(timezone.utc).isoformat())

        for gap in payload.get("gaps", []):
            gap_key = str(gap.get("gap_key") or "").strip()
            if not gap_key:
                continue
            gap_id = _gap_id(candidate_id, gap_key)
            upsert_capability_gap(
                conn,
                {
                    "gap_id": gap_id,
                    "candidate_id": candidate_id,
                    "gap_key": gap_key,
                    "label": str(gap.get("label") or "").strip(),
                    "gap_type": str(gap.get("gap_type") or "").strip(),
                    "description": f"Generated from evaluation evidence for candidate {candidate_id}.",
                    "created_at": updated_at,
                    "updated_at": updated_at,
                },
            )

            for evidence in gap.get("evidence", []):
                insert_gap_evidence(
                    conn,
                    {
                        "gap_evidence_id": _gap_evidence_id(
                            candidate_id,
                            gap_key,
                            str(evidence.get("job_id") or ""),
                            str(evidence.get("evidence_source") or ""),
                            str(evidence.get("evidence_text") or ""),
                        ),
                        "candidate_id": candidate_id,
                        "gap_id": gap_id,
                        "job_id": str(evidence.get("job_id") or "").strip(),
                        "evaluation_id": str(evidence.get("evaluation_id") or "").strip(),
                        "run_id": str(evidence.get("run_id") or "").strip(),
                        "severity": str(evidence.get("severity") or "").strip(),
                        "evidence_source": str(evidence.get("evidence_source") or "").strip(),
                        "evidence_text": str(evidence.get("evidence_text") or "").strip(),
                        "evidence_json": {
                            "title": str(evidence.get("title") or "").strip(),
                            "employer": str(evidence.get("employer") or "").strip(),
                            "recommendation_reason": str(evidence.get("recommendation_reason") or "").strip(),
                            "updated_at": str(evidence.get("updated_at") or "").strip(),
                        },
                        "fit_score": evidence.get("fit_score"),
                        "pivot_score": evidence.get("pivot_score"),
                        "final_decision": str(evidence.get("final_decision") or "").strip(),
                        "created_at": updated_at,
                    },
                )

            upsert_gap_assessment(
                conn,
                {
                    "candidate_id": candidate_id,
                    "gap_id": gap_id,
                    "frequency_score": gap.get("frequency_score"),
                    "severity_score": gap.get("severity_score"),
                    "unlock_score": gap.get("unlock_score"),
                    "opportunity_quality_score": gap.get("opportunity_quality_score"),
                    "time_to_close": str(gap.get("time_to_close") or "").strip(),
                    "confidence_score": gap.get("confidence_score"),
                    "priority": str(gap.get("priority") or "").strip(),
                    "assessment_json": {
                        "jobs_considered": payload.get("jobs_considered"),
                        "jobs_with_gap_evidence": payload.get("jobs_with_gap_evidence"),
                        "frequency_jobs": gap.get("frequency_jobs"),
                        "sample_jobs": gap.get("sample_jobs", []),
                    },
                    "updated_at": updated_at,
                },
            )

        conn.commit()
    finally:
        conn.close()


def _render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Capability Gap Report")
    lines.append("")
    lines.append(f"- Candidate: `{payload.get('candidate_id')}`")
    lines.append(f"- Generated: `{payload.get('generated_at')}`")
    lines.append(f"- Adjacent jobs considered: `{payload.get('jobs_considered', 0)}`")
    lines.append(f"- Jobs with gap evidence: `{payload.get('jobs_with_gap_evidence', 0)}`")
    lines.append(f"- Gap concepts: `{payload.get('gap_count', 0)}`")
    lines.append("")

    gaps = payload.get("gaps", [])
    if not gaps:
        lines.append("No repeated capability gaps found in the current evaluation set.")
        return "\n".join(lines) + "\n"

    for section in ("close_now", "monitor", "ignore"):
        section_gaps = [gap for gap in gaps if gap.get("priority") == section]
        if not section_gaps:
            continue
        lines.append(f"## {section.replace('_', ' ').title()}")
        lines.append("")
        for gap in section_gaps:
            lines.append(f"### {gap.get('label')}")
            lines.append("")
            lines.append(f"- Type: `{gap.get('gap_type')}`")
            lines.append(f"- Frequency: `{gap.get('frequency_jobs')}` jobs")
            lines.append(f"- Severity score: `{gap.get('severity_score')}`")
            lines.append(f"- Unlock score: `{gap.get('unlock_score')}`")
            lines.append(f"- Opportunity quality: `{gap.get('opportunity_quality_score')}`")
            lines.append(f"- Confidence: `{gap.get('confidence_score')}`")
            lines.append(f"- Time to close: `{gap.get('time_to_close')}`")
            sample_jobs = gap.get("sample_jobs", [])
            if sample_jobs:
                lines.append("- Sample jobs:")
                for job in sample_jobs:
                    lines.append(
                        f"  - {job.get('title') or '-'} @ {job.get('employer') or '-'} "
                        f"(decision={job.get('final_decision') or '-'}, fit={job.get('fit_score') or '-'})"
                    )
            lines.append("")

    return "\n".join(lines) + "\n"


def run_gap_analysis(
    *,
    db_path: Path,
    candidate_id: str,
    out_md: Path,
    out_json: Path,
    min_fit: int = 40,
) -> dict[str, Any]:
    payload = build_gap_analysis_payload(db_path, candidate_id, min_fit=min_fit)
    persist_gap_analysis(db_path, payload)

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    _configure_stdout()
    ap = argparse.ArgumentParser(
        description="Analyze repeated capability gaps from current job evaluations and persist the result to the primary DB."
    )
    ap.add_argument("--db", default=str(primary_db_path()), help="Path to primary SQLite DB")
    ap.add_argument("--candidate-id", default=DEFAULT_CANDIDATE_ID, help="Candidate ID to analyze")
    ap.add_argument("--min-fit", type=int, default=40, help="Minimum fit score for jobs considered in the report")
    ap.add_argument("--out", default=str(exports_root() / "capability_gap_report.md"), help="Markdown report output path")
    ap.add_argument("--out-json", default=str(exports_root() / "capability_gap_report.json"), help="JSON report output path")
    args = ap.parse_args()

    payload = run_gap_analysis(
        db_path=Path(args.db),
        candidate_id=args.candidate_id,
        out_md=Path(args.out),
        out_json=Path(args.out_json),
        min_fit=args.min_fit,
    )
    print(f"Capability gap report exported: {args.out}")
    print(f"Structured JSON exported: {args.out_json}")
    print(
        f"  {payload.get('gap_count', 0)} gaps from "
        f"{payload.get('jobs_with_gap_evidence', 0)} jobs "
        f"({payload.get('jobs_considered', 0)} adjacent jobs considered)"
    )


if __name__ == "__main__":
    main()
