"""Reactive Resume REST API client.

Shared by prepare_application, JobSane tools, and future JobDesk usage.
RR self-hosted instance exposes a REST API. Auth is optional — pass token
when the instance requires Bearer auth.
"""
from __future__ import annotations

import requests


def push_resume_to_rr(
    base_url: str,
    resume_json: dict,
    *,
    token: str = "",
) -> dict:
    """Create a new resume in the running RR instance. Returns the created resume dict."""
    url = f"{base_url.rstrip('/')}/api/resume"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.post(url, json=resume_json, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def update_resume_in_rr(
    base_url: str,
    resume_id: str,
    resume_json: dict,
    *,
    token: str = "",
) -> dict:
    """Update an existing resume by ID."""
    url = f"{base_url.rstrip('/')}/api/resume/{resume_id}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.patch(url, json=resume_json, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_resume_url(base_url: str, resume_id: str) -> str:
    return f"{base_url.rstrip('/')}/resume/{resume_id}"


__all__ = ["push_resume_to_rr", "update_resume_in_rr", "get_resume_url"]
