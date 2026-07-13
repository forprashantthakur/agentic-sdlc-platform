from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def merge(a: dict, b: dict) -> dict:
    return {**(a or {}), **(b or {})}


def last(a, b):
    """Last writer wins.

    Required the moment two nodes run concurrently: LangGraph refuses to merge two writes to the
    same key in one step unless you tell it how. Agent 3 and Agent 4 now finish in the same
    superstep and both report status — without this, the graph raises
    "Can receive only one value per step", which is LangGraph correctly refusing to guess.
    """
    return b if b is not None else a


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
    status: Annotated[str, last]
    error: Annotated[str, last]


MAX_REVISIONS = 3  # a gate that loops forever is a stuck programme, not a feature
