from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False


def check_gmail_deps() -> bool:
    if not GMAIL_AVAILABLE:
        print(
            "Error: Gmail API packages not installed.\n"
            "Run: pip install google-auth-oauthlib google-api-python-client --break-system-packages",
            file=sys.stderr,
        )
        return False
    return True


def get_gmail_credentials(token_path: Path, creds_path: Path) -> Any | None:
    creds = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception:
            pass

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as exc:
                print(f"Warning: token refresh failed ({exc}). Re-running OAuth flow.", file=sys.stderr)
                creds = None

        if not creds:
            if not creds_path.exists():
                print(
                    f"Error: Gmail credentials file not found: {creds_path}\n"
                    "Run:  python -m jobpipe.cli.scan_gmail --setup\n"
                    "See module docstring for setup instructions.",
                    file=sys.stderr,
                )
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


def build_gmail_service(token_path: Path, creds_path: Path) -> Any | None:
    if not check_gmail_deps():
        return None
    creds = get_gmail_credentials(token_path, creds_path)
    if not creds:
        return None
    return build("gmail", "v1", credentials=creds)


def list_unique_message_ids(service: Any, queries: list[str], *, max_results: int) -> list[str]:
    found_ids: set[str] = set()
    msg_ids: list[str] = []

    for query in queries:
        result = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        for message in result.get("messages", []):
            msg_id = message["id"]
            if msg_id not in found_ids:
                found_ids.add(msg_id)
                msg_ids.append(msg_id)

    return msg_ids


def fetch_full_message(service: Any, msg_id: str) -> dict[str, Any]:
    return service.users().messages().get(userId="me", id=msg_id, format="full").execute()


def setup_oauth(creds_path: Path, token_path: Path) -> None:
    if not check_gmail_deps():
        return

    if not creds_path.exists():
        print(f"\nGmail credentials file not found: {creds_path}")
        print("\nTo create it:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Create or select a project")
        print("  3. Enable the Gmail API")
        print("  4. Create OAuth2 credentials (Application type: Desktop)")
        print("  5. Download the JSON and save it to:")
        print(f"     {creds_path.resolve()}")
        print("\nThen re-run:  python -m jobpipe.cli.scan_gmail --setup")
        return

    print(f"Starting OAuth2 flow using credentials from: {creds_path}")
    print("A browser window will open. Approve Gmail read-only access.")
    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"\n[OK] Authorization complete. Token saved to: {token_path}")
    print("You can now run:  python -m jobpipe.cli.scan_gmail --dry-run")


__all__ = [
    "build_gmail_service",
    "fetch_full_message",
    "check_gmail_deps",
    "get_gmail_credentials",
    "list_unique_message_ids",
    "setup_oauth",
]
