from __future__ import annotations

from typing import Protocol, runtime_checkable

from jobpipe.authoring.case_context import AuthoringCaseContext
from jobpipe.authoring.output_models import GeneratedApplicationPackage


@runtime_checkable
class AuthorAdapter(Protocol):
    """Swappable interface for the author/revise layer."""

    def generate(self, ctx: AuthoringCaseContext) -> GeneratedApplicationPackage: ...


__all__ = ["AuthorAdapter"]
