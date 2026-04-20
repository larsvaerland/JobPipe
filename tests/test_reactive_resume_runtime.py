from __future__ import annotations

import sqlite3

from jobpipe.model import ReactiveResumeRenderedDocumentRef
from jobpipe.runtime import record_reactive_resume_document_ref


def test_record_reactive_resume_document_ref_writes_generated_documents(tmp_path) -> None:
    db_path = tmp_path / "jobpipe.sqlite"

    record_reactive_resume_document_ref(
        db_path,
        ReactiveResumeRenderedDocumentRef(
            document_id="doc-rr-1",
            candidate_id="candidate-a",
            job_id="job-123",
            evaluation_id="run-123",
            kind="tailored_cv_docx",
            storage_path="C:/tmp/tailored_cv.docx",
            status="ready",
            producer="reactive_resume",
            updated_at="2026-04-20T12:00:00Z",
            preview_text="Tailored CV",
            document_json={"template": "ats-safe"},
        ),
    )

    con = sqlite3.connect(str(db_path))
    row = con.execute(
        """
        SELECT kind, producer, status, storage_path, preview_text
        FROM generated_documents
        WHERE candidate_id = ? AND job_id = ?
        """,
        ["candidate-a", "job-123"],
    ).fetchone()
    con.close()

    assert row == ("tailored_cv_docx", "reactive_resume", "ready", "C:/tmp/tailored_cv.docx", "Tailored CV")
