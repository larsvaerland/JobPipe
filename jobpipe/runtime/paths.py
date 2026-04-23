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


def data_root() -> Path | None:
    raw = (os.environ.get("JOBPIPE_DATA_DIR") or "").strip()
    if not raw:
        return None
    return _expand_path(raw)


def cache_root() -> Path:
    raw = (os.environ.get("JOBPIPE_CACHE_DIR") or "").strip()
    if raw:
        return _expand_path(raw)
    root = data_root()
    if root is not None:
        return root / "cache"
    return repo_root() / "reports"


def secrets_root() -> Path:
    raw = (os.environ.get("JOBPIPE_SECRETS_DIR") or "").strip()
    if raw:
        return _expand_path(raw)
    root = data_root()
    if root is not None:
        return root / "secrets"
    return repo_root() / "reports"


def db_root() -> Path:
    raw = (os.environ.get("JOBPIPE_DB_DIR") or "").strip()
    if raw:
        return _expand_path(raw)
    root = data_root()
    if root is not None:
        return root / "db"
    return repo_root() / "reports"


def primary_db_path() -> Path:
    raw = (os.environ.get("JOBPIPE_DB_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    return db_root() / "jobpipe.sqlite"


def artifacts_root() -> Path:
    raw = (os.environ.get("JOBPIPE_ARTIFACT_DIR") or "").strip()
    if raw:
        return _expand_path(raw)
    root = data_root()
    if root is not None:
        return root / "artifacts"
    return repo_root() / "out_runs"


def documents_root() -> Path:
    raw = (os.environ.get("JOBPIPE_DOCUMENTS_DIR") or "").strip()
    if raw:
        return _expand_path(raw)
    root = data_root()
    if root is not None:
        return root / "documents"
    return repo_root() / "reports" / "documents"


def exports_root() -> Path:
    raw = (os.environ.get("JOBPIPE_EXPORT_DIR") or "").strip()
    if raw:
        return _expand_path(raw)
    root = data_root()
    if root is not None:
        return root / "exports"
    return repo_root() / "reports"


def profile_dir() -> Path:
    """
    Authoritative profile input folder.

    Contract: mirrors the Job Hunter Crew (CrewAI) `profile/` layout:
      profile/profile_pack.md     — truth source for triage + authoring
      profile/resume.json         — JSON Resume 1.0
      profile/constraints.md      — hard constraints (geo, language, comp, timeline)
      profile/motivation.md       — strategic direction (role types, stage, team)
      profile/cover_letter_voice.md — authoring voice rules (T002)
      profile/*.example           — templates for future candidates

    Override with JOBPIPE_PROFILE_DIR.
    """
    raw = (os.environ.get("JOBPIPE_PROFILE_DIR") or "").strip()
    if raw:
        return _expand_path(raw)
    return repo_root() / "profile"


def profile_pack_path() -> Path:
    raw = (os.environ.get("JOBPIPE_PROFILE_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    # Preferred: <repo_root>/profile/profile_pack.md (Job Hunter Crew layout)
    dir_candidate = profile_dir() / "profile_pack.md"
    if dir_candidate.exists():
        return dir_candidate
    root = data_root()
    if root is not None:
        return _prefer_existing(documents_root() / "profile_pack.md", root / "profile_pack.md")
    return repo_root() / "profile_pack.md"


def resume_json_path() -> Path:
    raw = (os.environ.get("JOBPIPE_RESUME_JSON") or "").strip()
    if raw:
        return _expand_path(raw)
    # Preferred: <repo_root>/profile/resume.json (Job Hunter Crew layout)
    dir_candidate = profile_dir() / "resume.json"
    if dir_candidate.exists():
        return dir_candidate
    root = data_root()
    if root is not None:
        return _prefer_existing(documents_root() / "resume.json", root / "resume.json")
    return repo_root() / "reports" / "resume.json"


def application_state_path() -> Path:
    raw = (os.environ.get("JOBPIPE_APP_STATE_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    root = data_root()
    if root is not None:
        return db_root() / "application_state.json"
    return repo_root() / "reports" / "application_state.json"


def gmail_token_path() -> Path:
    raw = (os.environ.get("JOBPIPE_GMAIL_TOKEN_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    root = data_root()
    if root is not None:
        return _prefer_existing(secrets_root() / "gmail_token.json", root / "gmail_token.json")
    return repo_root() / "reports" / "gmail_token.json"


def gmail_credentials_path() -> Path:
    raw = (os.environ.get("JOBPIPE_GMAIL_CREDENTIALS_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    root = data_root()
    if root is not None:
        return _prefer_existing(secrets_root() / "gmail_credentials.json", root / "gmail_credentials.json")
    return repo_root() / "reports" / "gmail_credentials.json"


def suggested_jobs_path() -> Path:
    raw = (os.environ.get("JOBPIPE_SUGGESTED_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    root = data_root()
    if root is not None:
        return db_root() / "suggested_jobs.jsonl"
    return repo_root() / "reports" / "suggested_jobs.jsonl"


def profile_embedding_cache_path() -> Path:
    raw = (os.environ.get("JOBPIPE_PROFILE_EMBEDDING_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    root = data_root()
    if root is not None:
        return cache_root() / "profile_embedding.npy"
    return repo_root() / "reports" / "profile_embedding.npy"


def jobs_state_path() -> Path:
    raw = (os.environ.get("JOBPIPE_JOBS_STATE_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    root = data_root()
    if root is not None:
        return db_root() / "jobs_state.json"
    return repo_root() / "jobs_state.json"


def jobs_delta_path() -> Path:
    raw = (os.environ.get("JOBPIPE_JOBS_DELTA_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    root = data_root()
    if root is not None:
        return db_root() / "jobs_delta.jsonl"
    return repo_root() / "jobs_delta.jsonl"


def jobs_expired_path() -> Path:
    raw = (os.environ.get("JOBPIPE_JOBS_EXPIRED_PATH") or "").strip()
    if raw:
        return _expand_path(raw)
    root = data_root()
    if root is not None:
        return db_root() / "jobs_expired.jsonl"
    return repo_root() / "jobs_expired.jsonl"


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
    "profile_dir",
    "profile_embedding_cache_path",
    "profile_pack_path",
    "repo_root",
    "resume_json_path",
    "secrets_root",
    "suggested_jobs_path",
]
