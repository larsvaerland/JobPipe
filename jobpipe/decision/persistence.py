from __future__ import annotations

import hashlib
import sqlite3

from jobpipe.core.io import now_iso
from jobpipe.core.primary_db import (
    replace_candidate_evidence_units,
    replace_job_claims,
    replace_job_selection_signals,
    replace_narrative_evidence_links,
    replace_narrative_fragments,
    replace_watchlists,
    upsert_candidate_narrative_profile,
    upsert_change_event,
    upsert_job_decision_table,
    upsert_job_narrative_assessment,
    upsert_job_selection_assessment,
)

from .models import (
    CandidateEvidenceContext,
    CandidateNarrativeContext,
    DecisionContext,
    MonitoringContext,
)


def _hash_id(prefix: str, *parts: str) -> str:
    raw = "|".join(parts)
    return f"{prefix}_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def persist_job_decision_state(
    conn: sqlite3.Connection,
    *,
    candidate_id: str,
    job_id: str,
    evaluation_id: str,
    decision_context: DecisionContext,
    updated_at: str = "",
    source_record_id: str = "",
) -> None:
    ts = updated_at or now_iso()

    claim_rows = []
    for claim in decision_context.job_claims:
        claim_rows.append(
            {
                "job_id": job_id,
                "claim_id": _hash_id(
                    "claim",
                    job_id,
                    claim.claim_type,
                    claim.claim_subject_type,
                    claim.normalized_key or claim.normalized_label or claim.claim_text,
                    claim.claim_text,
                    claim.source_section,
                ),
                "source_record_id": source_record_id,
                "claim_type": claim.claim_type,
                "claim_strength": claim.claim_strength,
                "claim_subject_type": claim.claim_subject_type,
                "normalized_key": claim.normalized_key,
                "normalized_label": claim.normalized_label,
                "claim_text": claim.claim_text,
                "source_basis": claim.source_basis,
                "source_section": claim.source_section,
                "evidence_span": claim.evidence_span,
                "confidence_score": claim.confidence_score,
                "importance_score": claim.importance_score,
                "claim_json": claim.claim_json,
                "created_at": ts,
                "updated_at": ts,
            }
        )
    replace_job_claims(conn, job_id, claim_rows)

    signal_rows = []
    for signal in decision_context.selection_signals:
        signal_rows.append(
            {
                "job_id": job_id,
                "signal_id": _hash_id(
                    "signal",
                    job_id,
                    signal.normalized_key or signal.signal_label,
                    signal.signal_type,
                    signal.selection_stage,
                    signal.signal_label,
                ),
                "signal_type": signal.signal_type,
                "signal_label": signal.signal_label,
                "selection_stage": signal.selection_stage,
                "signal_strength": signal.signal_strength,
                "normalized_key": signal.normalized_key,
                "evidence_required": signal.evidence_required,
                "confidence_score": signal.confidence_score,
                "importance_score": signal.importance_score,
                "source_basis": signal.source_basis,
                "signal_json": signal.signal_json,
                "created_at": ts,
                "updated_at": ts,
            }
        )
    replace_job_selection_signals(conn, job_id, signal_rows)

    assessment = decision_context.selection_assessment
    upsert_job_selection_assessment(
        conn,
        {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "evaluation_id": evaluation_id,
            "structural_pass": 1 if assessment.structural_pass else 0,
            "screenability_score": assessment.screenability_score,
            "title_continuity_score": assessment.title_continuity_score,
            "domain_continuity_score": assessment.domain_continuity_score,
            "ambiguity_risk_score": assessment.ambiguity_risk_score,
            "evidence_burden_score": assessment.evidence_burden_score,
            "selection_risk_level": assessment.selection_risk_level,
            "likely_rejection_vectors_json": assessment.likely_rejection_vectors,
            "mitigation_moves_json": assessment.mitigation_moves,
            "assessment_reason": assessment.assessment_reason,
            "assessment_json": assessment.assessment_json,
            "updated_at": ts,
        },
    )

    table = decision_context.decision_table
    upsert_job_decision_table(
        conn,
        {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "evaluation_id": evaluation_id,
            "can_do_level": table.can_do.level,
            "can_do_score": table.can_do.score,
            "can_do_reason": table.can_do.reason,
            "can_do_supporting_points_json": table.can_do.supporting_points,
            "can_do_risk_points_json": table.can_do.risk_points,
            "can_get_level": table.can_get.level,
            "can_get_score": table.can_get.score,
            "can_get_reason": table.can_get.reason,
            "can_get_supporting_points_json": table.can_get.supporting_points,
            "can_get_risk_points_json": table.can_get.risk_points,
            "should_want_level": table.should_want.level,
            "should_want_score": table.should_want.score,
            "should_want_reason": table.should_want.reason,
            "should_want_supporting_points_json": table.should_want.supporting_points,
            "should_want_risk_points_json": table.should_want.risk_points,
            "can_explain_level": table.can_explain.level,
            "can_explain_score": table.can_explain.score,
            "can_explain_reason": table.can_explain.reason,
            "can_explain_supporting_points_json": table.can_explain.supporting_points,
            "can_explain_risk_points_json": table.can_explain.risk_points,
            "act_now": table.act_now,
            "confidence_score": table.confidence_score,
            "table_reason": table.table_reason,
            "next_moves_json": table.next_moves,
            "decision_table_json": table.model_dump(mode="json"),
            "updated_at": ts,
        },
    )


