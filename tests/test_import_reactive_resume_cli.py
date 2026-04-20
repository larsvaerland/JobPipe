from __future__ import annotations

import json
import sqlite3

from jobpipe.cli import import_reactive_resume


def test_import_reactive_resume_cli_updates_candidate_profile(tmp_path) -> None:
    resume_path = tmp_path / "reactive_resume.json"
    resume_path.write_text(
        json.dumps(
            {
                "basics": {"name": "Lars Værland", "email": "lars@example.com"},
                "work": [{"name": "Example Co", "position": "Product Manager"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    profile_path = tmp_path / "profile_pack.md"
    profile_path.write_text(
        "# PROFILE\n\n## 0) Candidate snapshot (quick facts)\n- Name: Lars Værland\n- Base: Oslo\n- Level: Mid-Senior\n- Positioning: Product leader\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "jobpipe.sqlite"

    import_reactive_resume.main(
        [
            str(resume_path),
            "--profile",
            str(profile_path),
            "--db",
            str(db_path),
            "--candidate-id",
            "candidate-a",
        ]
    )

    con = sqlite3.connect(str(db_path))
    candidate = con.execute(
        "SELECT display_name, email FROM candidates WHERE candidate_id = ?",
        ["candidate-a"],
    ).fetchone()
    profile = con.execute(
        "SELECT source_kind, resume_json FROM candidate_profiles WHERE candidate_id = ? AND is_active = 1",
        ["candidate-a"],
    ).fetchone()
    con.close()

    assert candidate == ("Lars Værland", "lars@example.com")
    assert profile is not None
    assert profile[0] == "reactive_resume_import"
    assert json.loads(profile[1])["work"][0]["position"] == "Product Manager"
