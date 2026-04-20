from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

TriageDecision = Literal["SKIP", "REVIEW", "APPLY_CANDIDATE"]
ReverseDecision = Literal["SKIP_CONFIRMED", "REVIVE_REVIEW", "REVIVE_APPLY"]
FinalDecision = Literal["APPLY_STRONGLY", "APPLY", "REVIEW_HIGH", "REVIEW_LOW", "SKIP"]
JobSyncStatusEventType = Literal[
    "shortlisted",
    "called",
    "applied",
    "interview",
    "second_interview",
    "accepted",
    "rejected",
    "dismissed",
]
ReactiveResumeRenderTarget = Literal["reactive_resume_json", "docx", "pdf"]


class TriageOut(BaseModel):
    triage_decision: TriageDecision
    confidence: float = Field(ge=0, le=1)
    explanation: str
    signals: List[str] = Field(default_factory=list)
    forced_safety: bool = False
    noise_level: Optional[float] = Field(default=None, ge=0, le=1)

    @field_validator("confidence")
    @classmethod
    def no_zero_confidence(cls, v: float) -> float:
        if v < 0.10:
            return 0.80
        return v


class ReverseTriageOut(BaseModel):
    reverse_decision: ReverseDecision
    confidence: float = Field(ge=0, le=1)
    rationale: str
    reasoning_flags: List[str] = Field(default_factory=list)


class JobParse(BaseModel):
    role_summary: str
    responsibilities: List[str]
    requirements_must: List[str]
    requirements_nice: List[str]
    seniority: Optional[str] = None
    domain_tags: List[str] = Field(default_factory=list)
    tools_tech: List[str] = Field(default_factory=list)
    org_context: Optional[str] = None
    red_flags: List[str] = Field(default_factory=list)


class ProfileMatchDimensions(BaseModel):
    """Dimension-level scoring for profile match. Each 0-100."""

    role_fit: int = Field(
        ge=0,
        le=100,
        description="Does the role TYPE match (PO, service owner, PM, digital project lead)?",
    )
    domain_fit: int = Field(
        ge=0,
        le=100,
        description="Does the domain/sector match candidate experience?",
    )
    seniority_fit: int = Field(
        ge=0,
        le=100,
        description="Does the seniority/autonomy level match candidate trajectory?",
    )
    skills_fit: int = Field(
        ge=0,
        le=100,
        description="Do the explicit skills/tools/methods required match candidate toolkit?",
    )


class ProfileMatchOut(BaseModel):
    dimensions: Optional[ProfileMatchDimensions] = None
    fit_score: int = Field(ge=0, le=100)
    match_level: Literal["strong", "medium", "weak"]
    overlaps: List[str]
    gaps: List[str]
    hard_blockers: List[str] = Field(default_factory=list)
    notes: str = ""


class PivotOut(BaseModel):
    pivot_score: int = Field(ge=0, le=100)
    pivot_type: str
    potential_risk: Literal["low", "medium", "high"]
    why_it_matters: List[str]


class ModeratorOut(BaseModel):
    final_decision: FinalDecision
    confidence: float = Field(ge=0, le=1)
    recommendation_reason: str
    cv_focus: List[str] = Field(default_factory=list)
    feedback_flags: List[str] = Field(default_factory=list)


class ApplicationPackOut(BaseModel):
    positioning_headline: str
    top_value_props: List[str]
    evidence_map: List[str]
    gap_mitigations: List[str]
    cover_letter_angle: str
    interview_prep: List[str]
    cv_highlights: List[str] = Field(default_factory=list)
    cv_experience_refs: List[str] = Field(default_factory=list)


class JobSyncJobSummary(BaseModel):
    job_id: str
    title: str
    employer: str = ""
    location: str = ""
    application_due: str = ""
    source_url: str = ""
    application_url: str = ""
    updated_at: str = ""


class JobSyncDecisionBrief(BaseModel):
    final_decision: str
    recommendation_reason: str = ""
    decision_table_summary: str = ""
    selection_risk_level: str = ""
    top_claims: List[str] = Field(default_factory=list)
    top_selection_signals: List[str] = Field(default_factory=list)
    top_mitigation_moves: List[str] = Field(default_factory=list)
    top_evidence_units: List[str] = Field(default_factory=list)
    narrative_motivation_brief: str = ""


class JobSyncDocumentRef(BaseModel):
    document_id: str = ""
    kind: str
    status: str = ""
    storage_path: str = ""
    updated_at: str = ""


