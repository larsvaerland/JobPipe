from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Mapping

from .models import CandidateEvidenceContext, CandidateEvidenceSelection, CandidateEvidenceUnit

_ROLE_FAMILY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("product", ("product", "roadmap", "backlog", "priorit", "plattform", "platform")),
    ("project_delivery", ("project", "delivery", "implement", "rollout", "go live", "program")),
    ("operations", ("operations", "drift", "service", "support", "process", "improvement")),
    ("transformation", ("transform", "change", "transition", "moderniz", "reorgan", "continuous improvement")),
    ("leadership", ("lead", "manager", "head", "principal", "director", "stakeholder")),
)

_DOMAIN_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("banking_finance", ("bank", "banking", "finance", "financial", "insurance", "fintech")),
    ("public_sector", ("public sector", "government", "municipal", "kommune", "state", "regulatory")),
    ("healthcare", ("health", "healthcare", "hospital", "clinic", "medical")),
    ("saas_software", ("saas", "software", "platform", "b2b", "digital product")),
    ("retail_commerce", ("retail", "commerce", "ecommerce", "marketplace", "butikk")),
)

_CAPABILITY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("stakeholder_management", ("stakeholder", "cross-functional", "cross functional", "coordination", "coordiner", "samspill")),
    ("product_strategy", ("product strategy", "roadmap", "priorit", "portfolio", "product")),
    ("delivery_execution", ("delivery", "implement", "launch", "rollout", "execution", "milepæl", "milestone")),
    ("process_improvement", ("improvement", "efficiency", "process", "workflow", "continuous improvement", "optimal")),
    ("analytics_insight", ("sql", "excel", "analytics", "analysis", "reporting", "dashboard", "data")),
    ("vendor_partner_management", ("vendor", "supplier", "partner", "procurement", "contract")),
    ("change_management", ("change", "transformation", "adoption", "training", "forankr", "enablement")),
)

_OUTCOME_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("delivery", ("delivered", "launched", "implemented", "rolled out", "shipped")),
    ("efficiency", ("improved", "reduced", "streamlined", "automated", "optimized")),
    ("growth", ("increased", "grew", "scal", "revenue", "adoption")),
    ("quality", ("quality", "stability", "reliability", "compliance", "audit")),
)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _text_blob(parts: Iterable[Any]) -> str:
    return " ".join(_clean_text(part) for part in parts if _clean_text(part))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9_]+", text.lower()) if len(token) >= 3}


def _tags_for_patterns(text: str, patterns: tuple[tuple[str, tuple[str, ...]], ...]) -> list[str]:
    lowered = text.lower()
    tags: list[str] = []
    for tag, needles in patterns:
        if any(needle in lowered for needle in needles):
            tags.append(tag)
    return tags


def _rewrite_policy_for_source(source_type: str) -> str:
    if source_type == "education":
        return "verbatim_preferred"
    if source_type == "summary_claim":
        return "can_summarize"
    return "light_rewrite_only"


def _make_evidence_unit_id(candidate_id: str, source_type: str, source_ref: str, canonical_text: str) -> str:
    raw = f"{candidate_id}|{source_type}|{source_ref}|{canonical_text}"
    return "evidence_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _base_tags(text: str) -> tuple[list[str], list[str], list[str], list[str]]:
    role_family_tags = _tags_for_patterns(text, _ROLE_FAMILY_PATTERNS)
    domain_tags = _tags_for_patterns(text, _DOMAIN_PATTERNS)
    capability_tags = _tags_for_patterns(text, _CAPABILITY_PATTERNS)
    outcome_tags = _tags_for_patterns(text, _OUTCOME_PATTERNS)
    if re.search(r"\b\d+[%+]?\b", text):
        outcome_tags = sorted({*outcome_tags, "quantified_result"})
    return role_family_tags, domain_tags, capability_tags, outcome_tags


