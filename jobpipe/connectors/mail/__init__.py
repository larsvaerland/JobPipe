"""Mail connector helpers and provider-specific normalization code."""

from .gmail_api import (
    build_gmail_service,
    check_gmail_deps,
    fetch_full_message,
    get_gmail_credentials,
    list_unique_message_ids,
    setup_oauth,
)
from .messages import decode_body, parse_message, strip_html
from .status import (
    build_status_queries,
    classify_email,
    clean_employer,
    extract_employer,
    extract_title,
    subject_matches_status_email,
)
from .suggestions import (
    build_suggestion_queries,
    catalog_placeholder_job,
    detect_suggestion_platform,
    extract_job_urls_from_payload,
    extract_suggestion_jobs,
    status_source_refs,
    suggestion_external_id,
    suggestion_id,
    suggestion_key,
)

__all__ = [
    "build_gmail_service",
    "build_status_queries",
    "build_suggestion_queries",
    "catalog_placeholder_job",
    "check_gmail_deps",
    "classify_email",
    "clean_employer",
    "decode_body",
    "detect_suggestion_platform",
    "extract_employer",
    "fetch_full_message",
    "extract_job_urls_from_payload",
    "extract_suggestion_jobs",
    "extract_title",
    "get_gmail_credentials",
    "list_unique_message_ids",
    "parse_message",
    "setup_oauth",
    "status_source_refs",
    "strip_html",
    "subject_matches_status_email",
    "suggestion_external_id",
    "suggestion_id",
    "suggestion_key",
]
