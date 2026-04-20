from __future__ import annotations

from jobpipe.cli import export_dashboard as cli_dashboard
from jobpipe.projections import dashboard as projection_dashboard


def test_cli_dashboard_reexports_projection_surface() -> None:
    assert cli_dashboard.build_payload is projection_dashboard.build_payload
    assert cli_dashboard.export is projection_dashboard.export
    assert cli_dashboard._load_app_state_merged is projection_dashboard._load_app_state_merged
