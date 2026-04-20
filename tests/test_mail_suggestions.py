from __future__ import annotations

import base64

from jobpipe.connectors.mail.suggestions import extract_job_urls_from_payload, extract_suggestion_jobs


def _gmail_body(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def test_extract_job_urls_from_payload_reads_html_and_text_parts():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/html",
                "body": {
                    "data": _gmail_body(
                        '<a href="https://click.finn.no/track/click?u=https%3A%2F%2Fwww.finn.no%2Fjob%2Ffulltime%2Fad.html%3Ffinnkode%3D378542101">FINN</a>'
                    )
                },
            },
            {
                "mimeType": "text/plain",
                "body": {
                    "data": _gmail_body("See https://www.linkedin.com/jobs/view/987654321/ for details.")
                },
            },
        ],
    }

    urls = extract_job_urls_from_payload(payload)

    assert any("click.finn.no" in url for url in urls)
    assert "https://www.linkedin.com/jobs/view/987654321/" in urls


def test_extract_suggestion_jobs_handles_encoded_and_direct_urls():
    urls = [
        "https://click.finn.no/track/click?u=https%3A%2F%2Fwww.finn.no%2Fjob%2Ffulltime%2Fad.html%3Ffinnkode%3D378542101",
        "https://www.linkedin.com/jobs/view/987654321/",
    ]

    jobs = extract_suggestion_jobs(urls)
    by_platform = {job["platform"]: job for job in jobs}

    assert by_platform["finn"]["finnkode"] == "378542101"
    assert by_platform["finn"]["job_url"] == "https://www.finn.no/job/fulltime/ad.html?finnkode=378542101"
    assert by_platform["linkedin"]["linkedin_job_id"] == "987654321"
    assert by_platform["linkedin"]["job_url"] == "https://www.linkedin.com/jobs/view/987654321"
