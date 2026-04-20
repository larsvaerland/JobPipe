from __future__ import annotations

import re


_INTERVIEW_RE = re.compile(
    r"intervju|interview|innkalling|vi\s+ønsker\s+å\s+invitere|samtale\s+til|"
    r"invit\w+\s+til\s+(et\s+)?intervju|we\s+(would\s+like|invite)\s+you\s+to|"
    r"kandidat\s+til\s+intervju|gå\s+videre\s+til|neste\s+runde",
    re.IGNORECASE,
)

_REJECTED_RE = re.compile(
    r"dessverre|ikke\s+gå\s+videre|ikke\s+aktuell|"
    r"har\s+valgt\s+andre|ikke\s+valgt|beklageligvis|"
    r"vi\s+har\s+besluttet|ikke\s+vil\s+gå\s+videre\s+med|"
    r"unfortunately|we\s+regret|not\s+moving\s+forward|"
    r"we\s+have\s+chosen\s+other|we\s+will\s+not\s+be\s+moving|"
    r"not\s+selected|position\s+has\s+been\s+filled",
    re.IGNORECASE,
)

_APPLIED_RE = re.compile(
    r"bekreftelse\s+på\s+(mottatt\s+)?søknad|søknad\s+er\s+mottatt|"
    r"mottatt\s+søknad|vi\s+har\s+mottatt\s+din\s+søknad|"
    r"din\s+søknad\s+er\s+registrert|takk\s+for\s+din\s+søknad|"
    r"takk\s+for\s+søknaden\s+din|"
    r"søknaden\s+din\s+er\s+(mottatt|registrert|sendt)|"
    r"din\s+søknad\s+.{0,40}?er\s+nå\s+sendt\s+til|"
    r"application\s+received|received\s+your\s+application|"
    r"thank\s+you\s+for\s+(your\s+)?applying|thanks\s+for\s+applying|"
    r"your\s+application\s+(has\s+been\s+)?(received|submitted|sent)",
    re.IGNORECASE,
)

_PORTAL_NOISE_RE = re.compile(
    r"\s*(?:jobbnorge\.?(?:no|as)?|easycruit|teamtailor|webcruiter(?:mail)?|"
    r"recruitpartner|talentech|xcruiter|jobylon|finn\.?no)\s*",
    re.IGNORECASE,
)


def classify_email(subject: str, snippet: str, body: str) -> str | None:
    subject_text = subject.lower()
    full_text = f"{subject} {snippet} {body[:500]}".lower()

    if _INTERVIEW_RE.search(subject_text) or _INTERVIEW_RE.search(full_text):
        return "interview"
    if _REJECTED_RE.search(subject_text) or _REJECTED_RE.search(full_text):
        return "rejected"
    if _APPLIED_RE.search(subject_text) or _APPLIED_RE.search(full_text):
        return "applied"
    return None


def build_status_queries(after_str: str) -> list[str]:
    return [
        'label:"Jobb/Jobbsøk/Status jobbsøknad"',
        f'label:"Jobb/Jobbsøk" after:{after_str}',
        f"(subject:søknad) (subject:bekreftelse OR subject:mottatt OR subject:registrert) after:{after_str}",
        f"(subject:application) (subject:received OR subject:confirmation OR subject:submitted) after:{after_str}",
        f"subject:\"takk for din søknad\" after:{after_str}",
        f"subject:\"takk for søknaden\" after:{after_str}",
        f"subject:\"thank you for applying\" after:{after_str}",
        f"subject:\"thanks for applying\" after:{after_str}",
        f"subject:intervju (søknad OR stilling OR kandidat) after:{after_str}",
        f"subject:interview (application OR position OR candidate) after:{after_str}",
        f"subject:innkalling after:{after_str}",
        f"subject:dessverre (søknad OR stilling OR kandidat) after:{after_str}",
        f"(subject:unfortunately OR subject:\"not moving forward\") (application OR position) after:{after_str}",
        f"from:jobbnorge.no after:{after_str}",
        f"from:easycruit.com after:{after_str}",
        f"from:teamtailor after:{after_str}",
        f"from:webcruitermail.no after:{after_str}",
        f"from:recruitpartner.no after:{after_str}",
        f"from:talentech.email after:{after_str}",
        f"from:xcruiter.no after:{after_str}",
        f"from:jobylon.com after:{after_str}",
        f"from:linkedin.com (søknad OR application OR intervju OR interview OR dessverre OR unfortunately) after:{after_str}",
        f"from:cmt@finn.no after:{after_str}",
        f"from:noreply@finn.no (søknad OR stilling) after:{after_str}",
    ]


