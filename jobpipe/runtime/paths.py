from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _expand_path(raw: str | os.PathLike[str]) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(str(raw)))).resolve()


def _prefer_existing(*candidates: Path) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def data_root() -> Path:
    """Return the data root directory, never writing inside the repo.

    Precedence: JOBPIPE_DATA_DIR env var → OS-appropriate user data root
    (~/JobpipeData on Windows, ~/Library/Application Support/JobPipe on macOS,
    $XDG_DATA_HOME/jobpipe on Linux).
    """
    raw = (os.environ.get("JOBPIPE_DATA_DIR") or "").strip()
    if raw:
        return _expand_path(raw)
    # Fall back to the same platform-aware default as jobpipe.core.paths
    from jobpipe.core.paths import default_data_root
    return default_data_root()


def cache_root() -> Path:
    raw = (os.environ.get("JOBPIPE_CACHE_DIR") or "").strip()
    if raw:
        return _expand_path(raw)
    return data_root() / "cache"


def secrets_root() -> Path:
    raw = (os.environ.get("JOBPIPE_SECRETS_DIR") or "").strip()
    if raw:
        return _expand_path(raw)
    return data_root() / "secrets"


def db_root() -> Path:
    raw = (os.environ.get("JOBPIPE_DB_DIR") or "").strip()
    if raw:
        return _expand_path(raw)
    return data_root() / "db"


def primary_db_path() -> Path:
    raw = (os.environ.get("JOBPIPE_DB_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    return db_root() / "jobpipe.sqlite"


def artifacts_root() -> Path:
    raw = (os.environ.get("JOBPIPE_ARTIFACT_DIR") or "").strip()
    if raw:
        return _expand_path(raw)
    return data_root() / "artifacts"


def documents_root() -> Path:
    raw = (os.environ.get("JOBPIPE_DOCUMENTS_DIR") or "").strip()
    if raw:
        return _expand_path(raw)
    return data_root() / "documents"


def exports_root() -> Path:
    raw = (os.environ.get("JOBPIPE_EXPORT_DIR") or "").strip()
    if raw:
        return _expand_path(raw)
    return data_root() / "exports"


def profile_pack_path() -> Path:
    raw = (os.environ.get("JOBPIPE_PROFILE_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    return _prefer_existing(documents_root() / "profile_pack.md", data_root() / "profile_pack.md")


def resume_json_path() -> Path:
    raw = (os.environ.get("JOBPIPE_RESUME_JSON") or "").strip()
    if raw:
        return _expand_path(raw)
    return _prefer_existing(documents_root() / "resume.json", data_root() / "resume.json")


def application_state_path() -> Path:
    raw = (os.environ.get("JOBPIPE_APP_STATE_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    return db_root() / "application_state.json"


def gmail_token_path() -> Path:
    raw = (os.environ.get("JOBPIPE_GMAIL_TOKEN_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    return _prefer_existing(secrets_root() / "gmail_token.json", data_root() / "gmail_token.json")


def gmail_credentials_path() -> Path:
    raw = (os.environ.get("JOBPIPE_GMAIL_CREDENTIALS_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    return _prefer_existing(secrets_root() / "gmail_credentials.json", data_root() / "gmail_credentials.json")


def suggested_jobs_path() -> Path:
    raw = (os.environ.get("JOBPIPE_SUGGESTED_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    return db_root() / "suggested_jobs.jsonl"


def profile_embedding_cache_path() -> Path:
    raw = (os.environ.get("JOBPIPE_PROFILE_EMBEDDING_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    return cache_root() / "profile_embedding.npy"


def jobs_state_path() -> Path:
    raw = (os.environ.get("JOBPIPE_JOBS_STATE_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    return db_root() / "jobs_state.json"


def jobs_delta_path() -> Path:
    raw = (os.environ.get("JOBPIPE_JOBS_DELTA_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    return db_root() / "jobs_delta.jsonl"


def jobs_expired_path() -> Path:
    raw = (os.environ.get("JOBPIPE_JOBS_EXPIRED_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    return db_root() / "jobs_expired.jsonl"


__all__ = [
    "application_state_path",
    "artifacts_root",
    "cache_root",
    "data_root",
    "db_root",
    "documents_root",
    "exports_root",
    "gmail_credentials_path",
    "gmail_token_path",
    "jobs_delta_path",
    "jobs_expired_path",
    "jobs_state_path",
    "primary_db_path",
    "profile_embedding_cache_path",
    "profile_pack_path",
    "repo_root",
    "resume_json_path",
    "secrets_root",
    "suggested_jobs_path",
]
