"""Deterministic offline brain — EXTRACTIVE, not scripted.

The first version of this file returned canned UPI AutoPay payloads for every task. That made the
UPI demo look brilliant and produced a UPI BRD for a foreign-exchange project. A mock that answers
a question it wasn't asked is worse than no mock: it hides exactly the failure it should expose.

So this one reads the evidence it is actually given. It pulls the source text out of the prompt and
derives requirements, conflicts, gaps and downstream documents from *that*. It does not reason —
it extracts, with deterministic heuristics — so the prose is plainer than Gemini's. But it is about
the right project, it cites real lines from real sources, and when the sources disagree it says so.

MOCK_MODE exists to prove the machinery (retrieval, gates, versioning, traceability, export) end to
end without a credential. It is not a substitute for the model, and it now behaves like something
that knows the difference.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# ─────────────────────────── prompt archaeology ───────────────────────────────
# The body must stop at the next source OR at the end of the evidence block. Without the second
# half of that lookahead, the last source swallows the TASK instructions that follow it — and the
# extractor happily "finds" a requirement inside my own prompt. Which it did, once, in testing.
SOURCE_RE = re.compile(
    r"### SOURCE \[(?P<kind>[A-Z_]+)\] (?P<title>.+?)\n\(id=.*?\)\n(?P<body>.*?)"
    r"(?=\n### SOURCE |\n--- |\nTASK\n|\nRETRIEVED |\Z)",
    re.S,
)

# Belt and braces: even inside a source body, a line that is obviously part of an instruction is
# not evidence. Prompt text must never become a requirement.
PROMPT_LEAK = re.compile(
    r"\b(emit a `?conflict|do NOT|Set `?confidence|source_evidence|requirement ids|BR-001, BR-002|"
    r"hallucination|Extract every distinct|TASK\b)", re.I,
)
JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")

MODAL = re.compile(
    r"\b(must|shall|should|will need to|needs to|has to|mandatory|required|non-negotiable|"
    r"cannot|may not|not permitted|is not negotiable)\b", re.I,
)
DECISION = re.compile(r"^\s*\d*\s*(DECISION|AGREED|RESOLVED)\s*[:\-]", re.I)

# The language of an unresolved argument. Our seed corpora are full of it, and so is real discovery.
CONFLICT_MARK = re.compile(
    r"\b(UNRESOLVED|disagreed|pushed back|I am not convinced|I do not agree|too low|too high|"
    r"rejected it|I will not sign|the answer is no|I think that is|but I have thought about it|"
    r"having looked at|I know I pushed back)\b", re.I,
)
# The language of something nobody thought about.
GAP_MARK = re.compile(
    r"\b(nobody (has )?(mentioned|asked|discussed|designed|answered)|we have not (decided|talked|discussed)|"
    r"I do not have (a good answer|that number)|there isn'?t one|has not been (decided|designed)|"
    r"needs a plan|write (that|it) down|park it|somebody needs to|that needs to be in the requirements|"
    r"I did not know that|no SLA|it is not small|is unspecified|not been decided)\b", re.I,
)
COMPLIANCE = re.compile(
    r"\b(RBI|FEMA|PMLA|KYC|AML|DPDP|PCI|SEBI|IRDAI|regulat|complian|audit|circular|statutory|"
    r"master direction|localisation|retention|FIU|STR)\b", re.I,
)
INTEGRATION = re.compile(
    r"\b(integrat|API|switch|NPCI|Visa|Mastercard|RuPay|core banking|Finacle|ESB|vendor|feed|"
    r"network|downstream|upstream|platform)\b", re.I,
)
DATA = re.compile(r"\b(data|record|retention|storage|database|audit trail|log|report)\b", re.I)
NFR_HINT = re.compile(r"\b(latency|second|seconds|availab|uptime|throughput|scale|performance|p95|TAT)\b", re.I)


def _clean(line: str) -> str:
    """Meeting notes arrive as '12 DECISION: retail customers must...'. Strip the scaffolding."""
    line = re.sub(r"^\s*\d{1,3}\s+", "", line)                       # leading line number
    line = re.sub(r"^\s*\d{2}:\d{2}:\d{2}\s+\w+:\s*", "", line)      # transcript timestamp + speaker
    line = re.sub(r"^\s*[-•*]\s*", "", line)                          # bullet
    line = re.sub(r"^(DECISION|AGREED|RESOLVED|UNRESOLVED|ACTION)\s*[:\-]\s*", "", line, flags=re.I)
    return " ".join(line.split()).strip()


def _sentences(body: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for i, raw in enumerate(body.split("\n"), 1):
        text = _clean(raw)
        if len(text) < 25 or PROMPT_LEAK.search(text):
            continue
        out.append((i, text))
    return out


def _parse_sources(prompt: str) -> list[dict[str, Any]]:
    return [
        {"kind": m.group("kind"), "title": m.group("title").strip(), "body": m.group("body")}
        for m in SOURCE_RE.finditer(prompt)
    ]


def _parse_json_from_prompt(prompt: str, key: str) -> dict[str, Any]:
    """Downstream agents receive upstream JSON inline. Recover it so the chain stays coherent."""
    for m in re.finditer(r"\{[\s\S]{40,}?\n\}", prompt):
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if key in obj:
            return obj
    return {}


def _project(prompt: str) -> str:
    m = re.search(r"^PROJECT:\s*(.+)$", prompt, re.M)
    return m.group(1).strip() if m else "the capability"


def _h(s: str, n: int) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest(), 16) % max(n, 1)


# ─────────────────────────── requirement extraction ───────────────────────────
def _categorise(text: str) -> str:
    if COMPLIANCE.search(text):
        return "COMPLIANCE"
    if INTEGRATION.search(text):
        return "INTEGRATION"
    if NFR_HINT.search(text):
        return "NON_FUNCTIONAL"
    if DATA.search(text):
        return "DATA"
    return "FUNCTIONAL"


def _priority(text: str) -> str:
    if re.search(r"\b(must|shall|mandatory|non-negotiable|not negotiable|cannot|may not|will not)\b", text, re.I):
        return "MUST"
    if re.search(r"\bshould\b", text, re.I):
        return "SHOULD"
    return "SHOULD"


def _title(text: str, n: int = 9) -> str:
    words = re.sub(r"^(the|a|an)\s+", "", text, flags=re.I).split()
    t = " ".join(words[:n]).rstrip(",;:.")
    return t[:1].upper() + t[1:]


def _requirements(prompt: str) -> dict[str, Any]:
    sources = _parse_sources(prompt)
    project = _project(prompt)

    candidates: list[dict[str, Any]] = []
    conflicts_raw: list[dict[str, str]] = []
    gaps: list[str] = []

    for s in sources:
        for line_no, text in _sentences(s["body"]):
            cite = f"{s['title']}, line {line_no}"

            if GAP_MARK.search(text):
                gaps.append(f"{text} — raised in {s['title']} and left unresolved.")
                continue

            if CONFLICT_MARK.search(text):
                conflicts_raw.append({"text": text, "cite": cite, "source": s["title"]})
                # a contested statement is still a requirement candidate, just a shakier one
                if MODAL.search(text) or DECISION.match(text):
                    candidates.append({"text": text, "cite": cite, "contested": True})
                continue

            if DECISION.match(text) or MODAL.search(text):
                candidates.append({"text": text, "cite": cite, "contested": False})

    # Deduplicate on the opening of the sentence; discovery material repeats itself constantly.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for c in candidates:
        key = " ".join(c["text"].lower().split()[:6])
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)

    # Prefer explicit decisions and compliance statements — they are what a BA writes down first.
    def rank(c: dict) -> tuple[int, int]:
        t = c["text"]
        score = 0
        if DECISION.match(t):
            score += 3
        if COMPLIANCE.search(t):
            score += 2
        if re.search(r"\b(must|shall|mandatory)\b", t, re.I):
            score += 2
        if c["contested"]:
            score -= 1
        return (-score, len(t))

    unique.sort(key=rank)
    unique = unique[:8]

    requirements = []
    for i, c in enumerate(unique, 1):
        contested = c["contested"]
        requirements.append({
            "id": f"BR-{i:03d}",
            "title": _title(c["text"]),
            "statement": c["text"],
            "category": _categorise(c["text"]),
            "priority": _priority(c["text"]),
            "actors": _actors(c["text"]),
            "source_evidence": [c["cite"]],
            # Contested statements are honestly less certain. That number is the whole point of
            # showing a confidence score at all.
            "confidence": round(0.62 + (_h(c["text"], 12) / 100), 2) if contested
                          else round(0.84 + (_h(c["text"], 12) / 100), 2),
            "open_question": "Contested in the evidence — see conflicts." if contested else "",
        })

    conflicts = []
    for c in conflicts_raw[:4]:
        related = [r["id"] for r in requirements
                   if _overlap(r["statement"], c["text"]) or r["open_question"]]
        conflicts.append({
            "description": f"{c['text']} (stated in {c['source']}) — this contradicts or reopens a "
                           f"decision recorded elsewhere in the evidence.",
            "requirement_ids": related[:2],
            "resolution_needed_from": _owner(c["text"]) or "Project sponsor",
        })

    stakeholders = _stakeholders(prompt, sources)

    return {
        "requirements": requirements,
        "stakeholders": stakeholders,
        "conflicts": conflicts,
        "gaps": _dedupe(gaps)[:6],
        "summary": (
            f"{len(requirements)} business requirements extracted from {len(sources)} source(s) for "
            f"{project}. {len(conflicts)} conflict(s) and {len(_dedupe(gaps)[:6])} gap(s) require human "
            f"resolution before the concept note is finalised."
        ),
    }


def _overlap(a: str, b: str) -> bool:
    wa = {w for w in re.findall(r"[a-z]{5,}", a.lower())}
    wb = {w for w in re.findall(r"[a-z]{5,}", b.lower())}
    return len(wa & wb) >= 3


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for i in items:
        k = " ".join(i.lower().split()[:6])
        if k not in seen:
            seen.add(k)
            out.append(i)
    return out


ROLE_RE = re.compile(
    r"\b(Head of [A-Z][\w &]+|Chief [A-Z][\w ]+Officer|MD,? [A-Z][\w ]+|[A-Z][\w ]{2,20} (Lead|Officer|Head|PO|Manager)|"
    r"Compliance|Market Risk|Fraud Risk|Internal Audit|Model Risk Management|Data Privacy Officer|CISO Office|"
    r"Ops Head|Dealing Desk Head|Data Science Lead)\b"
)
EMAIL_RE = re.compile(r"([A-Za-z][\w .'-]{2,40})\s*<([\w.+-]+@[\w.-]+)>")


def _stakeholders(prompt: str, sources: list[dict]) -> list[dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    blob = "\n".join(s["body"] for s in sources)

    for name, email in EMAIL_RE.findall(blob):
        n = name.strip()
        if n and n not in out:
            out[n] = {"name": n, "role": n, "email": email}

    for m in ROLE_RE.findall(blob):
        role = m[0] if isinstance(m, tuple) else m
        role = role.strip()
        if role and role not in out and len(out) < 8:
            out[role] = {"name": role, "role": role, "email": ""}

    return list(out.values())[:8]


def _owner(text: str) -> str:
    m = ROLE_RE.search(text)
    return m.group(0).strip() if m else ""


ACTOR_RE = re.compile(
    r"\b(customer|corporate|merchant|analyst|agent|dealer|applicant|client|back office|"
    r"call centre|branch|regulator|vendor)\b", re.I,
)


def _actors(text: str) -> list[str]:
    found = {a.title() for a in ACTOR_RE.findall(text)}
    return sorted(found)[:4] or ["System"]


# ─────────────────────── downstream derivations ───────────────────────────────
def _concept_note(prompt: str) -> dict[str, Any]:
    reqs = _parse_json_from_prompt(prompt, "requirements").get("requirements", [])
    project = _project(prompt)
    ctx = _context_lines(prompt)

    compliance = [r for r in reqs if r["category"] == "COMPLIANCE"]
    must = [r for r in reqs if r["priority"] == "MUST"]

    return {
        "title": f"Concept Note — {project}",
        "business_objectives": ctx.get("objectives") or [
            f"Deliver {project} as specified by the approved business requirements.",
            "Reduce manual effort in the current journey and improve customer outcomes.",
        ],
        "scope": [r["title"] for r in must[:6]] or [f"{project} — core capability"],
        "out_of_scope": ctx.get("out_of_scope") or [
            "Anything not explicitly traced to a business requirement in this release.",
            "Channels, products and customer segments not named in the evidence.",
        ],
        "business_rules": [
            {"id": f"BRULE-{i:02d}", "rule": r["statement"]}
            for i, r in enumerate(compliance + [x for x in must if x not in compliance], 1)
        ][:8] or [{"id": "BRULE-01", "rule": "To be ratified — no decision rule stated in the evidence."}],
        "assumptions": [
            "The evidence base is complete for release 1; anything absent is captured as a gap.",
            "Named regulatory constraints apply as stated and have not changed since the workshop.",
        ],
        "dependencies": [
            {"name": d, "type": "EXTERNAL" if COMPLIANCE.search(d) is None else "REGULATORY",
             "impact": "Named in the evidence as a dependency; delivery cannot proceed without it."}
            for d in _dependencies(reqs)
        ] or [{"name": "None identified in the evidence", "type": "INTERNAL",
               "impact": "No dependency was stated — this is itself a gap worth confirming."}],
        "risks": _risks(prompt, reqs),
        "success_metrics": ctx.get("kpis") or [
            "No measurable success metric was stated in the evidence — this must be supplied.",
        ],
    }


def _context_lines(prompt: str) -> dict[str, list[str]]:
    """The intake form is indexed as evidence, so its fields turn up in the retrieved context."""
    out: dict[str, list[str]] = {}
    if m := re.search(r"Business Objective:\s*(.+)", prompt):
        out["objectives"] = [m.group(1).strip()]
    if m := re.search(r"Business Kpis:\s*(.+)", prompt):
        out["kpis"] = [k.strip() for k in m.group(1).split(",") if k.strip()]
    return out


DEP_RE = re.compile(
    r"\b(NPCI|Visa|Mastercard|RuPay|Finacle|core banking|ESB|vendor|FIU-IND|Income Tax database|"
    r"Aadhaar|rate feed|dealing desk|network|switch|certification)\b", re.I,
)


def _dependencies(reqs: list[dict]) -> list[str]:
    found = {d.title() for r in reqs for d in DEP_RE.findall(r["statement"])}
    return sorted(found)[:5]


def _risks(prompt: str, reqs: list[dict]) -> list[dict[str, str]]:
    payload = _parse_json_from_prompt(prompt, "requirements")
    risks = []
    for i, c in enumerate(payload.get("conflicts", [])[:3], 1):
        risks.append({
            "id": f"RISK-{i:02d}",
            "risk": f"Unresolved conflict carried into build: {c['description'][:150]}",
            "likelihood": "HIGH", "impact": "MEDIUM",
            "mitigation": f"Escalate to {c.get('resolution_needed_from', 'the sponsor')} before the "
                          "concept note is approved. Do not let the FRD assume an answer.",
        })
    for j, g in enumerate(payload.get("gaps", [])[:2], len(risks) + 1):
        risks.append({
            "id": f"RISK-{j:02d}",
            "risk": f"Requirement gap: {g[:150]}",
            "likelihood": "MEDIUM", "impact": "MEDIUM",
            "mitigation": "Close the gap with the business before the FRD; a guessed requirement here "
                          "becomes a defect in UAT.",
        })
    low = [r for r in reqs if r.get("confidence", 1) < 0.75]
    if low:
        risks.append({
            "id": f"RISK-{len(risks) + 1:02d}",
            "risk": f"{len(low)} requirement(s) rest on thin or contested evidence.",
            "likelihood": "MEDIUM", "impact": "MEDIUM",
            "mitigation": "Confirm each with the named business owner before sign-off.",
        })
    return risks or [{"id": "RISK-01", "risk": "No material risk surfaced from the evidence.",
                      "likelihood": "LOW", "impact": "LOW",
                      "mitigation": "Revisit once discovery is complete."}]


def _document(prompt: str, doc_type: str) -> dict[str, Any]:
    project = _project(prompt)
    reqs = _parse_json_from_prompt(prompt, "requirements").get("requirements", [])
    concept = _parse_json_from_prompt(prompt, "business_objectives")

    titles = {"BRD": "Business Requirements Document", "FRD": "Functional Requirements Document",
              "SRS": "Software Requirements Specification"}
    sections: list[dict[str, str]] = []

    if doc_type == "BRD":
        sections = [
            {"heading": "1. Executive Summary",
             "body": f"{project}. " + " ".join(concept.get("business_objectives", [])[:2])},
            {"heading": "2. Business Context & Problem Statement",
             "body": _joined(concept.get("business_objectives", []))
                     or "Derived from the discovery evidence supplied for this project."},
            {"heading": "3. Scope", "body": _joined(concept.get("scope", []))},
            {"heading": "4. Out of Scope", "body": _joined(concept.get("out_of_scope", []))},
            {"heading": "5. Business Requirements",
             "body": "\n".join(f"{r['id']} [{r['priority']}] {r['title']} — {r['statement']}" for r in reqs)},
            {"heading": "6. Business Rules",
             "body": "\n".join(f"{b['id']}: {b['rule']}" for b in concept.get("business_rules", []))},
            {"heading": "7. Assumptions, Dependencies & Risks",
             "body": _joined(concept.get("assumptions", [])) + "\n\n"
                     + "\n".join(f"{r['id']} ({r['likelihood']}/{r['impact']}): {r['risk']} — {r['mitigation']}"
                                 for r in concept.get("risks", []))},
            {"heading": "8. Success Metrics", "body": _joined(concept.get("success_metrics", []))},
        ]
    elif doc_type == "FRD":
        sections = [{"heading": "1. Purpose",
                     "body": f"Decomposes the approved business requirements for {project} into "
                             "implementable functional behaviour."}]
        sections += [
            {"heading": f"{i + 2}. FR-{i + 1:02d} — {r['title']}",
             "body": f"The system SHALL: {r['statement']}\n\n"
                     f"Actors: {', '.join(r.get('actors', []))}\n"
                     f"Traces to: {r['id']}\n"
                     f"Evidence: {'; '.join(r.get('source_evidence', []))}"
                     + (f"\nOPEN QUESTION: {r['open_question']}" if r.get("open_question") else "")}
            for i, r in enumerate(reqs)
        ]
        sections.append({"heading": f"{len(reqs) + 2}. Error Handling & Audit",
                         "body": "Every state transition writes an immutable audit record with actor, "
                                 "timestamp, before/after state and a correlation id. No raw downstream "
                                 "error is surfaced to a customer."})
    else:  # SRS
        sections = [
            {"heading": "1. Introduction",
             "body": f"Software requirements for {project}, derived from the approved BRD and FRD."},
            {"heading": "2. Overall Description",
             "body": _joined(concept.get("scope", [])) + "\n\nConstraints:\n"
                     + _joined(concept.get("assumptions", []))},
            {"heading": "3. External Interfaces",
             "body": "\n".join(f"{d['name']} ({d['type']}) — {d['impact']}"
                               for d in concept.get("dependencies", []))},
            {"heading": "4. Data & Retention",
             "body": "\n".join(r["statement"] for r in reqs if r["category"] == "DATA")
                     or "No explicit data requirement was stated in the evidence. This is a gap."},
            {"heading": "5. Compliance Requirements",
             "body": "\n".join(f"{r['id']}: {r['statement']}" for r in reqs if r["category"] == "COMPLIANCE")
                     or "No compliance requirement was extracted — verify this with Compliance."},
            {"heading": "6. Verification",
             "body": "Each functional requirement maps to at least one acceptance criterion and one "
                     "automated test."},
        ]

    return {
        "document_type": doc_type,
        "title": f"{titles[doc_type]} — {project}",
        "sections": sections,
        "traceability": [{"requirement_id": r["id"],
                          "section": "5. Business Requirements" if doc_type == "BRD"
                                     else f"FR-{i + 1:02d}" if doc_type == "FRD" else "2. Overall Description"}
                         for i, r in enumerate(reqs)],
    }


def _joined(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items)


def _user_stories(prompt: str) -> dict[str, Any]:
    reqs = _parse_json_from_prompt(prompt, "requirements").get("requirements", [])
    points = [3, 5, 8, 13]
    stories = []
    for i, r in enumerate(reqs, 1):
        actor = (r.get("actors") or ["user"])[0].lower()
        stories.append({
            "id": f"US-{i:02d}",
            "as_a": actor,
            "i_want": r["title"][0].lower() + r["title"][1:],
            "so_that": "the business outcome described in the requirement is achieved",
            "requirement_ids": [r["id"]],
            "story_points": points[_h(r["id"], len(points))],
            "acceptance_criteria": [
                f"GIVEN the preconditions in {r['id']} WHEN the actor performs the action "
                f"THEN the system behaves as stated: {r['statement'][:110]}",
                f"GIVEN an invalid input WHEN the action is attempted THEN it is rejected with a "
                f"customer-safe message and nothing is committed",
            ] + ([f"GIVEN the open question '{r['open_question']}' THEN this story is blocked until it is answered"]
                 if r.get("open_question") else []),
        })
    return {"stories": stories}


def _api_requirements(prompt: str) -> dict[str, Any]:
    reqs = _parse_json_from_prompt(prompt, "requirements").get("requirements", [])
    project = _project(prompt)
    slug = re.sub(r"[^a-z]+", "-", project.lower()).strip("-")[:24] or "resource"
    verbs = ["POST", "GET", "PATCH", "DELETE"]
    endpoints = []
    for i, r in enumerate(reqs[:6]):
        method = verbs[i % len(verbs)]
        endpoints.append({
            "method": method,
            "path": f"/v1/{slug}/{re.sub(r'[^a-z]+', '-', r['title'].lower()).strip('-')[:22]}",
            "purpose": r["title"],
            "auth": "OAuth2 + step-up authentication" if r["priority"] == "MUST" else "OAuth2",
            "request_schema": "{ …fields derived from the requirement, idempotencyKey }",
            "response_schema": "{ id, status, …}",
            "errors": ["400 VALIDATION_FAILED", "401 UNAUTHORIZED", "409 ILLEGAL_STATE", "502 UPSTREAM_UNAVAILABLE"],
            "sla_ms": 2500 if method != "GET" else 800,
            "idempotent": method != "POST",
            "requirement_ids": [r["id"]],
        })
    return {
        "endpoints": endpoints or [{
            "method": "GET", "path": f"/v1/{slug}", "purpose": "Placeholder — no requirement to derive from",
            "auth": "OAuth2", "request_schema": "{}", "response_schema": "{}",
            "errors": ["401 UNAUTHORIZED"], "sla_ms": 800, "idempotent": True, "requirement_ids": [],
        }],
        "conventions": "REST/JSON, camelCase, RFC 7807 problem+json errors, mandatory Idempotency-Key on "
                       "mutating calls, X-Correlation-Id propagated end to end, path versioning.",
    }


def _nfr(prompt: str) -> dict[str, Any]:
    reqs = _parse_json_from_prompt(prompt, "requirements").get("requirements", [])
    stated = [r for r in reqs if r["category"] in ("NON_FUNCTIONAL", "COMPLIANCE", "DATA")]

    nfrs = [{
        "id": f"NFR-{i:02d}",
        "category": "Compliance" if r["category"] == "COMPLIANCE" else
                    "Data Residency" if r["category"] == "DATA" else "Performance",
        "requirement": r["statement"],
        "measurement": "Evidenced in audit; monitored continuously against the stated threshold.",
        "requirement_ids": [r["id"]],
    } for i, r in enumerate(stated, 1)]

    # Bank-standard NFRs the evidence rarely states but every bank system needs. Marked as such —
    # they are proposed, not extracted, and a reviewer should know the difference.
    baseline = [
        ("Availability", "99.95% monthly availability for customer-facing endpoints, with graceful "
                         "degradation when a downstream dependency is unavailable.",
         "SLO with an error-budget policy."),
        ("Security", "PII encrypted at rest (AES-256, HSM-backed) and in transit (TLS 1.3). No PII in "
                     "application logs.", "Annual VAPT; automated log scanning in CI."),
        ("Observability", "Distributed tracing end to end with a correlation id; alerting on SLA breach "
                          "within 5 minutes.", "Trace completeness ≥99%; alert MTTA ≤5 min."),
        ("Accessibility", "WCAG 2.1 AA for all customer-facing screens.",
         "Automated axe scan plus a manual assistive-technology pass per release."),
        ("Data Residency", "All customer data stored and processed within India (RBI data localisation).",
         "Infrastructure attestation; region-pinned resources only."),
    ]
    for j, (cat, req, meas) in enumerate(baseline, len(nfrs) + 1):
        nfrs.append({
            "id": f"NFR-{j:02d}", "category": cat,
            "requirement": f"[PROPOSED — not stated in the evidence] {req}",
            "measurement": meas, "requirement_ids": [],
        })
    return {"nfrs": nfrs}




# ── Curated demo wireframes ───────────────────────────────────────────────────────────────────
# Five seeded projects, five real screen flows. Hand-authored because a generic
# Dashboard/Capture/Review skeleton is defensible for an unknown project and embarrassing for a
# known one: a Corporate FX portal needs a deal blotter and a FEMA declaration, not "Capture".
#
# `match` keywords are NOT decoration. Requirement IDs are resolved at run time by matching these
# against the requirements Agent 1 ACTUALLY extracted from that project's documents. Hardcoding
# BR-004 would produce a traceability table that looks perfect and cites a requirement that may not
# exist — the precise failure this platform is meant to prevent.
DEMO_WIREFRAMES: dict[str, list[dict[str, Any]]] = {
    "upi autopay": [
        {"name": "Mandate Dashboard", "purpose": "All active UPI AutoPay mandates for the customer, with next debit date and cap.",
         "match": ("view", "list", "dashboard", "active", "visib", "data must remain"),
         "components": [("Table", "Active mandates — merchant, cap, frequency, next debit"),
                        ("Card", "Total committed this month"),
                        ("Input", "Search by merchant"),
                        ("PrimaryButton", "Create new mandate")]},
        {"name": "Create Mandate", "purpose": "Self-service mandate creation without the merchant's involvement.",
         "match": ("create", "retail", "self-service", "merchant", "without"),
         "components": [("Input", "Merchant / biller"),
                        ("Input", "Maximum debit amount (cap)"),
                        ("Input", "Frequency — monthly / quarterly"),
                        ("Input", "Valid until"),
                        ("PrimaryButton", "Continue to authentication")]},
        {"name": "AFA Authentication", "purpose": "Additional Factor of Authentication — mandatory on every mandate execution.",
         "match": ("additional factor", "afa", "authenticat", "every execution"),
         "components": [("Banner", "AFA is mandatory for every mandate execution (NPCI)"),
                        ("Input", "UPI PIN"),
                        ("PrimaryButton", "Authorise mandate")]},
        {"name": "Pre-debit Notification", "purpose": "The 24-hour pre-debit notice the regulator requires.",
         "match": ("pre-debit", "notification", "24", "notif", "told"),
         "components": [("Banner", "Customer notified 24h before every debit — hard requirement"),
                        ("Table", "Upcoming debits in the next 7 days"),
                        ("PrimaryButton", "Acknowledge")]},
        {"name": "Pause / Cancel Mandate", "purpose": "Pause, modify or revoke a mandate without calling the branch.",
         "match": ("pause", "cancel", "revoke", "modify", "stop"),
         "components": [("Card", "Mandate — Netflix, INR 649, monthly"),
                        ("Input", "Reason (optional)"),
                        ("PrimaryButton", "Pause mandate"),
                        ("Alert", "Paused mandates resume only on customer action")]},
    ],
    "corporate fx": [
        {"name": "Deal Blotter", "purpose": "Every FX deal booked by the corporate, retrievable for 10 years.",
         "match": ("retriev", "10 year", "audit", "record", "view", "report"),
         "components": [("Table", "Deals — pair, notional, tenor, rate, status"),
                        ("Input", "Filter by counterparty / date"),
                        ("Chart", "Exposure by currency pair"),
                        ("PrimaryButton", "New booking")]},
        {"name": "Rate Request", "purpose": "Corporate treasurer requests a live rate for a currency pair and tenor.",
         "match": ("book", "request", "initiat", "create", "enter", "treasur"),
         "components": [("Input", "Currency pair — USD/INR"),
                        ("Input", "Notional amount"),
                        ("Input", "Value date / tenor"),
                        ("PrimaryButton", "Request live quote")]},
        {"name": "Quote Review", "purpose": "Dealer quotes with spread, valid for a countdown window.",
         "match": ("quote", "rate", "spread", "price", "dealer", "review"),
         "components": [("Card", "Best quote — 83.4150, valid 12s"),
                        ("Table", "Competing dealer quotes and spreads"),
                        ("Alert", "Quote expires — re-request after countdown"),
                        ("PrimaryButton", "Accept quote")]},
        {"name": "FEMA Declaration", "purpose": "Every trade tagged with an FEMA purpose code before it can settle.",
         "match": ("fema", "declaration", "purpose code", "complian", "regulat", "tag"),
         "components": [("Banner", "FEMA: every trade must carry a purpose code"),
                        ("Input", "Purpose code"),
                        ("Input", "Underlying document reference"),
                        ("PrimaryButton", "Submit declaration")]},
        {"name": "Limit & Risk Check", "purpose": "Deals above the threshold escalate to Market Risk before booking.",
         "match": ("limit", "risk", "escalat", "threshold", "above", "usd 1"),
         "components": [("Banner", "Deal exceeds threshold — Market Risk approval required"),
                        ("Card", "Utilised limit vs sanctioned limit"),
                        ("PrimaryButton", "Send to Market Risk")]},
        {"name": "Booking Confirmation", "purpose": "Deal slip, settlement instructions and audit reference.",
         "match": ("confirm", "settle", "slip", "receipt", "book"),
         "components": [("Card", "Deal booked — reference FX-2026-00841"),
                        ("Table", "Settlement instructions"),
                        ("PrimaryButton", "Download deal slip")]},
    ],
    "v-kyc": [
        {"name": "Application Start", "purpose": "Aadhaar and PAN capture — the top of the account-opening funnel.",
         "match": ("kyc", "rbi", "master direction", "aadhaar", "pan", "identity", "open", "capture"),
         "components": [("Input", "Mobile number"), ("Input", "PAN"), ("Input", "Aadhaar (masked)"),
                        ("Banner", "Consent — DPDP Act notice"),
                        ("PrimaryButton", "Begin application")]},
        {"name": "Document Upload", "purpose": "Proof of address and income, with quality checks before submission.",
         "match": ("document", "upload", "proof", "attack", "forged", "certified", "address"),
         "components": [("Input", "Upload proof of address"), ("Input", "Upload income proof"),
                        ("Alert", "Blurred or cropped images are rejected at V-CIP — check before submitting"),
                        ("PrimaryButton", "Submit documents")]},
        {"name": "V-CIP Queue", "purpose": "Live queue position and wait time — the 11-minute wait is the drop-off driver.",
         "match": ("wait", "queue", "agent", "volume", "spiky", "capacity", "v-cip", "vcip"),
         "components": [("Card", "Estimated wait — 2 min 40 s"),
                        ("Chart", "Queue depth by hour"),
                        ("Banner", "Target: V-CIP wait under 3 minutes"),
                        ("PrimaryButton", "Join video call")]},
        {"name": "Video KYC Session", "purpose": "Live agent V-CIP with liveness, geo-tagging and recording.",
         "match": ("liveness", "attack", "certified", "vendor", "video", "v-cip", "session"),
         "components": [("Card", "Live agent — recording, geo-tagged"),
                        ("Banner", "Session recorded and retained per RBI V-CIP norms"),
                        ("PrimaryButton", "Complete verification")]},
        {"name": "Account Activated", "purpose": "Account number, welcome kit and first-funding nudge.",
         "match": ("activat", "complete", "account", "casa", "welcome", "end-to-end"),
         "components": [("Card", "Account active — opened in 9 min 12 s"),
                        ("Table", "Account number, IFSC, customer ID"),
                        ("PrimaryButton", "Fund your account")]},
    ],
    "dispute": [
        {"name": "Dispute Dashboard", "purpose": "Status of every raised dispute — the screen that removes 60% of status calls.",
         "match": ("queue", "status", "track", "dashboard", "review", "dispute"),
         "components": [("Table", "Disputes — txn, amount, stage, TAT clock"),
                        ("Card", "Provisional credit — expected in 2 days"),
                        ("PrimaryButton", "Raise new dispute")]},
        {"name": "Raise Dispute", "purpose": "Pick the transaction, choose a reason code, raise digitally.",
         "match": ("raise", "claim", "fraud claim", "service dispute", "transaction", "digital"),
         "components": [("Table", "Recent card transactions — select one"),
                        ("Input", "Reason code — fraud / duplicate / not received"),
                        ("Input", "Describe what happened"),
                        ("PrimaryButton", "Raise dispute")]},
        {"name": "Evidence Upload", "purpose": "Customer evidence attached at source, so the analyst never chases it.",
         "match": ("evidence", "representment", "review", "upload", "attach"),
         "components": [("Input", "Upload receipt / merchant communication"),
                        ("Alert", "Missing evidence is the single biggest cause of TAT breach"),
                        ("PrimaryButton", "Attach and continue")]},
        {"name": "Provisional Credit", "purpose": "The 3-working-day provisional credit clock, visible to the customer.",
         "match": ("immediately", "credit", "provisional", "auto-approve", "tat", "compensation"),
         "components": [("Banner", "Provisional credit due within 3 working days — TAT breach triggers compensation"),
                        ("Card", "INR 12,400 credited provisionally"),
                        ("PrimaryButton", "View credit")]},
        {"name": "Resolution", "purpose": "Chargeback outcome, final credit or reversal, with reasoning.",
         "match": ("fraud", "resolv", "outcome", "chargeback", "approve", "recover"),
         "components": [("Card", "Dispute resolved in your favour"),
                        ("Table", "Chargeback trail and network reference"),
                        ("PrimaryButton", "Download resolution letter")]},
    ],
    "aml": [
        {"name": "Alert Queue", "purpose": "The alert backlog — 11,000 down to zero is the programme's headline.",
         "match": ("backlog", "alert", "queue", "volume", "11,000", "false positive"),
         "components": [("Table", "Alerts — customer, scenario, risk score, age"),
                        ("Chart", "Backlog burn-down"),
                        ("Input", "Filter by scenario / risk band"),
                        ("PrimaryButton", "Open alert")]},
        {"name": "Alert Triage", "purpose": "Analyst disposition with the evidence assembled on one screen.",
         "match": ("triage", "analyst", "investigat", "disposit", "review", "fte"),
         "components": [("Card", "Alert AML-2026-88214 — score 74"),
                        ("Table", "Triggering transactions"),
                        ("Input", "Disposition — close / escalate"),
                        ("PrimaryButton", "Save disposition")]},
        {"name": "Customer Risk 360", "purpose": "Everything known about the customer, so triage is not done blind.",
         "match": ("customer", "risk", "profile", "360", "history", "kyc"),
         "components": [("Card", "Risk band — High"),
                        ("Chart", "Transaction pattern vs peer group"),
                        ("Table", "Linked parties and prior alerts")]},
        {"name": "Model Tuning", "purpose": "Threshold changes with a false-positive/true-positive impact preview.",
         "match": ("model", "threshold", "tun", "false-positive", "true positive", "missed"),
         "components": [("Banner", "No threshold change may reduce true positives — CCO red line"),
                        ("Input", "Scenario threshold"),
                        ("Chart", "Simulated FP reduction vs TP retained"),
                        ("PrimaryButton", "Submit for CCO approval")]},
        {"name": "STR Filing", "purpose": "Suspicious Transaction Report to FIU-IND, with the audit trail attached.",
         "match": ("str", "fiu", "report", "regulat", "audit", "aud-2026", "file"),
         "components": [("Banner", "Audit finding AUD-2026-114 — filing trail is evidence"),
                        ("Input", "STR narrative"),
                        ("Table", "Attached transactions and analyst trail"),
                        ("PrimaryButton", "File STR")]},
    ],
}


def _demo_screens(project: str) -> list[dict[str, Any]] | None:
    p = (project or "").lower()
    for key, screens in DEMO_WIREFRAMES.items():
        if key in p:
            return screens
    return None


def _match_reqs(screen: dict[str, Any], reqs: list[dict]) -> list[str]:
    """Trace this screen to the requirements it actually serves — by reading them, not by guessing."""
    keys = screen.get("match", ())
    ids = [r["id"] for r in reqs
           if any(k in f"{r.get('title','')} {r.get('statement','')}".lower() for k in keys)]
    return ids[:4]


# A screen is not a requirement. Naming a screen by truncating a requirement sentence gives you
# "FEMA compliance: every trade must be tag" on a card in front of a CEO. Requirements are grouped
# INTO screens by the journey stage they belong to, which is what a real designer does.
_STAGE = [
    ("Dashboard",     ("dashboard", "view", "list", "search", "report", "monitor", "retriev")),
    ("Capture",       ("enter", "input", "capture", "submit", "book", "create", "raise", "initiat")),
    ("Review",        ("quote", "rate", "price", "calculat", "review", "verify", "preview")),
    ("Compliance",    ("fema", "kyc", "aml", "complian", "regulat", "rbi", "audit", "limit", "risk")),
    ("Confirmation",  ("confirm", "approve", "authoris", "authoriz", "notify", "receipt", "settle")),
]


def _stage_for(r: dict) -> str:
    text = f"{r.get('title','')} {r.get('statement','')}".lower()
    for name, keys in _STAGE:
        if any(k in text for k in keys):
            return name
    return "Dashboard"


def _wireframe(prompt: str) -> dict[str, Any]:
    reqs = _parse_json_from_prompt(prompt, "requirements").get("requirements", [])
    project = _project(prompt)

    if curated := _demo_screens(project):
        screens = []
        for sc in curated:
            ids = _match_reqs(sc, reqs)
            if not ids:
                # A screen that traces to NO requirement is exactly the defect this platform exists
                # to catch. Do not ship it as if it were justified — drop it, and let the coverage
                # check below account for anything left over.
                continue
            screens.append({
                "name": sc["name"],
                "purpose": sc["purpose"],
                "components": [{"type": t, "label": l, "props": {"requirement": ids[0]}}
                               for t, l in sc["components"]],
                "requirement_ids": ids,
            })

        # And the converse: a requirement that appears on NO screen is an uncovered requirement.
        # Say so on a screen of its own rather than quietly losing it between the BRD and the UI.
        covered = {i for sc in screens for i in sc["requirement_ids"]}
        orphans = [r for r in reqs if r["id"] not in covered]
        if orphans:
            screens.append({
                "name": "Uncovered Requirements",
                "purpose": "Requirements with no screen yet — surfaced, not hidden.",
                "components": [{"type": "Alert", "label": r["title"][:46],
                                "props": {"requirement": r["id"]}} for r in orphans[:6]],
                "requirement_ids": [r["id"] for r in orphans],
            })

        return {"screens": screens,
                "flow": " → ".join(x["name"] for x in screens),
                "design_system": "HDFC Bank DS — Inter, #004C8F",
                "notes": (f"Screen flow for {project}. Every screen traces to at least one extracted "
                          f"requirement; any requirement without a screen is listed explicitly.")}

    grouped: dict[str, list[dict]] = {}
    for r in reqs:
        grouped.setdefault(_stage_for(r), []).append(r)

    screens = []
    for stage, _keys in _STAGE:                      # keep the journey in order
        rs = grouped.get(stage)
        if not rs:
            continue
        comps = [{"type": "AppBar", "label": f"{project} — {stage}", "props": {}}]
        for r in rs[:4]:
            kind = ("Table" if stage == "Dashboard" else
                    "Banner" if stage == "Compliance" else
                    "Card" if stage == "Review" else "Input")
            comps.append({"type": kind, "label": r["title"][:44], "props": {"requirement": r["id"]}})
        comps.append({"type": "PrimaryButton",
                      "label": {"Dashboard": "Open", "Capture": "Submit", "Review": "Accept quote",
                                "Compliance": "Acknowledge", "Confirmation": "Confirm"}[stage],
                      "props": {}})
        screens.append({
            "name": stage,
            "purpose": rs[0]["statement"][:140],
            "components": comps,
            "requirement_ids": [r["id"] for r in rs[:4]],
        })
    if not screens:
        screens = [{"name": "Placeholder", "purpose": "No requirement available to derive a screen from.",
                    "components": [{"type": "EmptyState", "label": "No requirements", "props": {}}],
                    "requirement_ids": []}]
    return {
        "screens": screens,
        "design_system": "HDFC design system — Navy #004C8F primary, 8pt grid, Inter typeface",
        "flow": " → ".join(s["name"] for s in screens),
        "notes": f"Low-fidelity greybox screens derived from the extracted requirements for {project}. "
                 "Visual design applies the bank design system in a later cycle.",
    }


def _sprint_plan(prompt: str) -> dict[str, Any]:
    stories = _parse_json_from_prompt(prompt, "stories").get("stories", [])
    velocity = 15
    if m := re.search(r"Velocity assumption:\s*(\d+)", prompt):
        velocity = int(m.group(1))

    features = [{"id": f"FEAT-{i:02d}", "name": s["i_want"][:40].title(), "story_ids": [s["id"]]}
                for i, s in enumerate(stories, 1)]
    epics = [{
        "id": "EPIC-01", "name": f"{_project(prompt)} — Core Capability",
        "goal": "Deliver the approved requirements for this release.",
        "features": features or [{"id": "FEAT-01", "name": "Placeholder", "story_ids": []}],
    }]

    sprints, current, points, n = [], [], 0, 1
    for s in stories:
        p = s.get("story_points", 5)
        if points + p > velocity and current:
            sprints.append({"number": n, "goal": f"Deliver {len(current)} stories.",
                            "story_ids": current, "points": points, "risks": []})
            n, current, points = n + 1, [], 0
        current.append(s["id"])
        points += p
    if current:
        sprints.append({"number": n, "goal": f"Deliver {len(current)} stories.",
                        "story_ids": current, "points": points,
                        "risks": ["Stories blocked by an unresolved open question cannot start."]})

    return {
        "epics": epics,
        "sprints": sprints or [{"number": 1, "goal": "Nothing to plan — no approved stories.",
                                "story_ids": [], "points": 0, "risks": []}],
        "velocity_assumption": velocity,
        "estimation_notes": "Points assigned deterministically in mock mode. With Gemini live, sizing "
                            "reflects integration risk and dependency depth.",
    }


# ────────────────────────────── entry points ──────────────────────────────────
_DERIVERS = {
    "requirement_gathering": _requirements,
    "concept_note": _concept_note,
    "wireframe": _wireframe,
    "brd": lambda p: _document(p, "BRD"),
    "frd": lambda p: _document(p, "FRD"),
    "srs": lambda p: _document(p, "SRS"),
    "user_stories": _user_stories,
    "api_requirements": _api_requirements,
    "nfr": _nfr,
    "sprint_plan": _sprint_plan,
}

FEEDBACK_RE = re.compile(r"REVIEWER FEEDBACK.*?---\n(.*?)--- END REVIEWER FEEDBACK", re.S)


def _feedback(prompt: str) -> list[str]:
    m = FEEDBACK_RE.search(prompt)
    if not m:
        return []
    return [ln.lstrip("- ").strip() for ln in m.group(1).splitlines() if ln.strip().startswith("-")]


def _apply_feedback(task: str, payload: dict, fbs: list[str]) -> dict:
    """Make a revision genuinely differ from the round it replaces.

    Live, Gemini does this for us. In mock mode we fold the comments in explicitly — otherwise the
    regenerated artifact is byte-identical, the content-addressed versioner (correctly) refuses to
    create a v2, and the revision loop looks broken when it is working perfectly.
    """
    if not fbs:
        return payload
    if task == "concept_note":
        start = len(payload.get("business_rules", [])) + 1
        for i, f in enumerate(fbs, start):
            payload.setdefault("business_rules", []).append(
                {"id": f"BRULE-{i:02d}", "rule": f"[Revised per review] {f}"})
        payload.setdefault("assumptions", []).append(
            "This revision incorporates reviewer comments raised at the concept-note gate.")
    elif task in ("brd", "frd", "srs"):
        payload.setdefault("sections", []).append(
            {"heading": "Appendix — Review Revisions", "body": "\n".join(f"- {f}" for f in fbs)})
    elif task == "requirement_gathering":
        payload.setdefault("gaps", []).extend(f"Reviewer-raised: {f}" for f in fbs)
    elif task == "sprint_plan":
        payload["estimation_notes"] = payload.get("estimation_notes", "") + \
            " Re-planned per reviewer comments: " + "; ".join(fbs)
    return payload


def mock_json(*, task: str, prompt: str, schema: dict) -> dict:
    fn = _DERIVERS.get(task)
    if fn:
        try:
            return _apply_feedback(task, fn(prompt), _feedback(prompt))
        except Exception:  # a broken heuristic must not fail the run
            pass
    return _from_schema(schema, task, prompt)


def mock_text(*, task: str, prompt: str) -> str:
    if task == "copilot":
        return _mock_copilot(prompt)
    if task == "change_summary":
        return "Regenerated after reviewer comments."
    if task == "approval_email":
        return "Please review the attached artifact and approve or request changes."
    return f"[mock:{task}] {prompt[:160]}"


def _mock_copilot(prompt: str) -> str:
    """Offline copilot: answer from the blocks that were actually retrieved."""
    q = ""
    if m := re.search(r"BUSINESS ANALYST'S QUESTION\n(.*?)\n\nAnswer", prompt, re.S):
        q = m.group(1).strip()

    blocks = re.findall(
        r"\[(\d+)\] \(ns=([a-z_]+), score=([\d.-]+)\)\n(.*?)(?=\n\[\d+\] \(|\n--- END)", prompt, re.S,
    )
    if not blocks:
        return (
            f'I cannot answer "{q}" from this project\'s evidence — nothing relevant was retrieved from '
            "its memory.\n\nTo answer it I would need the discovery notes, the sponsor's email thread, or "
            "a transcript covering this topic. Upload them under Knowledge Ingestion and ask me again."
            "\n\n_(Mock mode: retrieval is real, the phrasing is deterministic. Set GOOGLE_API_KEY and "
            "MOCK_MODE=false for Gemini 2.5 Pro reasoning.)_"
        )

    lines = [f"Based on {len(blocks)} passage(s) retrieved from this project's memory:"]
    for n, ns, score, body in blocks[:3]:
        snippet = " ".join(body.split())[:230]
        lines.append(f"**[{n}]** _{ns}_ (relevance {float(score):.2f}) — {snippet}…")
    lines.append("That is what the evidence supports. Anything beyond it would be speculation, and this "
                 "platform does not let an agent speculate into a BRD.")
    lines.append("_(Mock mode: retrieval is real, the phrasing is deterministic. Set GOOGLE_API_KEY and "
                 "MOCK_MODE=false for Gemini 2.5 Pro reasoning.)_")
    return "\n\n".join(lines)


def _from_schema(schema: dict, task: str, prompt: str) -> Any:
    """Schema-conformant filler — the safety net when a heuristic has nothing to work with."""
    t = schema.get("type", "object")
    if t == "object":
        return {k: _from_schema(v, task, prompt + k) for k, v in (schema.get("properties") or {}).items()}
    if t == "array":
        item = schema.get("items", {"type": "string"})
        return [_from_schema(item, task, prompt + str(i)) for i in range(2)]
    if t == "integer":
        return [1, 2, 3, 5, 8][_h(prompt, 5)]
    if t == "number":
        return round(0.6 + _h(prompt, 40) / 100, 2)
    if t == "boolean":
        return _h(prompt, 2) == 1
    if enum := schema.get("enum"):
        return enum[_h(prompt, len(enum))]
    return f"[mock:{task}] no evidence available to derive this field"


# ══════════════════════════ Process Flow 2 — mock generators ═══════════════════
def _stories_from(prompt: str) -> list[dict[str, Any]]:
    """Recover the Flow-1 user stories the Flow-2 agents build on."""
    us = _parse_json_from_prompt(prompt, "stories").get("stories", [])
    if us:
        return us
    # fall back to any story-like titles in the prompt
    return [{"id": f"US-{i+1:02d}", "title": t[:80]}
            for i, t in enumerate(re.findall(r"(?:story|US-\d+)[:\-\s]+(.+)", prompt, re.I)[:6])] or \
           [{"id": "US-01", "title": "Deliver the approved capability"}]


def _points(title: str) -> int:
    return [2, 3, 5, 8, 13][_h(title, 5)]


def _backlog_refinement(prompt: str) -> dict[str, Any]:
    project = _project(prompt)
    stories = _stories_from(prompt)
    refined = []
    for s in stories:
        title = s.get("title", "")
        refined.append({
            "id": s.get("id"),
            "title": title,
            "estimate_points": _points(title),
            "acceptance_criteria": s.get("acceptance_criteria")
                or [f"Given the {project} context, {title.lower()} behaves as specified",
                    "All mandatory validations and error states are handled",
                    "The action is auditable and traceable to its requirement"],
            "source_requirement": s.get("source_evidence", ["Approved requirement pack"])[0]
                if isinstance(s.get("source_evidence"), list) else "Approved requirement pack",
        })
    return {
        "project": project,
        "refined_stories": refined,
        "open_questions": [
            {"id": "Q-01", "question": "Confirm the story-point baseline with the delivery team",
             "raised_by": "Development", "status": "OPEN"},
        ],
        "total_points": sum(r["estimate_points"] for r in refined),
        "notes": "Stories refined from the approved Flow-1 pack; estimates deterministic in mock mode.",
    }


def _grooming(prompt: str) -> dict[str, Any]:
    project = _project(prompt)
    stories = _stories_from(prompt)
    cap = 15
    sprints, cur, load, n = [], [], 0, 1
    for s in stories:
        pts = _points(s.get("title", ""))
        if load + pts > cap and cur:
            sprints.append({"number": n, "story_ids": cur, "points": load,
                            "goal": f"Deliver sprint {n} scope for {project}"})
            cur, load, n = [], 0, n + 1
        cur.append(s.get("id"))
        load += pts
    if cur:
        sprints.append({"number": n, "story_ids": cur, "points": load,
                        "goal": f"Deliver sprint {n} scope for {project}"})
    return {
        "project": project,
        "sprints": sprints,
        "capacity_per_sprint": cap,
        "dependencies": [{"from": stories[0].get("id"), "to": stories[-1].get("id"),
                          "note": "Sequence dependency identified in grooming"}] if len(stories) > 1 else [],
        "grooming_notes": "Sprint composition proposed against a 15-point capacity; confirmed in the "
                          "grooming workshop and written back to Jira.",
    }


def _code_review(prompt: str) -> dict[str, Any]:
    project = _project(prompt)
    stories = _stories_from(prompt)
    reviews = []
    for s in stories:
        reviews.append({
            "story_id": s.get("id"),
            "checklist": [
                {"item": "Implements every acceptance criterion", "status": "PASS"},
                {"item": "Input validation and error handling present", "status": "PASS"},
                {"item": "No secrets or PII in code or logs", "status": "PASS"},
                {"item": "Unit tests accompany the change", "status": "PASS"},
                {"item": "Meets the bank coding standard", "status": "PASS"},
            ],
        })
    return {
        "project": project,
        "reviews": reviews,
        "summary": f"Code-review checklist generated for {len(reviews)} stories from their acceptance "
                   "criteria and the bank coding standard; awaiting Technical-Lead approval.",
    }


def _qe_round(prompt: str) -> int:
    m = re.search(r"QE ROUND:\s*(\d+)", prompt)
    return int(m.group(1)) if m else 1


def _test_generation(prompt: str) -> dict[str, Any]:
    project = _project(prompt)
    stories = _stories_from(prompt)
    rnd = _qe_round(prompt)
    cases = []
    for s in stories:
        for j, ac in enumerate((s.get("acceptance_criteria") or
                                [f"{s.get('title','')} behaves as specified"])[:3]):
            cases.append({
                "test_id": f"{s.get('id')}-T{j+1}",
                "story_id": s.get("id"),
                "acceptance_criterion": ac if isinstance(ac, str) else str(ac),
                "steps": "Given the precondition, when the action is performed, then the AC holds.",
                "expected": "Outcome matches the acceptance criterion.",
                "result": "PASS",
            })
    # Deterministic rework loop: bugs on the FIRST QE pass, clean on the second — exactly the
    # "bugs identified? -> back to development" cycle in the diagram, bounded to one loop.
    bugs = []
    if rnd < 2 and cases:
        c = cases[0]
        c["result"] = "FAIL"
        bugs = [{"id": "BUG-01", "story_id": c["story_id"], "severity": "Medium",
                 "title": f"{c['story_id']}: acceptance criterion not met on first build",
                 "detail": f"Test {c['test_id']} failed — {c['acceptance_criterion'][:80]}"}]
    return {
        "project": project,
        "qe_round": rnd,
        "test_cases": cases,
        "bugs": bugs,
        "bugs_identified": bool(bugs),
        "coverage": f"{len(cases)} test cases across {len(stories)} stories, one per acceptance criterion.",
        "summary": ("Bugs identified — routing back to development." if bugs
                    else "All acceptance criteria pass — ready to present to PO & BTG."),
    }


def _release_handoff(prompt: str) -> dict[str, Any]:
    project = _project(prompt)
    stories = _stories_from(prompt)
    return {
        "project": project,
        "completed_stories": [{"id": s.get("id"), "title": s.get("title", ""), "status": "Done"}
                              for s in stories],
        "evidence": {
            "tests_passed": True,
            "code_review_approved": True,
            "acceptance_criteria_covered": "100%",
            "sign_off": "PO & BTG",
        },
        "release_notes": f"All stories for {project} pass QE with acceptance-criteria coverage, "
                         "code review approved, and PO/BTG sign-off recorded. Handed to DevOps for "
                         "production deployment.",
        "devops_handoff": {"status": "NOTIFIED", "channel": "devops"},
    }


_DERIVERS.update({
    "backlog_refinement": _backlog_refinement,
    "grooming": _grooming,
    "code_review": _code_review,
    "test_generation": _test_generation,
    "release_handoff": _release_handoff,
})
