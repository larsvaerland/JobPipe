from __future__ import annotations

import os
from pathlib import Path

import pytest

import jobpipe.runtime.paths as rp


# ── helpers ──────────────────────────────────────────────────────────────────

def _clear_data_env(monkeypatch) -> None:
    """Remove all JOBPIPE path overrides so defaults are exercised."""
    for key in [
        "JOBPIPE_DATA_DIR",
        "JOBPIPE_EXPORT_DIR",
        "JOBPIPE_DOCUMENTS_DIR",
        "JOBPIPE_ARTIFACT_DIR",
        "JOBPIPE_CACHE_DIR",
        "JOBPIPE_DB_DIR",
        "JOBPIPE_SECRETS_DIR",
        "JOBPIPE_DB_PATH",
        "JOBPIPE_PROFILE_PATH",
        "JOBPIPE_RESUME_JSON",
    ]:
        monkeypatch.delenv(key, raising=False)


# ── data_root ─────────────────────────────────────────────────────────────────

def test_data_root_respects_env(monkeypatch, tmp_path: Path) -> None:
    custom = tmp_path / "custom-data"
    monkeypatch.setenv("JOBPIPE_DATA_DIR", str(custom))
    assert rp.data_root() == custom


def test_data_root_never_returns_none(monkeypatch) -> None:
    _clear_data_env(monkeypatch)
    result = rp.data_root()
    assert result is not None
    assert isinstance(result, Path)


def test_data_root_default_is_not_inside_repo(monkeypatch) -> None:
    _clear_data_env(monkeypatch)
    result = rp.data_root()
    repo = rp.repo_root()
    # Default must not nest inside the repository directory
    assert not str(result).startswith(str(repo)), (
        f"data_root() returned a repo-local path: {result}"
    )


# ── exports_root ──────────────────────────────────────────────────────────────

def test_exports_root_uses_data_root_by_default(monkeypatch) -> None:
    _clear_data_env(monkeypatch)
    result = rp.exports_root()
    repo = rp.repo_root()
    assert not str(result).startswith(str(repo)), (
        f"exports_root() fell back into repo: {result}"
    )


def test_exports_root_uses_custom_data_dir(monkeypatch, tmp_path: Path) -> None:
    custom = tmp_path / "mydata"
    monkeypatch.setenv("JOBPIPE_DATA_DIR", str(custom))
    monkeypatch.delenv("JOBPIPE_EXPORT_DIR", raising=False)
    assert rp.exports_root() == custom / "exports"


def test_exports_root_env_override_takes_precedence(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JOBPIPE_DATA_DIR", str(tmp_path / "data"))
    override = tmp_path / "my-exports"
    monkeypatch.setenv("JOBPIPE_EXPORT_DIR", str(override))
    assert rp.exports_root() == override


# ── documents_root ────────────────────────────────────────────────────────────

def test_documents_root_is_not_inside_repo(monkeypatch) -> None:
    _clear_data_env(monkeypatch)
    result = rp.documents_root()
    repo = rp.repo_root()
    assert not str(result).startswith(str(repo)), (
        f"documents_root() fell back into repo: {result}"
    )


def test_documents_root_uses_custom_data_dir(monkeypatch, tmp_path: Path) -> None:
    custom = tmp_path / "mydata"
    monkeypatch.setenv("JOBPIPE_DATA_DIR", str(custom))
    monkeypatch.delenv("JOBPIPE_DOCUMENTS_DIR", raising=False)
    assert rp.documents_root() == custom / "documents"


# ── artifacts_root ────────────────────────────────────────────────────────────

def test_artifacts_root_is_not_inside_repo(monkeypatch) -> None:
    _clear_data_env(monkeypatch)
    result = rp.artifacts_root()
    repo = rp.repo_root()
    assert not str(result).startswith(str(repo)), (
        f"artifacts_root() fell back into repo: {result}"
    )


def test_artifacts_root_uses_custom_data_dir(monkeypatch, tmp_path: Path) -> None:
    custom = tmp_path / "mydata"
    monkeypatch.setenv("JOBPIPE_DATA_DIR", str(custom))
    monkeypatch.delenv("JOBPIPE_ARTIFACT_DIR", raising=False)
    assert rp.artifacts_root() == custom / "artifacts"


# ── db_root / primary_db_path ─────────────────────────────────────────────────

def test_primary_db_path_is_not_inside_repo(monkeypatch) -> None:
    _clear_data_env(monkeypatch)
    result = rp.primary_db_path()
    repo = rp.repo_root()
    assert not str(result).startswith(str(repo)), (
        f"primary_db_path() fell back into repo: {result}"
    )


def test_primary_db_path_env_override(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "custom.sqlite"
    monkeypatch.setenv("JOBPIPE_DB_PATH", str(db_path))
    assert rp.primary_db_path() == db_path
