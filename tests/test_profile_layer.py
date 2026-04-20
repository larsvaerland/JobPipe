from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from jobpipe.core.profile_layer import (
    PROFILE_LAYER_SCHEMA_VERSION,
    build_profile_dashboard_payload,
    build_triage_instruction_profile_summary,
    build_profile_layer,
    build_triage_profile_text,
    load_or_build_profile_layer_for_paths,
    load_persisted_profile_layer,
    persist_profile_layer,
)
from jobpipe.core.paths import JobPipePaths


def _write_sources(tmp_path: Path) -> tuple[Path, Path, Path]:
    profile_path = tmp_path / "profile_pack.md"
    profile_path.write_text(
        dedent(
            """
            # PROFILE_PACK

            ## 0) Candidate snapshot
            - Base: Arendal
            - Languages: Norwegian + English
            - Level: Senior IC / lead
            - Positioning: Builds digital services across tech, business, and operations.

            ### Strategic direction
            Long-term goal is strategic service ownership with clear business value.

            ## 1) Target roles
            ### Primary targets
            - Produktleder
            - Tjenesteeier

            ### Secondary targets
            - CRM-ansvarlig

            ### Stepping-stone roles
            - Teamleder IT

            ## 2) Must-haves
            ### Location (OK if any)
            - Agder
            - Oslo
            Remote/Hybrid: always OK

            ## 7b) Market positioning context
            Motivation language core: "Jeg er motivert av roller der jeg kan forbedre digitale tjenester."
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    resume_path = tmp_path / "resume.json"
    resume_path.write_text(
        json.dumps(
            {
                "basics": {
                    "name": "Lars Værland",
                    "label": "Produkteier",
                    "summary": "Experienced product and service owner.",
                },
                "meta": {"version": "v1.0.0"},
                "work": [
                    {
                        "name": "Avinor",
                        "position": "Produktleder",
                        "startDate": "2024-01-01",
                        "endDate": "2025-01-01",
                        "summary": "Ledet produktutvikling og digital tjenesteforbedring.",
                        "highlights": [
                            "Ledet produktteam",
                            "Drevet digitalisering",
                        ],
                    },
                    {
                        "name": "Merkle",
                        "position": "Prosjektleder",
                        "startDate": "2021-01-01",
                        "endDate": "2023-12-31",
                        "summary": "Leveranser på tvers av tech og forretning.",
                        "highlights": [
                            "Koordinerte leveranser på tvers av fagmiljøer",
                        ],
                    },
                ],
                "projects": [
                    {
                        "name": "CRM-program",
                        "description": "Forbedret kundereiser og systemstøtte.",
                    }
                ],
                "skills": [
                    {
                        "name": "Produkt",
                        "keywords": ["Prioritering", "Backlog"],
                    },
                    {
                        "name": "ServiceNow",
                        "keywords": ["ITSM", "Forvaltning"],
                    },
                ],
                "education": [{"institution": "BI", "area": "Endringsledelse"}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    draft_path = tmp_path / "profile_builder_state.json"
    draft_path.write_text(
        json.dumps({"headline": "Endringsleder | Produkteier"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return profile_path, resume_path, draft_path


def test_build_profile_layer_creates_person_model_and_runtime_profiles(tmp_path: Path) -> None:
    profile_path, resume_path, _ = _write_sources(tmp_path)
    layer = build_profile_layer(
        profile_path.read_text(encoding="utf-8"),
        json.loads(resume_path.read_text(encoding="utf-8")),
        source_files=[str(profile_path), str(resume_path)],
    )

    assert layer.schema_version == PROFILE_LAYER_SCHEMA_VERSION
    assert layer.resume_master.resume_master_id == "resume_master:default"
    assert layer.resume_master.default_language == "nb"
    assert len(layer.role_records) == 2
    assert len(layer.role_variants) == 2
    assert len(layer.project_records) == 1
    assert len(layer.evidence_atoms) >= 4
    assert layer.content_library.section_inventory["work"] == [record.role_record_id for record in layer.role_records]
    assert layer.selection_rules.preferred_section_order[:4] == ["basics", "work", "projects", "skills"]
    assert layer.layout_profile.engine == "reactive-resume"
    assert layer.layout_profile.template_key == "rr-json-resume-baseline"
    assert layer.layout_profile.locale == "nb-NO"
    assert layer.layout_profile.rr_compat["section_order"] == layer.layout_profile.section_order
    assert layer.profile_snapshot.target_roles[:2] == ["Produktleder", "Tjenesteeier"]
    assert layer.targeting_profile.allowed_geos == ["Agder", "Oslo"]
    assert "Produktleder" in layer.triage_profile.role_summary
    assert layer.authoring_profile.selected_evidence_atom_ids
    assert layer.narrative_profile.language_preferences == "Norwegian + English"
    assert layer.profile_snapshot.source_provenance["object_kind"] == "ProfileSnapshot"
    assert layer.layout_profile.source_provenance["object_kind"] == "LayoutProfile"


def test_build_triage_profile_text_uses_derived_profile_layer(tmp_path: Path) -> None:
    profile_path, resume_path, _ = _write_sources(tmp_path)
    layer = build_profile_layer(
        profile_path.read_text(encoding="utf-8"),
        json.loads(resume_path.read_text(encoding="utf-8")),
        source_files=[str(profile_path), str(resume_path)],
    )

    text = build_triage_profile_text(layer)

    assert "Target roles: Produktleder, Tjenesteeier" in text
    assert "Skill clusters: Produkt, ServiceNow" in text
    assert "Ledet produktteam" in text


def test_build_triage_instruction_profile_summary_uses_targeting_layer(tmp_path: Path) -> None:
    profile_path, resume_path, _ = _write_sources(tmp_path)
    layer = build_profile_layer(
        profile_path.read_text(encoding="utf-8"),
        json.loads(resume_path.read_text(encoding="utf-8")),
        source_files=[str(profile_path), str(resume_path)],
    )

    text = build_triage_instruction_profile_summary(layer)

    assert "Primary targets: Produktleder, Tjenesteeier" in text
    assert "Allowed geography: Agder, Oslo" in text
    assert "Remote policy: always OK" in text


def test_build_profile_dashboard_payload_exposes_derived_contract(tmp_path: Path) -> None:
    profile_path, resume_path, draft_path = _write_sources(tmp_path)

    payload = build_profile_dashboard_payload(profile_path, resume_path, draft_path)

    assert payload["schema_version"] == PROFILE_LAYER_SCHEMA_VERSION
    assert payload["builder_state"]["headline"] == "Endringsleder | Produkteier"
    assert payload["target_roles"]["primary"] == ["Produktleder", "Tjenesteeier"]
    assert payload["target_geography"]["remote_policy"] == "always OK"
    assert payload["derived"]["profile_snapshot"]["target_roles"][0] == "Produktleder"
    assert payload["derived"]["content_library"]["section_inventory"]["work"]
    assert payload["derived"]["selection_rules"]["preferred_section_order"][0] == "basics"
    assert payload["derived"]["layout_profile"]["engine"] == "reactive-resume"
    assert payload["derived"]["counts"]["role_records"] == 2
    assert payload["derived"]["counts"]["skill_atoms"] == 2
    assert payload["derived"]["counts"]["content_library_sections"] >= 4


def test_profile_layer_can_be_persisted_and_reloaded_as_projection(tmp_path: Path) -> None:
    profile_path, resume_path, _ = _write_sources(tmp_path)
    layer = build_profile_layer(
        profile_path.read_text(encoding="utf-8"),
        json.loads(resume_path.read_text(encoding="utf-8")),
        source_files=[str(profile_path), str(resume_path)],
    )
    projection_path = tmp_path / "reports" / "profile_layer_state.json"

    persist_profile_layer(projection_path, layer)
    persisted = load_persisted_profile_layer(projection_path)

    assert persisted is not None
    assert persisted.schema_version == PROFILE_LAYER_SCHEMA_VERSION
    assert persisted.source_hash == layer.source_hash
    assert persisted.targeting_profile.preferred_domains == ["Produkt", "ServiceNow"]
    assert persisted.selection_rules.featured_skill_atom_ids[:2] == [skill.skill_atom_id for skill in layer.skill_atoms[:2]]
    assert persisted.layout_profile.rr_compat["meta_version"] == "v1.0.0"


def test_load_or_build_profile_layer_for_paths_uses_projection_boundary(tmp_path: Path) -> None:
    profile_path, resume_path, _ = _write_sources(tmp_path)
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    runtime_profile_path = tmp_path / "profile_pack.md"
    runtime_profile_path.write_text(profile_path.read_text(encoding="utf-8"), encoding="utf-8")
    runtime_resume_path = reports_dir / "resume.json"
    runtime_resume_path.write_text(resume_path.read_text(encoding="utf-8"), encoding="utf-8")
    paths = JobPipePaths(repo_root=tmp_path, data_root=tmp_path)

    layer = load_or_build_profile_layer_for_paths(paths)
    projection_path = reports_dir / "profile_layer_state.json"
    persisted = load_persisted_profile_layer(projection_path)

    assert projection_path.exists()
    assert persisted is not None
    assert persisted.source_hash == layer.source_hash
    assert persisted.profile_snapshot.target_roles[:2] == ["Produktleder", "Tjenesteeier"]
    assert persisted.layout_profile.section_order[:3] == ["basics", "work", "projects"]


def test_profile_layer_prefers_rr_style_layout_when_available(tmp_path: Path) -> None:
    profile_path, resume_path, _ = _write_sources(tmp_path)
    resume_payload = json.loads(resume_path.read_text(encoding="utf-8"))
    resume_payload["metadata"] = {"version": "v5.2.0", "source": "reactive-resume"}
    resume_payload["layout"] = {
        "template": "azurill",
        "locale": "en-US",
        "paperSize": "Letter",
        "lineHeight": "relaxed",
    }
    resume_payload["sections"] = [
        {"key": "basics"},
        {"key": "skills"},
        {"key": "work"},
        {"key": "projects"},
    ]

    layer = build_profile_layer(
        profile_path.read_text(encoding="utf-8"),
        resume_payload,
        source_files=[str(profile_path), str(resume_path)],
    )

    assert layer.resume_master.source_type == "reactive-resume.v5"
    assert layer.selection_rules.preferred_section_order[:4] == ["basics", "skills", "work", "projects"]
    assert layer.layout_profile.template_key == "azurill"
    assert layer.layout_profile.locale == "en-US"
    assert layer.layout_profile.page_settings["paper_size"] == "Letter"
    assert layer.layout_profile.rr_compat["meta_version"] == "v5.2.0"
