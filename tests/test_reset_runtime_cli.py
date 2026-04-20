from __future__ import annotations

import json

from jobpipe.cli import reset_runtime


def test_reset_runtime_archives_generated_state_and_restores_app_state(tmp_path, monkeypatch) -> None:
    data_root = tmp_path / "JobpipeData"
    (data_root / "db").mkdir(parents=True)
    (data_root / "artifacts" / "job-a").mkdir(parents=True)
    (data_root / "exports").mkdir(parents=True)
    (data_root / "cache").mkdir(parents=True)
    (data_root / "audit").mkdir(parents=True)

    (data_root / "db" / "jobpipe.sqlite").write_text("db", encoding="utf-8")
    (data_root / "db" / "application_state.json").write_text('{"applications": {"job-a": {}}}', encoding="utf-8")
    (data_root / "artifacts" / "job-a" / "00_input.json").write_text("{}", encoding="utf-8")
    (data_root / "exports" / "dashboard.html").write_text("<html></html>", encoding="utf-8")
    (data_root / "cache" / "profile_embedding.npy").write_bytes(b"cache")
    (data_root / "jobs_state.json").write_text("{}", encoding="utf-8")
    (data_root / "profile_pack.md").write_text("# profile", encoding="utf-8")
    (data_root / "gmail_credentials.json").write_text("secret", encoding="utf-8")
    (data_root / "audit" / "keep.txt").write_text("keep", encoding="utf-8")

    monkeypatch.setenv("JOBPIPE_DATA_DIR", str(data_root))

    summary = reset_runtime.reset_runtime_state(
        data_root_path=data_root,
        archive_root_path=data_root / "_archives",
        tag="baseline_a",
        restore_app_state=True,
    )

    archive_dir = data_root / "_archives" / "baseline_a"
    assert archive_dir.exists()
    assert (archive_dir / "db" / "jobpipe.sqlite").exists()
    assert (archive_dir / "artifacts" / "job-a" / "00_input.json").exists()
    assert (archive_dir / "exports" / "dashboard.html").exists()
    assert (archive_dir / "jobs_state.json").exists()

    assert (data_root / "db").exists()
    assert (data_root / "artifacts").exists()
    assert (data_root / "exports").exists()
    assert (data_root / "cache").exists()
    assert not (data_root / "db" / "jobpipe.sqlite").exists()
    assert json.loads((data_root / "db" / "application_state.json").read_text(encoding="utf-8")) == {
        "applications": {"job-a": {}}
    }

    assert (data_root / "profile_pack.md").read_text(encoding="utf-8") == "# profile"
    assert (data_root / "gmail_credentials.json").read_text(encoding="utf-8") == "secret"
    assert (data_root / "audit" / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert (archive_dir / "reset_manifest.json").exists()
    assert "db" in summary["archived_paths"]
    assert "db/application_state.json" in summary["restored_paths"]


def test_reset_runtime_can_skip_app_state_restore(tmp_path, monkeypatch) -> None:
    data_root = tmp_path / "JobpipeData"
    (data_root / "db").mkdir(parents=True)
    (data_root / "db" / "application_state.json").write_text('{"applications": {"job-a": {}}}', encoding="utf-8")

    monkeypatch.setenv("JOBPIPE_DATA_DIR", str(data_root))

    reset_runtime.reset_runtime_state(
        data_root_path=data_root,
        archive_root_path=data_root / "_archives",
        tag="baseline_b",
        restore_app_state=False,
    )

    assert not (data_root / "db" / "application_state.json").exists()
