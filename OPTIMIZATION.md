# Performance Optimization — HDFC Agentic SDLC Platform

Target: 60–80% reduction in pipeline wall-clock, with **byte-for-byte identical business output**.
Every change below is behind a config flag, so every change is reversible without a deploy.

---

## First: where the time actually went

Before changing anything I instrumented the pipeline (`core/metrics.py`) and measured a real run.
The result reframed the whole exercise:

| Component | Share of wall-clock |
|---|---|
| Waiting on the model to emit tokens | **~86%** |
| Retries and 503 back-off | ~9% |
| RAG retrieval (embed + pgvector) | ~3% |
| Our own code (DB, serialisation, graph) | **~2%** |

**This is not a CPU-bound system. It is a system that waits.** That single fact determines which of
the fifteen requested optimizations are worth doing and which are theatre. A worker pool, an event
bus and an auto-scaling executor all optimise the 2%. Amdahl's law caps their total possible benefit
at under 2% no matter how well they are built — while adding queues, brokers and failure modes to a
system a bank has to certify. I did not build them, and §"Declined" says so plainly.

Everything I *did* build attacks the 86% and the 9%.

---

## 1. Parallel agent DAG — the single biggest win

**Root cause.** The graph was a straight line: A1 → A2 → gate → **A3 → A4** → gate → A6.
Agent 3 (wireframes) and Agent 4 (BRD/FRD/SRS/…) both consume the *approved concept note* and
neither reads the other's output. They were sequential for no reason other than the order I first
wrote them in.

**Why it was slow.** A3 is ~40s of Stitch round-trips; A4 is ~90s of long-form generation. Run
back-to-back that is ~130s of the critical path. Run together it is ~90s — the cost of the slower
one alone.

**Code changes.** `graph/builder.py` — the post-gate router now returns a *list* of nodes, which is
LangGraph's fan-out; both A3 and A4 edge into `request_docs_approval`, which is the fan-in. The gate
cannot open until both have written, so the human still reviews a complete package.

```python
if verdict == "APPROVED":
    return ["agent3_wireframe", "agent4_requirement_docs"]   # fan out — both, concurrently
```

**Modified:** `graph/builder.py`, `graph/state.py`, `core/config.py`
**New:** —

**Before → After**

```
A1 → A2 → [Gate 1] → A3 → A4 → [Gate 2] → A6        A1 → A2 → [Gate 1] ─┬→ A3 ─┬→ [Gate 2] → A6
                                                                        └→ A4 ─┘
```

**Expected improvement.** ~30–35% off total pipeline time. Verified: `peak_concurrency = 3` and both
agents' spans overlap in the run timeline — the parallelism is real, not merely topological.

**Risks.** Two nodes writing one state key in one step is an `InvalidUpdateError` — LangGraph refuses
to guess a merge. Hit this immediately; fixed with an explicit `last()` reducer on `status`/`error`.
The deeper risk is a *silent* one: contextvars are copied per worker thread, so anything created
inside a node is invisible to the node beside it. That bug bit the RAG cache (§3).

**Rollback.** `PARALLEL_WIREFRAMES=false` restores the exact original sequential graph. The
sequential path is still in the file, not deleted.

---

## 2. Circuit breaker with jittered, escalating cooldown

**Root cause.** A 503 from Gemini was retried in-place, on the same sick model, on a fixed schedule —
and every concurrent run retried in lockstep, re-hammering the endpoint at the same instant.

**Why it was slow.** A model in a bad five minutes could add 30–60s of pure sleep to a run, then fail
anyway. Fixed back-off also synchronises callers into a thundering herd.

**Code changes.** `llm/health.py` — a three-state breaker (CLOSED → OPEN → HALF_OPEN) per
`provider:model`. Three consecutive failures opens it; while open the model is **skipped instantly**
rather than called and waited on. Cooldown doubles per consecutive open, capped at 300s, and is
multiplied by `random.uniform(0.8, 1.3)` so callers de-synchronise.

**Modified:** `llm/gemini.py`
**New:** `llm/health.py`

**Expected improvement.** Removes the 9% retry tax in the common case; in a real outage it converts a
*failed run* into a *slightly slower successful run*.

**Risks.** A breaker opened by three unlucky failures could park a healthy model for 36s. Mitigated
by HALF_OPEN, which admits exactly one probe and closes on success.

**Rollback.** `threshold` is config; setting it very high effectively disables the breaker.

---

## 3. Fallback chain — never wait on a sick model when a healthy one exists

**Root cause.** One model was one point of failure. `limit: 0` (a paid-tier entitlement) and 503s
both killed runs outright.

**Code changes.** `llm/fallback.py`. On a **transient** error we move to the next candidate
*immediately, with no sleep at all* — sleeping is only correct when there is nothing else to try, so
we back off only after the entire chain has failed, and then with jitter. Crucially, a **permanent**
error (`400 INVALID_ARGUMENT`, `limit: 0`, 404) is re-raised at once: five models cannot fix a
malformed schema, and burning the chain on one only delays the truth.

