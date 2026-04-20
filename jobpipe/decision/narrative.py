from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any, Iterable, Mapping

from .models import (
    CandidateEvidenceSelection,
    CandidateEvidenceUnit,
    CandidateNarrativeContext,
    CandidateNarrativeProfile,
    JobDecisionTable,
    JobNarrativeAssessment,
    NarrativeEvidenceLink,
    NarrativeFragment,
    NarrativeMotivationTheme,
)

_TONE_RULES = [
    "Grounded, concrete, and not overexcited.",
    "Future-oriented without sounding vague or inflated.",
    "Specific about value and evidence, not adjective-heavy.",
]

_MOTIVATION_CUES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "ownership",
        "wants clearer ownership and less diffusion of responsibility",
        "looking for work with clearer ownership and visible value creation",
        ("ownership", "owner", "ansvar", "eierskap", "scope"),
    ),
    (
        "structure",
        "wants environments with more structure and less operational chaos",
        "looking for environments where structure, prioritization, and follow-through matter",
        ("structure", "structured", "chaos", "messy", "priorit", "forbedr", "improvement"),
    ),
    (
        "impact",
        "wants work that creates visible and meaningful outcomes",
        "looking for work with meaningful responsibility and visible outcomes",
        ("impact", "value", "outcome", "delivery", "result", "improve", "lead"),
    ),
    (
        "transition",
        "wants an adjacent move that still builds toward a stronger long-term fit",
        "looking for adjacent roles where existing strengths transfer into a stronger future direction",
        ("pivot", "adjacent", "transition", "product", "transformation", "change"),
    ),
)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _bounded_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _pretty_tag(text: str) -> str:
    return text.replace("_", " ").strip()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _hash_id(prefix: str, *parts: str) -> str:
    raw = "|".join(parts)
    return f"{prefix}_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _profile_lines(profile_pack: str) -> list[str]:
    lines: list[str] = []
    for raw_line in profile_pack.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[#*\-\d\.\)\s]+", "", line).strip()
        if line:
            lines.append(line)
    return lines


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _dominant_tags(units: Iterable[CandidateEvidenceUnit], attr: str, limit: int = 3) -> list[str]:
    counts: Counter[str] = Counter()
    for unit in units:
        for value in getattr(unit, attr, []) or []:
            text = _clean_text(value)
            if text:
                counts[text] += 1
    return [tag for tag, _ in counts.most_common(limit)]


def _selected_tags(selections: Iterable[CandidateEvidenceSelection], attr: str, limit: int = 3) -> list[str]:
    counts: Counter[str] = Counter()
    for selection in selections:
        for value in getattr(selection, attr, []) or []:
            text = _clean_text(value)
            if text:
                counts[text] += 1
    return [tag for tag, _ in counts.most_common(limit)]


def _core_identity_from_tags(
    capability_tags: list[str],
    role_family_tags: list[str],
    outcome_tags: list[str],
) -> list[str]:
    identity: list[str] = []
    if capability_tags:
        label = ", ".join(_pretty_tag(tag) for tag in capability_tags[:2])
        identity.append(f"Brings repeatable strength in {label}.")
    if role_family_tags:
        label = ", ".join(_pretty_tag(tag) for tag in role_family_tags[:2])
        identity.append(f"Most credible in roles spanning {label}.")
    if outcome_tags:
        label = ", ".join(_pretty_tag(tag) for tag in outcome_tags[:2])
        identity.append(f"Evidence repeatedly points to {label} rather than only activity without outcomes.")
    if not identity:
        identity.append("Most credible in structured, delivery-oriented roles with visible ownership.")
    return identity[:3]


def _future_direction_from_profile(
    profile_pack: str,
    selected_role_tags: list[str],
    selected_domain_tags: list[str],
) -> list[str]:
    lowered = profile_pack.lower()
    directions: list[str] = []
    if "product" in lowered or "produkt" in lowered:
        directions.append("Move toward product-facing roles with clearer ownership and prioritization scope.")
    if "project" in lowered or "program" in lowered or "delivery" in lowered:
        directions.append("Stay close to delivery-heavy roles where execution and coordination remain visible strengths.")
    if "change" in lowered or "transform" in lowered:
        directions.append("Keep adjacent transformation and change-oriented roles in scope.")
    if not directions and selected_role_tags:
        label = ", ".join(_pretty_tag(tag) for tag in selected_role_tags[:2])
        directions.append(f"Lean toward roles around {label}.")
    if selected_domain_tags:
        label = ", ".join(_pretty_tag(tag) for tag in selected_domain_tags[:2])
        directions.append(f"Stay open to domains where existing evidence in {label} remains transferable.")
    if not directions:
        directions.append("Favor adjacent roles where existing delivery, coordination, and ownership strengths stay legible.")
    return directions[:3]


def _motivation_themes_from_profile(profile_pack: str, selected_evidence: list[CandidateEvidenceSelection]) -> list[NarrativeMotivationTheme]:
    text = " ".join([profile_pack, *[selection.canonical_text for selection in selected_evidence]])
    themes: list[NarrativeMotivationTheme] = []
    for theme_tag, private_driver, professional_framing, needles in _MOTIVATION_CUES:
        if _contains_any(text, needles):
            themes.append(
                NarrativeMotivationTheme(
                    private_driver=private_driver,
                    professional_framing=professional_framing,
                    theme_tags=[theme_tag],
                )
            )
    if not themes:
        themes.append(
            NarrativeMotivationTheme(
                private_driver="wants a role with clearer ownership and more durable fit",
                professional_framing="looking for work with clearer ownership, visible delivery, and stronger long-term fit",
                theme_tags=["ownership", "impact"],
            )
        )
    return themes[:3]


def _pivot_thesis(
    selected_role_tags: list[str],
    selected_capability_tags: list[str],
    decision_table: JobDecisionTable | None,
) -> list[str]:
    statements: list[str] = []
    if selected_capability_tags:
        label = ", ".join(_pretty_tag(tag) for tag in selected_capability_tags[:2])
        statements.append(f"The move is credible because the same strengths in {label} transfer across adjacent titles.")
    if selected_role_tags:
        label = ", ".join(_pretty_tag(tag) for tag in selected_role_tags[:2])
        statements.append(f"The profile does not depend on one exact title; it remains legible across {label}.")
    if decision_table and decision_table.can_explain.score >= 60:
        statements.append("Current decision support already suggests the move can be explained without overclaiming.")
    if not statements:
        statements.append("The next move is most credible where existing delivery and coordination strengths remain visible even if the title shifts.")
    return statements[:3]


def derive_candidate_narrative_profile(
    profile_pack: str,
    evidence_units: list[CandidateEvidenceUnit],
    *,
    candidate_id: str = "default",
    selected_evidence_units: list[CandidateEvidenceSelection] | None = None,
    decision_table: JobDecisionTable | None = None,
) -> CandidateNarrativeProfile:
    selected_evidence_units = selected_evidence_units or []
    selected_role_tags = _selected_tags(selected_evidence_units, "matched_role_family_tags")
    selected_domain_tags = _selected_tags(selected_evidence_units, "matched_domain_tags")
    selected_capability_tags = _selected_tags(selected_evidence_units, "matched_capability_tags")

    capability_tags = selected_capability_tags or _dominant_tags(evidence_units, "capability_tags")
    role_family_tags = selected_role_tags or _dominant_tags(evidence_units, "role_family_tags")
    domain_tags = selected_domain_tags or _dominant_tags(evidence_units, "domain_tags")
    outcome_tags = _dominant_tags(evidence_units, "outcome_tags")

    core_identity = _core_identity_from_tags(capability_tags, role_family_tags, outcome_tags)
    future_direction = _future_direction_from_profile(profile_pack, role_family_tags, domain_tags)
    motivation_themes = _motivation_themes_from_profile(profile_pack, selected_evidence_units)
    pivot_thesis = _pivot_thesis(role_family_tags, capability_tags, decision_table)
    proof_themes = [_pretty_tag(tag) for tag in (capability_tags + role_family_tags + outcome_tags)[:4]]
    story_boundaries = [
        "Do not present the profile as a narrow specialist if the evidence is broader and cross-functional.",
        "Do not oversell every adjacent role as a long-term passion match.",
        "Do not let the story get cleaner than the evidence can support.",
    ]
    narrative_summary = " ".join((core_identity + future_direction + pivot_thesis)[:3])[:600]

    return CandidateNarrativeProfile(
        narrative_version_id=_hash_id("narrative", candidate_id, narrative_summary or "default"),
        candidate_id=candidate_id,
        source_kind="profile_pack_heuristic",
        core_identity=core_identity,
        future_direction=future_direction,
        motivation_themes=motivation_themes,
        pivot_thesis=pivot_thesis,
        proof_themes=proof_themes,
        story_boundaries=story_boundaries,
        tone_rules=_TONE_RULES,
        narrative_summary=narrative_summary,
    )


def derive_narrative_fragments(profile: CandidateNarrativeProfile) -> list[NarrativeFragment]:
    fragments: list[NarrativeFragment] = []
    candidates: list[tuple[str, str, str, str]] = []
    if profile.core_identity:
        candidates.append(("identity", "recruiter", profile.core_identity[0], "light_rewrite_only"))
    if profile.motivation_themes:
        candidates.append(("motivation", "cover_letter", profile.motivation_themes[0].professional_framing, "light_rewrite_only"))
    if profile.pivot_thesis:
        candidates.append(("pivot", "cover_letter", profile.pivot_thesis[0], "light_rewrite_only"))
    if profile.narrative_summary:
        candidates.append(("summary", "cv_summary", profile.narrative_summary, "can_summarize"))
    if profile.story_boundaries:
        candidates.append(("anti_pattern", "internal", profile.story_boundaries[0], "verbatim_preferred"))

    for fragment_type, audience, canonical_text, rewrite_policy in candidates:
        fragments.append(
            NarrativeFragment(
                fragment_id=_hash_id("fragment", profile.narrative_version_id, fragment_type, audience, canonical_text),
                candidate_id=profile.candidate_id,
                narrative_version_id=profile.narrative_version_id,
                fragment_type=fragment_type,
                audience=audience,
                canonical_text=canonical_text,
                rewrite_policy=rewrite_policy,
                fragment_json={},
            )
        )
    return fragments


def derive_narrative_evidence_links(
    profile: CandidateNarrativeProfile,
    evidence_units: list[CandidateEvidenceUnit],
) -> list[NarrativeEvidenceLink]:
    links: list[NarrativeEvidenceLink] = []
    profile_terms = {_slug(value) for value in (profile.proof_themes + profile.future_direction)}
    for unit in evidence_units[:8]:
        shared_terms = set(unit.role_family_tags) | set(unit.capability_tags) | set(unit.outcome_tags)
        overlap = shared_terms & profile_terms
        if unit.role_family_tags and any(tag in _slug(" ".join(profile.future_direction)) for tag in unit.role_family_tags):
            link_type = "supports_role_family"
        elif unit.capability_tags:
            link_type = "supports_identity"
        else:
            link_type = "supports_pivot"
        strength = 0.45 + min(len(overlap) * 0.12, 0.4)
        notes = (
            f"Supports {_pretty_tag(link_type.replace('supports_', ''))} through "
            f"{', '.join(_pretty_tag(tag) for tag in list(shared_terms)[:2])}."
        )
        links.append(
            NarrativeEvidenceLink(
                narrative_link_id=_hash_id("narrative_link", profile.narrative_version_id, unit.evidence_unit_id, link_type),
                candidate_id=profile.candidate_id,
                narrative_version_id=profile.narrative_version_id,
                evidence_unit_id=unit.evidence_unit_id,
                link_type=link_type,
                strength_score=max(0.0, min(1.0, round(strength, 2))),
                notes=notes,
            )
        )
    return links[:6]


def derive_job_narrative_assessment(
    job: Mapping[str, Any],
    profile: CandidateNarrativeProfile,
    selected_evidence_units: list[CandidateEvidenceSelection],
    *,
    decision_table: JobDecisionTable | None = None,
) -> JobNarrativeAssessment:
    role_hits = sum(len(selection.matched_role_family_tags) for selection in selected_evidence_units)
    domain_hits = sum(len(selection.matched_domain_tags) for selection in selected_evidence_units)
    capability_hits = sum(len(selection.matched_capability_tags) for selection in selected_evidence_units)

    direction_fit = _bounded_score(
        35 + (role_hits * 8) + (domain_hits * 5) + (decision_table.should_want.score * 0.35 if decision_table else 15)
    )
    motivation_fit = _bounded_score(
        35
        + (len(profile.motivation_themes) * 8)
        + (capability_hits * 4)
        + (decision_table.should_want.score * 0.25 if decision_table else 15)
    )
    pivot_credibility = _bounded_score(
        30
        + (len(selected_evidence_units) * 6)
        + (capability_hits * 4)
        + (decision_table.can_explain.score * 0.4 if decision_table else 20)
    )
    story_strength = _bounded_score((direction_fit * 0.35) + (motivation_fit * 0.25) + (pivot_credibility * 0.4))

    misalignment_flags: list[str] = []
    if decision_table and decision_table.should_want.level in {"fragile", "weak"}:
        misalignment_flags.append("The role may be technically plausible but weak on forward-fit.")
    if decision_table and decision_table.can_explain.level in {"fragile", "weak"}:
        misalignment_flags.append("The role currently needs more explanation work than the story can easily carry.")
    if not selected_evidence_units:
        misalignment_flags.append("There is little selected evidence supporting a credible role-specific story.")
    if direction_fit < 55:
        misalignment_flags.append("The role does not align cleanly with the current forward direction.")

    if not misalignment_flags and decision_table and decision_table.act_now == "pursue_now":
        brief_end = "The story is specific enough to support an active application now."
    elif not misalignment_flags:
        brief_end = "The story is plausible, but still benefits from explicit evidence ordering."
    else:
        brief_end = "The story is not broken, but it still has visible strategic or explanation risk."

    motivation_brief = (
        f"{profile.motivation_themes[0].professional_framing}. "
        f"{profile.pivot_thesis[0]} "
        f"{brief_end}"
    )[:700]
    assessment_reason = (
        f"Direction fit {direction_fit}/100, motivation fit {motivation_fit}/100, "
        f"pivot credibility {pivot_credibility}/100, story strength {story_strength}/100."
    )

    return JobNarrativeAssessment(
        direction_fit_score=direction_fit,
        motivation_fit_score=motivation_fit,
        pivot_credibility_score=pivot_credibility,
        story_strength_score=story_strength,
        misalignment_flags=misalignment_flags[:4],
        assessment_reason=assessment_reason,
        motivation_brief=motivation_brief,
    )


def build_candidate_narrative_context(
    job: Mapping[str, Any],
    profile_pack: str,
    evidence_units: list[CandidateEvidenceUnit],
    selected_evidence_units: list[CandidateEvidenceSelection],
    *,
    candidate_id: str = "default",
    decision_table: JobDecisionTable | None = None,
) -> CandidateNarrativeContext:
    profile = derive_candidate_narrative_profile(
        profile_pack,
        evidence_units,
        candidate_id=candidate_id,
        selected_evidence_units=selected_evidence_units,
        decision_table=decision_table,
    )
    fragments = derive_narrative_fragments(profile)
    links = derive_narrative_evidence_links(profile, evidence_units)
    assessment = derive_job_narrative_assessment(
        job,
        profile,
        selected_evidence_units,
        decision_table=decision_table,
    )
    return CandidateNarrativeContext(
        narrative_profile=profile,
        narrative_fragments=fragments,
        narrative_evidence_links=links,
        job_narrative_assessment=assessment,
    )


__all__ = [
    "build_candidate_narrative_context",
    "derive_candidate_narrative_profile",
    "derive_job_narrative_assessment",
    "derive_narrative_evidence_links",
    "derive_narrative_fragments",
]
