from __future__ import annotations

from jobpipe.connectors.mail.status import (
    classify_email,
    extract_employer,
    extract_title,
    subject_matches_status_email,
)


def test_classify_email_detects_interview_and_rejection():
    assert classify_email("Invitasjon til intervju", "", "") == "interview"
    assert classify_email("Unfortunately, we are not moving forward", "", "") == "rejected"


def test_subject_matches_status_email_for_confirmation_subject():
    assert subject_matches_status_email("Takk for søknaden din")


def test_extract_employer_prefers_sender_display_name_when_clean():
    employer = extract_employer(
        subject="Application update",
        snippet="",
        sender="Statens vegvesen <noreply@teamtailor.example>",
        body="",
    )

    assert employer == "Statens vegvesen"


def test_extract_title_finds_linkedin_pattern():
    title = extract_title(
        subject="Your application to Senior Product Manager at Example AS",
        body="",
    )

    assert title == "Senior Product Manager"
