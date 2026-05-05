from __future__ import annotations

from jobpipe.core.schema import JobContext, RunMeta, TriageOut
from jobpipe.stages.triage import triage_stage_factory


class _FakeResult:
    def __init__(self, out: TriageOut):
        self._out = out

    def final_output_as(self, model):
        return self._out


def _ctx(job: dict) -> JobContext:
    return JobContext(
        meta=RunMeta(run_id="test", pipeline_name="test", created_at="2026-01-01T00:00:00Z"),
        job_id="job-1",
        job=job,
        profile_pack="",
    )


def test_hard_no_title_skip_records_failed_title_gate() -> None:
    _, run = triage_stage_factory(
        model="gpt-4.1-nano",
        max_ad_text_chars=1000,
        safety_rules={"hard_no_title_regex": r"butikkmedarbeider"},
    )

    ctx = run(_ctx({"title": "Butikkmedarbeider", "description_html": "irrelevant"}), job_dir="/tmp")

    assert ctx.triage is not None
    assert ctx.triage.triage_decision == "SKIP"
    assert ctx.triage.hard_gates is not None
    assert ctx.triage.hard_gates.title_gate is False
    assert ctx.triage.hard_gates.blocker_reasons == ["hard_no_title"]


def test_llm_reached_case_records_passing_hard_gates(monkeypatch) -> None:
    def _fake_run_agent(agent, input_text, trace=None):
        return _FakeResult(
            TriageOut(
                triage_decision="REVIEW",
                confidence=0.76,
                explanation="Reached LLM triage.",
                signals=["ownership"],
            )
        )

    monkeypatch.setattr("jobpipe.stages.triage.run_agent", _fake_run_agent)

    _, run = triage_stage_factory(
        model="gpt-4.1-nano",
        max_ad_text_chars=1000,
        safety_rules={},
    )

    ctx = run(
        _ctx(
            {
                "title": "Produkteier",
                "description_html": "Ansvar for roadmap og plattform.",
                "work_city": "Oslo",
            }
        ),
        job_dir="/tmp",
    )

    assert ctx.triage is not None
    assert ctx.triage.triage_decision == "REVIEW"
    assert ctx.triage.hard_gates is not None
    assert ctx.triage.hard_gates.passed() is True
    assert ctx.triage.hard_gates.blocker_reasons == []
