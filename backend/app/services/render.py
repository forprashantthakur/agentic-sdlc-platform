"""Payload → markdown renderers.

The structured payload is the machine-readable truth; the rendered markdown is what a
human reviews, what gets pushed to Google Drive, and what the diff engine compares.
Keeping rendering out of the LLM means the document layout is deterministic and the
model only has to be right about content.
"""

from __future__ import annotations

from typing import Any

from app.models import ArtifactType


def _tbl(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("\n", "<br>") for c in r) + " |")
    return "\n".join(out)


def render_requirements(p: dict[str, Any]) -> str:
    s = ["# Structured Business Requirements", "", f"_{p.get('summary','')}_", ""]
    s += ["## Requirements", ""]
    s += [_tbl(
        ["ID", "Title", "Category", "Priority", "Confidence", "Statement", "Evidence"],
        [[r["id"], r["title"], r["category"], r["priority"], f"{r.get('confidence', 0):.2f}",
          r["statement"], "; ".join(r.get("source_evidence", []))] for r in p.get("requirements", [])],
    ), ""]
    if p.get("stakeholders"):
        s += ["## Stakeholders", "", _tbl(["Name", "Role", "Email"],
              [[x["name"], x["role"], x.get("email", "")] for x in p["stakeholders"]]), ""]
    if p.get("conflicts"):
        s += ["## Conflicts requiring human resolution", ""]
        s += [f"- **{', '.join(c.get('requirement_ids', []))}** — {c['description']} "
              f"_(owner: {c.get('resolution_needed_from','TBD')})_" for c in p["conflicts"]]
        s += [""]
    if p.get("gaps"):
        s += ["## Gaps", ""] + [f"- {g}" for g in p["gaps"]] + [""]
    return "\n".join(s)


def render_concept_note(p: dict[str, Any]) -> str:
    s = [f"# {p.get('title','Concept Note')}", ""]
    s += ["## Business Objectives", ""] + [f"- {x}" for x in p.get("business_objectives", [])] + [""]
    s += ["## Scope", ""] + [f"- {x}" for x in p.get("scope", [])] + [""]
    s += ["## Out of Scope", ""] + [f"- {x}" for x in p.get("out_of_scope", [])] + [""]
    s += ["## Business Rules", "", _tbl(["ID", "Rule"],
          [[r["id"], r["rule"]] for r in p.get("business_rules", [])]), ""]
    s += ["## Assumptions", ""] + [f"- {x}" for x in p.get("assumptions", [])] + [""]
    s += ["## Dependencies", "", _tbl(["Dependency", "Type", "Impact"],
          [[d["name"], d["type"], d["impact"]] for d in p.get("dependencies", [])]), ""]
    s += ["## Risks", "", _tbl(["ID", "Risk", "Likelihood", "Impact", "Mitigation"],
          [[r["id"], r["risk"], r["likelihood"], r["impact"], r["mitigation"]]
           for r in p.get("risks", [])]), ""]
    if p.get("success_metrics"):
        s += ["## Success Metrics", ""] + [f"- {x}" for x in p["success_metrics"]] + [""]
    return "\n".join(s)


def render_wireframe(p: dict[str, Any]) -> str:
    s = ["# Wireframe Specification", "", f"**Design system:** {p.get('design_system','')}", ""]
    s += [f"**Flow:** {p.get('flow','')}", ""]
    for sc in p.get("screens", []):
        s += [f"## {sc['name']}", "", f"_{sc.get('purpose','')}_", "",
              _tbl(["Component", "Label", "Props"],
                   [[c["type"], c.get("label", ""), ", ".join(f"{k}={v}" for k, v in (c.get("props") or {}).items())]
                    for c in sc.get("components", [])]),
              "", f"**Traces to:** {', '.join(sc.get('requirement_ids', []))}", ""]
    wf = p.get("wireframes") or p.get("figma")
    if wf:
        provider = (wf.get("provider") or "figma").title()
        s += [f"## Generated screens — {provider}", ""]
        if wf.get("error"):
            s += [f"> Screens pending: {wf['error']}", ""]
        else:
            if wf.get("project_url") or wf.get("file_url"):
                s += [f"- Project: {wf.get('project_url') or wf.get('file_url')}", ""]
            if wf.get("screens"):
                s += [_tbl(["Screen", "Traces to", "Preview", "Link"],
                           [[sc["name"], ", ".join(sc.get("requirement_ids", [])),
                             f"![{sc['name']}]({sc['screenshot_url']})" if sc.get("screenshot_url") else "—",
                             sc.get("url", "—")] for sc in wf["screens"]]), ""]
            elif wf.get("frames"):
                s += [f"- Frames: {', '.join(wf['frames'])}", ""]
    if p.get("notes"):
        s += ["## Notes", "", p["notes"], ""]
    return "\n".join(s)


