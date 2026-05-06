"""Persist and mutate AuthoringSession JSON files in per-job run directories."""
from __future__ import annotations

import datetime
import json
import uuid
from pathlib import Path
from typing import Optional

from jobpipe.model.schema import AcceptedPatch, AuthoringSession, SuggestedPatch


def session_path(job_dir: Path) -> Path:
    return job_dir / "authoring_session.json"


def load_session(job_dir: Path) -> Optional[AuthoringSession]:
    p = session_path(job_dir)
    if not p.exists():
        return None
    try:
        return AuthoringSession.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_session(job_dir: Path, session: AuthoringSession) -> None:
    session_path(job_dir).write_text(
        session.model_dump_json(indent=2), encoding="utf-8"
    )


def get_or_create_session(job_dir: Path, job_id: str, candidate_id: str) -> AuthoringSession:
    existing = load_session(job_dir)
    if existing is not None:
        return existing
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    session = AuthoringSession(
        session_id=str(uuid.uuid4()),
        job_id=job_id,
        candidate_id=candidate_id,
        created_at=now,
        updated_at=now,
    )
    save_session(job_dir, session)
    return session


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def append_chat_turn(session: AuthoringSession, role: str, content: str) -> AuthoringSession:
    session.chat_history.append({"role": role, "content": content, "ts": _now_iso()})
    session.updated_at = _now_iso()
    return session


def add_suggested_patch(session: AuthoringSession, patch: SuggestedPatch) -> AuthoringSession:
    session.suggested_patches.append(patch)
    session.updated_at = _now_iso()
    return session


def accept_patch(session: AuthoringSession, patch_id: str) -> AuthoringSession:
    now = _now_iso()
    for patch in session.suggested_patches:
        if patch.patch_id == patch_id and patch.status == "pending":
            patch.status = "accepted"
            session.accepted_patches.append(
                AcceptedPatch(
                    patch_id=patch.patch_id,
                    kind=patch.kind,
                    section_ref=patch.section_ref,
                    accepted_text=patch.suggested_text,
                    accepted_at=now,
                )
            )
            break
    session.updated_at = now
    return session


def reject_patch(session: AuthoringSession, patch_id: str) -> AuthoringSession:
    for patch in session.suggested_patches:
        if patch.patch_id == patch_id and patch.status == "pending":
            patch.status = "rejected"
            break
    session.updated_at = _now_iso()
    return session
