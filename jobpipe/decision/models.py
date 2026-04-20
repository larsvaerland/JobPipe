from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ClaimType = Literal[
    "role_summary",
    "responsibility",
    "must_requirement",
    "preferred_requirement",
    "credential_requirement",
    "domain_requirement",
    "tool_requirement",
    "language_requirement",
    "location_requirement",
    "org_context",
    "culture_signal",
    "boilerplate",
]

ClaimStrength = Literal[
    "explicit_must",
    "explicit_preferred",
    "inferred_likely",
    "weak_signal",
    "boilerplate",
]

ClaimSubjectType = Literal[
    "role_family",
    "capability",
    "domain",
    "credential",
    "language",
    "location",
    "org_context",
    "culture",
]

SelectionSignalType = Literal[
    "structural_gate",
    "screening_signal",
    "ambiguity_tolerance",
    "evidence_burden",
]

SelectionStage = Literal["ats", "recruiter_screen", "hiring_manager", "overall"]

SignalStrength = Literal["hard", "strong", "moderate", "weak", "speculative"]

SelectionRiskLevel = Literal["low", "medium", "high", "very_high"]

DecisionDimensionKey = Literal["can_do", "can_get", "should_want", "can_explain"]

DecisionDimensionLevel = Literal["strong", "viable", "fragile", "weak"]

DecisionAction = Literal["pursue_now", "review_then_pursue", "monitor", "skip"]

CandidateEvidenceSourceType = Literal[
    "work_highlight",
    "project_case",
    "education",
    "summary_claim",
    "skill_claim",
]

EvidenceRewritePolicy = Literal["verbatim_preferred", "light_rewrite_only", "can_summarize"]

NarrativeSourceKind = Literal["manual", "guided_form", "agent_draft", "calibrated_update", "profile_pack_heuristic"]

NarrativeFragmentType = Literal["identity", "motivation", "pivot", "summary", "intro", "anti_pattern"]

NarrativeAudience = Literal["internal", "recruiter", "cover_letter", "cv_summary", "interview"]

NarrativeEvidenceLinkType = Literal[
    "supports_identity",
    "supports_pivot",
    "supports_motivation",
    "supports_role_family",
]

WatchType = Literal["employer", "role_family", "search_pattern", "source_feed", "job"]

ChangeType = Literal[
    "new_job",
    "job_changed",
    "deadline_changed",
    "selection_logic_changed",
    "watch_match",
    "status_changed",
]

ChangeMateriality = Literal["low", "medium", "high"]

CalibrationPolarity = Literal["supports", "mixed", "neutral", "caution"]


class JobClaim(BaseModel):
    claim_type: ClaimType
    claim_strength: ClaimStrength
    claim_subject_type: ClaimSubjectType
    normalized_key: str = ""
    normalized_label: str = ""
    claim_text: str
    source_basis: Literal["field", "text_pattern", "derived_pattern"] = "field"
    source_section: str = ""
    evidence_span: str = ""
    confidence_score: float = Field(ge=0, le=1)
    importance_score: float = Field(ge=0, le=1)
    claim_json: dict[str, Any] = Field(default_factory=dict)


class JobSelectionSignal(BaseModel):
    signal_type: SelectionSignalType
    signal_label: str
    selection_stage: SelectionStage
    signal_strength: SignalStrength
    normalized_key: str = ""
    evidence_required: str = ""
    confidence_score: float = Field(ge=0, le=1)
    importance_score: float = Field(ge=0, le=1)
    source_basis: Literal["explicit_claim", "derived_pattern", "evaluation_state", "market_heuristic"]
    signal_json: dict[str, Any] = Field(default_factory=dict)


class JobSelectionAssessment(BaseModel):
    structural_pass: bool
    screenability_score: int = Field(ge=0, le=100)
    title_continuity_score: int = Field(ge=0, le=100)
    domain_continuity_score: int = Field(ge=0, le=100)
    ambiguity_risk_score: int = Field(ge=0, le=100)
    evidence_burden_score: int = Field(ge=0, le=100)
    selection_risk_level: SelectionRiskLevel
    likely_rejection_vectors: list[str] = Field(default_factory=list)
    mitigation_moves: list[str] = Field(default_factory=list)
    assessment_reason: str
    assessment_json: dict[str, Any] = Field(default_factory=dict)