def derive_candidate_evidence_units(
    resume_json: Mapping[str, Any],
    *,
    candidate_id: str = "default",
) -> list[CandidateEvidenceUnit]:
    from jobpipe.core.rr_compat import normalize_rr_to_jsonresume
    resume_json = normalize_rr_to_jsonresume(dict(resume_json))
    units: list[CandidateEvidenceUnit] = []

    for work_index, work_entry in enumerate(resume_json.get("work", []) or []):
        company = _clean_text(work_entry.get("name") or work_entry.get("company"))
        position = _clean_text(work_entry.get("position"))
        summary = _clean_text(work_entry.get("summary"))
        base_text = _text_blob([company, position, summary])
        role_family_tags, domain_tags, capability_tags, outcome_tags = _base_tags(base_text)

        for highlight_index, highlight in enumerate(work_entry.get("highlights", []) or []):
            canonical_text = _clean_text(highlight)
            if not canonical_text:
                continue
            combined_text = _text_blob([base_text, canonical_text])
            highlight_role_tags, highlight_domain_tags, highlight_capability_tags, highlight_outcome_tags = _base_tags(combined_text)
            source_ref = f"work:{company or 'unknown'}:{position or 'unknown'}:{highlight_index}"
            units.append(
                CandidateEvidenceUnit(
                    evidence_unit_id=_make_evidence_unit_id(candidate_id, "work_highlight", source_ref, canonical_text),
                    candidate_id=candidate_id,
                    source_type="work_highlight",
                    source_ref=source_ref,
                    role_family_tags=sorted({*role_family_tags, *highlight_role_tags}),
                    domain_tags=sorted({*domain_tags, *highlight_domain_tags}),
                    capability_tags=sorted({*capability_tags, *highlight_capability_tags}),
                    outcome_tags=sorted({*outcome_tags, *highlight_outcome_tags}),
                    canonical_text=canonical_text,
                    rewrite_policy="light_rewrite_only",
                    evidence_json={
                        "company": company,
                        "position": position,
                        "summary": summary,
                        "highlight_index": highlight_index,
                    },
                )
            )

    for project_index, project in enumerate(resume_json.get("projects", []) or []):
        name = _clean_text(project.get("name"))
        description = _clean_text(project.get("description"))
        canonical_text = description or name
        if not canonical_text:
            continue
        combined_text = _text_blob([name, description])
        role_family_tags, domain_tags, capability_tags, outcome_tags = _base_tags(combined_text)
        source_ref = f"project:{name or project_index}"
        units.append(
            CandidateEvidenceUnit(
                evidence_unit_id=_make_evidence_unit_id(candidate_id, "project_case", source_ref, canonical_text),
                candidate_id=candidate_id,
                source_type="project_case",
                source_ref=source_ref,
                role_family_tags=role_family_tags,
                domain_tags=domain_tags,
                capability_tags=capability_tags,
                outcome_tags=outcome_tags,
                canonical_text=canonical_text,
                rewrite_policy="light_rewrite_only",
                evidence_json={"project_name": name, "project_index": project_index},
            )
        )

    for education_index, education in enumerate(resume_json.get("education", []) or []):
        institution = _clean_text(education.get("institution"))
        area = _clean_text(education.get("area"))
        study_type = _clean_text(education.get("studyType"))
        canonical_text = _text_blob([study_type, area, institution]).strip()
        if not canonical_text:
            continue
        combined_text = _text_blob([institution, area, study_type])
        role_family_tags, domain_tags, capability_tags, outcome_tags = _base_tags(combined_text)
        source_ref = f"education:{institution or education_index}:{area or study_type or 'general'}"
        units.append(
            CandidateEvidenceUnit(
                evidence_unit_id=_make_evidence_unit_id(candidate_id, "education", source_ref, canonical_text),
                candidate_id=candidate_id,
                source_type="education",
                source_ref=source_ref,
                role_family_tags=role_family_tags,
                domain_tags=domain_tags,
                capability_tags=capability_tags,
                outcome_tags=outcome_tags,
                canonical_text=canonical_text,
                rewrite_policy="verbatim_preferred",
                evidence_json={
                    "institution": institution,
                    "area": area,
                    "study_type": study_type,
                    "education_index": education_index,
                },
            )
        )

    return units


