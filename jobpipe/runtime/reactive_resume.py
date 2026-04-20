"""Thin Reactive Resume write-back helpers."""

from __future__ import annotations

from pathlib import Path

from jobpipe.core.io import now_iso
from jobpipe.core.primary_db import connect_primary_db, ensure_candidate, insert_generated_document
from jobpipe.model import ReactiveResumeRenderedDocumentRef


def record_reactive_resume_document_ref(
    db_path: str | Path,
    ref: ReactiveResumeRenderedDocumentRef,
) -> ReactiveResumeRenderedDocumentRef:
    payload = ReactiveResumeRenderedDocumentRef.model_validate(ref)
    updated_at = payload.updated_at or now_iso()

    conn = connect_primary_db(db_path)
    try:
        ensure_candidate(conn, payload.candidate_id)
        insert_generated_document(
            conn,
            {
                "document_id": payload.document_id,
                "candidate_id": payload.candidate_id,
                "job_id": payload.job_id,
                "evaluation_id": payload.evaluation_id,
                "kind": payload.kind,
                "producer": payload.producer,
                "status": payload.status,
                "storage_path": payload.storage_path,
                "preview_text": payload.preview_text,
                "document_json": payload.document_json,
                "created_at": updated_at,
                "updated_at": updated_at,
            },
        )
        conn.commit()
    finally:
        conn.close()
    return payload


__all__ = ["record_reactive_resume_document_ref"]
