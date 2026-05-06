"""Generate a Norwegian cover letter using the OpenAI API."""
from __future__ import annotations

import json
import os

import openai

from jobpipe.authoring.case_context import AuthoringCaseContext

_SYSTEM_PROMPT = """Du er en norsk jobbsøkningsassistent.

Du mottar jobbsøknadskontekst som JSON og skriver et skreddersydd søknadsbrev på norsk.

Regler:
- Skriv på bokmål, direkte og troverdig — ingen klisjeer.
- Brevet skal ha 3–4 korte avsnitt: åpning, kjernekompetanse/erfaring, motivasjon, avslutning.
- Bruk konkrete eksempler fra selected_evidence og cv_selected_bullets. Finn ikke opp erfaringer.
- Speil cv_focus fra decision_brief og claim_targets fra artifact_plan for å understreke det arbeidsgiveren verdsetter.
- Unngå fraser som «engasjert lagspiller», «sterk kommunikator», «brennende opptatt av».
- Avslutt med tydelig initiativ, f.eks. «Ser frem til å høre fra dere.»
- Ikke ta med sted/dato, adresse eller hilsenfrase øverst — bare selve brevteksten.
- Maks 350 ord.

Hvis cover_letter_strategy er tilstede:
- Følg den overordnede strategien beskrevet i cover_letter_strategy nøye.

Hvis narrative_positioning_angle er tilstede:
- La denne vinkelen prege åpningsavsnittet og tonen gjennom hele brevet.

Hvis narrative_brand_frame er tilstede:
- Bruk denne rammen til å posisjonere kandidatens profil konsistent.

Hvis narrative_why_me_now er tilstede:
- Sørg for at brevet svarer tydelig på dette spørsmålet, gjerne i motivasjonsavsnittet.

Hvis differentiation_signals er tilstede:
- Vev inn ett eller to av de sterkeste signalene naturlig i teksten — ikke som en liste.

Hvis recruiter_hook er tilstede:
- Bruk dette som inspirasjon til åpningssetningen eller første avsnitt.

Hvis neutralizing_evidence er tilstede:
- Brevet kan proaktivt adressere potensielle gap med disse bevisene — ærlig og uten unnskyldninger.

Hvis artifact_plan er tilstede:
- Brevet skal være konsistent med cv_headline og cv_summary.
- cv_selected_bullets representerer det som allerede vises i CV-en — bekreft og utdyp, ikke bare gjenta.
- cv_suppressed_items er erfaring som IKKE er i CV-en. Brevet kan kort adressere relevante gap
  (f.eks. manglende sertifisering, kortere erfaring i et felt) — ærlig og uten unnskyldninger.
"""

_COVER_LETTER_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "cover_letter",
        "description": "Return the generated cover letter text.",
        "parameters": {
            "type": "object",
            "properties": {
                "cover_letter": {
                    "type": "string",
                    "description": "Full cover letter in Norwegian, plain text with paragraph breaks (\\n\\n).",
                }
            },
            "required": ["cover_letter"],
        },
    },
}


def generate_cover_letter(
    ctx: AuthoringCaseContext,
    *,
    model: str = "gpt-4o-mini",
) -> str:
    """Call the OpenAI API to write a Norwegian cover letter. Returns the letter text."""
    payload: dict = {
        "job_id": ctx.job_id,
        "job_summary": ctx.job_summary,
        "decision_brief": ctx.decision_brief,
        "selected_evidence": ctx.selected_evidence[:8],
        "narrative_brief": ctx.narrative_brief,
        "artifact_plan": ctx.artifact_plan,
    }
    # v3 signals — include only when present so the model isn't distracted by nulls
    if ctx.cover_letter_strategy:
        payload["cover_letter_strategy"] = ctx.cover_letter_strategy
    if ctx.narrative_positioning_angle:
        payload["narrative_positioning_angle"] = ctx.narrative_positioning_angle
    if ctx.narrative_brand_frame:
        payload["narrative_brand_frame"] = ctx.narrative_brand_frame
    if ctx.narrative_why_me_now:
        payload["narrative_why_me_now"] = ctx.narrative_why_me_now
    if ctx.differentiation_signals:
        payload["differentiation_signals"] = ctx.differentiation_signals
    if ctx.recruiter_hook:
        payload["recruiter_hook"] = ctx.recruiter_hook
    if ctx.neutralizing_evidence:
        payload["neutralizing_evidence"] = ctx.neutralizing_evidence
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=model,
        max_tokens=1500,
        tools=[_COVER_LETTER_TOOL],
        tool_choice={"type": "function", "function": {"name": "cover_letter"}},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )
    choice = response.choices[0]
    if choice.message.tool_calls:
        call = choice.message.tool_calls[0]
        try:
            args = json.loads(call.function.arguments)
            return str(args.get("cover_letter", "")).strip()
        except Exception:
            pass
    return ""


__all__ = ["generate_cover_letter"]
