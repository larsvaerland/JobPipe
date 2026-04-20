from __future__ import annotations

from jobpipe.projections.jobsync import build_jobsync_application_case_projection


def test_build_jobsync_case_projection_from_dashboard_like_row() -> None:
    row = {
        "job_id": "job-1",
        "title": "Service Designer",
        "employer": "Example Kommune",
        "work_city": "Oslo",
        "work_county": "Oslo",
        "applicationDue": "2026-05-01",
        "source_url": "https://example.com/job/1",
        "application_url": "https://example.com/apply/1",
        "updated_at": "2026-04-20T10:00:00Z",
        "final_decision": "APPLY",
        "recommendation_reason": "Strong public-sector service improvement fit.",
        "selection_assessment": {
            "selection_risk_level": "medium",
            "mitigation_moves": [
                "Front-load direct service-delivery examples.",
                "Clarify public-sector adjacency.",
            ],
        },
        "job_claims": [
            {"normalized_label": "Service design", "claim_text": "Service design"},
            {"claim_text": "Cross-functional delivery"},
        ],
        "selection_signals": [
            {"signal_label": "Title continuity pressure"},
            {"signal_label": "Public-sector credibility"},
        ],
        "detail": {
            "cv_focus_mod": [
                "Led service improvement across cross-functional stakeholders.",
                "Built structured delivery in complex environments.",
            ],
        },
        "job_narrative_assessment": {
            "motivation_brief": "Credible move because the role fits structured public-service improvement."
        },
        "decision_table": {
            "can_do": {"level": "strong", "score": 82},
            "can_get": {"level": "viable", "score": 64},
            "should_want": {"level": "strong", "score": 79},
            "can_explain": {"level": "strong", "score": 76},
        },
        "generated_documents": [
            {
                "document_id": "doc-1",
                "kind": "cover_letter_docx",
                "status": "draft",
                "storage_path": "documents/default/job-1/cover-letter.docx",
                "updated_at": "2026-04-20T11:00:00Z",
            }
        ],
        "app_status": "shortlisted",
        "app_updated_at": "2026-04-20T12:00:00Z",
    }

    projection = build_jobsync_application_case_projection(row)

    assert projection.job_summary.job_id == "job-1"
    assert projection.job_summary.location == "Oslo, Oslo"
    assert projection.decision_brief.final_decision == "APPLY"
    assert projection.decision_brief.selection_risk_level == "medium"
    assert projection.decision_brief.top_claims == ["Service design", "Cross-functional delivery"]
    assert projection.decision_brief.top_selection_signals == [
        "Title continuity pressure",
        "Public-sector credibility",
    ]
    assert projection.decision_brief.top_mitigation_moves == [
        "Front-load direct service-delivery examples.",
        "Clarify public-sector adjacency.",
    ]
    assert projection.decision_brief.top_evidence_units == [
        "Led service improvement across cross-functional stakeholders.",
        "Built structured delivery in complex environments.",
    ]
    assert "can_do:strong 82" in projection.decision_brief.decision_table_summary
    assert projection.current_application_status == "shortlisted"
    assert projection.document_refs[0].kind == "cover_letter_docx"
    assert projection.next_action_hint == "Review decision brief and prepare application materials."
