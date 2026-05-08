from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_run(root: Path) -> Path:
    run_dir = root / "jobpipe_v1_cli"
    job_dir = run_dir / "job-1"
    job_dir.mkdir(parents=True)
    (run_dir / "index.jsonl").write_text(
        json.dumps(
            {
                "job_id": "job-1",
                "title": "Product Manager",
                "employer": "Example AS",
                "triage_v3_weighted_score": 81,
                "final_decision": "APPLY",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        job_dir / "00_input.json",
        {
            "job_id": "job-1",
            "title": "Product Manager",
            "normalized_title": "Product Manager",
            "employer_name": "Example AS",
            "description_html": "Hybrid platform role with stakeholder work.",
            "applicationUrl": "https://example.test/apply",
            "work_city": "Oslo",
        },
    )
    _write_json(
        job_dir / "bridge_triage_features.json",
        {
            "core_tech_alignment": {"score": 80, "reason": "Platform work matches."},
            "role_specificity": {"score": 75, "reason": "Product ownership is explicit."},
            "operating_fit": {"score": 70, "reason": "Stakeholder work fits."},
            "requirement_density": {"score": 62, "reason": "Requirements are manageable."},
            "stakeholder_complexity": {"score": 64, "reason": "Complexity is useful."},
            "autonomy_level": {"score": 70, "reason": "Autonomy is visible."},
            "geospatial_friction": {"score": 55, "reason": "Oslo is workable."},
            "remote_veracity": {"score": 55, "reason": "Hybrid is stated."},
            "legacy_burden": {"score": 35, "reason": "Legacy burden needs framing."},
        },
    )
    _write_json(
        job_dir / "bridge_triage_decision_v3.json",
        {
            "label": "shortlist",
            "weighted_score": 81,
            "confidence": 75,
            "blockers": ["Legacy burden needs framing"],
            "boosts": ["Strong product overlap"],
            "summary": "Worth review effort.",
        },
    )
    _write_json(
        job_dir / "10_moderator.json",
        {
            "final_decision": "APPLY",
            "recommendation_reason": "Apply with product framing.",
            "cv_focus": ["Platform ownership"],
            "feedback_flags": [],
        },
    )
    return run_dir


def test_workspace_cases_cli_lists_redacted_cases(tmp_path: Path) -> None:
    _write_run(tmp_path)

    result = subprocess.run(
        [sys.executable, "-m", "jobpipe.cli.workspace_cases", "--out-root", str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "run_id: jobpipe_v1_cli" in result.stdout
    assert "job-1 | Example AS | Product Manager | apply | score=81" in result.stdout
    assert str(tmp_path) not in result.stdout
    assert "https://example.test" not in result.stdout


def test_workspace_cases_cli_json_output(tmp_path: Path) -> None:
    _write_run(tmp_path)

    result = subprocess.run(
        [sys.executable, "-m", "jobpipe.cli.workspace_cases", "--out-root", str(tmp_path), "--json"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["run_id"] == "jobpipe_v1_cli"
    assert payload["cases"][0]["case_id"] == "job-1"
    assert payload["cases"][0]["decision_signal_keys"] == [
        "can_do",
        "can_get",
        "should_want",
        "can_explain",
    ]
    assert "applicationUrl" not in result.stdout
    assert str(tmp_path) not in result.stdout


def test_workspace_cases_cli_case_detail(tmp_path: Path) -> None:
    _write_run(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "jobpipe.cli.workspace_cases",
            "--out-root",
            str(tmp_path),
            "--run-id",
            "jobpipe_v1_cli",
            "--case-id",
            "job-1",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "summary: Worth review effort." in result.stdout
    assert "artifact_refs:" in result.stdout
    assert str(tmp_path) not in result.stdout


def test_workspace_cases_cli_missing_run_exits_nonzero(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "jobpipe.cli.workspace_cases", "--out-root", str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "No valid artifact run found" in result.stderr or "No valid artifact run found" in result.stdout


def test_workspace_cases_registered_in_main_cli() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "jobpipe.cli.main", "workspace-cases", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--out-root" in result.stdout
