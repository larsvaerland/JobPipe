from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from .models import (
    DecisionContext,
    JobClaim,
    JobDecisionDimension,
    JobDecisionTable,
    JobSelectionAssessment,
    JobSelectionSignal,
)

_TOOL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("salesforce", "salesforce"),
    ("jira", "jira"),
    ("sql", "sql"),
    ("excel", "excel"),
    ("aws", "aws"),
    ("azure", "azure"),
    ("scrum", "scrum"),
)

_LANGUAGE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("norsk", "Norwegian"),
    ("norwegian", "Norwegian"),
    ("engelsk", "English"),
    ("english", "English"),
)

_CREDENTIAL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("bachelor", "Bachelor degree"),
    ("master", "Master degree"),
    ("phd", "PhD"),
    ("sertifisering", "Certification"),
    ("certification", "Certification"),
    ("security clearance", "Security clearance"),
    ("clearance", "Security clearance"),
    ("autorisasjon", "Authorization"),
)

_RIGID_DOMAIN_MARKERS = (
    "regulated",
    "compliance",
    "bank",
    "banking",
    "finance",
    "public sector",
    "government",
    "health",
    "healthcare",
    "insurance",
)

_FLEXIBLE_ROLE_MARKERS = (
    "product",
    "project",
    "program",
    "transformation",
    "strategy",
    "change",
    "service",
)

_SENIORITY_MARKERS = (
    "senior",
    "lead",
    "principal",
    "head",
    "director",
    "chief",
)

_LEADERSHIP_SCOPE_MARKERS = (
    "lead",
    "leder",
    "manager",
    "head",
    "director",
    "chief",
    "principal",
)

_SCOPE_CAUTION_MARKERS = (
    "specialist",
    "analyst",
    "coordinator",
    "associate",
    "early",
    "junior",
    "mid",
)

_PRODUCT_FAMILY_MARKERS = (
    "product",
    "produkt",
)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _bounded_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _bounded_confidence(value: float) -> float:
    return max(0.0, min(1.0, round(value, 2)))


def _combined_text(job: Mapping[str, Any]) -> str:
    parts = [
        _clean_text(job.get("title")),
        _clean_text(job.get("employer")),
        _clean_text(job.get("sector")),
        _clean_text(job.get("description_snip")),
        _clean_text(job.get("triage_explanation")),
        _clean_text(job.get("recommendation_reason")),
    ]
    detail = job.get("detail")
    if isinstance(detail, Mapping):
        parts.extend(
            [
                " ".join(str(x) for x in detail.get("overlaps", []) if str(x).strip()),
                " ".join(str(x) for x in detail.get("gaps", []) if str(x).strip()),
                " ".join(str(x) for x in detail.get("hard_blockers", []) if str(x).strip()),
                _clean_text(detail.get("match_notes")),
                _clean_text(detail.get("pivot_type")),
                " ".join(str(x) for x in detail.get("pivot_why", []) if str(x).strip()),
            ]
        )
    return " \n".join(part for part in parts if part)


def _text_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token}


def _profile_list(profile: Mapping[str, Any], *path: str) -> list[str]:
    current: Any = profile
    for key in path:
        if not isinstance(current, Mapping):
            return []
        current = current.get(key)
    if not isinstance(current, list):
        return []
    return [str(value).strip() for value in current if str(value).strip()]


def _profile_text(profile: Mapping[str, Any]) -> str:
    snapshot = profile.get("snapshot")
    parts = []
    if isinstance(snapshot, Mapping):
        parts.extend(
            [
                _clean_text(snapshot.get("level")),
                _clean_text(snapshot.get("positioning")),
            ]
        )
    parts.append(_clean_text(profile.get("strategic_direction")))
    return " ".join(part for part in parts if part)


def _matches_profile_phrase(text: str, phrase: str) -> bool:
    haystack = text.lower()
    needle = str(phrase or "").strip().lower()
    if not needle:
        return False
    if needle in haystack:
        return True
    needle_tokens = _text_tokens(needle)
    haystack_tokens = _text_tokens(haystack)
    return bool(needle_tokens) and needle_tokens.issubset(haystack_tokens)


