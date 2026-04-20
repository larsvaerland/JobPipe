from __future__ import annotations

import json
from pathlib import Path

from jobpipe.cli.run_shadow_triage_experiment import _load_shadow_input, _parse_feature_weights
from jobpipe.core.experiments import (
    append_experiment_run,
    build_false_negative_review_sample,
    build_threshold_shadow_run,
    compare_threshold_shadow_sample,
    load_latest_shadow_review_queue,
    load_recent_shadow_experiment_summaries,
    load_experiment_runs,
    persist_experiment_detail,
)
from jobpipe.core.schema import FeatureScore, HardGates, TriageFeatures


def _feature(score: int, confidence: int = 80) -> FeatureScore:
    return FeatureScore(score=score, confidence=confidence, reason="test", evidence_spans=[])


def _features(**overrides: int) -> TriageFeatures:
    defaults = {
        "core_tech_alignment": 78,
        "legacy_burden": 68,
        "role_specificity": 72,
        "requirement_density": 66,
        "geospatial_friction": 70,
        "remote_veracity": 68,
        "autonomy_level": 65,
        "stakeholder_complexity": 62,
        "operating_fit": 64,
    }
    defaults.update(overrides)
    return TriageFeatures(**{name: _feature(score) for name, score in defaults.items()})


def test_compare_threshold_shadow_sample_detects_label_change() -> None:
    sample = compare_threshold_shadow_sample(
        run_id="run_1",
        job_id="nav_1",
        features=_features(
            core_tech_alignment=72,
            legacy_burden=65,
            role_specificity=64,
            requirement_density=60,
            geospatial_friction=58,
            remote_veracity=62,
            autonomy_level=58,
            stakeholder_complexity=54,
            operating_fit=56,
        ),
        hard_gates=HardGates(),
        review_threshold=40.0,
        shortlist_threshold=55.0,
    )

    assert sample["baseline_label"] in {"review", "discard", "shortlist"}
    assert sample["candidate_label"] in {"review", "discard", "shortlist"}
    assert sample["direction"] in {"upgrade", "downgrade", "unchanged"}


def test_compare_threshold_shadow_sample_accepts_feature_weight_overrides() -> None:
    sample = compare_threshold_shadow_sample(
        run_id="run_1",
        job_id="nav_1",
        features=_features(
            core_tech_alignment=80,
            legacy_burden=50,
            role_specificity=52,
            requirement_density=48,
            geospatial_friction=45,
            remote_veracity=44,
            autonomy_level=40,
            stakeholder_complexity=38,
            operating_fit=40,
        ),
        hard_gates=HardGates(),
        review_threshold=48.0,
        shortlist_threshold=67.0,
        feature_weights={
            "core_tech_alignment": 0.45,
            "legacy_burden": 0.10,
            "role_specificity": 0.10,
            "requirement_density": 0.05,
            "geospatial_friction": 0.08,
            "remote_veracity": 0.06,
            "autonomy_level": 0.06,
            "stakeholder_complexity": 0.05,
            "operating_fit": 0.05,
        },
    )

    assert sample["candidate_weighted_score"] != sample["baseline_weighted_score"]


def test_threshold_shadow_run_persistence_round_trip(tmp_path: Path) -> None:
    run = build_threshold_shadow_run(
        review_threshold=44.0,
        shortlist_threshold=60.0,
        samples=[
            {
                "run_id": "run_1",
                "job_id": "nav_1",
                "baseline_label": "review",
                "baseline_weighted_score": 55.0,
                "candidate_label": "shortlist",
                "candidate_weighted_score": 55.0,
                "changed": True,
                "direction": "upgrade",
                "baseline_needs_ambiguity": False,
                "candidate_needs_ambiguity": False,
            }
        ],
        review_sample_max=5,
    )

    detail_path = tmp_path / "reports" / "experiments" / f"{run['experiment_id']}.json"
    index_path = tmp_path / "reports" / "experiment_runs.json"

    persist_experiment_detail(detail_path, run)
    summary = dict(run)
    summary.pop("samples", None)
    summary["detail_path"] = str(detail_path)
    append_experiment_run(index_path, summary)

    loaded_index = load_experiment_runs(index_path)
    loaded_detail = json.loads(detail_path.read_text(encoding="utf-8"))

    assert loaded_index[0]["experiment_id"] == run["experiment_id"]
    assert loaded_index[0]["changed_count"] == 1
    assert loaded_index[0]["review_sample_count"] == 1
    assert loaded_detail["samples"][0]["direction"] == "upgrade"
    assert loaded_detail["review_sample"][0]["review_reason"] == "promoted_in_shadow"


