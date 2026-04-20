from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from jobpipe.core.experiments import (
    append_experiment_run,
    build_threshold_shadow_run,
    compare_threshold_shadow_sample,
    persist_experiment_detail,
)
from jobpipe.core.paths import bootstrap_private_data, get_jobpipe_paths
from jobpipe.core.schema import HardGates, JobContext, JobParse, ProfileMatchOut, RunMeta, TriageFeatures
from jobpipe.stages.triage_features import build_triage_features


def _find_latest_suffix_artifact(job_dir: Path, suffix: str) -> Optional[Path]:
    matches = sorted(job_dir.glob(f"*{suffix}"))
    return matches[-1] if matches else None


def _load_json(path: Optional[Path]) -> Dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _iter_job_dirs(out_runs_dir: Path) -> Iterable[Tuple[str, Path]]:
    if not out_runs_dir.exists():
        return []
    items: List[Tuple[str, Path]] = []
    for run_dir in sorted(out_runs_dir.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        for job_dir in sorted(run_dir.iterdir()):
            if job_dir.is_dir():
                items.append((run_dir.name, job_dir))
    return items


def _rebuild_features_from_stage_artifacts(run_id: str, job_dir: Path) -> Optional[TriageFeatures]:
    input_raw = _load_json(job_dir / "00_input.json")
    parsed_raw = _load_json(_find_latest_suffix_artifact(job_dir, "_parsed.json"))
    profile_match_raw = _load_json(_find_latest_suffix_artifact(job_dir, "_profile_match.json"))
    if not input_raw or not parsed_raw or not profile_match_raw:
        return None

    job = input_raw.get("job", input_raw) if isinstance(input_raw, dict) else {}
    if not isinstance(job, dict) or not job:
        return None

    try:
        parsed = JobParse.model_validate(parsed_raw)
        profile_match = ProfileMatchOut.model_validate(profile_match_raw)
    except Exception:
        return None

    ctx = JobContext(
        meta=RunMeta(run_id=run_id, pipeline_name="shadow_triage_experiment", created_at=""),
        job_id=job_dir.name,
        job=job,
        profile_pack="",
        parsed=parsed,
        profile_match=profile_match,
    )
    return build_triage_features(ctx)


def _load_shadow_input(run_id: str, job_dir: Path) -> Optional[Dict[str, Any]]:
    job_id = job_dir.name
    features_raw = _load_json(_find_latest_suffix_artifact(job_dir, "_triage_features.json"))
    triage_raw = _load_json(_find_latest_suffix_artifact(job_dir, "_triage.json"))
    decision_raw = _load_json(_find_latest_suffix_artifact(job_dir, "_triage_decision_v3.json"))
    ambiguity_raw = _load_json(_find_latest_suffix_artifact(job_dir, "_triage_ambiguity_v3.json"))

    features: Optional[TriageFeatures] = None
    if features_raw:
        try:
            features = TriageFeatures.model_validate(features_raw)
        except Exception:
            features = None
    if features is None:
        features = _rebuild_features_from_stage_artifacts(run_id, job_dir)
    if features is None:
        return None

    hard_gates_raw = triage_raw.get("hard_gates", {}) if isinstance(triage_raw, dict) else {}
    try:
        hard_gates = HardGates.model_validate(hard_gates_raw or {})
    except Exception:
        hard_gates = HardGates()

    baseline_label = ""
    baseline_weighted_score = None
    if isinstance(ambiguity_raw.get("final_decision"), dict):
        baseline_label = str(ambiguity_raw["final_decision"].get("label") or "")
    baseline_label = baseline_label or str(decision_raw.get("label") or "")
    if decision_raw.get("weighted_score") is not None:
        try:
            baseline_weighted_score = float(decision_raw.get("weighted_score"))
        except Exception:
            baseline_weighted_score = None

    return {
        "run_id": run_id,
        "job_id": job_id,
        "features": features,
        "hard_gates": hard_gates,
        "baseline_label": baseline_label,
        "baseline_weighted_score": baseline_weighted_score,
        "feature_source": "artifact" if features_raw else "replayed_from_stage_artifacts",
    }


def _parse_feature_weights(raw: str) -> Dict[str, float]:
    if not raw.strip():
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("feature weights must be a JSON object")
    return {str(name): float(value) for name, value in parsed.items()}


def main(argv: List[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Run a safe shadow threshold experiment over triage-v3 artifacts.")
    ap.add_argument("--data-root", default="", help="JobPipe user data root")
    ap.add_argument("--review-threshold", type=float, required=True, help="Candidate review threshold")
    ap.add_argument("--shortlist-threshold", type=float, required=True, help="Candidate shortlist threshold")
    ap.add_argument("--max", type=int, default=0, help="Maximum number of jobs to compare")
    ap.add_argument("--review-sample-max", type=int, default=10, help="Maximum false-negative review items to persist")
    ap.add_argument("--feature-weights-json", default="", help="Optional JSON object overriding candidate triage feature weights")
    ap.add_argument("--feature-weights-file", default="", help="Optional path to a JSON file overriding candidate triage feature weights")
    ap.add_argument("--candidate-name", default="", help="Optional candidate label for the experiment summary")
    ap.add_argument("--job-id", default="", help="Limit to one job id")
    ap.add_argument("--dry-run", action="store_true", help="Print the experiment run without persisting it")
    args = ap.parse_args(argv)

    paths = get_jobpipe_paths(args.data_root or None)
    bootstrap_private_data(paths, include_artifacts=False)
    feature_weights: Dict[str, float] = {}
    if args.feature_weights_file:
        feature_weights = _parse_feature_weights(Path(args.feature_weights_file).read_text(encoding="utf-8"))
    elif args.feature_weights_json:
        feature_weights = _parse_feature_weights(args.feature_weights_json)
    candidate_name = args.candidate_name.strip() or (
        "triage_v3_feature_weight_variant" if feature_weights else "triage_v3_threshold_variant"
    )

    samples: List[Dict[str, Any]] = []
    count = 0
    for run_id, job_dir in _iter_job_dirs(paths.out_runs_dir):
        if args.job_id and job_dir.name != args.job_id:
            continue
        loaded = _load_shadow_input(run_id, job_dir)
        if not loaded:
            continue
        samples.append(
            compare_threshold_shadow_sample(
                run_id=loaded["run_id"],
                job_id=loaded["job_id"],
                features=loaded["features"],
                hard_gates=loaded["hard_gates"],
                baseline_label=loaded["baseline_label"],
                baseline_weighted_score=loaded["baseline_weighted_score"],
                review_threshold=args.review_threshold,
                shortlist_threshold=args.shortlist_threshold,
                feature_weights=feature_weights or None,
            )
        )
        samples[-1]["feature_source"] = loaded.get("feature_source", "")
        count += 1
        if args.max > 0 and count >= args.max:
            break

    run = build_threshold_shadow_run(
        review_threshold=args.review_threshold,
        shortlist_threshold=args.shortlist_threshold,
        samples=samples,
        review_sample_max=args.review_sample_max,
        feature_weights=feature_weights or None,
        candidate_name=candidate_name,
    )

    if args.dry_run:
        print(json.dumps(run, ensure_ascii=False, indent=2))
        return

    detail_path = paths.experiments_dir / f"{run['experiment_id']}.json"
    persist_experiment_detail(detail_path, run)
    summary = dict(run)
    summary.pop("samples", None)
    summary.pop("review_sample", None)
    summary["detail_path"] = str(detail_path)
    append_experiment_run(paths.experiment_runs_path, summary)

    print(
        f"[OK] Shadow experiment recorded: {run['experiment_id']} "
        f"({run['sample_size']} jobs, {run['changed_count']} changes, "
        f"{run['review_sample_count']} review items)"
    )


if __name__ == "__main__":
    main()
