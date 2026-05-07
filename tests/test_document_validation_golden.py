"""Golden-output tests for validate_document_content.

Each test protects a specific authoring policy from silent regression.
Test names are the policy name — they document intent, not implementation.

Fixture drafts are minimal but realistic: correct word counts, no banned phrases,
at least one evidence term. Failing fixtures contain exactly one violation each
so assertions are unambiguous.
"""
from __future__ import annotations

import pytest

from jobpipe.authoring.validation import validate_document_content

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_EVIDENCE = [{"employer": "Brownells", "role": "Produktsjef"}]

# A clean Norwegian cover letter: ~270 words, no banned phrases, mentions "Brownells".
_GOOD_NO = """\
Dere søker en produktleder som kan omsette brukerbehov til konkrete produktbeslutninger.
Det er nettopp den koblingen mellom kundeinnsikt og systemdesign jeg har jobbet med hos
Brownells de siste tre årene.

I rollen som Produktsjef hos Brownells ledet jeg tre parallelle leveranser i 2023:
integrasjon av sanntidsoppdateringer i lagersystemet, utrulling av ny handlekurvflyt i
ti markeder og innføring av strukturert brukerintervju-program. Alle leveransene ble
gjennomført innenfor budsjett og ga målbare forbedringer i konverteringsrate.

Stillingen dere lyser ut tiltrekker seg fordi dere opererer i en kompleks
logistikkdomene der produktbeslutninger må koordineres på tvers av teknologi,
innkjøp og salg. Jeg har erfaring med akkurat det fra Brownells, der vi daglig
balanserte krav fra fire avdelinger mot kapasitet og kundepåvirkning.

Jeg søker nå et miljø der jeg kan bidra med erfaring fra e-commerce og
distribusjon til et team med tydelig produkteierskap og korte beslutningsveier.
""" * 2  # repeat to get over 150 words

# A clean English cover letter: ~270 words, no banned phrases, mentions "Brownells".
_GOOD_EN = """\
Your team is looking for a product manager who can translate user research into
concrete product decisions. That is the exact connection between customer insight
and system design I built at Brownells over the last three years.

As Product Manager at Brownells I led three parallel deliveries in 2023:
real-time inventory integration, a new checkout flow rolled out to ten markets,
and a structured user-interview program. All delivered within budget and produced
measurable improvements in conversion rate.

The role you are hiring for is compelling because you operate in a complex
logistics domain where product decisions must be coordinated across technology,
procurement, and sales. At Brownells I navigated exactly that, balancing
requirements from four departments against capacity and customer impact every day.

I am now looking for an environment where I can bring e-commerce and distribution
experience to a team with clear product ownership and short decision cycles.
""" * 2


def _validate_no(draft: str, evidence=None) -> object:
    return validate_document_content(draft, "no", evidence or _EVIDENCE, "cover_letter")


def _validate_en(draft: str, evidence=None) -> object:
    return validate_document_content(draft, "en", evidence or _EVIDENCE, "cover_letter")


# ---------------------------------------------------------------------------
# Passing drafts
# ---------------------------------------------------------------------------

def test_clean_norwegian_draft_passes_all_rules():
    result = _validate_no(_GOOD_NO)
    assert result.passed, f"Expected clean draft to pass. Failures: {result.failures}"
    assert result.score == 1.0
    assert result.failures == []
    assert result.warnings == []


def test_clean_english_draft_passes_all_rules():
    result = _validate_en(_GOOD_EN)
    assert result.passed, f"Expected clean draft to pass. Failures: {result.failures}"
    assert result.score == 1.0
    assert result.failures == []
    assert result.warnings == []


# ---------------------------------------------------------------------------
# Word-count policy
# ---------------------------------------------------------------------------

def test_cover_letter_below_minimum_word_count_fails():
    short_draft = "Dette er for kort. " * 5  # ~30 words — under 150 limit
    result = _validate_no(short_draft)
    assert not result.passed
    assert any("[word_count_too_short]" in f for f in result.failures), result.failures
    failure_text = next(f for f in result.failures if "[word_count_too_short]" in f)
    assert "150" in failure_text, "Failure should mention the minimum word count"


