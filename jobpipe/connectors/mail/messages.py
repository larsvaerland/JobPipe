from __future__ import annotations

import base64
import re
from typing import Any


def strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&(?:nbsp|amp|quot|lt|gt|raquo|laquo);", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def decode_body(payload: dict[str, Any]) -> str:
    plain: list[str] = []
    html: list[str] = []

    def _walk(part: dict[str, Any]) -> None:
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data", "")
        if data:
            try:
                decoded = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
                if mime == "text/plain":
                    plain.append(decoded)
                elif mime == "text/html":
                    html.append(decoded)
            except Exception:
                pass
        for sub in part.get("parts", []):
            _walk(sub)

    _walk(payload)
    if plain:
        return plain[0]
    if html:
        return strip_html(html[0])
    return ""


def parse_message(msg: dict[str, Any]) -> dict[str, Any]:
    headers = {header["name"].lower(): header["value"] for header in msg.get("payload", {}).get("headers", [])}
    subject = headers.get("subject", "")
    sender = headers.get("from", "")
    date_str = headers.get("date", "")
    snippet = msg.get("snippet", "")
    body = decode_body(msg.get("payload", {}))

    email_date = ""
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(date_str)
        email_date = dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    return {
        "id": msg["id"],
        "subject": subject,
        "sender": sender,
        "date": email_date,
        "snippet": snippet,
        "body": body[:3000],
    }


__all__ = ["decode_body", "parse_message", "strip_html"]
