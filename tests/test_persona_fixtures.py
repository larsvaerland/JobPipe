from __future__ import annotations

import json
from pathlib import Path

from jobpipe.cli.bootstrap_state_db import parse_profile_pack


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "personas"


def test_persona_manifest_and_fixture_files_are_complete():
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))

    personas = manifest.get("personas", [])
    assert len(personas) == 4

    for persona in personas:
        profile_path = FIXTURE_ROOT / persona["profile_pack"]
        resume_path = FIXTURE_ROOT / persona["resume_json"]

        assert profile_path.exists()
        assert resume_path.exists()

        parsed_profile = parse_profile_pack(profile_path.read_text(encoding="utf-8"))
        assert parsed_profile["snapshot"]["name"]
        assert parsed_profile["strategic_direction"]
        assert parsed_profile["target_roles"]["primary"]
        assert parsed_profile["hard_no_roles"]
        assert parsed_profile["evidence_sections"]

        resume = json.loads(resume_path.read_text(encoding="utf-8"))
        assert resume["basics"]["name"]
        assert len(resume.get("work", [])) >= 2
        assert len(resume.get("education", [])) >= 1