def _candidate_alignment_flags(
    job: Mapping[str, Any],
    candidate_profile: Mapping[str, Any] | None,
) -> dict[str, bool]:
    if not isinstance(candidate_profile, Mapping) or not candidate_profile:
        return {
            "primary_target_alignment": False,
            "secondary_target_alignment": False,
            "hard_no_alignment": False,
            "negative_keyword_overlap": False,
            "scope_mismatch": False,
            "leadership_title_off_anchor": False,
            "product_leadership_off_anchor": False,
        }

    title = _clean_text(job.get("title")).lower()
    combined = _combined_text(job).lower()
    profile_title_space = f"{title}\n{combined}"

    primary_targets = _profile_list(candidate_profile, "target_roles", "primary")
    secondary_targets = _profile_list(candidate_profile, "target_roles", "secondary")
    hard_no_targets = sorted(
        {
            *_profile_list(candidate_profile, "target_roles", "hard_no"),
            *_profile_list(candidate_profile, "hard_no_roles"),
        }
    )
    negative_keywords = _profile_list(candidate_profile, "negative_keywords")

    primary_target_alignment = any(_matches_profile_phrase(profile_title_space, item) for item in primary_targets)
    secondary_target_alignment = any(_matches_profile_phrase(profile_title_space, item) for item in secondary_targets)
    hard_no_alignment = any(_matches_profile_phrase(profile_title_space, item) for item in hard_no_targets)
    negative_keyword_overlap = any(_matches_profile_phrase(profile_title_space, item) for item in negative_keywords)

    profile_summary = _profile_text(candidate_profile).lower()
    scope_caution = any(marker in profile_summary for marker in _SCOPE_CAUTION_MARKERS)
    leadership_scope = any(marker in title for marker in _LEADERSHIP_SCOPE_MARKERS)
    scope_mismatch = leadership_scope and scope_caution and not (primary_target_alignment or secondary_target_alignment)

    has_declared_anchors = bool(primary_targets or secondary_targets or hard_no_targets)
    leadership_title_off_anchor = (
        has_declared_anchors
        and leadership_scope
        and not primary_target_alignment
        and not secondary_target_alignment
        and not hard_no_alignment
    )
    product_scope = any(marker in title for marker in _PRODUCT_FAMILY_MARKERS)
    product_leadership_off_anchor = leadership_title_off_anchor and product_scope

    return {
        "primary_target_alignment": primary_target_alignment,
        "secondary_target_alignment": secondary_target_alignment,
        "hard_no_alignment": hard_no_alignment,
        "negative_keyword_overlap": negative_keyword_overlap,
        "scope_mismatch": scope_mismatch,
        "leadership_title_off_anchor": leadership_title_off_anchor,
        "product_leadership_off_anchor": product_leadership_off_anchor,
    }


def _triage_signal_set(job: Mapping[str, Any]) -> set[str]:
    raw = job.get("triage_signals") or ""
    if isinstance(raw, str):
        return {part.strip() for part in raw.split(",") if part.strip()}
    if isinstance(raw, Iterable):
        return {str(part).strip() for part in raw if str(part).strip()}
    return set()


def _detail_list(job: Mapping[str, Any], key: str) -> list[str]:
    detail = job.get("detail")
    if not isinstance(detail, Mapping):
        return []
    raw = detail.get(key, [])
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes)):
        return []
    return [str(value).strip() for value in raw if str(value).strip()]


def _decision_level(score: int) -> str:
    if score >= 75:
        return "strong"
    if score >= 60:
        return "viable"
    if score >= 40:
        return "fragile"
    return "weak"


def _dedupe_points(*groups: Iterable[str], limit: int = 4) -> list[str]:
    seen: set[str] = set()
    points: list[str] = []
    for group in groups:
        for value in group:
            text = str(value).strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            points.append(text)
            if len(points) >= limit:
                return points
    return points


def _build_dimension(
    *,
    dimension_key: str,
    score: int,
    reason: str,
    supporting_points: Iterable[str] = (),
    risk_points: Iterable[str] = (),
) -> JobDecisionDimension:
    return JobDecisionDimension(
        dimension_key=dimension_key,
        level=_decision_level(score),
        score=score,
        reason=reason,
        supporting_points=_dedupe_points(supporting_points, limit=3),
        risk_points=_dedupe_points(risk_points, limit=3),
    )


