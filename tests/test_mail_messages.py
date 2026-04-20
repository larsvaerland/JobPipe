from __future__ import annotations

import base64

from jobpipe.connectors.mail.messages import decode_body, parse_message


def _encoded(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def test_decode_body_prefers_plain_text_over_html():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/html", "body": {"data": _encoded("<p>Hello <b>HTML</b></p>")}},
            {"mimeType": "text/plain", "body": {"data": _encoded("Hello plain text")}},
        ],
    }

    assert decode_body(payload) == "Hello plain text"


def test_parse_message_extracts_headers_date_and_body():
    raw = {
        "id": "msg-1",
        "snippet": "Short snippet",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Interview invitation"},
                {"name": "From", "value": "Example AS <jobs@example.com>"},
                {"name": "Date", "value": "Fri, 17 Apr 2026 10:15:00 +0200"},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _encoded("Body text from Gmail")}},
            ],
        },
    }

    parsed = parse_message(raw)

    assert parsed["id"] == "msg-1"
    assert parsed["subject"] == "Interview invitation"
    assert parsed["sender"] == "Example AS <jobs@example.com>"
    assert parsed["date"] == "2026-04-17"
    assert parsed["snippet"] == "Short snippet"
    assert parsed["body"] == "Body text from Gmail"
