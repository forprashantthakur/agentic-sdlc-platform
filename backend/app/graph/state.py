from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def merge(a: dict, b: dict) -> dict:
    return {**(a or {}), **(b or {})}


class SDLCState(TypedDict, total=False):
    # identity
    project_id: str
    project_name: str
    run_id: str
    approvers: list[str]
    velocity: int
    base_url: str

    # accumulated agent output — merged, never overwritten wholesale
    payloads: Annotated[dict[str, Any], merge]     # ArtifactType.value -> payload dict
    artifacts: Annotated[dict[str, str], merge]    # ArtifactType.value -> ArtifactVersion.id
    external: Annotated[dict[str, Any], merge]     # figma/jira/drive refs

    # human-in-the-loop
    gate_decisions: Annotated[dict[str, str], merge]        # gate -> APPROVED|CHANGES_REQUESTED|REJECTED
    feedback: Annotated[dict[str, list[str]], merge]        # gate -> reviewer comments
    revision: Annotated[dict[str, int], merge]              # gate -> how many times we've looped

    # observability
    trace: Annotated[list[dict[str, Any]], operator.add]
    status: str
    error: str


MAX_REVISIONS = 3  # a gate that loops forever is a stuck programme, not a feature