def derive_job_claims(job: Mapping[str, Any]) -> list[JobClaim]:
    claims: list[JobClaim] = []

    title = _clean_text(job.get("title"))
    if title:
        claims.append(
            JobClaim(
                claim_type="role_summary",
                claim_strength="explicit_must",
                claim_subject_type="role_family",
                normalized_key=_slug(title),
                normalized_label=title,
                claim_text=f"Role title: {title}",
                source_basis="field",
                source_section="title",
                evidence_span=title,
                confidence_score=0.98,
                importance_score=0.95,
            )
        )

    sector = _clean_text(job.get("sector"))
    if sector:
        claims.append(
            JobClaim(
                claim_type="domain_requirement",
                claim_strength="inferred_likely",
                claim_subject_type="domain",
                normalized_key=_slug(sector),
                normalized_label=sector,
                claim_text=f"Sector or domain context: {sector}",
                source_basis="field",
                source_section="metadata",
                evidence_span=sector,
                confidence_score=0.85,
                importance_score=0.6,
            )
        )

    city = _clean_text(job.get("work_city"))
    county = _clean_text(job.get("work_county"))
    postal = _clean_text(job.get("work_postalCode"))
    if city or county or postal:
        location_bits = [part for part in (city, county, postal) if part]
        location_label = ", ".join(location_bits)
        claims.append(
            JobClaim(
                claim_type="location_requirement",
                claim_strength="explicit_must",
                claim_subject_type="location",
                normalized_key=_slug(location_label),
                normalized_label=location_label,
                claim_text=f"Location constraint: {location_label}",
                source_basis="field",
                source_section="metadata",
                evidence_span=location_label,
                confidence_score=0.92,
                importance_score=0.72,
            )
        )

    text = _combined_text(job).lower()

    for needle, label in _LANGUAGE_PATTERNS:
        if needle in text:
            claims.append(
                JobClaim(
                    claim_type="language_requirement",
                    claim_strength="explicit_must" if label == "Norwegian" else "inferred_likely",
                    claim_subject_type="language",
                    normalized_key=_slug(label),
                    normalized_label=label,
                    claim_text=f"Language requirement or signal: {label}",
                    source_basis="text_pattern",
                    source_section="description",
                    evidence_span=needle,
                    confidence_score=0.78,
                    importance_score=0.62,
                )
            )

    for needle, label in _CREDENTIAL_PATTERNS:
        if needle in text:
            claims.append(
                JobClaim(
                    claim_type="credential_requirement",
                    claim_strength="explicit_must",
                    claim_subject_type="credential",
                    normalized_key=_slug(label),
                    normalized_label=label,
                    claim_text=f"Credential or qualification signal: {label}",
                    source_basis="text_pattern",
                    source_section="description",
                    evidence_span=needle,
                    confidence_score=0.76,
                    importance_score=0.74,
                )
            )

    seen_tools: set[str] = set()
    for needle, label in _TOOL_PATTERNS:
        if needle in text and label not in seen_tools:
            seen_tools.add(label)
            claims.append(
                JobClaim(
                    claim_type="tool_requirement",
                    claim_strength="inferred_likely",
                    claim_subject_type="capability",
                    normalized_key=_slug(label),
                    normalized_label=label.upper() if label.isupper() else label.title(),
                    claim_text=f"Tool or method signal: {label}",
                    source_basis="text_pattern",
                    source_section="description",
                    evidence_span=needle,
                    confidence_score=0.7,
                    importance_score=0.45,
                )
            )

    return claims