def _job_terms(job: Mapping[str, Any], focus_terms: Iterable[str]) -> set[str]:
    parts = [
        job.get("title"),
        job.get("sector"),
        job.get("description_snip"),
        job.get("recommendation_reason"),
        *focus_terms,
    ]
    detail = job.get("detail")
    if isinstance(detail, Mapping):
        parts.extend(detail.get("overlaps", []) or [])
        parts.extend(detail.get("gaps", []) or [])
        parts.extend(detail.get("hard_blockers", []) or [])
        parts.append(detail.get("match_notes"))
    return _tokenize(_text_blob(parts))


def select_candidate_evidence_units(
    job: Mapping[str, Any],
    evidence_units: list[CandidateEvidenceUnit],
    *,
    focus_terms: Iterable[str] = (),
    limit: int = 6,
) -> list[CandidateEvidenceSelection]:
    job_terms = _job_terms(job, focus_terms)
    selections: list[CandidateEvidenceSelection] = []

    for unit in evidence_units:
        matched_role_family_tags = sorted(tag for tag in unit.role_family_tags if any(token in job_terms for token in _tokenize(tag.replace("_", " "))))
        matched_domain_tags = sorted(tag for tag in unit.domain_tags if any(token in job_terms for token in _tokenize(tag.replace("_", " "))))
        matched_capability_tags = sorted(tag for tag in unit.capability_tags if any(token in job_terms for token in _tokenize(tag.replace("_", " "))))
        text_terms = _tokenize(unit.canonical_text)
        targeted_terms = sorted((text_terms & job_terms))[:5]

        relevance = 20
        relevance += min(len(matched_role_family_tags) * 15, 30)
        relevance += min(len(matched_domain_tags) * 10, 20)
        relevance += min(len(matched_capability_tags) * 10, 30)
        relevance += min(len(targeted_terms) * 4, 12)
        if unit.outcome_tags:
            relevance += 8
        if "quantified_result" in unit.outcome_tags:
            relevance += 5

        if not (matched_role_family_tags or matched_domain_tags or matched_capability_tags or targeted_terms):
            relevance -= 12

        relevance = max(0, min(100, relevance))
        if relevance < 20:
            continue

        if matched_capability_tags:
            reason = f"Supports capability signals: {', '.join(matched_capability_tags[:2]).replace('_', ' ')}."
        elif matched_role_family_tags:
            reason = f"Supports the target role family: {', '.join(matched_role_family_tags[:2]).replace('_', ' ')}."
        elif matched_domain_tags:
            reason = f"Supports domain continuity: {', '.join(matched_domain_tags[:2]).replace('_', ' ')}."
        elif targeted_terms:
            reason = f"Shares useful language with the job: {', '.join(targeted_terms[:3])}."
        else:
            reason = "Potentially relevant supporting evidence."

        selections.append(
            CandidateEvidenceSelection(
                evidence_unit_id=unit.evidence_unit_id,
                source_type=unit.source_type,
                source_ref=unit.source_ref,
                canonical_text=unit.canonical_text,
                rewrite_policy=unit.rewrite_policy,
                relevance_score=relevance,
                matched_role_family_tags=matched_role_family_tags,
                matched_domain_tags=matched_domain_tags,
                matched_capability_tags=matched_capability_tags,
                targeted_terms=targeted_terms,
                selection_reason=reason,
            )
        )

    selections.sort(
        key=lambda item: (
            item.relevance_score,
            len(item.matched_capability_tags),
            len(item.matched_role_family_tags),
            len(item.matched_domain_tags),
        ),
        reverse=True,
    )
    return selections[:limit]


def build_candidate_evidence_context(
    job: Mapping[str, Any],
    resume_json: Mapping[str, Any],
    *,
    candidate_id: str = "default",
    focus_terms: Iterable[str] = (),
    limit: int = 6,
) -> CandidateEvidenceContext:
    units = derive_candidate_evidence_units(resume_json, candidate_id=candidate_id)
    selections = select_candidate_evidence_units(job, units, focus_terms=focus_terms, limit=limit)
    return CandidateEvidenceContext(
        candidate_evidence_units=units,
        selected_evidence_units=selections,
    )


__all__ = [
    "build_candidate_evidence_context",
    "derive_candidate_evidence_units",
    "select_candidate_evidence_units",
]