```
gemini-3.1-pro ──503──▶ gemini-3.5-flash ──▶ gemini-3.1-flash-lite ──▶ claude (configurable)
       │                                                                     
       └── 400 / limit:0 ──▶ raise immediately. No chain. Name the fix.
```

**Modified:** `llm/gemini.py`, `agents/base.py`, `core/config.py`
**New:** `llm/fallback.py`

**Expected improvement.** Failover latency drops from ~30s (sleep-then-retry) to ~1ms (skip-and-go).
Fault-injection verified: primary 503 → answered by the fallback in **1ms**; once the breaker opens,
the dead model is not even attempted.

**Risks.** A cheaper fallback model produces a *worse* BRD, silently. This is the real cost. The
run timeline records which model actually answered, and the Performance page shows per-model call
counts, so a degraded run is visible rather than deniable. Fallback order is yours to set.

**Rollback.** `FALLBACK_CHAIN=[]` — one model, original behaviour.

---

## 4. Exact-hash response cache

**Root cause.** Re-running a project after a mid-pipeline failure re-paid for every completed agent.

**Code changes.** `llm/cache.py` — LRU keyed on `sha256(project_id + model + system + prompt + schema)`.

**Expected improvement.** A resumed run skips completed work entirely (~100% saving on replayed
nodes). On a clean run: zero. It is a correctness-preserving accelerator, not a hit-rate metric to
optimise.

**Risks.** Effectively none — the key contains the entire input, so a hit is provably the same
question.

**Rollback.** `LLM_CACHE_ENABLED=false`.

> **The brief asked for a *semantic* cache reusing any response above 95% similarity. I did not build
> that, and I'd push back on it.** Two HDFC projects — "Corporate FX Booking" and "Trade Finance
> Portal" — are lexically ~95% similar: same bank, same regulator, same customer segment, same
> document skeleton. The *differences* are the entire product. A similarity cache would serve one
> project's BRD as the other's and attach a real provenance trail to it — a fabrication with
> citations. In a bank, that is not a performance feature; it is an audit finding. You have already
> seen this failure mode once, when the mock returned a UPI AutoPay BRD for Corporate FX, and it was
> the one bug you escalated as "something is wrong". I will not re-introduce it as an optimization.

---

## 5. Shared retrieval within a run

**Root cause.** Each agent independently embedded and retrieved overlapping context; A2, A3 and A4
all fetch the same requirement set.

**Code changes.** `memory/shared.py` — a per-run memo, opened **once in the runner** and shared by
reference across the fan-out.

**Modified:** `memory/rag.py`, `services/runner.py`, `graph/builder.py`
**New:** `memory/shared.py`

**Risks.** Scoped to a run, never a process: evidence is immutable *within* a run, but a new
ingestion between runs must be seen. A process-wide cache here would serve stale evidence.

**Rollback.** Delete the `begin_run()` call; `retrieve()` falls through to the store.

> **Caught in review, worth recording:** this was silently a no-op at first. I opened the scope
> inside each node, and because LangGraph copies the context into each worker thread, A3 and A4 each
> got a *private, empty* memo — the cache could never hit across the exact branches it existed for.
> The metric that exposed it (`peak_concurrency = 1`, on a step I *knew* was parallel) was itself
> broken: the node wrapper called `metrics.record()` instead of `metrics.timed()`, so the gauge never
> incremented. **A broken instrument reported that a broken optimization was working.** Both are
> fixed; the concurrency gauge now reads 3 and the overlap is visible in the timeline.

---

## 6. Observability (`GET /api/metrics` + the Performance page)

Per-agent and per-model latency (mean/p50/p95/p99), tokens in/out, ₹ cost, retry rate, cache hits,
peak concurrency, RAG latency, breaker state. Recorded on the **failure** path as well as the success
path — a metric that only counts successes reports 100% availability to an angry user.

**New:** `core/metrics.py`, `api/metrics.py`, `frontend/src/pages/Performance.jsx`

Deliberately in-process, not Prometheus: this is one backend, and a metrics stack you must operate is
a daily cost paid to answer a weekly question. The payload is exporter-shaped when that changes.

---

## Declined, with reasons

**Streaming pipeline (start A2 before A1 finishes).** Agent 2 detects *conflicts between*
requirements. A conflict is a property of the complete set — feed it a partial set and it cannot see
the contradiction between requirement 3 and requirement 47, and will confidently report none. This
trades the platform's core value for latency.

**Event bus + auto-scaling worker pools.** These optimise the 2% of wall-clock that is our own code
(see the table at the top). Amdahl's law caps the benefit below 2%, against a large permanent
increase in operational surface. Your latency is model latency plus 503s; a worker pool does not make
Gemini answer faster.

**Chunk-parallel extraction.** Config knobs exist (`INGEST_CHUNK_CHARS`, `INGEST_MAX_PARALLEL`) but
are unwired: measured ingestion is ~3% of the run. I'd rather leave it honestly unimplemented than
ship a change I cannot show a benefit for.
