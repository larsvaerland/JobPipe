from __future__ import annotations

import json

from jobpipe.core.candidate_data import (
    load_candidate_profile_json,
    load_candidate_profile_pack,
    load_candidate_resume_json,
)
from jobpipe.core.primary_db import connect_primary_db, ensure_candidate, upsert_candidate_profile


def test_load_candidate_profile_pack_reads_active_profile_from_db(tmp_path, monkeypatch):
    db_path = tmp_path / "jobpipe.sqlite"
    monkeypatch.setenv("JOBPIPE_DB_PATH", str(db_path))
    monkeypatch.setenv("JOBPIPE_CANDIDATE_ID", "candidate-a")

    conn = connect_primary_db(db_path)
    ensure_candidate(conn, candidate_id="candidate-a")
    upsert_candidate_profile(
        conn,
        {
            "profile_version_id": "profile_v1",
            "candidate_id": "candidate-a",
            "source_kind": "bootstrap",
            "is_active": 1,
            "content_hash": "hash-1",
            "profile_pack_md": "# PROFILE\nDB-backed profile",
            "profile_json": json.dumps({"target_roles": ["PM"]}, ensure_ascii=False),
            "resume_json": json.dumps({"work": [{"name": "Example", "position": "PM"}]}, ensure_ascii=False),
            "created_at": "2026-04-16T10:00:00Z",
            "updated_at": "2026-04-16T10:00:00Z",
        },
    )
    conn.commit()
    conn.close()

    assert load_candidate_profile_pack(candidate_id="candidate-a", db_path=db_path) == "# PROFILE\nDB-backed profile"
    resume = load_candidate_resume_json(candidate_id="candidate-a", db_path=db_path)
    assert resume["work"][0]["position"] == "PM"


def test_load_candidate_profile_pack_explicit_file_overrides_db(tmp_path, monkeypatch):
    db_path = tmp_path / "jobpipe.sqlite"
    explicit_profile = tmp_path / "profile_pack.md"
    explicit_profile.write_text("# PROFILE\nFile override", encoding="utf-8")

    monkeypatch.setenv("JOBPIPE_DB_PATH", str(db_path))
    monkeypatch.setenv("JOBPIPE_CANDIDATE_ID", "candidate-a")

    conn = connect_primary_db(db_path)
    ensure_candidate(conn, candidate_id="candidate-a")
    upsert_candidate_profile(
        conn,
        {
            "profile_version_id": "profile_v1",
            "candidate_id": "candidate-a",
            "source_kind": "bootstrap",
            "is_active": 1,
            "content_hash": "hash-1",
            "profile_pack_md": "# PROFILE\nDB-backed profile",
            "profile_json": json.dumps({}, ensure_ascii=False),
            "resume_json": json.dumps({}, ensure_ascii=False),
            "created_at": "2026-04-16T10:00:00Z",
            "updated_at": "2026-04-16T10:00:00Z",
        },
    )
    conn.commit()
    conn.close()

    assert load_candidate_profile_pack(explicit_profile, candidate_id="candidate-a", db_path=db_path) == "# PROFILE\nFile override"


def test_load_candidate_profile_pack_and_resume_fall_back_to_default_files(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    documents_dir = data_dir / "documents"
    documents_dir.mkdir()
    (documents_dir / "profile_pack.md").write_text("# PROFILE\nFile fallback", encoding="utf-8")
    (documents_dir / "resume.json").write_text(
        json.dumps({"work": [{"name": "Fallback Co", "position": "Designer"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.delenv("JOBPIPE_DB_PATH", raising=False)
    monkeypatch.setenv("JOBPIPE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("JOBPIPE_CANDIDATE_ID", "candidate-a")

    assert load_candidate_profile_pack() == "# PROFILE\nFile fallback"
    resume = load_candidate_resume_json()
    assert resume["work"][0]["position"] == "Designer"


def test_load_candidate_profile_json_prefers_structured_profile_json_from_db(tmp_path, monkeypatch):
    db_path = tmp_path / "jobpipe.sqlite"
    monkeypatch.setenv("JOBPIPE_DB_PATH", str(db_path))
    monkeypatch.setenv("JOBPIPE_CANDIDATE_ID", "candidate-a")

    conn = connect_primary_db(db_path)
    ensure_candidate(conn, candidate_id="candidate-a")
    upsert_candidate_profile(
        conn,
        {
            "profile_version_id": "profile_v1",
            "candidate_id": "candidate-a",
            "source_kind": "bootstrap",
            "is_active": 1,
            "content_hash": "hash-1",
            "profile_pack_md": "# PROFILE\nDB-backed profile",
            "profile_json": json.dumps(
                {
                    "snapshot": {"level": "Mid-Level Specialist"},
                    "target_roles": {"primary": ["BI Analyst"], "secondary": [], "hard_no": []},
                    "negative_keywords": ["cashier"],
                },
                ensure_ascii=False,
            ),
            "resume_json": json.dumps({}, ensure_ascii=False),
            "created_at": "2026-04-16T10:00:00Z",
            "updated_at": "2026-04-16T10:00:00Z",
        },
    )
    conn.commit()
    conn.close()

    profile = load_candidate_profile_json(candidate_id="candidate-a", db_path=db_path)

    assert profile["snapshot"]["level"] == "Mid-Level Specialist"
    assert profile["target_roles"]["primary"] == ["BI Analyst"]
