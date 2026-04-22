import dataclasses
import json

from jobpipe.authoring.case_context import AuthoringCaseContext
from jobpipe.authoring.output_models import GeneratedApplicationPackage


class CrewAIAuthor:
    """crewAI implementation of AuthorAdapter. May import crewai freely.
    jobpipe/ must never import this module statically."""

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self._model = model

    def generate(self, ctx: AuthoringCaseContext) -> GeneratedApplicationPackage:
        """Skeleton - real crew wired in Task 3."""
        return GeneratedApplicationPackage(
            job_id=ctx.job_id,
            cover_letter_draft="[stub - crewAI crew not yet wired]",
            tailored_cv_projection={},
            evidence_refs=[],
            gap_notes=["CrewAIAuthor skeleton - real crew wired in Task 3"],
        )