def test_threshold_shadow_run_marks_feature_weight_variant_when_present() -> None:
    run = build_threshold_shadow_run(
        experiment_id="shadow_weights",
        review_threshold=44.0,
        shortlist_threshold=62.0,
        samples=[],
        feature_weights={"core_tech_alignment": 0.45},
        candidate_name="triage_v3_feature_weight_variant",
    )

    assert run["kind"] == "shadow_feature_weight_eval"
    assert run["candidate"]["name"] == "triage_v3_feature_weight_variant"
    assert run["candidate"]["feature_weights"]["core_tech_alignment"] == 0.45
    assert run["baseline"]["feature_weights"]["core_tech_alignment"] > 0


def test_false_negative_review_sample_prioritizes_discard_promotions() -> None:
    review_sample = build_false_negative_review_sample(
        [
            {
                "run_id": "run_1",
                "job_id": "discard_to_review",
                "baseline_label": "discard",
                "baseline_weighted_score": 47.6,
                "candidate_label": "review",
                "candidate_weighted_score": 47.6,
                "changed": True,
                "direction": "upgrade",
                "baseline_needs_ambiguity": True,
                "candidate_needs_ambiguity": True,
            },
            {
                "run_id": "run_1",
                "job_id": "review_to_shortlist",
                "baseline_label": "review",
                "baseline_weighted_score": 64.1,
                "candidate_label": "shortlist",
                "candidate_weighted_score": 64.1,
                "changed": True,
                "direction": "upgrade",
                "baseline_needs_ambiguity": True,
                "candidate_needs_ambiguity": True,
            },
            {
                "run_id": "run_1",
                "job_id": "borderline_discard",
                "baseline_label": "discard",
                "baseline_weighted_score": 46.8,
                "candidate_label": "discard",
                "candidate_weighted_score": 46.8,
                "changed": False,
                "direction": "unchanged",
                "baseline_needs_ambiguity": True,
                "candidate_needs_ambiguity": True,
            },
        ],
        review_threshold=48.0,
        max_items=2,
    )

    assert [sample["job_id"] for sample in review_sample] == [
        "discard_to_review",
        "review_to_shortlist",
    ]
    assert review_sample[0]["review_reason"] == "promoted_from_discard"
    assert review_sample[1]["review_reason"] == "promoted_in_shadow"


