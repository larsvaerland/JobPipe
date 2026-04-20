"""Architecture-boundary tests for the mail connector slice.

These tests are the runtime-checkable version of the rule in
specs/architecture-boundaries.md §4 ("Connectors must stop at normalization").

The jobpipe.connectors.mail package must own:
  - Gmail provider access (OAuth, session, list/fetch)
  - raw payload parsing and normalization
  - per-source classification and query builders

It must NOT reach into canonical-state / runtime storage. Those imports
belong at the orchestrator level (jobpipe.cli.scan_gmail) or in
jobpipe.runtime, not inside the connector slice.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

MAIL_PACKAGE = Path(__file__).resolve().parent.parent / "jobpipe" / "connectors" / "mail"

# Modules a connector slice must not import from. These are canonical-state
# and runtime-orchestration surfaces; reading them from inside the connector
# breaks the "stop at normalization" boundary rule.
FORBIDDEN_PREFIXES = (
    "jobpipe.core.primary_db",
    "jobpipe.core.evaluation_state",
    "jobpipe.runtime.catalog",
    "jobpipe.runtime.paths",
    "jobpipe.projections",
    "jobpipe.decision",
    "jobpipe.stages",
)


def _iter_mail_modules() -> list[Path]:
    return sorted(p for p in MAIL_PACKAGE.glob("*.py") if p.name != "__pycache__")


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


@pytest.mark.parametrize("module_path", _iter_mail_modules(), ids=lambda p: p.name)
def test_mail_connector_does_not_import_canonical_state(module_path: Path) -> None:
    """Each mail connector module must stay free of canonical-state imports."""
    source = module_path.read_text(encoding="utf-8")
    imported = _imported_modules(source)
    violations = {
        name
        for name in imported
        if any(name == prefix or name.startswith(prefix + ".") for prefix in FORBIDDEN_PREFIXES)
    }
    assert not violations, (
        f"{module_path.name} imports forbidden runtime/state modules: "
        f"{sorted(violations)}. Connectors must stop at normalization "
        f"(see specs/architecture-boundaries.md §4)."
    )


def test_mail_package_init_exposes_only_connector_surface() -> None:
    """jobpipe.connectors.mail.__all__ must not re-export state-access helpers."""
    import jobpipe.connectors.mail as mail_pkg

    # A positive spot-check: the known pure helpers remain exported.
    for name in (
        "build_gmail_service",
        "parse_message",
        "classify_email",
        "build_suggestion_queries",
        "detect_suggestion_platform",
        "extract_suggestion_jobs",
    ):
        assert name in mail_pkg.__all__, f"{name} missing from mail __all__"

    # A negative check: state-access helpers must not leak through the package.
    for name in ("load_existing_suggestion_keys",):
        assert name not in mail_pkg.__all__, (
            f"{name} must not be re-exported from jobpipe.connectors.mail — "
            "it reads canonical state and belongs at the orchestrator layer."
        )
        assert not hasattr(mail_pkg, name), (
            f"{name} must not be importable from jobpipe.connectors.mail"
        )
