from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jobpipe.workspace import ArtifactRunSource, ArtifactWorkspaceHub
from jobpipe.workspace.contracts import ApplicationCaseReadModel, CaseListItem


def _case_summary(item: CaseListItem, case: ApplicationCaseReadModel | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "case_id": item.id,
        "role": item.role,
        "company": item.company,
        "recommendation": item.recommendation.value,
        "score": item.score,
        "decision_signal_keys": [signal.key.value for signal in case.decision_signals] if case else [],
        "artifact_ref_count": len(case.artifacts) if case else 0,
    }
    if case is not None:
        payload.update(
            {
                "summary": _truncate(case.summary),
                "strength_count": len(case.strengths),
                "gap_count": len(case.gaps),
                "strengths": [_truncate(value, limit=90) for value in case.strengths[:3]],
                "gaps": [_truncate(value, limit=90) for value in case.gaps[:3]],
                "artifact_ref_ids": [artifact.id for artifact in case.artifacts],
            }
        )
    return payload


def _truncate(value: str, *, limit: int = 160) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _print_text(run_id: str, cases: list[dict[str, Any]], *, detail: bool) -> None:
    print(f"run_id: {run_id}")
    print(f"cases: {len(cases)}")
    for case in cases:
        print(
            " - "
            f"{case['case_id']} | {case['company']} | {case['role']} | "
            f"{case['recommendation']} | score={case['score']} | "
            f"signals={','.join(case['decision_signal_keys']) or '-'} | "
            f"artifacts={case['artifact_ref_count']}"
        )
        if detail:
            if case.get("summary"):
                print(f"   summary: {case['summary']}")
            print(f"   strengths={case['strength_count']} gaps={case['gap_count']}")
            if case.get("artifact_ref_ids"):
                print(f"   artifact_refs: {', '.join(case['artifact_ref_ids'])}")


def _build_payload(args: argparse.Namespace) -> tuple[str, list[dict[str, Any]]]:
    source = ArtifactRunSource(Path(args.out_root))
    run_ref = source.latest_run() if not args.run_id else None
    run_dir = source.resolve(args.run_id or None)
    if run_dir is None:
        raise SystemExit("No valid artifact run found.")

    run_id = args.run_id or (run_ref.id if run_ref else run_dir.name)
    hub = ArtifactWorkspaceHub(run_dir)
    items = hub.cases.list()

    if args.case_id:
        case = hub.cases.get(args.case_id)
        if case is None:
            raise SystemExit(f"Case not found: {args.case_id}")
        return run_id, [_case_summary(case.to_list_item(), case)]

    summaries: list[dict[str, Any]] = []
    for item in items:
        case = hub.cases.get(item.id)
        summaries.append(_case_summary(item, case))
    return run_id, summaries


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Preview redacted ApplicationWorkspaceHub cases from local JobPipe artifacts."
    )
    parser.add_argument("--out-root", required=True, help="Root containing JobPipe run directories.")
    parser.add_argument("--run-id", default="", help="Opaque run directory ID. Defaults to newest valid run.")
    parser.add_argument("--case-id", default="", help="Optional case ID for detail preview.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of compact text.")
    args = parser.parse_args(argv)

    run_id, cases = _build_payload(args)
    payload = {"run_id": run_id, "cases": cases}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    _print_text(run_id, cases, detail=bool(args.case_id))


if __name__ == "__main__":
    main(sys.argv[1:])
