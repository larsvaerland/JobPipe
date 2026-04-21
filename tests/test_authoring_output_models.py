from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from jobpipe.authoring.output_models import DocumentValidationResult, GeneratedApplicationPackage


def _generated_package(**overrides: object) -> GeneratedApplicationPackage:
    values = {
        "job_id": "job-1",
        "cover_letter_draft": "Dear hiring team...",
        "tailored_cv_projection": {
            "headline": "Product leader",
            "selected_bullets": ["Led roadmap work."],
        },
        "evidence_refs": [{"evidence_unit_id": "evidence-1"}],
        "gap_notes": ["Clarify sector transition."],
        "validation": {"passed": True, "score": 0.91},
    }
    values.update(overrides)
    return GeneratedApplicationPackage(**values)


def test_generated_package_happy_path() -> None:
    package = _generated_package()

    assert package.job_id == "job-1"
    assert package.cover_letter_draft == "Dear hiring team..."
    assert package.tailored_cv_projection["headline"] == "Product leader"
    assert package.evidence_refs == [{"evidence_unit_id": "evidence-1"}]
    assert package.gap_notes == ["Clarify sector transition."]
    assert package.validation == {"passed": True, "score": 0.91}


def test_generated_package_validation_field_accepts_dict() -> None:
    package = _generated_package(validation={"passed": False, "failures": ["missing evidence"]})

    assert package.validation == {"passed": False, "failures": ["missing evidence"]}


def test_generated_package_missing_required_field_raises() -> None:
    with pytest.raises(ValidationError):
        GeneratedApplicationPackage(
            job_id="job-1",
            cover_letter_draft="Dear hiring team...",
            tailored_cv_projection={},
            evidence_refs=[],
        )


def test_generated_package_model_dump_shape() -> None:
    package = _generated_package(validation=None)

    assert package.model_dump() == {
        "job_id": "job-1",
        "cover_letter_draft": "Dear hiring team...",
        "tailored_cv_projection": {
            "headline": "Product leader",
            "selected_bullets": ["Led roadmap work."],
        },
        "evidence_refs": [{"evidence_unit_id": "evidence-1"}],
        "gap_notes": ["Clarify sector transition."],
        "validation": None,
    }


def test_validation_result_happy_path() -> None:
    result = DocumentValidationResult(
        passed=True,
        score=0.87,
        failures=[],
        warnings=["Review tone."],
    )

    assert result.passed is True
    assert result.score == 0.87
    assert result.failures == []
    assert result.warnings == ["Review tone."]


def test_validation_result_score_coerces_int() -> None:
    result = DocumentValidationResult(
        passed=True,
        score=1,
        failures=[],
        warnings=[],
    )

    assert result.score == 1.0


def test_no_crewai_import() -> None:
    env = None
    git_grep_dir = Path("C:/Program Files/Git/usr/bin")
    if git_grep_dir.exists():
        env = dict(os.environ)
        env["PATH"] = f"{git_grep_dir}{os.pathsep}{env.get('PATH', '')}"

    result = subprocess.run(
        ["grep", "-r", "crewai", "jobpipe/", "--include=*.py"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 1, f"Unexpected crewai reference found:\n{result.stdout}"
    assert result.stdout == ""
