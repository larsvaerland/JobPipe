from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from jobpipe.core.paths import JOBPIPE_DATA_ROOT_ENV
from jobpipe.core.paths import get_jobpipe_paths
from jobpipe.core.profile_layer import build_profile_match_context, load_profile_layer_for_paths


def _write_profile_sources(data_root: Path) -> None:
    (data_root / "reports").mkdir(parents=True, exist_ok=True)
    (data_root / "profile_pack.md").write_text(
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
    (data_root / "reports" / "resume.json").write_text(
        json.dumps(
            {
                "basics": {"name": "Lars Værland", "label": "Produkteier"},
                "work": [
                    {
                        "name": "Avinor",
                        "position": "Produktleder",
                        "startDate": "2024-01-01",
                        "endDate": "2025-01-01",
                        "summary": "Ledet produktutvikling og digital tjenesteforbedring.",
                        "highlights": ["Ledet produktteam", "Drevet digitalisering"],
                    }
                ],
                "projects": [
                    {"name": "CRM-program", "description": "Forbedret kundereiser og systemstøtte."}
                ],
                "skills": [
                    {"name": "Produkt", "keywords": ["Prioritering", "Backlog"]},
                    {"name": "ServiceNow", "keywords": ["ITSM", "Forvaltning"]},
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_profile_match_context_comes_from_derived_profile_layer(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(JOBPIPE_DATA_ROOT_ENV, str(tmp_path))
    _write_profile_sources(tmp_path)

    layer = load_profile_layer_for_paths(get_jobpipe_paths(data_root=tmp_path))
    context = build_profile_match_context(layer)

    assert context["schema_version"] == "jobpipe.profile-layer.v2"
    assert context["profile_snapshot"]["target_roles"][:2] == ["Produktleder", "Tjenesteeier"]
    assert "Produkt" in context["triage_profile"]["skill_clusters"]
    assert context["selected_role_variants"][0]["summary"]
    assert context["evidence_atoms_compact"][0]["text"] == "Ledet produktteam"