def render_document(p: dict[str, Any]) -> str:
    s = [f"# {p.get('title', p.get('document_type', 'Document'))}", ""]
    for sec in p.get("sections", []):
        s += [f"## {sec['heading']}", "", sec["body"], ""]
    if p.get("traceability"):
        s += ["## Traceability Matrix", "", _tbl(["Requirement", "Section"],
              [[t["requirement_id"], t["section"]] for t in p["traceability"]]), ""]
    return "\n".join(s)


def render_user_stories(p: dict[str, Any]) -> str:
    s = ["# User Stories & Acceptance Criteria", ""]
    for st in p.get("stories", []):
        s += [f"## {st['id']} — {st['i_want'][:70]}", "",
              f"**As a** {st['as_a']} **I want** {st['i_want']} **so that** {st['so_that']}", "",
              f"**Points:** {st.get('story_points','-')} · **Traces to:** {', '.join(st.get('requirement_ids', []))}", "",
              "**Acceptance criteria**", ""]
        s += [f"{i + 1}. {ac}" for i, ac in enumerate(st.get("acceptance_criteria", []))]
        s += [""]
    return "\n".join(s)


def render_acceptance_criteria(p: dict[str, Any]) -> str:
    rows = []
    for st in p.get("stories", []):
        for i, ac in enumerate(st.get("acceptance_criteria", []), 1):
            rows.append([f"{st['id']}-AC{i}", st["id"], ", ".join(st.get("requirement_ids", [])), ac])
    return "\n".join(["# Acceptance Criteria (Given/When/Then)", "",
                      _tbl(["AC ID", "Story", "Requirement", "Criterion"], rows), ""])


def render_api(p: dict[str, Any]) -> str:
    s = ["# API Requirements", "", f"**Conventions:** {p.get('conventions','')}", "",
         _tbl(["Method", "Path", "Purpose", "Auth", "SLA (ms)", "Idempotent", "Errors", "Traces to"],
              [[e["method"], f"`{e['path']}`", e["purpose"], e["auth"], e.get("sla_ms", "-"),
                "yes" if e.get("idempotent") else "no", ", ".join(e.get("errors", [])),
                ", ".join(e.get("requirement_ids", []))] for e in p.get("endpoints", [])]), ""]
    for e in p.get("endpoints", []):
        s += [f"### {e['method']} {e['path']}", "",
              f"- Request: `{e.get('request_schema','')}`",
              f"- Response: `{e.get('response_schema','')}`", ""]
    return "\n".join(s)


def render_nfr(p: dict[str, Any]) -> str:
    return "\n".join(["# Non-Functional Requirements", "",
        _tbl(["ID", "Category", "Requirement", "How it is measured", "Traces to"],
             [[n["id"], n["category"], n["requirement"], n.get("measurement", ""),
               ", ".join(n.get("requirement_ids", []))] for n in p.get("nfrs", [])]), ""])


def render_sprint_plan(p: dict[str, Any]) -> str:
    s = ["# Sprint Plan", "", f"_Velocity assumption: {p.get('velocity_assumption','-')} points/sprint_", ""]
    s += ["## Epics & Features", ""]
    for ep in p.get("epics", []):
        s += [f"### {ep['id']} — {ep['name']}", "", f"_{ep.get('goal','')}_", ""]
        for f in ep.get("features", []):
            s += [f"- **{f['id']} {f['name']}** → stories: {', '.join(f.get('story_ids', []))}"]
        s += [""]
    s += ["## Sprints", "", _tbl(["Sprint", "Goal", "Stories", "Points", "Risks"],
          [[sp["number"], sp["goal"], ", ".join(sp.get("story_ids", [])), sp.get("points", "-"),
            "; ".join(sp.get("risks", [])) or "—"] for sp in p.get("sprints", [])]), ""]
    if p.get("jira"):
        s += ["## Jira", "", _tbl(["Key", "Type", "Summary", "URL"],
              [[i["key"], i["type"], i["summary"], i.get("url", "")] for i in p["jira"]]), ""]
    if p.get("estimation_notes"):
        s += ["## Estimation Notes", "", p["estimation_notes"], ""]
    return "\n".join(s)


RENDERERS = {
    ArtifactType.BUSINESS_REQUIREMENTS: render_requirements,
    ArtifactType.CONCEPT_NOTE: render_concept_note,
    ArtifactType.WIREFRAME: render_wireframe,
    ArtifactType.BRD: render_document,
    ArtifactType.FRD: render_document,
    ArtifactType.SRS: render_document,
    ArtifactType.USER_STORIES: render_user_stories,
    ArtifactType.ACCEPTANCE_CRITERIA: render_acceptance_criteria,
    ArtifactType.API_REQUIREMENTS: render_api,
    ArtifactType.NFR: render_nfr,
    ArtifactType.SPRINT_PLAN: render_sprint_plan,
}


def render(atype: ArtifactType, payload: dict[str, Any]) -> str:
    return RENDERERS[atype](payload)