def derive_selection_signals(
    job: Mapping[str, Any],
    claims: list[JobClaim] | None = None,
    *,
    candidate_profile: Mapping[str, Any] | None = None,
) -> list[JobSelectionSignal]:
    claims = claims or derive_job_claims(job)
    signals: list[JobSelectionSignal] = []

    title = _clean_text(job.get("title")).lower()
    sector = _clean_text(job.get("sector")).lower()
    combined_text = _combined_text(job).lower()

    has_location_claim = any(claim.claim_type == "location_requirement" for claim in claims)
    if has_location_claim and not re.search(r"\b(remote|hybrid|fjern|hjemmekontor)\b", combined_text):
        signals.append(
            JobSelectionSignal(
                signal_type="structural_gate",
                signal_label="Location is likely screened early",
                selection_stage="ats",
                signal_strength="strong",
                normalized_key="location_gate",
                evidence_required="Make location or relocation viability explicit early.",
                confidence_score=0.82,
                importance_score=0.78,
                source_basis="explicit_claim",
            )
        )

    if any(claim.claim_type == "credential_requirement" for claim in claims):
        signals.append(
            JobSelectionSignal(
                signal_type="structural_gate",
                signal_label="Credential or qualification gate",
                selection_stage="ats",
                signal_strength="hard",
                normalized_key="credential_gate",
                evidence_required="Surface required degree, certification, or authorization early.",
                confidence_score=0.8,
                importance_score=0.84,
                source_basis="explicit_claim",
            )
        )

    title_pressure = any(marker in title for marker in _SENIORITY_MARKERS)
    if title_pressure:
        signals.append(
            JobSelectionSignal(
                signal_type="screening_signal",
                signal_label="Title continuity pressure",
                selection_stage="recruiter_screen",
                signal_strength="strong",
                normalized_key="title_continuity_pressure",
                evidence_required="Translate adjacent titles into equivalent ownership and scope.",
                confidence_score=0.8,
                importance_score=0.75,
                source_basis="derived_pattern",
            )
        )

    domain_rigid = any(marker in sector for marker in _RIGID_DOMAIN_MARKERS) or any(
        marker in combined_text for marker in _RIGID_DOMAIN_MARKERS
    )
    if domain_rigid:
        signals.append(
            JobSelectionSignal(
                signal_type="screening_signal",
                signal_label="Domain continuity likely matters",
                selection_stage="recruiter_screen",
                signal_strength="moderate",
                normalized_key="domain_continuity_pressure",
                evidence_required="Make relevant sector or regulated-context examples explicit.",
                confidence_score=0.68,
                importance_score=0.63,
                source_basis="derived_pattern",
            )
        )

    flexible = any(marker in title for marker in _FLEXIBLE_ROLE_MARKERS)
    ambiguity_strength = "weak" if flexible and not domain_rigid and not title_pressure else "strong" if domain_rigid or title_pressure else "moderate"
    ambiguity_label = (
        "Role looks more tolerant of adjacency"
        if ambiguity_strength == "weak"
        else "Role likely has limited ambiguity tolerance"
        if ambiguity_strength == "strong"
        else "Role shows mixed ambiguity tolerance"
    )
    signals.append(
        JobSelectionSignal(
            signal_type="ambiguity_tolerance",
            signal_label=ambiguity_label,
            selection_stage="overall",
            signal_strength=ambiguity_strength,
            normalized_key="ambiguity_tolerance",
            evidence_required="Decide how much title/domain translation must be front-loaded.",
            confidence_score=0.62,
            importance_score=0.58,
            source_basis="market_heuristic",
        )
    )

    signals.append(
        JobSelectionSignal(
            signal_type="evidence_burden",
            signal_label="Role requires explicit evidence early",
            selection_stage="recruiter_screen",
            signal_strength="strong" if (title_pressure or domain_rigid) else "moderate",
            normalized_key="evidence_burden",
            evidence_required="Lead with the top 2-4 evidence points that make the candidacy legible in first pass.",
            confidence_score=0.72,
            importance_score=0.76,
            source_basis="market_heuristic",
        )
    )

    alignment = _candidate_alignment_flags(job, candidate_profile)
    if alignment["primary_target_alignment"]:
        signals.append(
            JobSelectionSignal(
                signal_type="screening_signal",
                signal_label="Role aligns with primary candidate target roles",
                selection_stage="recruiter_screen",
                signal_strength="moderate",
                normalized_key="candidate_primary_target_alignment",
                evidence_required="Keep the application anchored in the candidate's strongest target role family.",
                confidence_score=0.76,
                importance_score=0.68,
                source_basis="evaluation_state",
            )
        )
    elif alignment["secondary_target_alignment"]:
        signals.append(
            JobSelectionSignal(
                signal_type="screening_signal",
                signal_label="Role aligns with secondary candidate target roles",
                selection_stage="recruiter_screen",
                signal_strength="weak",
                normalized_key="candidate_secondary_target_alignment",
                evidence_required="Make the adjacent fit legible without overselling scope.",
                confidence_score=0.72,
                importance_score=0.55,
                source_basis="evaluation_state",
            )
        )

    if alignment["hard_no_alignment"]:
        signals.append(
            JobSelectionSignal(
                signal_type="structural_gate",
                signal_label="Role overlaps with explicit candidate hard-no constraints",
                selection_stage="overall",
                signal_strength="hard",
                normalized_key="candidate_hard_no_alignment",
                evidence_required="Treat as a skip unless the title is clearly misleading.",
                confidence_score=0.92,
                importance_score=0.9,
                source_basis="evaluation_state",
            )
        )

    if alignment["negative_keyword_overlap"]:
        signals.append(
            JobSelectionSignal(
                signal_type="screening_signal",
                signal_label="Role language overlaps with candidate noise signals",
                selection_stage="recruiter_screen",
                signal_strength="moderate",
                normalized_key="candidate_negative_keyword_overlap",
                evidence_required="Only keep if the underlying work still matches target roles closely.",
                confidence_score=0.72,
                importance_score=0.6,
                source_basis="evaluation_state",
            )
        )

    if alignment["scope_mismatch"]:
        signals.append(
            JobSelectionSignal(
                signal_type="screening_signal",
                signal_label="Role scope looks broader than the candidate's current target profile",
                selection_stage="recruiter_screen",
                signal_strength="strong",
                normalized_key="candidate_scope_mismatch",
                evidence_required="Show equivalent ownership scope with explicit evidence before prioritizing.",
                confidence_score=0.8,
                importance_score=0.78,
                source_basis="evaluation_state",
            )
        )

    if alignment["leadership_title_off_anchor"]:
        signals.append(
            JobSelectionSignal(
                signal_type="screening_signal",
                signal_label="Leadership title sits outside the candidate's declared target roles",
                selection_stage="recruiter_screen",
                signal_strength="moderate",
                normalized_key="candidate_leadership_title_off_anchor",
                evidence_required="Only keep if the underlying work still maps cleanly to declared target roles despite the leadership title.",
                confidence_score=0.76,
                importance_score=0.72,
                source_basis="evaluation_state",
            )
        )

    if alignment["product_leadership_off_anchor"]:
        signals.append(
            JobSelectionSignal(
                signal_type="screening_signal",
                signal_label="Product-leadership title is attractive but outside declared candidate target roles",
                selection_stage="recruiter_screen",
                signal_strength="strong",
                normalized_key="candidate_product_leadership_off_anchor",
                evidence_required="Do not let attractive product-leadership titles crowd out role-family-aligned roles for this candidate.",
                confidence_score=0.82,
                importance_score=0.8,
                source_basis="evaluation_state",
            )
        )

    return signals


