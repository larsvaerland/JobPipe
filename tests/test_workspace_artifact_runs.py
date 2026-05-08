from __future__ import annotations

import json
from pathlib import Path

from jobpipe.workspace import ArtifactRunSource, build_latest_artifact_workspace_hub


def _write_index(run_dir: Path, job_id: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "index.jsonl").write_text(
        json.dumps({"job_id": job_id, "title": "Product Manager"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_case(run_dir: Path, job_id: str, *, failed: bool = False) -> None:
    job_dir = run_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "00_input.json").write_text(
        json.dumps({"job_id": job_id, "title": "Product Manager"}, ensure_ascii=False),
        encoding="utf-8",
    )
    if failed:
        (job_dir / "pipeline_error.json").write_text(
            json.dumps({"error": "failed"}, ensure_ascii=False),
            encoding="utf-8",
        )


def test_artifact_run_source_lists_valid_runs_newest_first(tmp_path: Path) -> None:
    old_run = tmp_path / "jobpipe_v1_11111111"
    new_run = tmp_path / "jobpipe_v1_22222222"
    _write_index(old_run, "job-old")
    _write_case(old_run, "job-old")
    _write_index(new_run, "job-new")
    _write_case(new_run, "job-new")
    (tmp_path / "not-a-run").mkdir()

    source = ArtifactRunSource(tmp_path)
    runs = source.list_runs()

    assert [run.id for run in runs] == ["jobpipe_v1_22222222", "jobpipe_v1_11111111"]
    assert source.latest_run() == runs[0]
    assert source.resolve() == new_run
    assert source.resolve("jobpipe_v1_11111111") == old_run
    assert source.resolve("missing") is None


def test_artifact_run_source_ignores_invalid_and_all_failed_runs(tmp_path: Path) -> None:
    invalid = tmp_path / "jobpipe_v1_invalid"
    invalid.mkdir()
    all_failed = tmp_path / "jobpipe_v1_failed"
    _write_index(all_failed, "job-failed")
    _write_case(all_failed, "job-failed", failed=True)

    source = ArtifactRunSource(tmp_path)

    assert source.list_runs() == []
    assert source.latest_run() is None
    assert source.resolve() is None


def test_artifact_run_source_allows_index_only_runs(tmp_path: Path) -> None:
    run_dir = tmp_path / "jobpipe_v1_index_only"
    _write_index(run_dir, "job-index")

    runs = ArtifactRunSource(tmp_path).list_runs()

    assert len(runs) == 1
    assert runs[0].id == "jobpipe_v1_index_only"
    assert runs[0].case_count == 1


def test_build_latest_artifact_workspace_hub_uses_latest_valid_run(tmp_path: Path) -> None:
    old_run = tmp_path / "jobpipe_v1_11111111"
    new_run = tmp_path / "jobpipe_v1_22222222"
    _write_index(old_run, "job-old")
    _write_case(old_run, "job-old")
    _write_index(new_run, "job-new")
    _write_case(new_run, "job-new")

    hub = build_latest_artifact_workspace_hub(tmp_path)

    assert hub is not None
    assert [item.id for item in hub.cases.list()] == ["job-new"]


def test_artifact_run_refs_do_not_expose_raw_paths(tmp_path: Path) -> None:
    run_dir = tmp_path / "jobpipe_v1_safe_id"
    _write_index(run_dir, "job-1")
    _write_case(run_dir, "job-1")

    run = ArtifactRunSource(tmp_path).latest_run()

    assert run is not None
    assert run.id == "jobpipe_v1_safe_id"
    assert str(tmp_path) not in json.dumps(run.__dict__, ensure_ascii=False)
    assert "\\" not in run.id
