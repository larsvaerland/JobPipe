from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from jobpipe.cli.workspace_server import build_server


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_run(root: Path, run_id: str = "jobpipe_v1_server") -> Path:
    run_dir = root / run_id
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
            "sourceurl": "https://example.test/job",
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


def _start_server(out_root: Path):
    server = build_server(out_root=out_root, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}"


def _get_json(url: str) -> dict:
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_error(url: str) -> tuple[int, dict]:
    try:
        _get_json(url)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    raise AssertionError("expected HTTPError")


def test_workspace_server_health_endpoint(tmp_path: Path) -> None:
    _write_run(tmp_path)
    server, base_url = _start_server(tmp_path)
    try:
        payload = _get_json(f"{base_url}/healthz")
    finally:
        server.shutdown()
        server.server_close()

    assert payload == {"schemaVersion": "jobpipe.workspace.health.v1", "status": "ok"}


def test_workspace_server_lists_latest_run_cases(tmp_path: Path) -> None:
    _write_run(tmp_path)
    server, base_url = _start_server(tmp_path)
    try:
        payload = _get_json(f"{base_url}/cases")
    finally:
        server.shutdown()
        server.server_close()

    assert payload["schemaVersion"] == "jobpipe.workspace.cases.list.v1"
    assert payload["runId"] == "jobpipe_v1_server"
    assert payload["cases"][0]["id"] == "job-1"
    assert payload["cases"][0]["company"] == "Example AS"
    assert payload["cases"][0]["decisionSignalKeys"] == [
        "can_do",
        "can_get",
        "should_want",
        "can_explain",
    ]


def test_workspace_server_lists_explicit_run_cases(tmp_path: Path) -> None:
    _write_run(tmp_path, "jobpipe_v1_11111111")
    _write_run(tmp_path, "jobpipe_v1_22222222")
    server, base_url = _start_server(tmp_path)
    try:
        payload = _get_json(f"{base_url}/cases?run_id=jobpipe_v1_11111111")
    finally:
        server.shutdown()
        server.server_close()

    assert payload["runId"] == "jobpipe_v1_11111111"
    assert payload["cases"][0]["id"] == "job-1"


def test_workspace_server_gets_case_detail(tmp_path: Path) -> None:
    _write_run(tmp_path)
    server, base_url = _start_server(tmp_path)
    try:
        payload = _get_json(f"{base_url}/cases/job-1")
    finally:
        server.shutdown()
        server.server_close()

    assert payload["schemaVersion"] == "jobpipe.workspace.cases.get.v1"
    assert payload["case"]["id"] == "job-1"
    assert payload["case"]["summary"] == "Worth review effort."
    assert payload["case"]["artifacts"][0]["id"].startswith("artifact:job-1:")
    serialized = json.dumps(payload, ensure_ascii=False)
    assert str(tmp_path) not in serialized
    assert "https://example.test" not in serialized


def test_workspace_server_case_not_found(tmp_path: Path) -> None:
    _write_run(tmp_path)
    server, base_url = _start_server(tmp_path)
    try:
        status, payload = _get_error(f"{base_url}/cases/missing")
    finally:
        server.shutdown()
        server.server_close()

    assert status == 404
    assert payload["error"]["code"] == "case_not_found"


def test_workspace_server_run_not_found(tmp_path: Path) -> None:
    _write_run(tmp_path)
    server, base_url = _start_server(tmp_path)
    try:
        status, payload = _get_error(f"{base_url}/cases?run_id=missing")
    finally:
        server.shutdown()
        server.server_close()

    assert status == 404
    assert payload["error"]["code"] == "run_not_found"


def test_workspace_server_does_not_import_forbidden_sources() -> None:
    source = Path("jobpipe/cli/workspace_server.py").read_text(encoding="utf-8")

    assert "dashboard" not in source
    assert "supabase" not in source.lower()
    assert "sqlite3" not in source


def test_workspace_server_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "jobpipe.cli.workspace_server", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--out-root" in result.stdout
    assert "--port" in result.stdout


def test_workspace_server_registered_in_main_cli() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "jobpipe.cli.main", "workspace-server", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--out-root" in result.stdout
