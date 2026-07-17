"""JSON Schemas passed to Gemini as `response_schema`.

Constraining the model at the decoding layer, not the prompt layer, is what makes this
safe to run unattended: an agent physically cannot emit a requirement without an id,
a priority and a source_evidence array.
"""

from __future__ import annotations

_STR = {"type": "string"}
_STRS = {"type": "array", "items": _STR}


def _req(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}


REQUIREMENTS = _req(
    {
        "requirements": {
            "type": "array",
            "items": _req(
                {
                    "id": _STR,
                    "title": _STR,
                    "statement": _STR,
                    "category": {"type": "string", "enum": ["FUNCTIONAL", "NON_FUNCTIONAL", "COMPLIANCE", "DATA", "INTEGRATION"]},
                    "priority": {"type": "string", "enum": ["MUST", "SHOULD", "COULD", "WONT"]},
                    "actors": _STRS,
                    "source_evidence": _STRS,
                    "confidence": {"type": "number"},
                    "open_question": _STR,
                },
                ["id", "title", "statement", "category", "priority", "source_evidence", "confidence"],
            ),
        },
        "stakeholders": {"type": "array", "items": _req({"name": _STR, "role": _STR, "email": _STR}, ["name", "role"])},
        "conflicts": {"type": "array", "items": _req(
            {"description": _STR, "requirement_ids": _STRS, "resolution_needed_from": _STR}, ["description"])},
        "gaps": _STRS,
        "summary": _STR,
    },
    ["requirements", "summary"],
)

CONCEPT_NOTE = _req(
    {
        "title": _STR,
        "business_objectives": _STRS,
        "scope": _STRS,
        "out_of_scope": _STRS,
        "business_rules": {"type": "array", "items": _req({"id": _STR, "rule": _STR}, ["id", "rule"])},
        "assumptions": _STRS,
        "dependencies": {"type": "array", "items": _req(
            {"name": _STR, "type": {"type": "string", "enum": ["INTERNAL", "EXTERNAL", "REGULATORY", "VENDOR"]}, "impact": _STR},
            ["name", "type", "impact"])},
        "risks": {"type": "array", "items": _req(
            {"id": _STR, "risk": _STR,
             "likelihood": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
             "impact": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
             "mitigation": _STR},
            ["id", "risk", "likelihood", "impact", "mitigation"])},
        "success_metrics": _STRS,
    },
    ["title", "business_objectives", "scope", "out_of_scope", "business_rules",
     "assumptions", "dependencies", "risks"],
)

WIREFRAME = _req(
    {
        "screens": {"type": "array", "items": _req(
            {"name": _STR, "purpose": _STR,
             # The prompt Stitch generates the screen from. The structured component list below is
             # still the contract — this is prose for the generator, not a substitute for the spec.
             "stitch_prompt": _STR,
             "components": {"type": "array", "items": _req(
                 {"type": _STR, "label": _STR, "props": {"type": "object"}}, ["type", "label"])},
             "requirement_ids": _STRS},
            ["name", "purpose", "components"])},
        "design_system": _STR,
        "flow": _STR,
        "notes": _STR,
    },
    ["screens", "flow"],
)

DOCUMENT = _req(
    {
        "document_type": {"type": "string", "enum": ["BRD", "FRD", "SRS"]},
        "title": _STR,
        "sections": {"type": "array", "items": _req({"heading": _STR, "body": _STR}, ["heading", "body"])},
        "traceability": {"type": "array", "items": _req({"requirement_id": _STR, "section": _STR}, ["requirement_id", "section"])},
    },
    ["document_type", "title", "sections", "traceability"],
)

USER_STORIES = _req(
    {
        "stories": {"type": "array", "items": _req(
            {"id": _STR, "as_a": _STR, "i_want": _STR, "so_that": _STR,
             "acceptance_criteria": _STRS, "requirement_ids": _STRS,
             "story_points": {"type": "integer"}},
            ["id", "as_a", "i_want", "so_that", "acceptance_criteria", "requirement_ids", "story_points"])}
    },
    ["stories"],
)

API_REQUIREMENTS = _req(
    {
        "endpoints": {"type": "array", "items": _req(
            {"method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
             "path": _STR, "purpose": _STR, "auth": _STR,
             "request_schema": _STR, "response_schema": _STR, "errors": _STRS,
             "sla_ms": {"type": "integer"}, "idempotent": {"type": "boolean"},
             "requirement_ids": _STRS},
            ["method", "path", "purpose", "auth", "errors", "requirement_ids"])},
        "conventions": _STR,
    },
    ["endpoints", "conventions"],
)

NFR = _req(
    {
        "nfrs": {"type": "array", "items": _req(
            {"id": _STR, "category": _STR, "requirement": _STR, "measurement": _STR, "requirement_ids": _STRS},
            ["id", "category", "requirement", "measurement"])}
    },
    ["nfrs"],
)

SPRINT_PLAN = _req(
    {
        "epics": {"type": "array", "items": _req(
            {"id": _STR, "name": _STR, "goal": _STR,
             "features": {"type": "array", "items": _req({"id": _STR, "name": _STR, "story_ids": _STRS}, ["id", "name", "story_ids"])}},
            ["id", "name", "goal", "features"])},
        "sprints": {"type": "array", "items": _req(
            {"number": {"type": "integer"}, "goal": _STR, "story_ids": _STRS,
             "points": {"type": "integer"}, "risks": _STRS},
            ["number", "goal", "story_ids", "points"])},
        "velocity_assumption": {"type": "integer"},
        "estimation_notes": _STR,
    },
    ["epics", "sprints"],
)


# ══════════════════════════ Process Flow 2 schemas ═════════════════════════════
_OBJ = {"type": "object"}
_OBJS = {"type": "array", "items": _OBJ}

REFINED_BACKLOG = _req(
    {"project": _STR, "refined_stories": _OBJS, "open_questions": _OBJS,
     "total_points": {"type": "integer"}, "notes": _STR},
    ["refined_stories"])

GROOMING_PACK = _req(
    {"project": _STR, "sprints": _OBJS, "capacity_per_sprint": {"type": "integer"},
     "dependencies": _OBJS, "grooming_notes": _STR},
    ["sprints"])

CODE_REVIEW = _req(
    {"project": _STR, "reviews": _OBJS, "summary": _STR},
    ["reviews"])

TEST_CASES = _req(
    {"project": _STR, "qe_round": {"type": "integer"}, "test_cases": _OBJS, "bugs": _OBJS,
     "bugs_identified": {"type": "boolean"}, "coverage": _STR, "summary": _STR},
    ["test_cases", "bugs_identified"])

RELEASE_HANDOFF = _req(
    {"project": _STR, "completed_stories": _OBJS, "evidence": _OBJ,
     "release_notes": _STR, "devops_handoff": _OBJ},
    ["completed_stories", "release_notes"])