class JobDecisionDimension(BaseModel):
    dimension_key: DecisionDimensionKey
    level: DecisionDimensionLevel
    score: int = Field(ge=0, le=100)
    reason: str
    supporting_points: list[str] = Field(default_factory=list)
    risk_points: list[str] = Field(default_factory=list)


class JobDecisionTable(BaseModel):
    can_do: JobDecisionDimension
    can_get: JobDecisionDimension
    should_want: JobDecisionDimension
    can_explain: JobDecisionDimension
    act_now: DecisionAction
    confidence_score: float = Field(ge=0, le=1)
    table_reason: str
    next_moves: list[str] = Field(default_factory=list)
    decision_table_json: dict[str, Any] = Field(default_factory=dict)


class CandidateEvidenceUnit(BaseModel):
    evidence_unit_id: str
    candidate_id: str
    source_type: CandidateEvidenceSourceType
    source_ref: str = ""
    role_family_tags: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    capability_tags: list[str] = Field(default_factory=list)
    outcome_tags: list[str] = Field(default_factory=list)
    canonical_text: str
    rewrite_policy: EvidenceRewritePolicy
    evidence_json: dict[str, Any] = Field(default_factory=dict)


class CandidateEvidenceSelection(BaseModel):
    evidence_unit_id: str
    source_type: CandidateEvidenceSourceType
    source_ref: str = ""
    canonical_text: str
    rewrite_policy: EvidenceRewritePolicy
    relevance_score: int = Field(ge=0, le=100)
    matched_role_family_tags: list[str] = Field(default_factory=list)
    matched_domain_tags: list[str] = Field(default_factory=list)
    matched_capability_tags: list[str] = Field(default_factory=list)
    targeted_terms: list[str] = Field(default_factory=list)
    selection_reason: str


class CandidateEvidenceContext(BaseModel):
    candidate_evidence_units: list[CandidateEvidenceUnit] = Field(default_factory=list)
    selected_evidence_units: list[CandidateEvidenceSelection] = Field(default_factory=list)


class NarrativeMotivationTheme(BaseModel):
    private_driver: str = ""
    professional_framing: str
    theme_tags: list[str] = Field(default_factory=list)


class CandidateNarrativeProfile(BaseModel):
    narrative_version_id: str
    candidate_id: str
    source_kind: NarrativeSourceKind
    core_identity: list[str] = Field(default_factory=list)
    future_direction: list[str] = Field(default_factory=list)
    motivation_themes: list[NarrativeMotivationTheme] = Field(default_factory=list)
    pivot_thesis: list[str] = Field(default_factory=list)
    proof_themes: list[str] = Field(default_factory=list)
    story_boundaries: list[str] = Field(default_factory=list)
    tone_rules: list[str] = Field(default_factory=list)
    narrative_summary: str


class NarrativeFragment(BaseModel):
    fragment_id: str
    candidate_id: str
    narrative_version_id: str
    fragment_type: NarrativeFragmentType
    audience: NarrativeAudience
    canonical_text: str
    rewrite_policy: EvidenceRewritePolicy
    fragment_json: dict[str, Any] = Field(default_factory=dict)


class NarrativeEvidenceLink(BaseModel):
    narrative_link_id: str
    candidate_id: str
    narrative_version_id: str
    evidence_unit_id: str
    link_type: NarrativeEvidenceLinkType
    strength_score: float = Field(ge=0, le=1)
    notes: str


class JobNarrativeAssessment(BaseModel):
    direction_fit_score: int = Field(ge=0, le=100)
    motivation_fit_score: int = Field(ge=0, le=100)
    pivot_credibility_score: int = Field(ge=0, le=100)
    story_strength_score: int = Field(ge=0, le=100)
    misalignment_flags: list[str] = Field(default_factory=list)
    assessment_reason: str
    motivation_brief: str


