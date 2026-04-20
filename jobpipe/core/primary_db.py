from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping

from jobpipe.core.io import now_iso


SCHEMA_VERSION = "7"


def _json_text(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def connect_primary_db(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=30000;")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS candidates (
            candidate_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '',
            locale TEXT NOT NULL DEFAULT 'nb-NO',
            timezone TEXT NOT NULL DEFAULT 'Europe/Oslo',
            base_location TEXT NOT NULL DEFAULT '',
            seniority_label TEXT NOT NULL DEFAULT '',
            positioning_summary TEXT NOT NULL DEFAULT '',
            strategic_direction TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS candidate_profiles (
            profile_version_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            content_hash TEXT NOT NULL,
            profile_pack_md TEXT NOT NULL,
            profile_json TEXT NOT NULL,
            resume_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_candidate_profiles_candidate_active
            ON candidate_profiles(candidate_id, is_active);

        CREATE TABLE IF NOT EXISTS application_events (
            application_event_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_at TEXT NOT NULL,
            source TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_application_events_candidate_job
            ON application_events(candidate_id, job_id);
        CREATE INDEX IF NOT EXISTS idx_application_events_event_at
            ON application_events(event_at);

        CREATE TABLE IF NOT EXISTS application_summary (
            candidate_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            current_stage TEXT NOT NULL DEFAULT '',
            current_outcome TEXT NOT NULL DEFAULT '',
            effective_status TEXT NOT NULL DEFAULT '',
            last_event_at TEXT NOT NULL DEFAULT '',
            notes_latest TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (candidate_id, job_id),
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );

        CREATE TABLE IF NOT EXISTS candidate_calibration_settings (
            candidate_id TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'general',
            setting_key TEXT NOT NULL,
            value_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (candidate_id, scope, setting_key),
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_candidate_calibration_settings_candidate_scope
            ON candidate_calibration_settings(candidate_id, scope, updated_at);

        CREATE TABLE IF NOT EXISTS candidate_feedback_events (
            feedback_event_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            job_id TEXT NOT NULL DEFAULT '',
            evaluation_id TEXT NOT NULL DEFAULT '',
            feedback_type TEXT NOT NULL,
            feedback_value TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'manual',
            notes TEXT NOT NULL DEFAULT '',
            evidence_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_candidate_feedback_events_candidate_job
            ON candidate_feedback_events(candidate_id, job_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_candidate_feedback_events_candidate_type
            ON candidate_feedback_events(candidate_id, feedback_type, created_at);

        CREATE TABLE IF NOT EXISTS generated_documents (
            document_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            evaluation_id TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL,
            producer TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            storage_path TEXT NOT NULL DEFAULT '',
            preview_text TEXT NOT NULL DEFAULT '',
            document_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_generated_documents_candidate_job
            ON generated_documents(candidate_id, job_id);

        CREATE TABLE IF NOT EXISTS capability_gaps (
            gap_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            gap_key TEXT NOT NULL,
            label TEXT NOT NULL,
            gap_type TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_capability_gaps_candidate_gap_key
            ON capability_gaps(candidate_id, gap_key);

        CREATE TABLE IF NOT EXISTS gap_evidence (
            gap_evidence_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            gap_id TEXT NOT NULL,
            job_id TEXT NOT NULL DEFAULT '',
            evaluation_id TEXT NOT NULL DEFAULT '',
            run_id TEXT NOT NULL DEFAULT '',
            severity TEXT NOT NULL DEFAULT '',
            evidence_source TEXT NOT NULL DEFAULT '',
            evidence_text TEXT NOT NULL DEFAULT '',
            evidence_json TEXT NOT NULL DEFAULT '{}',
            fit_score INTEGER,
            pivot_score INTEGER,
            final_decision TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id),
            FOREIGN KEY(gap_id) REFERENCES capability_gaps(gap_id)
        );
        CREATE INDEX IF NOT EXISTS idx_gap_evidence_candidate_gap
            ON gap_evidence(candidate_id, gap_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_gap_evidence_candidate_job
            ON gap_evidence(candidate_id, job_id, created_at);

        CREATE TABLE IF NOT EXISTS gap_assessments (
            candidate_id TEXT NOT NULL,
            gap_id TEXT NOT NULL,
            frequency_score REAL,
            severity_score REAL,
            unlock_score REAL,
            opportunity_quality_score REAL,
            time_to_close TEXT NOT NULL DEFAULT '',
            confidence_score REAL,
            priority TEXT NOT NULL DEFAULT '',
            assessment_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (candidate_id, gap_id),
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id),
            FOREIGN KEY(gap_id) REFERENCES capability_gaps(gap_id)
        );
        CREATE INDEX IF NOT EXISTS idx_gap_assessments_candidate_priority
            ON gap_assessments(candidate_id, priority, updated_at);

        CREATE TABLE IF NOT EXISTS suggestion_leads (
            suggestion_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            external_id TEXT NOT NULL,
            job_url TEXT NOT NULL DEFAULT '',
            job_id_hint TEXT NOT NULL DEFAULT '',
            suggested_at TEXT NOT NULL DEFAULT '',
            email_subject TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'gmail_suggestions',
            status TEXT NOT NULL DEFAULT 'queued',
            fetched_at TEXT NOT NULL DEFAULT '',
            last_error TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_suggestion_leads_candidate_platform_external
            ON suggestion_leads(candidate_id, platform, external_id);
        CREATE INDEX IF NOT EXISTS idx_suggestion_leads_candidate_status
            ON suggestion_leads(candidate_id, status, platform, updated_at);

        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            dedupe_key TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            employer TEXT NOT NULL DEFAULT '',
            work_city TEXT NOT NULL DEFAULT '',
            work_county TEXT NOT NULL DEFAULT '',
            work_postalCode TEXT NOT NULL DEFAULT '',
            applicationDue TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            application_url TEXT NOT NULL DEFAULT '',
            description_text TEXT NOT NULL DEFAULT '',
            description_html TEXT NOT NULL DEFAULT '',
            sector TEXT NOT NULL DEFAULT '',
            job_metadata_json TEXT NOT NULL DEFAULT '{}',
            content_hash TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL DEFAULT '',
            last_seen_at TEXT NOT NULL DEFAULT '',
            closed_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_dedupe_key
            ON jobs(dedupe_key);
        CREATE INDEX IF NOT EXISTS idx_jobs_employer_title
            ON jobs(employer, title);

        CREATE TABLE IF NOT EXISTS job_source_records (
            source_record_id TEXT PRIMARY KEY,
            source_name TEXT NOT NULL,
            source_job_key TEXT NOT NULL,
            job_id TEXT NOT NULL,
            seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            source_url TEXT NOT NULL DEFAULT '',
            work_city TEXT NOT NULL DEFAULT '',
            work_county TEXT NOT NULL DEFAULT '',
            work_postalCode TEXT NOT NULL DEFAULT '',
            applicationDue TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL DEFAULT '',
            raw_payload_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(job_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_job_source_records_source_key
            ON job_source_records(source_name, source_job_key);
        CREATE INDEX IF NOT EXISTS idx_job_source_records_job_id
            ON job_source_records(job_id, is_active, last_seen_at);

        CREATE TABLE IF NOT EXISTS job_replay_inputs (
            job_id TEXT PRIMARY KEY,
            source_name TEXT NOT NULL DEFAULT '',
            source_job_key TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            application_url TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            employer TEXT NOT NULL DEFAULT '',
            work_city TEXT NOT NULL DEFAULT '',
            work_county TEXT NOT NULL DEFAULT '',
            work_postalCode TEXT NOT NULL DEFAULT '',
            applicationDue TEXT NOT NULL DEFAULT '',
            description_text TEXT NOT NULL DEFAULT '',
            description_html TEXT NOT NULL DEFAULT '',
            input_payload_json TEXT NOT NULL DEFAULT '{}',
            input_hash TEXT NOT NULL DEFAULT '',
            captured_from_run_id TEXT NOT NULL DEFAULT '',
            captured_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_job_replay_inputs_source_key
            ON job_replay_inputs(source_name, source_job_key, updated_at DESC);

        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            profile_version_id TEXT NOT NULL DEFAULT '',
            config_version TEXT NOT NULL DEFAULT '',
            jobs_path TEXT NOT NULL DEFAULT '',
            max_jobs INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT '',
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL DEFAULT '',
            jobs_seen INTEGER NOT NULL DEFAULT 0,
            jobs_failed INTEGER NOT NULL DEFAULT 0,
            source_batch_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_pipeline_runs_candidate_started
            ON pipeline_runs(candidate_id, started_at DESC);

        CREATE TABLE IF NOT EXISTS job_evaluations (
            candidate_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            run_id TEXT NOT NULL DEFAULT '',
            run_mtime REAL NOT NULL DEFAULT 0,
            run_seen_at TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            employer TEXT NOT NULL DEFAULT '',
            sector TEXT NOT NULL DEFAULT '',
            work_city TEXT NOT NULL DEFAULT '',
            work_county TEXT NOT NULL DEFAULT '',
            work_postalCode TEXT NOT NULL DEFAULT '',
            applicationDue TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            application_url TEXT NOT NULL DEFAULT '',
            triage_decision TEXT NOT NULL DEFAULT '',
            triage_confidence REAL,
            triage_explanation TEXT NOT NULL DEFAULT '',
            triage_signals TEXT NOT NULL DEFAULT '',
            reverse_decision TEXT NOT NULL DEFAULT '',
            reverse_confidence REAL,
            reverse_rationale TEXT NOT NULL DEFAULT '',
            fit_score INTEGER,
            pivot_score INTEGER,
            final_decision TEXT NOT NULL DEFAULT '',
            final_confidence REAL,
            recommendation_reason TEXT NOT NULL DEFAULT '',
            cv_focus TEXT NOT NULL DEFAULT '',
            feedback_flags TEXT NOT NULL DEFAULT '',
            description_snip TEXT NOT NULL DEFAULT '',
            skip_reason TEXT NOT NULL DEFAULT '',
            raw_index_json TEXT NOT NULL DEFAULT '',
            raw_match_json TEXT NOT NULL DEFAULT '',
            raw_pivot_json TEXT NOT NULL DEFAULT '',
            raw_moderator_json TEXT NOT NULL DEFAULT '',
            closed_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (candidate_id, job_id),
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_job_evaluations_candidate_decision
            ON job_evaluations(candidate_id, final_decision, applicationDue);

        CREATE TABLE IF NOT EXISTS job_run_events (
            candidate_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            run_mtime REAL NOT NULL DEFAULT 0,
            seen_at TEXT NOT NULL DEFAULT '',
            final_decision TEXT NOT NULL DEFAULT '',
            final_confidence REAL,
            triage_decision TEXT NOT NULL DEFAULT '',
            triage_confidence REAL,
            fit_score INTEGER,
            pivot_score INTEGER,
            applicationDue TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            employer TEXT NOT NULL DEFAULT '',
            work_city TEXT NOT NULL DEFAULT '',
            work_county TEXT NOT NULL DEFAULT '',
            work_postalCode TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            application_url TEXT NOT NULL DEFAULT '',
            raw_index_json TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (candidate_id, run_id, job_id),
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_job_run_events_candidate_job
            ON job_run_events(candidate_id, job_id, run_mtime);

        CREATE TABLE IF NOT EXISTS job_claims (
            job_id TEXT NOT NULL,
            claim_id TEXT NOT NULL,
            source_record_id TEXT NOT NULL DEFAULT '',
            claim_type TEXT NOT NULL,
            claim_strength TEXT NOT NULL,
            claim_subject_type TEXT NOT NULL,
            normalized_key TEXT NOT NULL DEFAULT '',
            normalized_label TEXT NOT NULL DEFAULT '',
            claim_text TEXT NOT NULL DEFAULT '',
            source_basis TEXT NOT NULL DEFAULT '',
            source_section TEXT NOT NULL DEFAULT '',
            evidence_span TEXT NOT NULL DEFAULT '',
            confidence_score REAL,
            importance_score REAL,
            claim_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (job_id, claim_id)
        );
        CREATE INDEX IF NOT EXISTS idx_job_claims_job_importance
            ON job_claims(job_id, importance_score DESC, updated_at DESC);

        CREATE TABLE IF NOT EXISTS job_selection_signals (
            job_id TEXT NOT NULL,
            signal_id TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            signal_label TEXT NOT NULL,
            selection_stage TEXT NOT NULL,
            signal_strength TEXT NOT NULL,
            normalized_key TEXT NOT NULL DEFAULT '',
            evidence_required TEXT NOT NULL DEFAULT '',
            confidence_score REAL,
            importance_score REAL,
            source_basis TEXT NOT NULL DEFAULT '',
            signal_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (job_id, signal_id)
        );
        CREATE INDEX IF NOT EXISTS idx_job_selection_signals_job_stage
            ON job_selection_signals(job_id, selection_stage, importance_score DESC);

        CREATE TABLE IF NOT EXISTS job_selection_assessments (
            candidate_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            evaluation_id TEXT NOT NULL DEFAULT '',
            structural_pass INTEGER NOT NULL DEFAULT 0,
            screenability_score INTEGER,
            title_continuity_score INTEGER,
            domain_continuity_score INTEGER,
            ambiguity_risk_score INTEGER,
            evidence_burden_score INTEGER,
            selection_risk_level TEXT NOT NULL DEFAULT '',
            likely_rejection_vectors_json TEXT NOT NULL DEFAULT '[]',
            mitigation_moves_json TEXT NOT NULL DEFAULT '[]',
            assessment_reason TEXT NOT NULL DEFAULT '',
            assessment_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (candidate_id, job_id),
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_job_selection_assessments_candidate_risk
            ON job_selection_assessments(candidate_id, selection_risk_level, updated_at DESC);

        CREATE TABLE IF NOT EXISTS job_decision_tables (
            candidate_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            evaluation_id TEXT NOT NULL DEFAULT '',
            can_do_level TEXT NOT NULL DEFAULT '',
            can_do_score INTEGER,
            can_do_reason TEXT NOT NULL DEFAULT '',
            can_do_supporting_points_json TEXT NOT NULL DEFAULT '[]',
            can_do_risk_points_json TEXT NOT NULL DEFAULT '[]',
            can_get_level TEXT NOT NULL DEFAULT '',
            can_get_score INTEGER,
            can_get_reason TEXT NOT NULL DEFAULT '',
            can_get_supporting_points_json TEXT NOT NULL DEFAULT '[]',
            can_get_risk_points_json TEXT NOT NULL DEFAULT '[]',
            should_want_level TEXT NOT NULL DEFAULT '',
            should_want_score INTEGER,
            should_want_reason TEXT NOT NULL DEFAULT '',
            should_want_supporting_points_json TEXT NOT NULL DEFAULT '[]',
            should_want_risk_points_json TEXT NOT NULL DEFAULT '[]',
            can_explain_level TEXT NOT NULL DEFAULT '',
            can_explain_score INTEGER,
            can_explain_reason TEXT NOT NULL DEFAULT '',
            can_explain_supporting_points_json TEXT NOT NULL DEFAULT '[]',
            can_explain_risk_points_json TEXT NOT NULL DEFAULT '[]',
            act_now TEXT NOT NULL DEFAULT '',
            confidence_score REAL,
            table_reason TEXT NOT NULL DEFAULT '',
            next_moves_json TEXT NOT NULL DEFAULT '[]',
            decision_table_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (candidate_id, job_id),
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_job_decision_tables_candidate_action
            ON job_decision_tables(candidate_id, act_now, updated_at DESC);

        CREATE TABLE IF NOT EXISTS candidate_evidence_units (
            candidate_id TEXT NOT NULL,
            evidence_unit_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_ref TEXT NOT NULL DEFAULT '',
            role_family_tags_json TEXT NOT NULL DEFAULT '[]',
            domain_tags_json TEXT NOT NULL DEFAULT '[]',
            capability_tags_json TEXT NOT NULL DEFAULT '[]',
            outcome_tags_json TEXT NOT NULL DEFAULT '[]',
            canonical_text TEXT NOT NULL DEFAULT '',
            rewrite_policy TEXT NOT NULL DEFAULT '',
            evidence_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (candidate_id, evidence_unit_id),
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_candidate_evidence_units_candidate_source
            ON candidate_evidence_units(candidate_id, source_type, updated_at DESC);

        CREATE TABLE IF NOT EXISTS candidate_narrative_profiles (
            narrative_version_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            core_identity_json TEXT NOT NULL DEFAULT '[]',
            future_direction_json TEXT NOT NULL DEFAULT '[]',
            motivation_themes_json TEXT NOT NULL DEFAULT '[]',
            pivot_thesis_json TEXT NOT NULL DEFAULT '[]',
            proof_themes_json TEXT NOT NULL DEFAULT '[]',
            story_boundaries_json TEXT NOT NULL DEFAULT '[]',
            tone_rules_json TEXT NOT NULL DEFAULT '[]',
            narrative_summary TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_candidate_narrative_profiles_candidate_active
            ON candidate_narrative_profiles(candidate_id, is_active, updated_at DESC);

        CREATE TABLE IF NOT EXISTS narrative_fragments (
            fragment_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            narrative_version_id TEXT NOT NULL,
            fragment_type TEXT NOT NULL,
            audience TEXT NOT NULL,
            canonical_text TEXT NOT NULL DEFAULT '',
            rewrite_policy TEXT NOT NULL DEFAULT '',
            fragment_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_narrative_fragments_candidate_version
            ON narrative_fragments(candidate_id, narrative_version_id, fragment_type);

        CREATE TABLE IF NOT EXISTS narrative_evidence_links (
            narrative_link_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            narrative_version_id TEXT NOT NULL,
            evidence_unit_id TEXT NOT NULL,
            link_type TEXT NOT NULL,
            strength_score REAL,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_narrative_evidence_links_candidate_version
            ON narrative_evidence_links(candidate_id, narrative_version_id, evidence_unit_id);

        CREATE TABLE IF NOT EXISTS job_narrative_assessments (
            candidate_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            evaluation_id TEXT NOT NULL DEFAULT '',
            narrative_version_id TEXT NOT NULL DEFAULT '',
            direction_fit_score INTEGER,
            motivation_fit_score INTEGER,
            pivot_credibility_score INTEGER,
            story_strength_score INTEGER,
            misalignment_flags_json TEXT NOT NULL DEFAULT '[]',
            assessment_reason TEXT NOT NULL DEFAULT '',
            motivation_brief TEXT NOT NULL DEFAULT '',
            assessment_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (candidate_id, job_id),
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_job_narrative_assessments_candidate_story
            ON job_narrative_assessments(candidate_id, story_strength_score DESC, updated_at DESC);

        CREATE TABLE IF NOT EXISTS watchlists (
            watchlist_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            watch_type TEXT NOT NULL,
            watch_key TEXT NOT NULL,
            watch_label TEXT NOT NULL DEFAULT '',
            watch_config_json TEXT NOT NULL DEFAULT '{}',
            is_active INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlists_candidate_type_key
            ON watchlists(candidate_id, watch_type, watch_key);

        CREATE TABLE IF NOT EXISTS change_events (
            change_event_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            watchlist_id TEXT NOT NULL DEFAULT '',
            job_id TEXT NOT NULL DEFAULT '',
            change_type TEXT NOT NULL,
            change_summary TEXT NOT NULL DEFAULT '',
            change_json TEXT NOT NULL DEFAULT '{}',
            materiality TEXT NOT NULL DEFAULT '',
            detected_at TEXT NOT NULL DEFAULT '',
            reviewed_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        );
        CREATE INDEX IF NOT EXISTS idx_change_events_candidate_detected
            ON change_events(candidate_id, detected_at DESC);
        CREATE INDEX IF NOT EXISTS idx_change_events_candidate_job
            ON change_events(candidate_id, job_id, detected_at DESC);
        """
    )

    ts = now_iso()
    conn.execute(
        """
        INSERT INTO schema_meta (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        ["schema_version", SCHEMA_VERSION, ts],
    )
    return conn


def _upsert(
    conn: sqlite3.Connection,
    table: str,
    row: Mapping[str, Any],
    key_columns: Iterable[str],
) -> None:
    names = list(row.keys())
    placeholders = ", ".join(["?"] * len(names))
    key_set = set(key_columns)
    assignments = ", ".join([f"{name}=excluded.{name}" for name in names if name not in key_set])
    sql = (
        f"INSERT INTO {table} ({', '.join(names)}) VALUES ({placeholders}) "
        f"ON CONFLICT({', '.join(key_columns)}) DO UPDATE SET {assignments};"
    )
    conn.execute(sql, [row.get(name) for name in names])


def upsert_candidate(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    _upsert(conn, "candidates", row, ["candidate_id"])


def ensure_candidate(
    conn: sqlite3.Connection,
    candidate_id: str,
    display_name: str = "Default Candidate",
    email: str = "",
    locale: str = "nb-NO",
    timezone: str = "Europe/Oslo",
) -> None:
    exists = conn.execute(
        "SELECT 1 FROM candidates WHERE candidate_id = ? LIMIT 1",
        [candidate_id],
    ).fetchone()
    if exists:
        return

    ts = now_iso()
    upsert_candidate(
        conn,
        {
            "candidate_id": candidate_id,
            "display_name": display_name,
            "email": email,
            "locale": locale,
            "timezone": timezone,
            "base_location": "",
            "seniority_label": "",
            "positioning_summary": "",
            "strategic_direction": "",
            "is_active": 1,
            "created_at": ts,
            "updated_at": ts,
        },
    )


def upsert_candidate_profile(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        "UPDATE candidate_profiles SET is_active = 0, updated_at = ? WHERE candidate_id = ?",
        [row["updated_at"], row["candidate_id"]],
    )
    _upsert(conn, "candidate_profiles", row, ["profile_version_id"])


def replace_imported_application_state(
    conn: sqlite3.Connection,
    candidate_id: str,
    events: list[Mapping[str, Any]],
    summaries: list[Mapping[str, Any]],
) -> None:
    conn.execute(
        "DELETE FROM application_events WHERE candidate_id = ? AND source LIKE 'state_import:%'",
        [candidate_id],
    )
    conn.execute("DELETE FROM application_summary WHERE candidate_id = ?", [candidate_id])

    for row in events:
        payload = dict(row)
        payload["metadata_json"] = _json_text(payload.get("metadata_json"))
        _upsert(conn, "application_events", payload, ["application_event_id"])

    for row in summaries:
        _upsert(conn, "application_summary", row, ["candidate_id", "job_id"])


def insert_application_event(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    payload = dict(row)
    payload["metadata_json"] = _json_text(payload.get("metadata_json"))
    _upsert(conn, "application_events", payload, ["application_event_id"])


def upsert_application_summary(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    _upsert(conn, "application_summary", row, ["candidate_id", "job_id"])


def upsert_candidate_calibration_setting(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    payload = dict(row)
    payload["value_json"] = _json_text(payload.get("value_json"))
    _upsert(conn, "candidate_calibration_settings", payload, ["candidate_id", "scope", "setting_key"])


def insert_candidate_feedback_event(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    payload = dict(row)
    payload["evidence_json"] = _json_text(payload.get("evidence_json"))
    _upsert(conn, "candidate_feedback_events", payload, ["feedback_event_id"])


def delete_application_tracking(conn: sqlite3.Connection, candidate_id: str, job_id: str) -> None:
    conn.execute(
        "DELETE FROM application_events WHERE candidate_id = ? AND job_id = ?",
        [candidate_id, job_id],
    )
    conn.execute(
        "DELETE FROM application_summary WHERE candidate_id = ? AND job_id = ?",
        [candidate_id, job_id],
    )


def insert_generated_document(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    payload = dict(row)
    payload["document_json"] = _json_text(payload.get("document_json"))
    _upsert(conn, "generated_documents", payload, ["document_id"])


def upsert_capability_gap(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    _upsert(conn, "capability_gaps", row, ["gap_id"])


def insert_gap_evidence(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    payload = dict(row)
    payload["evidence_json"] = _json_text(payload.get("evidence_json"))
    _upsert(conn, "gap_evidence", payload, ["gap_evidence_id"])


def upsert_gap_assessment(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    payload = dict(row)
    payload["assessment_json"] = _json_text(payload.get("assessment_json"))
    _upsert(conn, "gap_assessments", payload, ["candidate_id", "gap_id"])


def replace_candidate_gap_state(conn: sqlite3.Connection, candidate_id: str) -> None:
    conn.execute(
        """
        DELETE FROM gap_assessments
        WHERE candidate_id = ?
        """,
        [candidate_id],
    )
    conn.execute(
        """
        DELETE FROM gap_evidence
        WHERE candidate_id = ?
        """,
        [candidate_id],
    )
    conn.execute(
        """
        DELETE FROM capability_gaps
        WHERE candidate_id = ?
        """,
        [candidate_id],
    )


def upsert_job(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    payload = dict(row)
    payload["job_metadata_json"] = _json_text(payload.get("job_metadata_json"))

    existing = conn.execute(
        "SELECT first_seen_at FROM jobs WHERE job_id = ? LIMIT 1",
        [payload["job_id"]],
    ).fetchone()
    if existing and existing[0]:
        payload["first_seen_at"] = existing[0]

    _upsert(conn, "jobs", payload, ["job_id"])


def upsert_job_source_record(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    payload = dict(row)
    payload["raw_payload_json"] = _json_text(payload.get("raw_payload_json"))
    _upsert(conn, "job_source_records", payload, ["source_record_id"])


def mark_source_records_inactive(
    conn: sqlite3.Connection,
    source_name: str,
    source_job_keys: Iterable[str],
    *,
    seen_at: str,
) -> None:
    keys = [str(k).strip() for k in source_job_keys if str(k).strip()]
    if not keys:
        return

    placeholders = ", ".join(["?"] * len(keys))
    conn.execute(
        f"""
        UPDATE job_source_records
        SET is_active = 0,
            last_seen_at = ?,
            updated_at = ?
        WHERE source_name = ?
          AND source_job_key IN ({placeholders})
        """,
        [seen_at, seen_at, source_name, *keys],
    )

    related_job_ids = [
        row[0]
        for row in conn.execute(
            f"""
            SELECT DISTINCT job_id
            FROM job_source_records
            WHERE source_name = ?
              AND source_job_key IN ({placeholders})
            """,
            [source_name, *keys],
        ).fetchall()
    ]

    for job_id in related_job_ids:
        active_count = conn.execute(
            "SELECT COUNT(*) FROM job_source_records WHERE job_id = ? AND is_active = 1",
            [job_id],
        ).fetchone()[0]
        if active_count == 0:
            conn.execute(
                """
                UPDATE jobs
                SET closed_at = CASE WHEN closed_at = '' THEN ? ELSE closed_at END,
                    updated_at = ?
                WHERE job_id = ?
                """,
                [seen_at, seen_at, job_id],
            )


def upsert_pipeline_run(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    payload = dict(row)
    payload["source_batch_json"] = _json_text(payload.get("source_batch_json"))
    _upsert(conn, "pipeline_runs", payload, ["run_id"])


def mark_pipeline_run_finished(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    status: str,
    finished_at: str,
    jobs_seen: int,
    jobs_failed: int,
) -> None:
    conn.execute(
        """
        UPDATE pipeline_runs
        SET status = ?,
            finished_at = ?,
            jobs_seen = ?,
            jobs_failed = ?,
            updated_at = ?
        WHERE run_id = ?
        """,
        [status, finished_at, jobs_seen, jobs_failed, finished_at, run_id],
    )


def upsert_suggestion_lead(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    payload = dict(row)
    payload["payload_json"] = _json_text(payload.get("payload_json"))
    _upsert(conn, "suggestion_leads", payload, ["suggestion_id"])


def list_suggestion_leads(
    conn: sqlite3.Connection,
    candidate_id: str,
    *,
    statuses: Iterable[str] | None = None,
    platform: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    clauses = ["candidate_id = ?"]
    params: list[Any] = [candidate_id]

    normalized_statuses = [str(s).strip() for s in (statuses or []) if str(s).strip()]
    if normalized_statuses:
        placeholders = ", ".join(["?"] * len(normalized_statuses))
        clauses.append(f"status IN ({placeholders})")
        params.extend(normalized_statuses)

    if platform:
        clauses.append("platform = ?")
        params.append(platform)

    sql = """
        SELECT suggestion_id, candidate_id, platform, external_id, job_url, job_id_hint,
               suggested_at, email_subject, source, status, fetched_at, last_error,
               payload_json, created_at, updated_at
        FROM suggestion_leads
        WHERE {where}
        ORDER BY
            CASE status
                WHEN 'queued' THEN 0
                WHEN 'fetched' THEN 1
                WHEN 'failed' THEN 2
                ELSE 3
            END,
            suggested_at DESC,
            updated_at DESC
    """.format(where=" AND ".join(clauses))
    if limit and int(limit) > 0:
        sql += " LIMIT ?"
        params.append(int(limit))

    cursor = conn.execute(sql, params)
    columns = [col[0] for col in (cursor.description or [])]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    for row in rows:
        try:
            row["payload_json"] = json.loads(row.get("payload_json") or "{}")
        except Exception:
            pass
    return rows


def mark_suggestion_lead_status(
    conn: sqlite3.Connection,
    suggestion_id: str,
    *,
    status: str,
    fetched_at: str = "",
    last_error: str = "",
    updated_at: str,
) -> None:
    conn.execute(
        """
        UPDATE suggestion_leads
        SET status = ?, fetched_at = ?, last_error = ?, updated_at = ?
        WHERE suggestion_id = ?
        """,
        [status, fetched_at, last_error, updated_at, suggestion_id],
    )


def upsert_job_evaluation(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    _upsert(conn, "job_evaluations", row, ["candidate_id", "job_id"])


def upsert_job_run_event(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    _upsert(conn, "job_run_events", row, ["candidate_id", "run_id", "job_id"])


def upsert_job_replay_input(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    payload = dict(row)
    payload["input_payload_json"] = _json_text(payload.get("input_payload_json"))
    _upsert(conn, "job_replay_inputs", payload, ["job_id"])


def replace_job_claims(conn: sqlite3.Connection, job_id: str, rows: Iterable[Mapping[str, Any]]) -> None:
    conn.execute("DELETE FROM job_claims WHERE job_id = ?", [job_id])
    for row in rows:
        payload = dict(row)
        payload["claim_json"] = _json_text(payload.get("claim_json"))
        _upsert(conn, "job_claims", payload, ["job_id", "claim_id"])


def replace_job_selection_signals(
    conn: sqlite3.Connection,
    job_id: str,
    rows: Iterable[Mapping[str, Any]],
) -> None:
    conn.execute("DELETE FROM job_selection_signals WHERE job_id = ?", [job_id])
    for row in rows:
        payload = dict(row)
        payload["signal_json"] = _json_text(payload.get("signal_json"))
        _upsert(conn, "job_selection_signals", payload, ["job_id", "signal_id"])


def upsert_job_selection_assessment(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    payload = dict(row)
    payload["likely_rejection_vectors_json"] = _json_text(payload.get("likely_rejection_vectors_json", []))
    payload["mitigation_moves_json"] = _json_text(payload.get("mitigation_moves_json", []))
    payload["assessment_json"] = _json_text(payload.get("assessment_json"))
    _upsert(conn, "job_selection_assessments", payload, ["candidate_id", "job_id"])


def upsert_job_decision_table(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    payload = dict(row)
    for field in (
        "can_do_supporting_points_json",
        "can_do_risk_points_json",
        "can_get_supporting_points_json",
        "can_get_risk_points_json",
        "should_want_supporting_points_json",
        "should_want_risk_points_json",
        "can_explain_supporting_points_json",
        "can_explain_risk_points_json",
        "next_moves_json",
    ):
        payload[field] = _json_text(payload.get(field, []))
    payload["decision_table_json"] = _json_text(payload.get("decision_table_json"))
    _upsert(conn, "job_decision_tables", payload, ["candidate_id", "job_id"])


def replace_candidate_evidence_units(
    conn: sqlite3.Connection,
    candidate_id: str,
    rows: Iterable[Mapping[str, Any]],
) -> None:
    conn.execute("DELETE FROM candidate_evidence_units WHERE candidate_id = ?", [candidate_id])
    for row in rows:
        payload = dict(row)
        for field in (
            "role_family_tags_json",
            "domain_tags_json",
            "capability_tags_json",
            "outcome_tags_json",
        ):
            payload[field] = _json_text(payload.get(field, []))
        payload["evidence_json"] = _json_text(payload.get("evidence_json"))
        _upsert(conn, "candidate_evidence_units", payload, ["candidate_id", "evidence_unit_id"])


def upsert_candidate_narrative_profile(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        "UPDATE candidate_narrative_profiles SET is_active = 0, updated_at = ? WHERE candidate_id = ?",
        [row["updated_at"], row["candidate_id"]],
    )
    payload = dict(row)
    for field in (
        "core_identity_json",
        "future_direction_json",
        "motivation_themes_json",
        "pivot_thesis_json",
        "proof_themes_json",
        "story_boundaries_json",
        "tone_rules_json",
    ):
        payload[field] = _json_text(payload.get(field, []))
    _upsert(conn, "candidate_narrative_profiles", payload, ["narrative_version_id"])


def replace_narrative_fragments(
    conn: sqlite3.Connection,
    candidate_id: str,
    narrative_version_id: str,
    rows: Iterable[Mapping[str, Any]],
) -> None:
    conn.execute(
        """
        DELETE FROM narrative_fragments
        WHERE candidate_id = ? AND narrative_version_id = ?
        """,
        [candidate_id, narrative_version_id],
    )
    for row in rows:
        payload = dict(row)
        payload["fragment_json"] = _json_text(payload.get("fragment_json"))
        _upsert(conn, "narrative_fragments", payload, ["fragment_id"])


def replace_narrative_evidence_links(
    conn: sqlite3.Connection,
    candidate_id: str,
    narrative_version_id: str,
    rows: Iterable[Mapping[str, Any]],
) -> None:
    conn.execute(
        """
        DELETE FROM narrative_evidence_links
        WHERE candidate_id = ? AND narrative_version_id = ?
        """,
        [candidate_id, narrative_version_id],
    )
    for row in rows:
        _upsert(conn, "narrative_evidence_links", row, ["narrative_link_id"])


def upsert_job_narrative_assessment(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    payload = dict(row)
    payload["misalignment_flags_json"] = _json_text(payload.get("misalignment_flags_json", []))
    payload["assessment_json"] = _json_text(payload.get("assessment_json"))
    _upsert(conn, "job_narrative_assessments", payload, ["candidate_id", "job_id"])


def replace_watchlists(
    conn: sqlite3.Connection,
    candidate_id: str,
    rows: Iterable[Mapping[str, Any]],
) -> None:
    conn.execute("DELETE FROM watchlists WHERE candidate_id = ?", [candidate_id])
    for row in rows:
        payload = dict(row)
        payload["watch_config_json"] = _json_text(payload.get("watch_config_json"))
        _upsert(conn, "watchlists", payload, ["watchlist_id"])


def upsert_change_event(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    payload = dict(row)
    payload["change_json"] = _json_text(payload.get("change_json"))
    _upsert(conn, "change_events", payload, ["change_event_id"])
