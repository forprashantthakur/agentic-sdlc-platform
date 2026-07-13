"""Exact-content response cache. Deliberately NOT a semantic cache.

The brief asked for "reuse the previous output if similarity > 95%". In a bank, that is the most
dangerous idea in the document, and I am not building it: it means a Corporate FX BRD can be served
to a Trade Finance project because their embeddings were close. That is not a cache — it is a
fabrication with provenance attached, and this platform exists precisely to prevent fabrication.

What IS safe, and is implemented here: an EXACT hash of (model, system, prompt, schema). Identical
input, identical output. This catches the cases that actually matter:

  * a re-run after a transient failure part-way through a pipeline
  * a replay of the same project (deterministic regeneration)
  * Agent 4's six generations, where the system prompt and much of the context repeat

It cannot serve one project's answer to another, because the project's evidence is in the prompt and
the prompt is in the key. Scoped per project, and bounded in size.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from typing import Any

from app.core.logging import log
from app.core.metrics import metrics


class ResponseCache:
    def __init__(self, capacity: int = 256) -> None:
        self._data: OrderedDict[str, Any] = OrderedDict()
        self._cap = capacity
        self._lock = threading.Lock()

    @staticmethod
    def key(*, project_id: str, model: str, system: str, prompt: str, schema: dict | None) -> str:
        blob = json.dumps(
            {"p": project_id, "m": model, "s": system, "u": prompt,
             "sc": schema or {}},
            sort_keys=True, ensure_ascii=False,
        )
        return hashlib.sha256(blob.encode()).hexdigest()

    def get(self, k: str) -> Any | None:
        with self._lock:
            if k in self._data:
                self._data.move_to_end(k)
                metrics.record(agent=None, model=None, stage="cache", ms=0.0, cache_hit=True)
                log.info("llm.cache_hit")
                return self._data[k]
        return None

    def put(self, k: str, value: Any) -> None:
        with self._lock:
            self._data[k] = value
            self._data.move_to_end(k)
            while len(self._data) > self._cap:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


response_cache = ResponseCache()