class CandidateNarrativeContext(BaseModel):
    narrative_profile: CandidateNarrativeProfile
    narrative_fragments: list[NarrativeFragment] = Field(default_factory=list)
    narrative_evidence_links: list[NarrativeEvidenceLink] = Field(default_factory=list)
    job_narrative_assessment: JobNarrativeAssessment


class Watchlist(BaseModel):
    watchlist_id: str
    candidate_id: str
    watch_type: WatchType
    watch_key: str
    watch_label: str
    watch_config_json: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ChangeEvent(BaseModel):
    change_event_id: str
    candidate_id: str
    watchlist_id: str = ""
    job_id: str = ""
    change_type: ChangeType
    change_summary: str
    change_json: dict[str, Any] = Field(default_factory=dict)
    materiality: ChangeMateriality
    detected_at: str
    reviewed_at: str = ""


class MonitoringContext(BaseModel):
    watchlists: list[Watchlist] = Field(default_factory=list)
    change_events: list[ChangeEvent] = Field(default_factory=list)


class CalibrationPattern(BaseModel):
    pattern_type: Literal["role_family", "source_host"]
    pattern_key: str
    pattern_label: str
    support_count: int = Field(ge=0)
    risk_count: int = Field(ge=0)
    net_score: int
    polarity: CalibrationPolarity
    evidence_sources: list[str] = Field(default_factory=list)


class CandidateCalibrationSummary(BaseModel):
    total_feedback_events: int = Field(ge=0)
    positive_feedback_events: int = Field(ge=0)
    negative_feedback_events: int = Field(ge=0)
    manual_promotions: int = Field(ge=0)
    manual_demotions: int = Field(ge=0)
    interview_or_better_outcomes: int = Field(ge=0)
    rejection_outcomes: int = Field(ge=0)
    active_setting_keys: list[str] = Field(default_factory=list)
    role_family_patterns: list[CalibrationPattern] = Field(default_factory=list)
    source_patterns: list[CalibrationPattern] = Field(default_factory=list)
    summary_reason: str


class JobCalibrationAssessment(BaseModel):
    support_score: int = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    polarity: CalibrationPolarity
    direct_feedback_signals: list[str] = Field(default_factory=list)
    supporting_patterns: list[str] = Field(default_factory=list)
    caution_patterns: list[str] = Field(default_factory=list)
    assessment_reason: str


class CandidateCalibrationContext(BaseModel):
    calibration_summary: CandidateCalibrationSummary
    job_calibration_assessment: JobCalibrationAssessment


class DecisionContext(BaseModel):
    job_claims: list[JobClaim] = Field(default_factory=list)
    selection_signals: list[JobSelectionSignal] = Field(default_factory=list)
    selection_assessment: JobSelectionAssessment
    decision_table: JobDecisionTable


__all__ = [
    "CandidateNarrativeContext",
    "CandidateNarrativeProfile",
    "CandidateEvidenceContext",
    "CandidateEvidenceSelection",
    "CandidateEvidenceSourceType",
    "CandidateEvidenceUnit",
    "CalibrationPattern",
    "CalibrationPolarity",
    "ChangeEvent",
    "ChangeMateriality",
    "ChangeType",
    "CandidateCalibrationContext",
    "CandidateCalibrationSummary",
    "ClaimStrength",
    "ClaimSubjectType",
    "ClaimType",
    "DecisionAction",
    "DecisionContext",
    "DecisionDimensionKey",
    "DecisionDimensionLevel",
    "EvidenceRewritePolicy",
    "JobClaim",
    "JobCalibrationAssessment",
    "JobDecisionDimension",
    "JobDecisionTable",
    "JobNarrativeAssessment",
    "JobSelectionAssessment",
    "JobSelectionSignal",
    "MonitoringContext",
    "NarrativeAudience",
    "NarrativeEvidenceLink",
    "NarrativeEvidenceLinkType",
    "NarrativeFragment",
    "NarrativeFragmentType",
    "NarrativeMotivationTheme",
    "NarrativeSourceKind",
    "SelectionRiskLevel",
    "SelectionSignalType",
    "SelectionStage",
    "SignalStrength",
    "WatchType",
    "Watchlist",
]
