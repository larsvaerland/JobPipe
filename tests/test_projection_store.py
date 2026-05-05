from __future__ import annotations

from pathlib import Path

from jobpipe.core.projection_store import (
    apply_input_enrichment_projection,
    apply_detail_projection,
    build_input_enrichment_projection,
    build_detail_projection,
    build_job_projection_bundle,
    build_projected_job_input,
    get_job_projection_bundle,
    load_job_projection_context,
    load_job_projection_bundle,
    persist_projection_store,
    projection_bundle_detail_projection,
    projection_bundle_input_enrichment,
    projection_decision_brief,
    projection_job_summary,
    set_job_projection_bundle,
)


def test_projection_store_helpers_round_trip_job_context(tmp_path: Path) -> None:
    store_path = tmp_path / "reports" / "projection_store.json"
    persist_projection_store(
        store_path,
        {
            "inputEnrichment": {
                "run_1::nav_1": {
                    "employer": "Avinor",
                    "application_url": "https://example.test/apply",
                }
            },
            "detailProjections": {
                "run_1::nav_1": {
                    "decision_brief": {
                        "schema_version": "jobpipe.decision-brief.v1",
                        "final_decision": "APPLY",
                    },
                    "application_case_projection": {
                        "schema_version": "jobpipe.application-case-projection.v1",
                        "job_summary": {
                            "title": "Produktleder",
                            "company": "Avinor",
                        },
                    },
                }
            },
        },
    )

    input_projection, detail_projection = load_job_projection_context(
        store_path,
        run_id="run_1",
        job_id="nav_1",
    )

    assert input_projection["employer"] == "Avinor"
    assert projection_job_summary(detail_projection)["title"] == "Produktleder"
    assert projection_decision_brief(detail_projection)["final_decision"] == "APPLY"


def test_build_and_apply_detail_projection_only_keeps_versioned_boundary_objects() -> None:
    projection = build_detail_projection(
        decision_brief={
            "schema_version": "jobpipe.decision-brief.v1",
            "final_decision": "APPLY_STRONGLY",
        },
        application_case_projection={
            "schema_version": "jobpipe.application-case-projection.v1",
            "job_summary": {"title": "Produktsjef"},
        },
        updated_at="2026-04-19T10:30:00Z",
    )

    detail = {"decision_brief": {"schema_version": "old"}, "application_case_projection": {}}
    applied = apply_detail_projection(detail, projection)

    assert projection["updated_at"] == "2026-04-19T10:30:00Z"
    assert applied["decision_brief"]["final_decision"] == "APPLY_STRONGLY"
    assert applied["application_case_projection"]["job_summary"]["title"] == "Produktsjef"


def test_input_enrichment_projection_build_and_apply_round_trip() -> None:
    row = {
        "employer": "Avinor",
        "normalized_title": "produktleder",
        "application_url": "https://example.test/apply",
        "source_url": "https://example.test/job",
        "applicationDue": "2026-05-01",
        "work_city": "Oslo",
        "work_county": "Oslo",
        "work_postalCode": "0150",
        "job_source": "nav",
    }

    projection = build_input_enrichment_projection(row)
    target = {"employer": "", "application_url": "", "job_source": ""}
    applied = apply_input_enrichment_projection(target, projection)

    assert projection["employer"] == "Avinor"
    assert applied["employer"] == "Avinor"
    assert applied["application_url"] == "https://example.test/apply"
    assert applied["job_source"] == "nav"
    assert applied["work_city"] == "Oslo"


def test_build_projected_job_input_uses_input_and_detail_projections() -> None:
    projected = build_projected_job_input(
        job_id="nav_1",
        input_projection={
            "employer": "Avinor",
            "normalized_title": "produktleder",
            "application_url": "https://example.test/apply",
            "source_url": "https://example.test/job",
            "applicationDue": "2026-05-01",
            "work_city": "Oslo",
            "work_county": "Oslo",
            "work_postalCode": "0150",
            "job_source": "nav",
        },
        detail_projection={
            "application_case_projection": {
                "schema_version": "jobpipe.application-case-projection.v1",
                "job_summary": {
                    "title": "Produktleder",
                    "company": "Avinor AS",
                    "description_snippet": "Led produktarbeid for kritiske tjenester.",
                },
            }
        },
    )

    assert projected["job_id"] == "nav_1"
    assert projected["title"] == "Produktleder"
    assert projected["normalized_title"] == "produktleder"
    assert projected["employer_name"] == "Avinor"
    assert projected["applicationUrl"] == "https://example.test/apply"
    assert projected["sourceurl"] == "https://example.test/job"
    assert projected["description"] == "Led produktarbeid for kritiske tjenester."


def test_job_projection_bundle_round_trip_across_store_helpers(tmp_path: Path) -> None:
    store_path = tmp_path / "reports" / "projection_store.json"
    store = persist_projection_store(store_path, {})

    bundle = build_job_projection_bundle(
        input_enrichment={"employer": "Entur", "job_source": "nav"},
        detail_projection={
            "decision_brief": {
                "schema_version": "jobpipe.decision-brief.v1",
                "final_decision": "APPLY",
            },
            "application_case_projection": {
                "schema_version": "jobpipe.application-case-projection.v1",
                "job_summary": {"title": "Produktsjef"},
            },
        },
    )
    set_job_projection_bundle(store, run_id="run_2", job_id="nav_2", bundle=bundle)
    persist_projection_store(store_path, store)

    loaded_bundle = load_job_projection_bundle(store_path, run_id="run_2", job_id="nav_2")
    loaded_from_store = get_job_projection_bundle(store, run_id="run_2", job_id="nav_2")

    assert projection_bundle_input_enrichment(loaded_bundle)["employer"] == "Entur"
    assert projection_bundle_detail_projection(loaded_bundle)["decision_brief"]["final_decision"] == "APPLY"
    assert projection_bundle_input_enrichment(loaded_from_store)["job_source"] == "nav"
    assert projection_bundle_detail_projection(loaded_from_store)["application_case_projection"]["job_summary"]["title"] == "Produktsjef"