class JobSyncApplicationCaseProjection(BaseModel):
    job_summary: JobSyncJobSummary
    decision_brief: JobSyncDecisionBrief
    document_refs: List[JobSyncDocumentRef] = Field(default_factory=list)
    current_application_status: str = ""
    last_application_event_at: str = ""
    next_action_hint: str = ""


class JobSyncApplicationStatusEvent(BaseModel):
    job_id: str
    candidate_id: str
    event_type: JobSyncStatusEventType
    event_at: str
    source: str = "jobsync"
    notes: str = ""
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class JobSyncNoteEvent(BaseModel):
    job_id: str
    candidate_id: str
    note_text: str
    created_at: str
    source: str = "jobsync"


class JobSyncDocumentRefEvent(BaseModel):
    job_id: str
    candidate_id: str
    document_kind: str
    storage_path: str
    status: str = ""
    created_at: str
    source: str = "jobsync"


class ReactiveResumeImportProjection(BaseModel):
    candidate_id: str
    resume_source_id: str
    schema_version: str = "v1"
    basics: Dict[str, Any] = Field(default_factory=dict)
    work: List[Dict[str, Any]] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    skills: List[Dict[str, Any]] = Field(default_factory=list)
    languages: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReactiveResumeTailoredCVPlan(BaseModel):
    candidate_id: str
    job_id: str
    evaluation_id: str = ""
    variant_strategy: Literal["conservative", "balanced", "aggressive"] = "balanced"
    selected_evidence_unit_ids: List[str] = Field(default_factory=list)
    selected_section_order: List[str] = Field(default_factory=list)
    suppressed_items: List[str] = Field(default_factory=list)
    summary_brief: str = ""
    rewrite_constraints: List[str] = Field(default_factory=list)
    claim_targets: List[str] = Field(default_factory=list)
    selection_mitigation_targets: List[str] = Field(default_factory=list)


class ReactiveResumeTailoredCVProjection(BaseModel):
    headline: str = ""
    summary_text: str = ""
    section_plan: List[Dict[str, Any]] = Field(default_factory=list)
    selected_bullets: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    render_target: ReactiveResumeRenderTarget = "reactive_resume_json"


class ReactiveResumeRenderedDocumentRef(BaseModel):
    document_id: str
    candidate_id: str
    job_id: str
    evaluation_id: str = ""
    kind: str
    storage_path: str
    status: str = "draft"
    producer: str = "reactive_resume"
    updated_at: str
    preview_text: str = ""
    document_json: Dict[str, Any] = Field(default_factory=dict)


class RunMeta(BaseModel):
    run_id: str
    pipeline_name: str
    created_at: str


class JobContext(BaseModel):
    meta: RunMeta
    job_id: str
    job: Dict[str, Any]
    profile_pack: str

    triage: Optional[TriageOut] = None
    reverse_triage: Optional[ReverseTriageOut] = None
    parsed: Optional[JobParse] = None
    profile_match: Optional[ProfileMatchOut] = None
    pivot: Optional[PivotOut] = None
    moderator: Optional[ModeratorOut] = None
    application_pack: Optional[ApplicationPackOut] = None
    notes: Dict[str, Any] = Field(default_factory=dict)

    def snapshot_summary(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "title": (self.job.get("title") or "").strip(),
            "employer": (self.job.get("employer_name") or "").strip(),
            "triage_decision": self.triage.triage_decision if self.triage else None,
            "triage_confidence": self.triage.confidence if self.triage else None,
            "triage_signals": self.triage.signals if self.triage else [],
            "final_decision": self.moderator.final_decision if self.moderator else None,
            "fit_score": self.profile_match.fit_score if self.profile_match else None,
            "pivot_score": self.pivot.pivot_score if self.pivot else None,
            "confidence": self.moderator.confidence if self.moderator else None,
        }


__all__ = [
    "ApplicationPackOut",
    "FinalDecision",
    "JobContext",
    "JobParse",
    "JobSyncApplicationCaseProjection",
    "JobSyncApplicationStatusEvent",
    "JobSyncDecisionBrief",
    "JobSyncDocumentRef",
    "JobSyncDocumentRefEvent",
    "JobSyncJobSummary",
    "JobSyncNoteEvent",
    "JobSyncStatusEventType",
    "ModeratorOut",
    "PivotOut",
    "ProfileMatchDimensions",
    "ProfileMatchOut",
    "ReactiveResumeImportProjection",
    "ReactiveResumeRenderedDocumentRef",
    "ReactiveResumeRenderTarget",
    "ReactiveResumeTailoredCVPlan",
    "ReactiveResumeTailoredCVProjection",
    "ReverseDecision",
    "ReverseTriageOut",
    "RunMeta",
    "TriageDecision",
    "TriageOut",
]