def derive_selection_assessment(
    job: Mapping[str, Any],
    signals: list[JobSelectionSignal] | None = None,
    *,
    candidate_profile: Mapping[str, Any] | None = None,
) -> JobSelectionAssessment:
    signals = signals or derive_selection_signals(job, candidate_profile=candidate_profile)
    signal_map = {signal.normalized_key: signal for signal in signals}
    triage_signals = _triage_signal_set(job)
    fit_score = int(job.get("fit_score") or 0)
    pivot_score = int(job.get("pivot_score") or 0)

    detail = job.get("detail")
    hard_blockers = []
    if isinstance(detail, Mapping):
        hard_blockers = [str(x).strip() for x in detail.get("hard_blockers", []) if str(x).strip()]

    title_pressure = 1 if "title_continuity_pressure" in signal_map else 0
    domain_pressure = 1 if "domain_continuity_pressure" in signal_map else 0
    location_gate = 1 if "location_gate" in signal_map else 0
    credential_gate = 1 if "credential_gate" in signal_map else 0
    primary_alignment = 1 if "candidate_primary_target_alignment" in signal_map else 0
    secondary_alignment = 1 if "candidate_secondary_target_alignment" in signal_map else 0
    candidate_hard_no = 1 if "candidate_hard_no_alignment" in signal_map else 0
    candidate_negative = 1 if "candidate_negative_keyword_overlap" in signal_map else 0
    scope_mismatch = 1 if "candidate_scope_mismatch" in signal_map else 0
    leadership_off_anchor = 1 if "candidate_leadership_title_off_anchor" in signal_map else 0
    product_leadership_off_anchor = 1 if "candidate_product_leadership_off_anchor" in signal_map else 0

    structural_pass = not (
        hard_blockers
        or {"geo_postal_skip", "geo_county_skip", "hard_no_title"} & triage_signals
        or candidate_hard_no
    )

    title_continuity_score = _bounded_score(fit_score - (10 if title_pressure and pivot_score < 60 else 0))
    domain_continuity_score = _bounded_score(fit_score - (8 if domain_pressure and pivot_score < 55 else 0))
    title_continuity_score = _bounded_score(
        title_continuity_score
        + (10 * primary_alignment)
        + (5 * secondary_alignment)
        - (15 * scope_mismatch)
        - (12 * candidate_negative)
        - (20 * candidate_hard_no)
        - (10 * leadership_off_anchor)
        - (6 * product_leadership_off_anchor)
    )
    domain_continuity_score = _bounded_score(
        domain_continuity_score
        + (4 * primary_alignment)
        + (2 * secondary_alignment)
        - (8 * candidate_negative)
        - (12 * candidate_hard_no)
    )

    ambiguity_risk = 30 + (20 * title_pressure) + (15 * domain_pressure) + (15 * credential_gate)
    if pivot_score < 50:
        ambiguity_risk += 10
    if hard_blockers:
        ambiguity_risk += 20
    ambiguity_risk += 15 * scope_mismatch
    ambiguity_risk += 10 * candidate_negative
    ambiguity_risk += 18 * candidate_hard_no
    ambiguity_risk += 12 * leadership_off_anchor
    ambiguity_risk += 8 * product_leadership_off_anchor
    ambiguity_risk -= 10 * primary_alignment
    ambiguity_risk -= 5 * secondary_alignment
    ambiguity_risk_score = _bounded_score(ambiguity_risk)

    evidence_burden = 35 + (15 * title_pressure) + (15 * domain_pressure) + (20 * credential_gate) + (10 * location_gate)
    if pivot_score < 55:
        evidence_burden += 10
    evidence_burden += 12 * scope_mismatch
    evidence_burden += 8 * candidate_negative
    evidence_burden += 10 * candidate_hard_no
    evidence_burden += 8 * leadership_off_anchor
    evidence_burden += 6 * product_leadership_off_anchor
    evidence_burden -= 8 * primary_alignment
    evidence_burden -= 4 * secondary_alignment
    evidence_burden_score = _bounded_score(evidence_burden)

    screenability = fit_score
    if not structural_pass:
        screenability -= 30
    if hard_blockers:
        screenability -= 20
    if ambiguity_risk_score >= 70:
        screenability -= 10
    if "platform_suggested" in triage_signals:
        screenability += 5
    screenability += 10 * primary_alignment
    screenability += 5 * secondary_alignment
    screenability -= 15 * scope_mismatch
    screenability -= 10 * candidate_negative
    screenability -= 25 * candidate_hard_no
    screenability -= 12 * leadership_off_anchor
    screenability -= 8 * product_leadership_off_anchor
    screenability_score = _bounded_score(screenability)

    rejection_vectors: list[str] = []
    mitigation_moves: list[str] = []

    if location_gate:
        rejection_vectors.append("Location may be screened early.")
        mitigation_moves.append("Make location, relocation, or work-mode viability explicit.")
    if credential_gate:
        rejection_vectors.append("Missing or unclear credential evidence may block first-pass review.")
        mitigation_moves.append("Surface required degree, certification, or authorization at the top of the application.")
    if title_pressure:
        rejection_vectors.append("Adjacent titles may look ambiguous in recruiter screening.")
        mitigation_moves.append("Translate prior titles into the ownership and scope expected for this role.")
    if domain_pressure:
        rejection_vectors.append("Domain continuity may be used as a shortlist shortcut.")
        mitigation_moves.append("Lead with the most relevant sector examples and quantified outcomes.")
    if candidate_hard_no:
        rejection_vectors.append("The role overlaps with explicit candidate hard-no constraints.")
        mitigation_moves.append("Skip unless the title is misleading and the underlying work is still within target scope.")
    if candidate_negative:
        rejection_vectors.append("The job language overlaps with known candidate noise signals.")
        mitigation_moves.append("Only keep if the actual work matches target roles more than the noisy title does.")
    if scope_mismatch:
        rejection_vectors.append("The role scope looks broader or more leadership-heavy than the candidate's current target profile.")
        mitigation_moves.append("Only pursue with explicit evidence of equivalent ownership scope and role-family continuity.")
    if product_leadership_off_anchor:
        rejection_vectors.append("Title signals product-leadership scope that is outside declared target roles for this candidate.")
        mitigation_moves.append("Do not let attractive product-leadership titles crowd out role-family-aligned roles for this candidate.")
    elif leadership_off_anchor:
        rejection_vectors.append("Title signals leadership scope outside declared target roles even if underlying language still overlaps.")
        mitigation_moves.append("Only keep if the underlying work still maps cleanly to declared target roles despite the leadership title.")
    if hard_blockers:
        rejection_vectors.append("Current match output already shows material blockers.")
        mitigation_moves.append("Only pursue if the blocker can be mitigated with explicit evidence or a direct explanation.")
    if not mitigation_moves:
        mitigation_moves.append("Lead with the strongest evidence points and keep the application specific.")

    if not structural_pass or screenability_score < 35:
        risk_level = "very_high"
    elif ambiguity_risk_score >= 75 or evidence_burden_score >= 75:
        risk_level = "high"
    elif ambiguity_risk_score >= 55 or evidence_burden_score >= 55:
        risk_level = "medium"
    else:
        risk_level = "low"

    reason = (
        f"Screenability {screenability_score}/100, "
        f"ambiguity risk {ambiguity_risk_score}/100, "
        f"evidence burden {evidence_burden_score}/100."
    )

    return JobSelectionAssessment(
        structural_pass=structural_pass,
        screenability_score=screenability_score,
        title_continuity_score=title_continuity_score,
        domain_continuity_score=domain_continuity_score,
        ambiguity_risk_score=ambiguity_risk_score,
        evidence_burden_score=evidence_burden_score,
        selection_risk_level=risk_level,
        likely_rejection_vectors=rejection_vectors,
        mitigation_moves=mitigation_moves[:4],
        assessment_reason=reason,
        assessment_json={
            "fit_score": fit_score,
            "pivot_score": pivot_score,
            "triage_signals": sorted(triage_signals),
            "hard_blockers": hard_blockers,
            "candidate_profile_flags": {
                "primary_target_alignment": bool(primary_alignment),
                "secondary_target_alignment": bool(secondary_alignment),
                "hard_no_alignment": bool(candidate_hard_no),
                "negative_keyword_overlap": bool(candidate_negative),
                "scope_mismatch": bool(scope_mismatch),
                "leadership_title_off_anchor": bool(leadership_off_anchor),
                "product_leadership_off_anchor": bool(product_leadership_off_anchor),
            },
        },
    )