def persist_candidate_materials(
    conn: sqlite3.Connection,
    *,
    candidate_id: str,
    job_id: str,
    evaluation_id: str,
    evidence_context: CandidateEvidenceContext,
    narrative_context: CandidateNarrativeContext,
    updated_at: str = "",
) -> None:
    ts = updated_at or now_iso()

    replace_candidate_evidence_units(
        conn,
        candidate_id,
        [
            {
                "candidate_id": candidate_id,
                "evidence_unit_id": unit.evidence_unit_id,
                "source_type": unit.source_type,
                "source_ref": unit.source_ref,
                "role_family_tags_json": unit.role_family_tags,
                "domain_tags_json": unit.domain_tags,
                "capability_tags_json": unit.capability_tags,
                "outcome_tags_json": unit.outcome_tags,
                "canonical_text": unit.canonical_text,
                "rewrite_policy": unit.rewrite_policy,
                "evidence_json": unit.evidence_json,
                "created_at": ts,
                "updated_at": ts,
            }
            for unit in evidence_context.candidate_evidence_units
        ],
    )

    profile = narrative_context.narrative_profile
    upsert_candidate_narrative_profile(
        conn,
        {
            "narrative_version_id": profile.narrative_version_id,
            "candidate_id": candidate_id,
            "source_kind": profile.source_kind,
            "core_identity_json": profile.core_identity,
            "future_direction_json": profile.future_direction,
            "motivation_themes_json": [theme.model_dump(mode="json") for theme in profile.motivation_themes],
            "pivot_thesis_json": profile.pivot_thesis,
            "proof_themes_json": profile.proof_themes,
            "story_boundaries_json": profile.story_boundaries,
            "tone_rules_json": profile.tone_rules,
            "narrative_summary": profile.narrative_summary,
            "is_active": 1,
            "created_at": ts,
            "updated_at": ts,
        },
    )

    replace_narrative_fragments(
        conn,
        candidate_id,
        profile.narrative_version_id,
        [
            {
                "fragment_id": fragment.fragment_id,
                "candidate_id": candidate_id,
                "narrative_version_id": profile.narrative_version_id,
                "fragment_type": fragment.fragment_type,
                "audience": fragment.audience,
                "canonical_text": fragment.canonical_text,
                "rewrite_policy": fragment.rewrite_policy,
                "fragment_json": fragment.fragment_json,
                "created_at": ts,
                "updated_at": ts,
            }
            for fragment in narrative_context.narrative_fragments
        ],
    )

    replace_narrative_evidence_links(
        conn,
        candidate_id,
        profile.narrative_version_id,
        [
            {
                "narrative_link_id": link.narrative_link_id,
                "candidate_id": candidate_id,
                "narrative_version_id": profile.narrative_version_id,
                "evidence_unit_id": link.evidence_unit_id,
                "link_type": link.link_type,
                "strength_score": link.strength_score,
                "notes": link.notes,
                "created_at": ts,
                "updated_at": ts,
            }
            for link in narrative_context.narrative_evidence_links
        ],
    )

    selected_evidence_unit_ids = [selection.evidence_unit_id for selection in evidence_context.selected_evidence_units]
    narrative_fragment_ids = [fragment.fragment_id for fragment in narrative_context.narrative_fragments]
    assessment = narrative_context.job_narrative_assessment
    upsert_job_narrative_assessment(
        conn,
        {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "evaluation_id": evaluation_id,
            "narrative_version_id": profile.narrative_version_id,
            "direction_fit_score": assessment.direction_fit_score,
            "motivation_fit_score": assessment.motivation_fit_score,
            "pivot_credibility_score": assessment.pivot_credibility_score,
            "story_strength_score": assessment.story_strength_score,
            "misalignment_flags_json": assessment.misalignment_flags,
            "assessment_reason": assessment.assessment_reason,
            "motivation_brief": assessment.motivation_brief,
            "assessment_json": {
                "selected_evidence_unit_ids": selected_evidence_unit_ids,
                "narrative_fragment_ids": narrative_fragment_ids,
            },
            "updated_at": ts,
        },
    )


def persist_monitoring_state(
    conn: sqlite3.Connection,
    *,
    candidate_id: str,
    monitoring_context: MonitoringContext,
    updated_at: str = "",
    replace_watchlists_state: bool = True,
) -> None:
    ts = updated_at or now_iso()

    if replace_watchlists_state:
        replace_watchlists(
            conn,
            candidate_id,
            [
                {
                    "watchlist_id": watch.watchlist_id,
                    "candidate_id": candidate_id,
                    "watch_type": watch.watch_type,
                    "watch_key": watch.watch_key,
                    "watch_label": watch.watch_label,
                    "watch_config_json": watch.watch_config_json,
                    "is_active": 1 if watch.is_active else 0,
                    "materiality": watch.materiality,
                    "updated_at": ts,
                }
                for watch in monitoring_context.watchlists
            ],
        )

    for event in monitoring_context.change_events:
        upsert_change_event(
            conn,
            {
                "change_event_id": event.change_event_id,
                "candidate_id": candidate_id,
                "watchlist_id": event.watchlist_id,
                "job_id": event.job_id,
                "change_type": event.change_type,
                "change_summary": event.change_summary,
                "change_json": event.change_json,
                "materiality": event.materiality,
                "detected_at": event.detected_at,
                "reviewed_at": event.reviewed_at,
                "updated_at": ts,
            },
        )


__all__ = [
    "persist_candidate_materials",
    "persist_job_decision_state",
    "persist_monitoring_state",
]
