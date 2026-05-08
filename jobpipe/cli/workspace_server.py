from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from jobpipe.workspace import ArtifactRunSource, ArtifactWorkspaceHub
from jobpipe.workspace.contracts import ApplicationCaseReadModel, CaseListItem, WorkspaceContractError


LIST_SCHEMA_VERSION = "jobpipe.workspace.cases.list.v1"
GET_SCHEMA_VERSION = "jobpipe.workspace.cases.get.v1"
HEALTH_SCHEMA_VERSION = "jobpipe.workspace.health.v1"


@dataclass(frozen=True)
class WorkspaceServerConfig:
    out_root: Path
    default_run_id: str = ""


def build_server(
    *,
    out_root: str | Path,
    run_id: str = "",
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    """Create a local read-only workspace cases HTTP server."""

    config = WorkspaceServerConfig(out_root=Path(out_root), default_run_id=run_id)

    class WorkspaceCasesHandler(BaseHTTPRequestHandler):
        server_version = "JobPipeWorkspaceCases/0.1"

        def do_GET(self) -> None:  # noqa: N802
            _handle_get(self, config)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), format % args))

    return ThreadingHTTPServer((host, port), WorkspaceCasesHandler)


def _handle_get(handler: BaseHTTPRequestHandler, config: WorkspaceServerConfig) -> None:
    parsed = urlparse(handler.path)
    try:
        if parsed.path == "/healthz":
            _write_json(handler, HTTPStatus.OK, {"schemaVersion": HEALTH_SCHEMA_VERSION, "status": "ok"})
            return

        if parsed.path == "/cases":
            run_id, hub = _resolve_hub(config, parse_qs(parsed.query))
            cases = [_case_summary(item, hub.cases.get(item.id)) for item in hub.cases.list()]
            _write_json(
                handler,
                HTTPStatus.OK,
                {"schemaVersion": LIST_SCHEMA_VERSION, "runId": run_id, "cases": cases},
            )
            return

        if parsed.path.startswith("/cases/"):
            case_id = unquote(parsed.path.removeprefix("/cases/")).strip()
            if not case_id or "/" in case_id:
                _write_error(handler, HTTPStatus.NOT_FOUND, "case_not_found", "Case not found.")
                return
            run_id, hub = _resolve_hub(config, parse_qs(parsed.query))
            case = hub.cases.get(case_id)
            if case is None:
                _write_error(handler, HTTPStatus.NOT_FOUND, "case_not_found", "Case not found.")
                return
            _write_json(
                handler,
                HTTPStatus.OK,
                {"schemaVersion": GET_SCHEMA_VERSION, "runId": run_id, "case": _case_detail(case)},
            )
            return

        _write_error(handler, HTTPStatus.NOT_FOUND, "artifact_unavailable", "Endpoint not found.")
    except WorkspaceContractError:
        _write_error(handler, HTTPStatus.INTERNAL_SERVER_ERROR, "contract_violation", "Workspace contract violation.")
    except ValueError as exc:
        _write_error(handler, HTTPStatus.BAD_REQUEST, "invalid_config", str(exc))
    except RunNotFoundError:
        _write_error(handler, HTTPStatus.NOT_FOUND, "run_not_found", "No valid artifact run found.")
    except OSError:
        _write_error(handler, HTTPStatus.INTERNAL_SERVER_ERROR, "artifact_unavailable", "Artifact unavailable.")
    except Exception:  # pragma: no cover - defensive boundary for the local wrapper
        _write_error(handler, HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error", "Internal server error.")


def _resolve_hub(
    config: WorkspaceServerConfig,
    query: dict[str, list[str]],
) -> tuple[str, ArtifactWorkspaceHub]:
    if not config.out_root.exists() or not config.out_root.is_dir():
        raise ValueError("Configured out_root is not a directory.")

    source = ArtifactRunSource(config.out_root)
    requested_run_id = _first_query_value(query, "run_id") or config.default_run_id
    if requested_run_id:
        run_dir = source.resolve(requested_run_id)
        if run_dir is None:
            raise RunNotFoundError
        return requested_run_id, ArtifactWorkspaceHub(run_dir)

    latest = source.latest_run()
    if latest is None:
        raise RunNotFoundError
    run_dir = source.resolve(latest.id)
    if run_dir is None:
        raise RunNotFoundError
    return latest.id, ArtifactWorkspaceHub(run_dir)


class RunNotFoundError(Exception):
    pass


def _case_summary(item: CaseListItem, case: ApplicationCaseReadModel | None = None) -> dict[str, Any]:
    return {
        "id": item.id,
        "company": item.company,
        "role": item.role,
        "location": item.location,
        "workMode": item.work_mode.value,
        "deadline": item.deadline,
        "score": item.score,
        "recommendation": item.recommendation.value,
        "applicationStatus": item.application_status.value,
        "mainStrength": _truncate(item.main_strength),
        "mainGap": _truncate(item.main_gap),
        "tailoringEffort": item.tailoring_effort.value,
        "nextAction": item.next_action,
        "decisionSignalKeys": [signal.key.value for signal in case.decision_signals] if case else [],
        "artifactRefCount": len(case.artifacts) if case else 0,
    }


def _case_detail(case: ApplicationCaseReadModel) -> dict[str, Any]:
    return {
        "id": case.id,
        "company": case.company,
        "role": case.role,
        "location": case.location,
        "workMode": case.work_mode.value,
        "deadline": case.deadline,
        "summary": _truncate(case.summary, limit=500),
        "atsKeywords": case.ats_keywords,
        "score": case.score,
        "recommendation": case.recommendation.value,
        "applicationStatus": case.application_status.value,
        "tailoringEffort": case.tailoring_effort.value,
        "nextAction": case.next_action,
        "decisionSignals": [
            {
                "key": signal.key.value,
                "label": signal.label,
                "score": signal.score,
                "band": signal.band,
                "rationale": _truncate(signal.rationale, limit=240),
                "confidence": signal.confidence,
                "evidenceIds": signal.evidence_ids,
                "supportingPoints": [_truncate(value) for value in signal.supporting_points[:4]],
                "riskPoints": [_truncate(value) for value in signal.risk_points[:4]],
            }
            for signal in case.decision_signals
        ],
        "strengths": [_truncate(value) for value in case.strengths[:6]],
        "gaps": [_truncate(value) for value in case.gaps[:6]],
        "evidence": [
            {
                "id": ref.id,
                "label": ref.label,
                "source": ref.source,
                "quote": _truncate(ref.quote),
                "confidence": ref.confidence,
            }
            for ref in case.evidence
        ],
        "artifacts": [
            {
                "id": artifact.id,
                "kind": artifact.kind,
                "status": artifact.status,
                "label": artifact.label,
                "preview": _truncate(artifact.preview),
                "updatedAt": artifact.updated_at,
            }
            for artifact in case.artifacts
        ],
    }


def _first_query_value(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key) or []
    return str(values[0] if values else "").strip()


def _truncate(value: str, *, limit: int = 160) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _write_json(handler: BaseHTTPRequestHandler, status: HTTPStatus, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status.value)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _write_error(handler: BaseHTTPRequestHandler, status: HTTPStatus, code: str, message: str) -> None:
    _write_json(handler, status, {"error": {"code": code, "message": message}})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve read-only ApplicationWorkspaceHub cases over local HTTP.")
    parser.add_argument("--out-root", required=True, help="Root containing JobPipe run directories.")
    parser.add_argument("--run-id", default="", help="Default opaque run directory ID. Defaults to newest valid run.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765).")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    server = build_server(out_root=args.out_root, run_id=args.run_id, host=args.host, port=args.port)
    host, port = server.server_address[:2]
    print(f"Serving workspace cases on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping workspace cases server.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main(sys.argv[1:])