def test_shadow_input_replays_features_from_stage_artifacts_when_bridge_artifact_missing(tmp_path: Path) -> None:
    job_dir = tmp_path / "out_runs" / "run_1" / "nav_1"
    job_dir.mkdir(parents=True)
    (job_dir / "00_input.json").write_text(
        json.dumps(
            {
                "job": {
                    "title": "Produktleder",
                    "description_html": "Hybrid rolle med produktutvikling og leveranseansvar.",
                    "remote": "Hybrid",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (job_dir / "03_parsed.json").write_text(
        json.dumps(
            {
                "role_summary": "Produktleder for digital tjeneste",
                "responsibilities": ["Lede roadmap", "Samarbeide med team"],
                "requirements_must": ["Produktledelse", "Smidig erfaring"],
                "requirements_nice": ["Offentlig sektor"],
                "seniority": "senior",
                "domain_tags": ["offentlig"],
                "tools_tech": ["jira"],
                "org_context": "Tverrfaglig team",
                "red_flags": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (job_dir / "04_profile_match.json").write_text(
        json.dumps(
            {
                "fit_score": 78,
                "match_level": "strong",
                "overlaps": ["Produktledelse"],
                "gaps": ["Ingen direkte sektorerfaring"],
                "hard_blockers": [],
                "notes": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (job_dir / "01_triage.json").write_text(
        json.dumps({"hard_gates": {"title_gate": True, "language_gate": True}}, ensure_ascii=False),
        encoding="utf-8",
    )

    loaded = _load_shadow_input("run_1", job_dir)

    assert loaded is not None
    assert loaded["feature_source"] == "replayed_from_stage_artifacts"
    assert loaded["features"].core_tech_alignment.score == 78


def test_load_latest_shadow_review_queue_returns_latest_review_items(tmp_path: Path) -> None:
    detail_path = tmp_path / "reports" / "experiments" / "shadow_latest.json"
    index_path = tmp_path / "reports" / "experiment_runs.json"
    run = build_threshold_shadow_run(
        experiment_id="shadow_latest",
        review_threshold=44.0,
        shortlist_threshold=62.0,
        samples=[
            {
                "run_id": "run_1",
                "job_id": "nav_1",
                "baseline_label": "discard",
                "baseline_weighted_score": 47.6,
                "candidate_label": "review",
                "candidate_weighted_score": 47.6,
                "changed": True,
                "direction": "upgrade",
                "baseline_needs_ambiguity": True,
                "candidate_needs_ambiguity": True,
            }
        ],
        review_sample_max=3,
    )
    persist_experiment_detail(detail_path, run)
    summary = dict(run)
    summary.pop("samples", None)
    summary["detail_path"] = str(detail_path)
    append_experiment_run(index_path, summary)

    loaded = load_latest_shadow_review_queue(index_path, max_items=2)

    assert loaded["schema_version"] == "jobpipe.experiments-dashboard.v1"
    assert loaded["latest_shadow_eval"]["experiment_id"] == "shadow_latest"
    assert loaded["latest_shadow_eval"]["review_sample_count"] == 1
    assert loaded["review_queue"][0]["job_id"] == "nav_1"


def test_load_recent_shadow_experiment_summaries_returns_latest_completed_shadow_runs(tmp_path: Path) -> None:
    index_path = tmp_path / "reports" / "experiment_runs.json"
    append_experiment_run(
        index_path,
        {
            "experiment_id": "shadow_feature",
            "kind": "shadow_feature_weight_eval",
            "status": "completed",
            "sample_size": 25,
            "changed_count": 4,
            "upgrade_count": 4,
            "downgrade_count": 0,
            "review_sample_count": 5,
            "created_at": "2026-04-19T18:20:00Z",
            "baseline": {"review_threshold": 48.0, "shortlist_threshold": 67.0},
            "candidate": {"name": "triage_v3_feature_weight_variant"},
            "detail_path": "C:/tmp/shadow_feature.json",
        },
    )
    append_experiment_run(
        index_path,
        {
            "experiment_id": "shadow_threshold",
            "kind": "shadow_threshold_eval",
            "status": "completed",
            "sample_size": 25,
            "changed_count": 8,
            "upgrade_count": 8,
            "downgrade_count": 0,
            "review_sample_count": 5,
            "created_at": "2026-04-19T18:30:00Z",
            "baseline": {"review_threshold": 48.0, "shortlist_threshold": 67.0},
            "candidate": {"name": "triage_v3_threshold_variant"},
            "detail_path": "C:/tmp/shadow_threshold.json",
        },
    )
    append_experiment_run(
        index_path,
        {
            "experiment_id": "ignored_pending",
            "kind": "shadow_threshold_eval",
            "status": "running",
            "created_at": "2026-04-19T18:40:00Z",
        },
    )

    loaded = load_recent_shadow_experiment_summaries(index_path, max_runs=2)

    assert [item["experiment_id"] for item in loaded] == ["shadow_threshold", "shadow_feature"]
    assert loaded[0]["candidate"]["name"] == "triage_v3_threshold_variant"
    assert loaded[0]["baseline"]["review_threshold"] == 48.0
    assert loaded[1]["kind"] == "shadow_feature_weight_eval"


def test_parse_feature_weights_requires_json_object() -> None:
    parsed = _parse_feature_weights('{"core_tech_alignment": 0.45, "legacy_burden": 0.12}')

    assert parsed["core_tech_alignment"] == 0.45
    assert parsed["legacy_burden"] == 0.12