def test_cover_letter_above_maximum_word_count_fails():
    # 620 words ≈ 5 words * 124 repetitions — over 600 limit
    long_draft = ("Dette er et veldig langt avsnitt. " * 200)
    result = _validate_no(long_draft)
    assert not result.passed
    assert any("[word_count_too_long]" in f for f in result.failures), result.failures
    failure_text = next(f for f in result.failures if "[word_count_too_long]" in f)
    assert "600" in failure_text, "Failure should mention the maximum word count"


def test_cv_has_wider_word_count_limits():
    # A 900-word draft that would fail cover_letter limit (600) but passes cv limit (1200)
    mid_draft = ("Erfaring fra produkt og leveranse. " * 30)  # ~150 words per block * 6
    mid_draft = mid_draft * 6  # ~900 words
    result = validate_document_content(mid_draft, "no", _EVIDENCE, "cv")
    # Should not fail word count for cv type
    word_count_failures = [f for f in result.failures if "word_count" in f]
    assert word_count_failures == [], f"CV should allow up to 1200 words: {word_count_failures}"


# ---------------------------------------------------------------------------
# Banned-phrase policy (Norwegian)
# ---------------------------------------------------------------------------

def test_norwegian_generic_cliche_interessenter_is_blocked():
    draft = _GOOD_NO + "\nVi jobber med alle interessenter i organisasjonen."
    result = _validate_no(draft)
    assert not result.passed
    banned_failures = [f for f in result.failures if "[banned_phrase]" in f]
    assert banned_failures, "Expected [banned_phrase] failure for 'interessenter'"
    assert any("interessenter" in f for f in banned_failures)


def test_norwegian_continuous_improvement_cliche_is_blocked():
    draft = _GOOD_NO + "\nTeamet jobber med kontinuerlig forbedring av prosessene."
    result = _validate_no(draft)
    assert not result.passed
    banned_failures = [f for f in result.failures if "[banned_phrase]" in f]
    assert any("kontinuerlig forbedring" in f for f in banned_failures)


def test_norwegian_generic_closing_sees_frem_til_is_blocked():
    draft = _GOOD_NO + "\nJeg ser frem til muligheten til å bidra til teamet deres."
    result = _validate_no(draft)
    banned_failures = [f for f in result.failures if "[banned_phrase]" in f]
    assert any("ser frem til muligheten til å" in f for f in banned_failures)


def test_norwegian_gap_apology_pattern_is_blocked():
    draft = _GOOD_NO + "\nSelv om jeg ikke har direkte erfaring med dette, er jeg motivert."
    result = _validate_no(draft)
    banned_failures = [f for f in result.failures if "[banned_phrase]" in f]
    assert any("selv om jeg ikke har direkte erfaring" in f for f in banned_failures)


def test_norwegian_banned_phrases_are_case_insensitive():
    draft = _GOOD_NO + "\nJeg er INTERESSENTER i alle prosjekter."
    result = _validate_no(draft)
    banned_failures = [f for f in result.failures if "[banned_phrase]" in f]
    assert banned_failures, "Banned phrase check should be case-insensitive"


# ---------------------------------------------------------------------------
# Banned-phrase policy (English)
# ---------------------------------------------------------------------------

def test_english_stakeholders_cliche_is_blocked():
    draft = _GOOD_EN + "\nI work with all stakeholders across the organisation."
    result = _validate_en(draft)
    assert not result.passed
    banned_failures = [f for f in result.failures if "[banned_phrase]" in f]
    assert any("stakeholders" in f for f in banned_failures)


def test_english_cross_functional_teams_cliche_is_blocked():
    draft = _GOOD_EN + "\nI have led cross-functional teams across multiple domains."
    result = _validate_en(draft)
    banned_failures = [f for f in result.failures if "[banned_phrase]" in f]
    assert any("cross-functional teams" in f for f in banned_failures)


def test_english_gap_apology_is_blocked():
    draft = _GOOD_EN + "\nAlthough I don't have direct experience in this area, I learn fast."
    result = _validate_en(draft)
    banned_failures = [f for f in result.failures if "[banned_phrase]" in f]
    assert any("although i don't have direct experience" in f for f in banned_failures)


