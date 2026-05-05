from __future__ import annotations

import argparse
import json
import os
import uuid
from typing import List

import traceback


def read_json_safe(path: str) -> dict | None:
    """Read a JSON file, returning None on any error."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def read_stage_json(job_dir: str, stage_name: str) -> dict | None:
    """Read a stage artifact by suffix so stage-number drift does not break recovery."""
    try:
        matches = sorted(
            name for name in os.listdir(job_dir)
            if name.endswith(f"_{stage_name}.json")
        )
    except Exception:
        return None
    if not matches:
        return None
    return read_json_safe(os.path.join(job_dir, matches[-1]))

from jobpipe.core.io import ensure_dir, iter_jobs, load_env_file, load_profile_pack, stable_job_id, now_iso, write_json
from jobpipe.core.paths import JOBPIPE_DATA_ROOT_ENV, bootstrap_private_data, get_jobpipe_paths
from jobpipe.core.profile_layer import build_triage_instruction_profile_summary, load_or_build_profile_layer_for_paths

from jobpipe.core.config import load_config
from jobpipe.core.schema import (
    JobContext, RunMeta,
    TriageOut, ReverseTriageOut, JobParse, ProfileMatchOut,
    PivotOut, TriageFeatures, TriageDecisionV3, TriageAmbiguityV3, AdvantageAssessmentV3, NarrativeStrategyV3, ModeratorOut, ApplicationPackOut,
)
from jobpipe.core.runner import PipelineRunner, Stage

from jobpipe.stages.application_pack import application_pack_stage_factory
from jobpipe.stages.advantage_assessment_v3 import advantage_assessment_v3_stage_factory
from jobpipe.stages.moderate import moderate_stage_factory
from jobpipe.stages.narrative_strategy_v3 import narrative_strategy_v3_stage_factory
from jobpipe.stages.parse import parse_stage_factory
from jobpipe.stages.pivot import pivot_stage_factory
from jobpipe.stages.profile_match import profile_match_stage_factory
from jobpipe.stages.reverse_triage import reverse_triage_stage_factory
from jobpipe.stages.triage import triage_stage_factory
from jobpipe.stages.triage_ambiguity_v3 import triage_ambiguity_v3_stage_factory
from jobpipe.stages.triage_decision_v3 import triage_decision_v3_stage_factory
from jobpipe.stages.triage_features import triage_features_stage_factory
from jobpipe.stages.advantage_assessment_v3 import advantage_assessment_v3_cache_key
from jobpipe.stages.narrative_strategy_v3 import narrative_strategy_v3_cache_key
from jobpipe.stages.triage_ambiguity_v3 import triage_ambiguity_v3_cache_key
from jobpipe.stages.triage_decision_v3 import triage_decision_v3_cache_key
from jobpipe.stages.triage_features import triage_features_cache_key

_DEFAULT_PATHS = get_jobpipe_paths()


def build_stages(
    cfg,
    profile_pack: str = "",
    *,
    triage_profile_summary: str = "",
    targeting_title_patterns: list[str] | None = None,
) -> List[Stage]:
    """
    Stage.name must match JobContext attribute names for artifact dumps.
    Accept YAML-friendly aliases:
      - parse     -> parsed
      - moderate  -> moderator
    """
    max_chars = int(cfg.thresholds.get("max_ad_text_chars", 2200))
    triage_max_chars = int(cfg.thresholds.get("triage_max_ad_text_chars", max_chars))
    rt_max_chars = int(cfg.thresholds.get("reverse_triage_max_ad_text_chars", max_chars))
    rt_min_conf = float(cfg.thresholds.get("reverse_triage_min_conf", 0.70))
    rt_skip_above = float(cfg.thresholds.get("reverse_triage_skip_above", 1.0))

    aliases = {"parse": "parsed", "moderate": "moderator"}

    default_order = [
        "triage",
        "reverse_triage",
        "parsed",
        "profile_match",
        "pivot",
        "triage_features",
        "triage_decision_v3",
        "triage_ambiguity_v3",
        "advantage_assessment_v3",
        "narrative_strategy_v3",
        "moderator",
        "application_pack",
    ]

    order_raw = cfg.stages or default_order
    order = [aliases.get(s, s) for s in order_raw]

    allowed = set(default_order)
    stages: List[Stage] = []

    for s in order:
        if s not in allowed:
            raise ValueError(
                f"Unknown stage '{s}'. Allowed: {sorted(allowed)} "
                "(aliases: parse->parsed, moderate->moderator)"
            )

        if s == "triage":
            should_tr, run_tr = triage_stage_factory(
                model=cfg.models.get("triage", "gpt-4.1-nano"),
                max_ad_text_chars=triage_max_chars,
                safety_rules=cfg.safety_rules,
                profile_pack=profile_pack,
                triage_profile_summary=triage_profile_summary,
                targeting_title_patterns=targeting_title_patterns,
                semantic_threshold=float(cfg.thresholds.get("semantic_filter_threshold", 0.0)),
                semantic_model=str(cfg.thresholds.get("semantic_filter_model", "BAAI/bge-small-en-v1.5")),
            )
            stages.append(Stage(name="triage", run=run_tr, should_run=should_tr, ctx_model=TriageOut))

        elif s == "reverse_triage":
            should_rt, run_rt = reverse_triage_stage_factory(
                model=cfg.models.get("reverse_triage", "gpt-4.1-mini"),
                max_ad_text_chars=rt_max_chars,
                min_conf=rt_min_conf,
                skip_above=rt_skip_above,
            )
            stages.append(Stage(name="reverse_triage", run=run_rt, should_run=should_rt, ctx_model=ReverseTriageOut))

        elif s == "parsed":
            should_parse, run_parse = parse_stage_factory(
                model=cfg.models.get("parse", "gpt-4.1-mini"),
                max_ad_text_chars=max_chars,
            )
            stages.append(Stage(name="parsed", run=run_parse, should_run=should_parse, ctx_model=JobParse))

        elif s == "profile_match":
            should_pm, run_pm = profile_match_stage_factory(
                model=cfg.models.get("profile_match", "gpt-4.1-mini"),
            )
            stages.append(Stage(name="profile_match", run=run_pm, should_run=should_pm, ctx_model=ProfileMatchOut))

        elif s == "pivot":
            should_pv, run_pv = pivot_stage_factory(
                model=cfg.models.get("pivot", "gpt-4.1-mini"),
            )
            stages.append(Stage(name="pivot", run=run_pv, should_run=should_pv, ctx_model=PivotOut))

        elif s == "triage_features":
            should_tf, run_tf = triage_features_stage_factory()
            stages.append(
                Stage(
                    name="triage_features",
                    run=run_tf,
                    should_run=should_tf,
                    ctx_model=TriageFeatures,
                    cache_key_fn=triage_features_cache_key,
                )
            )

        elif s == "triage_decision_v3":
            should_td, run_td = triage_decision_v3_stage_factory()
            stages.append(
                Stage(
                    name="triage_decision_v3",
                    run=run_td,
                    should_run=should_td,
                    ctx_model=TriageDecisionV3,
                    cache_key_fn=triage_decision_v3_cache_key,
                )
            )

        elif s == "triage_ambiguity_v3":
            should_ta, run_ta = triage_ambiguity_v3_stage_factory()
            stages.append(
                Stage(
                    name="triage_ambiguity_v3",
                    run=run_ta,
                    should_run=should_ta,
                    ctx_model=TriageAmbiguityV3,
                    cache_key_fn=triage_ambiguity_v3_cache_key,
                )
            )

        elif s == "advantage_assessment_v3":
            should_aa, run_aa = advantage_assessment_v3_stage_factory()
            stages.append(
                Stage(
                    name="advantage_assessment_v3",
                    run=run_aa,
                    should_run=should_aa,
                    ctx_model=AdvantageAssessmentV3,
                    cache_key_fn=advantage_assessment_v3_cache_key,
                )
            )

        elif s == "narrative_strategy_v3":
            should_ns, run_ns = narrative_strategy_v3_stage_factory()
            stages.append(
                Stage(
                    name="narrative_strategy_v3",
                    run=run_ns,
                    should_run=should_ns,
                    ctx_model=NarrativeStrategyV3,
                    cache_key_fn=narrative_strategy_v3_cache_key,
                )
            )

        elif s == "moderator":
            should_mod, run_mod = moderate_stage_factory(cfg.thresholds)
            stages.append(Stage(name="moderator", run=run_mod, should_run=should_mod, ctx_model=ModeratorOut))

        elif s == "application_pack":
            should_pack, run_pack = application_pack_stage_factory(
                model=cfg.models.get("application_pack", "gpt-4.1"),
            )
            stages.append(Stage(name="application_pack", run=run_pack, should_run=should_pack, ctx_model=ApplicationPackOut))

    return stages


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True, help="Path to jobs .jsonl/.json/.csv")
    ap.add_argument(
        "--data-root",
        default="",
        help=f"JobPipe user data root (default: {_DEFAULT_PATHS.data_root})",
    )
    ap.add_argument(
        "--env-file",
        default="",
        help=f"Path to .env file (default: {_DEFAULT_PATHS.env_file})",
    )
    ap.add_argument(
        "--profile",
        default="",
        help=f"Path to profile_pack.md (default: {_DEFAULT_PATHS.profile_pack_path})",
    )
    ap.add_argument(
        "--out",
        default="",
        help=f"Output directory (default: {_DEFAULT_PATHS.out_runs_dir})",
    )
    ap.add_argument(
        "--config",
        default="",
        help=f"Pipeline config YAML (default: {_DEFAULT_PATHS.default_config_path})",
    )
    ap.add_argument("--config-overlay", action="append", default=[], help="Optional config overlay YAML. Can be passed multiple times.")
    ap.add_argument("--max", type=int, default=0, help="Max number of jobs (0 = all)")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite per-stage artifacts")
    args = ap.parse_args()

    paths = get_jobpipe_paths(args.data_root or None)
    os.environ[JOBPIPE_DATA_ROOT_ENV] = str(paths.data_root)
    bootstrap_private_data(paths, include_artifacts=True)
    env_file = args.env_file or str(paths.env_file)
    profile_path = args.profile or str(paths.profile_pack_path)
    out_path = args.out or str(paths.out_runs_dir)
    config_path = args.config or str(paths.default_config_path)

    load_env_file(env_file)
    cfg = load_config(config_path, overlays=args.config_overlay)
    profile_pack = load_profile_pack(profile_path)
    profile_layer = load_or_build_profile_layer_for_paths(paths)

    run_id = f"{cfg.pipeline_name}_{uuid.uuid4().hex[:8]}"
    run_dir = os.path.join(out_path, run_id)
    ensure_dir(run_dir)

    runner = PipelineRunner(
        build_stages(
            cfg,
            profile_pack=profile_pack,
            triage_profile_summary=build_triage_instruction_profile_summary(profile_layer),
            targeting_title_patterns=list(profile_layer.targeting_profile.target_title_patterns),
        )
    )
    meta = RunMeta(run_id=run_id, pipeline_name=cfg.pipeline_name, created_at=now_iso())

    count = 0
    errors = 0
    for job in iter_jobs(args.jobs):
        count += 1
        if args.max and count > args.max:
            break

        job_id = stable_job_id(job)
        job_dir = os.path.join(run_dir, job_id)
        ctx = JobContext(meta=meta, job_id=job_id, job=job, profile_pack=profile_pack)

        try:
            ctx = runner.run_job(ctx, job_dir=job_dir, overwrite=args.overwrite)
        except Exception as exc:
            errors += 1
            ensure_dir(job_dir)
            write_json(
                os.path.join(job_dir, "pipeline_error.json"),
                {"job_id": job_id, "error": str(exc), "traceback": traceback.format_exc()},
            )
            print(f"[ERROR] job {job_id} failed: {exc}", flush=True)

        try:
            runner.append_index(run_dir, ctx)
        except Exception as idx_exc:
            print(f"[WARN] index write failed for {job_id}: {idx_exc}", flush=True)

    # ── Post-run self-heal: repair any missing index entries ──────────────────
    # Catches cases where append_index silently failed mid-run (e.g. file lock,
    # exception after run_job completed successfully).
    try:
        index_path = os.path.join(run_dir, "index.jsonl")
        existing_ids: set = set()
        if os.path.exists(index_path):
            with open(index_path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                        if rec.get("job_id"):
                            existing_ids.add(rec["job_id"])
                    except Exception:
                        pass

        repaired = 0
        for entry in sorted(os.scandir(run_dir), key=lambda e: e.name):
            if not entry.is_dir():
                continue
            jid = entry.name
            if jid in existing_ids:
                continue
            # Reconstruct a minimal summary from artifacts
            try:
                inp = read_json_safe(os.path.join(entry.path, "00_input.json")) or {}
                triage = read_stage_json(entry.path, "triage") or {}
                profile = read_stage_json(entry.path, "profile_match") or {}
                pivot = read_stage_json(entry.path, "pivot") or {}
                triage_decision_v3 = read_stage_json(entry.path, "triage_decision_v3") or {}
                triage_ambiguity_v3 = read_stage_json(entry.path, "triage_ambiguity_v3") or {}
                advantage_assessment_v3 = read_stage_json(entry.path, "advantage_assessment_v3") or {}
                narrative_strategy_v3 = read_stage_json(entry.path, "narrative_strategy_v3") or {}
                mod = read_stage_json(entry.path, "moderator") or {}
                effective_triage_v3 = (
                    triage_ambiguity_v3.get("final_decision")
                    if isinstance(triage_ambiguity_v3.get("final_decision"), dict)
                    else triage_decision_v3
                )
                rec = {
                    "job_id": jid,
                    "title": inp.get("title", ""),
                    "employer": inp.get("employer_name", ""),
                    "triage_decision": triage.get("triage_decision", triage.get("decision", "")),
                    "triage_confidence": triage.get("confidence"),
                    "triage_signals": triage.get("signals", []),
                    "triage_v3_label": effective_triage_v3.get("label"),
                    "triage_v3_weighted_score": effective_triage_v3.get("weighted_score"),
                    "triage_v3_confidence": effective_triage_v3.get("confidence"),
                    "triage_v3_needs_ambiguity": effective_triage_v3.get("needs_ambiguity_pass"),
                    "triage_ambiguity_label": triage_ambiguity_v3.get("resolved_label"),
                    "advantage_type": advantage_assessment_v3.get("advantage_type"),
                    "advantage_review_priority": advantage_assessment_v3.get("review_priority"),
                    "narrative_positioning_angle": narrative_strategy_v3.get("positioning_angle"),
                    "narrative_brand_frame": narrative_strategy_v3.get("brand_frame"),
                    "final_decision": mod.get("final_decision", ""),
                    "fit_score": profile.get("fit_score"),
                    "pivot_score": pivot.get("pivot_score"),
                    "repaired": True,
                }
                with open(index_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                repaired += 1
            except Exception as rep_exc:
                print(f"[WARN] repair failed for {jid}: {rep_exc}", flush=True)

        if repaired:
            print(f"[INFO] Repaired {repaired} missing index entries.", flush=True)
    except Exception as heal_exc:
        print(f"[WARN] Post-run index repair failed: {heal_exc}", flush=True)

    suffix = f" ({errors} errors)" if errors else ""
    print(f"Done. Run dir: {run_dir}{suffix}")


if __name__ == "__main__":
    main()