def subject_matches_status_email(subject: str) -> bool:
    return bool(
        _APPLIED_RE.search(subject)
        or _INTERVIEW_RE.search(subject)
        or _REJECTED_RE.search(subject)
    )


def clean_employer(name: str) -> str:
    name = _PORTAL_NOISE_RE.sub(" ", name).strip().strip(".,;:-")
    name = re.sub(r"\s+", " ", name).strip()
    return name


def extract_employer(subject: str, snippet: str, sender: str, body: str) -> str:
    full_text = f"{body} {snippet}"

    for pattern in [
        r"(?:melding|søknad)\s+fra[:\s]+([^\n<]{3,60})",
        r"fra:\s*([A-ZÆØÅ][^\n<]{2,60})",
    ]:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            candidate = clean_employer(match.group(1))
            if candidate and not re.search(r"jobbnorge|easycruit|teamtailor|webcruiter|linkedin|finn\.no", candidate, re.IGNORECASE):
                return candidate[:80]

    match = re.search(r'hos\s+([A-ZÆØÅ][^\n<"]{2,60}?)\s+er\s+mottatt', full_text, re.IGNORECASE)
    if match:
        return clean_employer(match.group(1))[:80]

    match = re.search(r'sendt\s+til\s+([A-ZÆØÅ][^\n<.]{2,60}?)(?:\.\s|\s*Har\s+du)', full_text, re.IGNORECASE)
    if match:
        return clean_employer(match.group(1))[:80]

    if "cmt@finn.no" in sender.lower():
        for pattern in [
            r'(?:hos|i)\s+([A-ZÆØÅ][^\n<,.]{2,60}?)(?:\s*$|\s*\.)',
            r'(?:søknad|stilling)\s+.{0,30}?\s+(?:hos|i|ved)\s+([A-ZÆØÅ][^\n<,.]{2,60})',
        ]:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                return clean_employer(match.group(1))[:80]

    for pattern in [
        r"application\s+was\s+sent\s+to\s+([^\n<.]{3,60})",
        r"([^\n<.]{3,60})\s+has\s+(?:reviewed|received)\s+your\s+application",
        r"([^\n<.]{3,60})\s+(?:has\s+)?decided\s+not\s+to\s+move",
    ]:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            candidate = clean_employer(match.group(1))
            if candidate:
                return candidate[:80]

    for pattern in [
        r"(?:stillingen?|stilling)\s+.{0,60}?\s+(?:ved|hos|i)\s+([A-ZÆØÅ][^\n<,.]{3,60})",
        r"(?:ved|hos)\s+([A-ZÆØÅ][^\n<,.]{3,60}?)(?:\s+er\s+|\s+har\s+|[,\.]|$)",
    ]:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            candidate = clean_employer(match.group(1))
            if candidate and not re.search(r"jobbnorge|easycruit|teamtailor|webcruiter|linkedin|finn\.no", candidate, re.IGNORECASE):
                return candidate[:80]

    match = re.match(r'^"?([^"<]{3,60})"?\s*<', sender)
    if match:
        name = match.group(1).strip()
        skip_names = {
            "noreply", "no-reply", "do not reply", "donotreply",
            "jobbnorge", "easycruit", "teamtailor", "webcruiter",
            "linkedin", "finn.no", "stepstone", "jobindex",
            "hr", "rekruttering", "recruitment", "jobs", "careers",
            "notifications", "varsler",
        }
        if name.lower() not in skip_names and len(name) > 3:
            return clean_employer(name)[:80]

    match = re.search(r"@([\w-]+)\.(no|com|org|gov|net)\b", sender)
    if match:
        domain = match.group(1)
        skip_domains = {
            "jobbnorge", "easycruit", "teamtailor", "webcruiter",
            "linkedin", "finn", "stepstone", "greenhouse", "lever",
            "workday", "visma", "reachmee", "gmail", "outlook",
        }
        if domain.lower() not in skip_domains:
            return domain.capitalize()[:40]

    return ""


def extract_title(subject: str, body: str) -> str:
    full = f"{subject} {body[:1000]}"
    for pattern in [
        r'søknad\s+på\s+stillingen?\s*[:\-–]?\s*"?([^"\n<]{5,80})"?',
        r'stillingen?\s+"([^"]{5,80})"',
        r'stillingen\s+"([^"]{5,80})"',
        r"application\s+to\s+(.{5,80}?)\s+at\s+",
        r"(?:position|role|stilling)\s+(?:of|as|som)\s+([^\n<,.]{5,60})",
    ]:
        match = re.search(pattern, full, re.IGNORECASE)
        if match:
            return match.group(1).strip().strip('"')[:80]
    return ""


__all__ = [
    "build_status_queries",
    "classify_email",
    "clean_employer",
    "extract_employer",
    "extract_title",
    "subject_matches_status_email",
]