def test_english_generic_closing_is_blocked():
    draft = _GOOD_EN + "\nI am looking forward to contributing to your team's success."
    result = _validate_en(draft)
    banned_failures = [f for f in result.failures if "[banned_phrase]" in f]
    assert any("looking forward to contributing" in f for f in banned_failures)


# ---------------------------------------------------------------------------
# Language routing policy — wrong-language phrases don't cross-contaminate
# ---------------------------------------------------------------------------

def test_norwegian_banned_phrases_not_checked_for_english_document():
    # "interessenter" is Norwegian banned — should NOT fire on an English-language document
    draft = _GOOD_EN + "\nThe interessenter concept does not apply here."
    result = _validate_en(draft)
    banned_failures = [f for f in result.failures if "[banned_phrase]" in f and "interessenter" in f]
    assert not banned_failures, (
        "Norwegian banned phrases must not fire on English-language documents"
    )


def test_english_banned_phrases_not_checked_for_norwegian_document():
    # "stakeholders" is English banned — Norwegian documents should use the Norwegian list
    draft = _GOOD_NO + "\nVi har mange stakeholders i dette prosjektet."
    result = _validate_no(draft)
    # "stakeholders" appears in _HARD_BANNED_NO as "cross-functional" not "stakeholders" —
    # the English-specific "stakeholders" entry must not fire on a Norwegian document.
    # (Norwegian list uses "interessenter" for the same concept.)
    # If "stakeholders" is not in the Norwegian list, no [banned_phrase] for it should appear.
    banned_for_stakeholders = [
        f for f in result.failures
        if "[banned_phrase]" in f and f.endswith("'stakeholders'")
    ]
    assert not banned_for_stakeholders, (
        "English-specific 'stakeholders' phrase must not be blocked in Norwegian documents"
    )


# ---------------------------------------------------------------------------
# Evidence reference policy
# ---------------------------------------------------------------------------

def test_document_with_no_evidence_reference_raises_warning():
    no_ref_draft = ("Dette er en generisk søknad uten konkrete navn. " * 10)
    result = validate_document_content(
        no_ref_draft, "no",
        [{"employer": "Brownells", "role": "Produktsjef"}],
        "cover_letter",
    )
    # Should warn but not fail (non-blocking)
    assert any("[no_evidence_reference]" in w for w in result.warnings), result.warnings
    # Score is penalised 0.05 per warning
    assert result.score < 1.0


def test_document_with_evidence_term_suppresses_reference_warning():
    draft = _GOOD_NO  # Already mentions "Brownells"
    result = _validate_no(draft)
    reference_warnings = [w for w in result.warnings if "[no_evidence_reference]" in w]
    assert not reference_warnings, (
        "Draft that mentions the employer name should not trigger no_evidence_reference"
    )


def test_empty_evidence_list_skips_evidence_reference_check():
    # When no evidence is provided the rule must not warn (nothing to check against)
    draft = _GOOD_NO
    result = validate_document_content(draft, "no", [], "cover_letter")
    reference_warnings = [w for w in result.warnings if "[no_evidence_reference]" in w]
    assert not reference_warnings


# ---------------------------------------------------------------------------
# Scoring formula
# ---------------------------------------------------------------------------

def test_score_decreases_by_0_2_per_failure():
    # One banned phrase = one failure → score should be 0.8
    draft = _GOOD_NO + "\nAlle interessenter er informert."
    result = _validate_no(draft)
    n_failures = len(result.failures)
    n_warnings = len(result.warnings)
    expected_score = max(0.0, 1.0 - n_failures * 0.2 - n_warnings * 0.05)
    assert abs(result.score - expected_score) < 1e-9, (
        f"Expected score {expected_score}, got {result.score}"
    )


def test_score_is_clamped_to_zero_on_many_failures():
    # Many banned phrases → score must not go below 0
    draft = (
        _GOOD_NO
        + "\ninteressenter kontinuerlig forbedring endringsprosesser brukervennlige løsninger"
        + " skape verdi offentlig sektor rask tilpasningsevne helhetlige løsninger"
        + " ser frem til muligheten til å anvende min kompetanse bidra til utviklingen av"
    )
    result = _validate_no(draft)
    assert result.score >= 0.0
    assert result.score == max(0.0, 1.0 - len(result.failures) * 0.2 - len(result.warnings) * 0.05)