def derive_decision_table(
    job: Mapping[str, Any],
    claims: list[JobClaim] | None = None,
    signals: list[JobSelectionSignal] | None = None,
    assessment: JobSelectionAssessment | None = None,
    *,
    candidate_profile: Mapping[str, Any] | None = None,
) -> JobDecisionTable:
    claims = claims or derive_job_claims(job)
    signals = signals or derive_selection_signals(job, claims=claims, candidate_profile=candidate_profile)
    assessment = assessment or derive_selection_assessment(job, signals=signals, candidate_profile=candidate_profile)

    signal_map = {signal.normalized_key: signal for signal in signals}
    fit_score = _bounded_score(float(job.get("fit_score") or 0))
    pivot_score = _bounded_score(float(job.get("pivot_score") or 0))
    final_decision = _clean_text(job.get("final_decision")).upper()
    triage_explanation = _clean_text(job.get("triage_explanation"))
    recommendation_reason = _clean_text(job.get("recommendation_reason"))
    overlaps = _detail_list(job, "overlaps")
    gaps = _detail_list(job, "gaps")
    hard_blockers = _detail_list(job, "hard_blockers")

    can_do_score = _bounded_score(
        fit_score
        + min(len(overlaps) * 4, 10)
        + (5 if final_decision == "APPLY_STRONGLY" else 3 if final_decision == "APPLY" else 0)
        - min(len(gaps) * 3, 10)
        - min(len(hard_blockers) * 10, 20)
    )
    can_do_reason = (
        "The work itself looks plausible, but current match output still shows material blockers."
        if hard_blockers
        else "Current fit and overlap signals suggest the core work is within reach."
        if can_do_score >= 70
        else "There is some substantive overlap, but the role still needs closer scrutiny on actual fit."
    )
    can_do = _build_dimension(
        dimension_key="can_do",
        score=can_do_score,
        reason=can_do_reason,
        supporting_points=[
            recommendation_reason,
            *[f"Overlap already identified: {value}" for value in overlaps[:2]],
            "The current evaluation path already treats the role as actionable." if final_decision in {"APPLY_STRONGLY", "APPLY", "REVIEW_HIGH", "REVIEW_LOW"} else "",
        ],
        risk_points=[
            *[f"Current gap: {value}" for value in gaps[:2]],
            *[f"Current blocker: {value}" for value in hard_blockers[:2]],
        ],
    )

    can_get_score = assessment.screenability_score
    can_get_reason = (
        "The role looks procedurally winnable in first-pass review."
        if assessment.structural_pass and can_get_score >= 70
        else "The role is substantively plausible, but early-stage screening risk is non-trivial."
        if can_get_score >= 45
        else "Selection risk is high enough that this role may fail before substantive fit gets seen."
    )
    can_get = _build_dimension(
        dimension_key="can_get",
        score=can_get_score,
        reason=can_get_reason,
        supporting_points=[
            "No obvious structural gate is currently failing." if assessment.structural_pass else "",
            f"Selection risk is currently {assessment.selection_risk_level.replace('_', ' ')}." if assessment.selection_risk_level in {"low", "medium"} else "",
        ],
        risk_points=assessment.likely_rejection_vectors,
    )

    can_explain_score = _bounded_score(
        pivot_score
        + (5 if recommendation_reason or triage_explanation else 0)
        - (10 if "title_continuity_pressure" in signal_map else 0)
        - (8 if "domain_continuity_pressure" in signal_map else 0)
        - (10 if assessment.ambiguity_risk_score >= 70 else 0)
        - (5 if hard_blockers else 0)
    )
    can_explain_reason = (
        "The candidate story is already legible with limited translation work."
        if can_explain_score >= 70
        else "The role can likely be explained, but the application will need explicit translation and evidence ordering."
        if can_explain_score >= 45
        else "The candidacy currently looks hard to explain cleanly in first-pass review."
    )
    explain_support = []
    if recommendation_reason:
        explain_support.append(recommendation_reason)
    if triage_explanation:
        explain_support.append(triage_explanation)
    if pivot_score >= 60:
        explain_support.append("Pivot and adjacency signals already look reasonably legible.")
    if "title_continuity_pressure" not in signal_map and "domain_continuity_pressure" not in signal_map:
        explain_support.append("There is limited title or domain translation pressure in the current read.")

    explain_risks = []
    if "title_continuity_pressure" in signal_map:
        explain_risks.append("Prior titles may need explicit translation into the scope this role expects.")
    if "domain_continuity_pressure" in signal_map:
        explain_risks.append("Sector continuity may need to be argued rather than assumed.")
    if assessment.ambiguity_risk_score >= 70:
        explain_risks.append("Ambiguity tolerance looks low, so explanation quality matters early.")
    can_explain = _build_dimension(
        dimension_key="can_explain",
        score=can_explain_score,
        reason=can_explain_reason,
        supporting_points=explain_support,
        risk_points=explain_risks,
    )

    should_want_score = _bounded_score(
        (can_do.score * 0.35)
        + (can_get.score * 0.35)
        + (can_explain.score * 0.2)
        + ((100 - assessment.evidence_burden_score) * 0.1)
        + (5 if final_decision in {"APPLY_STRONGLY", "APPLY"} else 0)
        - (10 if hard_blockers and can_get.score < 50 else 0)
        - (10 if assessment.selection_risk_level == "very_high" else 0)
    )
    should_want_reason = (
        "This looks worth prioritizing because substantive fit and process survivability are both reasonable."
        if should_want_score >= 70
        else "This is plausible, but only worth real attention if the main screening risks can be handled explicitly."
        if should_want_score >= 45
        else "This currently looks expensive to pursue relative to the likely return."
    )
    should_want = _build_dimension(
        dimension_key="should_want",
        score=should_want_score,
        reason=should_want_reason,
        supporting_points=[
            "The current final decision already places the role in an actionable bucket." if final_decision in {"APPLY_STRONGLY", "APPLY", "REVIEW_HIGH", "REVIEW_LOW"} else "",
            "Evidence burden looks manageable." if assessment.evidence_burden_score < 55 else "",
        ],
        risk_points=[
            "Evidence burden is high for first-pass review." if assessment.evidence_burden_score >= 70 else "",
            "Selection risk is high enough that time investment should be scrutinized." if assessment.selection_risk_level in {"high", "very_high"} else "",
            *hard_blockers[:2],
        ],
    )

    if should_want.score < 40 or can_do.score < 35:
        act_now = "skip"
    elif can_get.score < 45 and assessment.evidence_burden_score >= 65:
        act_now = "monitor"
    elif should_want.score >= 70 or final_decision in {"APPLY_STRONGLY", "APPLY"}:
        act_now = "pursue_now"
    else:
        act_now = "review_then_pursue"

    next_moves = _dedupe_points(
        assessment.mitigation_moves,
        [
            "Build the application around the top two evidence points that survive first-pass review."
            if act_now == "pursue_now"
            else "",
            "Check whether the main rejection vector can be countered explicitly before applying."
            if act_now == "review_then_pursue"
            else "",
            "Monitor for requirement changes that lower the screening burden."
            if act_now == "monitor"
            else "",
            "Deprioritize unless new evidence or job changes materially alter the current picture."
            if act_now == "skip"
            else "",
        ],
        limit=4,
    )

    confidence_score = _bounded_confidence(
        0.42
        + (0.12 if fit_score else 0.0)
        + (0.08 if pivot_score else 0.0)
        + min(len(claims), 6) * 0.03
        + min(len(signals), 5) * 0.02
        + (0.08 if overlaps or gaps or hard_blockers else 0.0)
        + (0.05 if final_decision else 0.0)
    )

    table_reason = (
        f"Can do looks {can_do.level}; can get looks {can_get.level}; "
        f"should want looks {should_want.level}; can explain looks {can_explain.level}. "
        f"Recommended action: {act_now.replace('_', ' ')}."
    )

    return JobDecisionTable(
        can_do=can_do,
        can_get=can_get,
        should_want=should_want,
        can_explain=can_explain,
        act_now=act_now,
        confidence_score=confidence_score,
        table_reason=table_reason,
        next_moves=next_moves,
        decision_table_json={
            "fit_score": fit_score,
            "pivot_score": pivot_score,
            "final_decision": final_decision,
            "selection_risk_level": assessment.selection_risk_level,
            "structural_pass": assessment.structural_pass,
            "signal_keys": sorted(signal_map),
            "candidate_profile_flags": assessment.assessment_json.get("candidate_profile_flags", {}),
        },
    )


def build_decision_context(
    job: Mapping[str, Any],
    *,
    candidate_profile: Mapping[str, Any] | None = None,
) -> DecisionContext:
    claims = derive_job_claims(job)
    signals = derive_selection_signals(job, claims=claims, candidate_profile=candidate_profile)
    assessment = derive_selection_assessment(job, signals=signals, candidate_profile=candidate_profile)
    decision_table = derive_decision_table(
        job,
        claims=claims,
        signals=signals,
        assessment=assessment,
        candidate_profile=candidate_profile,
    )
    return DecisionContext(
        job_claims=claims,
        selection_signals=signals,
        selection_assessment=assessment,
        decision_table=decision_table,
    )


__all__ = [
    "build_decision_context",
    "derive_decision_table",
    "derive_job_claims",
    "derive_selection_assessment",
    "derive_selection_signals",
]
