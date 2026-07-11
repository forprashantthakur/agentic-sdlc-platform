"""Deterministic offline brain.

MOCK_MODE exists so a reviewer can `docker compose up` with an empty .env and watch
all six agents, both approval gates, RAG retrieval and artifact versioning run
end-to-end. Payloads are canned but schema-conformant and domain-realistic
(HDFC UPI-autopay flavoured); anything not canned falls back to a schema-driven
filler so the pipeline never breaks on a schema change.
"""

from __future__ import annotations

import hashlib
from typing import Any

_SEEDLESS = "unknown"


def _h(s: str, n: int) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest(), 16) % max(n, 1)


# ────────────────────────── canned, domain-realistic payloads ─────────────────
def _requirements() -> dict:
    return {
        "requirements": [
            {
                "id": "BR-001",
                "title": "Customer self-service UPI AutoPay mandate creation",
                "statement": "A retail customer must be able to create a UPI AutoPay mandate from the MobileBanking app without calling the branch or contacting the call centre.",
                "category": "FUNCTIONAL",
                "priority": "MUST",
                "actors": ["Retail Customer", "Core Banking System", "NPCI UPI Switch"],
                "source_evidence": ["Meeting notes 2026-06-18, line 12", "Email from Head of Payments, 2026-06-20"],
                "confidence": 0.92,
                "open_question": "",
            },
            {
                "id": "BR-002",
                "title": "Mandate cap of INR 1,00,000 without additional factor",
                "statement": "Mandates up to INR 1,00,000 execute without AFA; above that threshold the customer must authenticate per RBI e-mandate guidelines.",
                "category": "COMPLIANCE",
                "priority": "MUST",
                "actors": ["Retail Customer", "Risk Engine"],
                "source_evidence": ["Voice transcript 2026-06-21, 00:14:30"],
                "confidence": 0.88,
                "open_question": "",
            },
            {
                "id": "BR-003",
                "title": "Pause, modify and revoke an active mandate",
                "statement": "Customers can pause, modify the cap of, or revoke an active mandate; changes take effect before the next debit cycle.",
                "category": "FUNCTIONAL",
                "priority": "MUST",
                "actors": ["Retail Customer"],
                "source_evidence": ["Meeting notes 2026-06-18, line 31"],
                "confidence": 0.9,
                "open_question": "",
            },
            {
                "id": "BR-004",
                "title": "Pre-debit notification 24 hours before execution",
                "statement": "The system sends a pre-debit notification 24h before each mandate execution over push and SMS.",
                "category": "COMPLIANCE",
                "priority": "MUST",
                "actors": ["Notification Service", "Retail Customer"],
                "source_evidence": ["Email from Compliance, 2026-06-22"],
                "confidence": 0.95,
                "open_question": "",
            },
            {
                "id": "BR-005",
                "title": "Failed-debit retry and dunning",
                "statement": "On insufficient balance the mandate retries per merchant-configured policy, capped at 3 attempts in 72 hours.",
                "category": "FUNCTIONAL",
                "priority": "SHOULD",
                "actors": ["Merchant", "Payments Engine"],
                "source_evidence": ["Voice transcript 2026-06-21, 00:22:10"],
                "confidence": 0.71,
                "open_question": "Is the retry cap merchant-configurable or bank-fixed? Conflicting statements between the meeting notes and the transcript.",
            },
        ],
        "stakeholders": [
            {"name": "Head of Payments", "role": "Business Sponsor", "email": "payments.head@hdfcbank.com"},
            {"name": "Compliance Officer", "role": "Regulatory Approver", "email": "compliance@hdfcbank.com"},
            {"name": "Digital Channels Product Owner", "role": "Product Owner", "email": "po.digital@hdfcbank.com"},
        ],
        "conflicts": [
            {
                "description": "Retry cap: meeting notes say bank-fixed at 3; the sponsor's voice transcript says merchant-configurable.",
                "requirement_ids": ["BR-005"],
                "resolution_needed_from": "Head of Payments",
            }
        ],
        "gaps": [
            "No stated requirement for mandate behaviour when the underlying account is frozen or dormant.",
            "Data-retention period for revoked mandates is unspecified.",
        ],
        "summary": "Five business requirements extracted from 3 sources for the UPI AutoPay self-service capability. One conflict and two gaps require human resolution before the concept note is finalised.",
    }


def _concept_note() -> dict:
    return {
        "title": "Concept Note — UPI AutoPay Self-Service (MobileBanking)",
        "business_objectives": [
            "Reduce mandate-related call-centre volume by 40% within two quarters of launch.",
            "Increase active recurring-payment mandates per retail customer from 0.4 to 1.1.",
            "Achieve mandate creation completion rate ≥ 85% (from the current assisted-channel 62%).",
        ],
        "scope": [
            "UPI AutoPay mandate creation, pause, modify, revoke in MobileBanking (iOS + Android).",
            "Pre-debit notification over push and SMS.",
            "Mandate dashboard listing active, paused and revoked mandates.",
            "Integration with the NPCI UPI switch and the Core Banking mandate registry.",
        ],
        "out_of_scope": [
            "NetBanking web parity (planned for a follow-on release).",
            "Corporate / current-account mandates.",
            "e-NACH and card-on-file mandates.",
            "Merchant-side onboarding portal.",
        ],
        "business_rules": [
            {"id": "BRULE-01", "rule": "Mandates ≤ INR 1,00,000 execute without AFA; above that, AFA is mandatory."},
            {"id": "BRULE-02", "rule": "A pre-debit notification is sent 24h ± 15min before every execution."},
            {"id": "BRULE-03", "rule": "Maximum 3 debit retries within 72 hours of the first failure."},
            {"id": "BRULE-04", "rule": "Revocation is irreversible; a new mandate must be created to resume."},
            {"id": "BRULE-05", "rule": "Mandates on frozen or dormant accounts are auto-paused, not revoked."},
        ],
        "assumptions": [
            "NPCI UPI AutoPay APIs remain at spec v2.3 through the delivery window.",
            "The existing MobileBanking authentication (MPIN + device binding) is sufficient for AFA.",
            "Core Banking exposes the mandate registry via the existing ESB.",
        ],
        "dependencies": [
            {"name": "NPCI UPI Switch", "type": "EXTERNAL", "impact": "Mandate registration and execution cannot proceed without switch certification."},
            {"name": "Core Banking (Finacle) mandate registry", "type": "INTERNAL", "impact": "Source of truth for mandate state."},
            {"name": "Notification platform", "type": "INTERNAL", "impact": "Pre-debit notification SLA."},
            {"name": "Compliance sign-off (RBI e-mandate)", "type": "REGULATORY", "impact": "Hard gate before production release."},
        ],
        "risks": [
            {"id": "RISK-01", "risk": "NPCI certification slips beyond the release window.", "likelihood": "MEDIUM", "impact": "HIGH", "mitigation": "Book the certification slot at sprint 1; run a parallel sandbox track."},
            {"id": "RISK-02", "risk": "Pre-debit notification SLA breach triggers regulatory observation.", "likelihood": "LOW", "impact": "HIGH", "mitigation": "Dedicated notification queue with a 15-minute SLA alarm and a fallback SMS path."},
            {"id": "RISK-03", "risk": "Unresolved retry-cap conflict causes rework in the FRD.", "likelihood": "HIGH", "impact": "MEDIUM", "mitigation": "Escalated to the Head of Payments at the concept-note approval gate."},
        ],
        "success_metrics": [
            "Call-centre mandate tickets ↓ 40% (baseline: 12,400/month).",
            "Mandate creation completion rate ≥ 85%.",
            "p95 mandate creation latency ≤ 2.5s end-to-end.",
        ],
    }


def _wireframe() -> dict:
    return {
        "screens": [
            {
                "name": "Mandate Dashboard",
                "purpose": "Entry point listing all mandates by state.",
                "components": [
                    {"type": "AppBar", "label": "AutoPay", "props": {"trailing": "help-icon"}},
                    {"type": "SegmentedControl", "label": "Active | Paused | Revoked", "props": {"default": "Active"}},
                    {"type": "CardList", "label": "Mandate cards", "props": {"item": "merchant, cap, next debit date, status pill"}},
                    {"type": "PrimaryButton", "label": "Create new mandate", "props": {"position": "bottom-sticky"}},
                    {"type": "EmptyState", "label": "No mandates yet", "props": {"cta": "Create your first AutoPay"}},
                ],
                "requirement_ids": ["BR-003"],
            },
            {
                "name": "Create Mandate — Details",
                "purpose": "Capture merchant, cap amount, frequency and validity.",
                "components": [
                    {"type": "SearchField", "label": "Merchant / UPI ID", "props": {"validation": "VPA format"}},
                    {"type": "AmountField", "label": "Maximum amount per debit", "props": {"hint": "AFA required above ₹1,00,000"}},
                    {"type": "Dropdown", "label": "Frequency", "props": {"options": "Daily, Weekly, Monthly, Quarterly, As presented"}},
                    {"type": "DateRange", "label": "Valid from / Valid until", "props": {}},
                    {"type": "InlineAlert", "label": "AFA notice", "props": {"visible_when": "amount > 100000"}},
                    {"type": "PrimaryButton", "label": "Continue", "props": {}},
                ],
                "requirement_ids": ["BR-001", "BR-002"],
            },
            {
                "name": "Create Mandate — Review & Authorise",
                "purpose": "Confirm terms and authorise with MPIN.",
                "components": [
                    {"type": "SummaryList", "label": "Mandate terms", "props": {}},
                    {"type": "Checkbox", "label": "I authorise HDFC Bank to debit as per these terms", "props": {"required": True}},
                    {"type": "MPINPad", "label": "Enter MPIN", "props": {"attempts": 3}},
                    {"type": "PrimaryButton", "label": "Authorise mandate", "props": {}},
                ],
                "requirement_ids": ["BR-001", "BR-002"],
            },
            {
                "name": "Mandate Detail — Manage",
                "purpose": "Pause, modify cap, or revoke an existing mandate.",
                "components": [
                    {"type": "StatusPill", "label": "Active", "props": {}},
                    {"type": "DetailList", "label": "Merchant, cap, frequency, next debit, created on", "props": {}},
                    {"type": "TimelineList", "label": "Debit history", "props": {"limit": 10}},
                    {"type": "SecondaryButton", "label": "Pause mandate", "props": {}},
                    {"type": "SecondaryButton", "label": "Modify cap", "props": {}},
                    {"type": "DestructiveButton", "label": "Revoke mandate", "props": {"confirm": "irreversible"}},
                ],
                "requirement_ids": ["BR-003"],
            },
            {
                "name": "Pre-debit Notification",
                "purpose": "24h-ahead notification with a one-tap pause affordance.",
                "components": [
                    {"type": "PushCard", "label": "₹499 to Netflix will be debited tomorrow", "props": {}},
                    {"type": "QuickAction", "label": "Pause this mandate", "props": {}},
                ],
                "requirement_ids": ["BR-004"],
            },
        ],
        "design_system": "HDFC MobileBanking DS v4 — Navy #004C8F primary, Red #ED232A accent, 8pt grid, Inter typeface",
        "flow": "Dashboard → Create Mandate (Details) → Review & Authorise → Success → Dashboard; Dashboard → Mandate Detail → Pause/Modify/Revoke",
        "notes": "Wireframes are low-fidelity greybox at this stage; visual design applies the HDFC DS in a later cycle.",
    }


def _brd() -> dict:
    return {
        "document_type": "BRD",
        "title": "Business Requirements Document — UPI AutoPay Self-Service",
        "sections": [
            {"heading": "1. Executive Summary", "body": "HDFC Bank will enable retail customers to create and manage UPI AutoPay mandates directly in MobileBanking, removing the current dependency on assisted channels. The capability targets a 40% reduction in mandate-related call-centre volume and materially lifts recurring-payment penetration in the retail book."},
            {"heading": "2. Business Context & Problem Statement", "body": "Mandate creation today is an assisted journey with a 62% completion rate and an average handling time of 7.4 minutes at the call centre. Competing banks already offer in-app mandate management, and the bank is losing recurring-payment share to third-party UPI apps."},
            {"heading": "3. Business Objectives", "body": "O1: Reduce mandate call-centre volume 40% within two quarters.\nO2: Lift active mandates per retail customer from 0.4 to 1.1.\nO3: Reach ≥85% mandate-creation completion rate."},
            {"heading": "4. Scope", "body": "In scope: mandate create / pause / modify / revoke in MobileBanking (iOS, Android); mandate dashboard; pre-debit notifications; NPCI UPI switch and Finacle mandate-registry integration.\nOut of scope: NetBanking parity, corporate mandates, e-NACH, card-on-file mandates, merchant onboarding portal."},
            {"heading": "5. Stakeholders", "body": "Business Sponsor — Head of Payments. Regulatory Approver — Compliance. Product Owner — Digital Channels. Delivery — Payments Engineering. Operations — Digital Support."},
            {"heading": "6. Business Requirements", "body": "BR-001 Self-service mandate creation (MUST).\nBR-002 INR 1,00,000 AFA threshold (MUST, compliance).\nBR-003 Pause / modify / revoke (MUST).\nBR-004 24h pre-debit notification (MUST, compliance).\nBR-005 Failed-debit retry and dunning (SHOULD)."},
            {"heading": "7. Business Rules", "body": "BRULE-01..05 as ratified in the approved Concept Note, including the AFA threshold, notification window, retry cap, irreversibility of revocation, and auto-pause on frozen accounts."},
            {"heading": "8. Assumptions, Dependencies & Risks", "body": "Assumes NPCI UPI AutoPay API v2.3 stability. Depends on NPCI certification, the Finacle mandate registry via ESB, the notification platform, and RBI e-mandate compliance sign-off. Principal risk is NPCI certification slippage (MEDIUM/HIGH), mitigated by booking the certification slot in sprint 1."},
            {"heading": "9. Success Metrics", "body": "Call-centre mandate tickets ↓40%; completion rate ≥85%; p95 mandate-creation latency ≤2.5s."},
            {"heading": "10. Regulatory Considerations", "body": "RBI e-mandate framework for recurring transactions: AFA threshold, pre-debit notification, and customer-initiated revocation without merchant dependency. Audit trail retained for 8 years per bank record-retention policy."},
        ],
        "traceability": [
            {"requirement_id": "BR-001", "section": "6. Business Requirements"},
            {"requirement_id": "BR-002", "section": "6. Business Requirements"},
            {"requirement_id": "BR-003", "section": "6. Business Requirements"},
            {"requirement_id": "BR-004", "section": "6. Business Requirements"},
            {"requirement_id": "BR-005", "section": "6. Business Requirements"},
        ],
    }


def _frd() -> dict:
    return {
        "document_type": "FRD",
        "title": "Functional Requirements Document — UPI AutoPay Self-Service",
        "sections": [
            {"heading": "1. Purpose", "body": "Decomposes the approved BRD into implementable functional behaviour for the MobileBanking app, the AutoPay BFF, and the mandate service."},
            {"heading": "2. Actors & Roles", "body": "Retail Customer; MobileBanking App; AutoPay BFF; Mandate Service; Risk Engine; NPCI UPI Switch; Notification Service; Finacle Core."},
            {"heading": "3. FR-01 Mandate Creation", "body": "Given an authenticated customer, when they submit merchant VPA, cap amount, frequency and validity, the system SHALL validate the VPA against the NPCI directory, evaluate the AFA rule (cap > ₹1,00,000 ⇒ AFA), collect MPIN authorisation, register the mandate with the UPI switch, persist it in the registry with state ACTIVE, and return a mandate reference within 2.5s (p95)."},
            {"heading": "4. FR-02 Mandate State Machine", "body": "States: DRAFT → PENDING_AUTH → ACTIVE → (PAUSED ⇄ ACTIVE) → REVOKED | EXPIRED. Transitions to REVOKED are terminal. AUTO_PAUSED is entered on account freeze/dormancy and can only be cleared by the account returning to ACTIVE."},
            {"heading": "5. FR-03 Pause / Modify / Revoke", "body": "The system SHALL apply pause, cap-modification and revocation before the next debit cycle and SHALL propagate the change to the UPI switch within 60 seconds; failures are retried with exponential backoff and surfaced to the customer as PENDING_SYNC."},
            {"heading": "6. FR-04 Pre-debit Notification", "body": "24h ± 15 min before each scheduled execution the system SHALL emit a push notification and an SMS containing merchant, amount, execution date, and a deep link to pause."},
            {"heading": "7. FR-05 Debit Execution & Retry", "body": "On execution failure with reason INSUFFICIENT_FUNDS the system SHALL retry up to 3 times within 72 hours per the retry policy ratified at the concept-note gate; other failure reasons are terminal for that cycle."},
            {"heading": "8. FR-06 Mandate Dashboard", "body": "The dashboard SHALL list mandates grouped by state, sorted by next-debit date ascending, paginated at 20 per page."},
            {"heading": "9. Error Handling", "body": "Every NPCI error code is mapped to a customer-safe message; unmapped codes surface a generic failure and raise a P3 alert. No raw switch error is ever shown to a customer."},
            {"heading": "10. Audit & Logging", "body": "Every state transition writes an immutable audit record with actor, timestamp, before/after state, and correlation id."},
        ],
        "traceability": [
            {"requirement_id": "BR-001", "section": "3. FR-01 Mandate Creation"},
            {"requirement_id": "BR-002", "section": "3. FR-01 Mandate Creation"},
            {"requirement_id": "BR-003", "section": "5. FR-03 Pause / Modify / Revoke"},
            {"requirement_id": "BR-004", "section": "6. FR-04 Pre-debit Notification"},
            {"requirement_id": "BR-005", "section": "7. FR-05 Debit Execution & Retry"},
        ],
    }


def _srs() -> dict:
    return {
        "document_type": "SRS",
        "title": "Software Requirements Specification — UPI AutoPay Self-Service (IEEE 830 style)",
        "sections": [
            {"heading": "1. Introduction", "body": "1.1 Purpose — specifies the software requirements for the AutoPay capability.\n1.2 Scope — MobileBanking client, AutoPay BFF, Mandate Service, and their integrations.\n1.3 Definitions — VPA, AFA, mandate, pre-debit notification, NPCI switch."},
            {"heading": "2. Overall Description", "body": "2.1 Product perspective — a new bounded context within the Digital Channels estate, fronted by the existing BFF and integrating with Finacle over the ESB.\n2.2 User classes — retail customers, digital-support agents (read-only), compliance auditors (read-only).\n2.3 Constraints — RBI e-mandate rules; data residency in India; a 2.5s p95 latency budget; the existing MPIN authentication scheme."},
            {"heading": "3. System Architecture", "body": "MobileBanking (React Native) → AutoPay BFF (Kotlin/Spring) → Mandate Service (Java, PostgreSQL) → NPCI UPI Switch adapter. Async execution and retries run on Kafka topics `mandate.execution` and `mandate.retry`. Notifications are published to `notification.predebit`."},
            {"heading": "4. Data Model", "body": "mandate(id, customer_id, merchant_vpa, cap_amount, frequency, valid_from, valid_to, state, npci_ref, created_at, updated_at); mandate_event(id, mandate_id, type, payload, actor, created_at); debit_attempt(id, mandate_id, cycle_date, amount, status, failure_code, attempt_no)."},
            {"heading": "5. External Interfaces", "body": "NPCI UPI AutoPay API v2.3 (mandate create/update/revoke/execute); Finacle account-status API; Notification platform (Kafka); the bank's Risk Engine (gRPC)."},
            {"heading": "6. Non-Functional Requirements", "body": "See the NFR artifact — performance, availability, security, observability, compliance and accessibility requirements are specified there and are normative."},
            {"heading": "7. Verification", "body": "Each functional requirement maps to at least one acceptance criterion and one automated test; NPCI integration is verified in the sandbox before certification."},
        ],
        "traceability": [
            {"requirement_id": "BR-001", "section": "3. System Architecture"},
            {"requirement_id": "BR-002", "section": "2. Overall Description"},
            {"requirement_id": "BR-003", "section": "4. Data Model"},
            {"requirement_id": "BR-004", "section": "5. External Interfaces"},
            {"requirement_id": "BR-005", "section": "4. Data Model"},
        ],
    }


def _user_stories() -> dict:
    return {
        "stories": [
            {"id": "US-01", "as_a": "retail customer", "i_want": "to create a UPI AutoPay mandate in the app", "so_that": "my recurring bills are paid without me remembering them", "requirement_ids": ["BR-001"], "story_points": 8,
             "acceptance_criteria": [
                 "GIVEN an authenticated customer WHEN they submit a valid merchant VPA, cap and frequency THEN the mandate is registered with NPCI and shown as ACTIVE within 2.5s (p95)",
                 "GIVEN a cap above ₹1,00,000 WHEN the customer continues THEN AFA is enforced before authorisation",
                 "GIVEN an invalid VPA WHEN the customer submits THEN an inline validation error is shown and no mandate is created",
             ]},
            {"id": "US-02", "as_a": "retail customer", "i_want": "to see all my mandates in one place", "so_that": "I know what is being debited and when", "requirement_ids": ["BR-003"], "story_points": 5,
             "acceptance_criteria": [
                 "GIVEN a customer with mandates WHEN they open AutoPay THEN mandates are grouped by state and sorted by next-debit date ascending",
                 "GIVEN a customer with no mandates WHEN they open AutoPay THEN the empty state with a create CTA is shown",
             ]},
            {"id": "US-03", "as_a": "retail customer", "i_want": "to pause or revoke a mandate", "so_that": "I stay in control of my money", "requirement_ids": ["BR-003"], "story_points": 8,
             "acceptance_criteria": [
                 "GIVEN an ACTIVE mandate WHEN the customer pauses it THEN no debit occurs on the next cycle and the switch is updated within 60s",
                 "GIVEN a REVOKED mandate WHEN the customer views it THEN no reactivation affordance is offered",
             ]},
            {"id": "US-04", "as_a": "retail customer", "i_want": "a notification before each debit", "so_that": "I can fund my account or pause the mandate", "requirement_ids": ["BR-004"], "story_points": 5,
             "acceptance_criteria": [
                 "GIVEN a scheduled execution WHEN it is 24h ± 15min away THEN a push and an SMS are delivered with merchant, amount and date",
                 "GIVEN the push is tapped THEN the customer deep-links into the mandate detail screen",
             ]},
            {"id": "US-05", "as_a": "merchant", "i_want": "failed debits to be retried", "so_that": "collection rates stay high", "requirement_ids": ["BR-005"], "story_points": 13,
             "acceptance_criteria": [
                 "GIVEN an INSUFFICIENT_FUNDS failure WHEN the retry policy allows THEN up to 3 retries occur within 72h",
                 "GIVEN a non-retryable failure code THEN no retry is attempted and the cycle is marked FAILED",
             ]},
            {"id": "US-06", "as_a": "compliance auditor", "i_want": "an immutable audit trail of mandate events", "so_that": "the bank can evidence RBI compliance", "requirement_ids": ["BR-002", "BR-004"], "story_points": 5,
             "acceptance_criteria": [
                 "GIVEN any mandate state transition THEN an audit record with actor, timestamp, before/after state and correlation id is written and is immutable",
             ]},
        ]
    }


def _api_requirements() -> dict:
    return {
        "endpoints": [
            {"method": "POST", "path": "/v1/mandates", "purpose": "Create a mandate", "auth": "OAuth2 + device binding + MPIN step-up",
             "request_schema": "{merchantVpa, capAmount, currency, frequency, validFrom, validTo, idempotencyKey}",
             "response_schema": "{mandateId, npciRef, state, nextDebitDate}",
             "errors": ["400 INVALID_VPA", "409 DUPLICATE_MANDATE", "422 AFA_REQUIRED", "502 SWITCH_UNAVAILABLE"],
             "sla_ms": 2500, "idempotent": True, "requirement_ids": ["BR-001", "BR-002"]},
            {"method": "GET", "path": "/v1/mandates", "purpose": "List mandates for the authenticated customer", "auth": "OAuth2",
             "request_schema": "?state=ACTIVE|PAUSED|REVOKED&page=1&size=20",
             "response_schema": "{items:[Mandate], page, size, total}",
             "errors": ["401 UNAUTHORIZED"], "sla_ms": 800, "idempotent": True, "requirement_ids": ["BR-003"]},
            {"method": "PATCH", "path": "/v1/mandates/{id}", "purpose": "Pause, resume or modify the cap", "auth": "OAuth2 + MPIN step-up",
             "request_schema": "{action: PAUSE|RESUME|MODIFY_CAP, capAmount?, idempotencyKey}",
             "response_schema": "{mandateId, state, syncStatus}",
             "errors": ["404 NOT_FOUND", "409 ILLEGAL_TRANSITION", "422 AFA_REQUIRED"],
             "sla_ms": 1500, "idempotent": True, "requirement_ids": ["BR-003"]},
            {"method": "DELETE", "path": "/v1/mandates/{id}", "purpose": "Revoke a mandate (terminal)", "auth": "OAuth2 + MPIN step-up",
             "request_schema": "{reason, idempotencyKey}",
             "response_schema": "{mandateId, state: REVOKED, revokedAt}",
             "errors": ["404 NOT_FOUND", "409 ALREADY_REVOKED"], "sla_ms": 1500, "idempotent": True, "requirement_ids": ["BR-003"]},
            {"method": "GET", "path": "/v1/mandates/{id}/debits", "purpose": "Debit history for a mandate", "auth": "OAuth2",
             "request_schema": "?limit=10", "response_schema": "{items:[DebitAttempt]}",
             "errors": ["404 NOT_FOUND"], "sla_ms": 800, "idempotent": True, "requirement_ids": ["BR-005"]},
            {"method": "POST", "path": "/internal/v1/mandates/{id}/execute", "purpose": "Switch-initiated debit execution callback", "auth": "mTLS (NPCI switch)",
             "request_schema": "{npciRef, cycleDate, amount, signature}",
             "response_schema": "{status: ACCEPTED}",
             "errors": ["401 BAD_SIGNATURE", "409 DUPLICATE_EXECUTION"], "sla_ms": 500, "idempotent": True, "requirement_ids": ["BR-005"]},
        ],
        "conventions": "REST/JSON, camelCase, RFC 7807 problem+json errors, `Idempotency-Key` header mandatory on every mutating call, `X-Correlation-Id` propagated end-to-end, cursor pagination on collections, API versioning in the path.",
    }


def _nfr() -> dict:
    return {
        "nfrs": [
            {"id": "NFR-PERF-01", "category": "Performance", "requirement": "Mandate creation p95 ≤ 2.5s, p99 ≤ 4s, measured at the BFF edge.", "measurement": "APM p95/p99 over a 7-day rolling window.", "requirement_ids": ["BR-001"]},
            {"id": "NFR-PERF-02", "category": "Performance", "requirement": "Dashboard listing p95 ≤ 800ms for up to 50 mandates.", "measurement": "Synthetic monitor every 60s.", "requirement_ids": ["BR-003"]},
            {"id": "NFR-SCAL-01", "category": "Scalability", "requirement": "Sustain 1,200 mandate creations/minute at peak and 40,000 debit executions/hour on the 1st and 5th of each month.", "measurement": "Load test at 1.5× projected peak before go-live.", "requirement_ids": ["BR-001", "BR-005"]},
            {"id": "NFR-AVAIL-01", "category": "Availability", "requirement": "99.95% monthly availability for customer-facing mandate APIs; graceful degradation to read-only if the switch is down.", "measurement": "Uptime SLO with an error budget policy.", "requirement_ids": ["BR-001"]},
            {"id": "NFR-SEC-01", "category": "Security", "requirement": "All mutating calls require MPIN step-up and device binding; PII and VPA encrypted at rest (AES-256, HSM-backed keys) and in transit (TLS 1.3).", "measurement": "Annual VAPT + quarterly key-rotation audit.", "requirement_ids": ["BR-001", "BR-002"]},
            {"id": "NFR-SEC-02", "category": "Security", "requirement": "No customer PII in application logs; VPA masked to the first 3 and last 4 characters.", "measurement": "Automated log-scanner in CI and in production sampling.", "requirement_ids": ["BR-001"]},
            {"id": "NFR-COMP-01", "category": "Compliance", "requirement": "RBI e-mandate: AFA above ₹1,00,000 and pre-debit notification 24h ahead; audit trail retained 8 years, immutable (WORM).", "measurement": "Compliance attestation before release; quarterly internal audit.", "requirement_ids": ["BR-002", "BR-004"]},
            {"id": "NFR-DATA-01", "category": "Data Residency", "requirement": "All mandate and customer data stored and processed within India (RBI data-localisation).", "measurement": "Infrastructure attestation; region-pinned resources only.", "requirement_ids": ["BR-001"]},
            {"id": "NFR-OBS-01", "category": "Observability", "requirement": "Distributed tracing across app → BFF → mandate service → switch with a correlation id; alert on pre-debit notification SLA breach within 5 minutes.", "measurement": "Trace-completeness ≥ 99%; alert MTTA ≤ 5 min.", "requirement_ids": ["BR-004"]},
            {"id": "NFR-A11Y-01", "category": "Accessibility", "requirement": "WCAG 2.1 AA for all mandate screens; full screen-reader support and a minimum 4.5:1 contrast ratio.", "measurement": "Automated axe scan + manual assistive-tech pass per release.", "requirement_ids": ["BR-001", "BR-003"]},
            {"id": "NFR-RESIL-01", "category": "Resilience", "requirement": "Switch calls protected by a circuit breaker (50% error rate over 20 calls ⇒ open for 30s); all mutating switch calls idempotent and replay-safe.", "measurement": "Chaos test in pre-prod each quarter.", "requirement_ids": ["BR-005"]},
        ]
    }


def _sprint_plan() -> dict:
    return {
        "epics": [
            {"id": "EPIC-01", "name": "Mandate Lifecycle", "goal": "Create, view, pause, modify and revoke UPI AutoPay mandates in MobileBanking.",
             "features": [
                 {"id": "FEAT-01", "name": "Mandate Creation Journey", "story_ids": ["US-01"]},
                 {"id": "FEAT-02", "name": "Mandate Dashboard & Detail", "story_ids": ["US-02", "US-03"]},
             ]},
            {"id": "EPIC-02", "name": "Debit Execution & Notification", "goal": "Execute debits reliably and keep customers informed ahead of every debit.",
             "features": [
                 {"id": "FEAT-03", "name": "Pre-debit Notification", "story_ids": ["US-04"]},
                 {"id": "FEAT-04", "name": "Execution, Failure & Retry", "story_ids": ["US-05"]},
             ]},
            {"id": "EPIC-03", "name": "Compliance & Auditability", "goal": "Evidence RBI e-mandate compliance end-to-end.",
             "features": [
                 {"id": "FEAT-05", "name": "Immutable Audit Trail", "story_ids": ["US-06"]},
             ]},
        ],
        "sprints": [
            {"number": 1, "goal": "Mandate creation happy path against the NPCI sandbox.", "story_ids": ["US-01", "US-02"], "points": 13,
             "risks": ["NPCI sandbox access must be provisioned in week 1."]},
            {"number": 2, "goal": "Mandate management and pre-debit notification.", "story_ids": ["US-03", "US-04"], "points": 13, "risks": []},
            {"number": 3, "goal": "Execution, retry and the compliance audit trail.", "story_ids": ["US-05", "US-06"], "points": 18,
             "risks": ["Retry-cap decision must be ratified before sprint 3 planning."]},
        ],
        "velocity_assumption": 15,
        "estimation_notes": "Fibonacci story points; velocity of 15/sprint assumed from the Payments squad's trailing three-sprint average. US-05 carries integration risk with the NPCI switch and is deliberately sized at 13.",
    }


_CANNED: dict[str, Any] = {
    "requirement_gathering": _requirements,
    "concept_note": _concept_note,
    "wireframe": _wireframe,
    "brd": _brd,
    "frd": _frd,
    "srs": _srs,
    "user_stories": _user_stories,
    "api_requirements": _api_requirements,
    "nfr": _nfr,
    "sprint_plan": _sprint_plan,
}


# ────────────────────────────── entry points ──────────────────────────────────
FEEDBACK_RE = __import__("re").compile(
    r"REVIEWER FEEDBACK.*?---\n(.*?)--- END REVIEWER FEEDBACK", __import__("re").S
)


def _feedback(prompt: str) -> list[str]:
    m = FEEDBACK_RE.search(prompt)
    if not m:
        return []
    return [ln.lstrip("- ").strip() for ln in m.group(1).splitlines() if ln.strip().startswith("-")]


def _apply_feedback(task: str, payload: dict, fbs: list[str]) -> dict:
    """Make a revision actually differ from the round it replaces.

    In live mode Gemini does this for us. In mock mode we have to fold the reviewer's comments
    into the payload explicitly — otherwise the regenerated artifact is byte-identical, the
    content-addressed versioner (correctly) refuses to create a v2, and the revision loop looks
    broken when in fact it is working perfectly.
    """
    if not fbs:
        return payload
    if task == "concept_note":
        for i, f in enumerate(fbs, start=len(payload.get("business_rules", [])) + 1):
            payload.setdefault("business_rules", []).append({"id": f"BRULE-{i:02d}", "rule": f"[Revised per review] {f}"})
        payload.setdefault("assumptions", []).append(
            "Revision incorporates reviewer comments raised at the concept-note gate."
        )
    elif task in ("brd", "frd", "srs"):
        payload.setdefault("sections", []).append(
            {"heading": "Appendix — Review Revisions",
             "body": "\n".join(f"- {f}" for f in fbs)}
        )
    elif task == "requirement_gathering":
        payload.setdefault("gaps", []).extend(f"Reviewer-raised: {f}" for f in fbs)
    elif task == "sprint_plan":
        payload.setdefault("estimation_notes", "")
        payload["estimation_notes"] += " Re-planned per reviewer comments: " + "; ".join(fbs)
    return payload


def mock_json(*, task: str, prompt: str, schema: dict) -> dict:
    fn = _CANNED.get(task)
    if fn:
        return _apply_feedback(task, fn(), _feedback(prompt))
    return _from_schema(schema, task, prompt)


def mock_text(*, task: str, prompt: str) -> str:
    if task == "change_summary":
        return "Regenerated after reviewer comments: business rules tightened, retry-cap conflict annotated, traceability refreshed."
    if task == "approval_email":
        return "Please review the attached artifact and approve or request changes."
    return f"[mock:{task}] {prompt[:160]}"


def _from_schema(schema: dict, task: str, prompt: str) -> Any:
    """Generic schema-conformant filler — the safety net for un-canned tasks."""
    t = schema.get("type", "object")
    if t == "object":
        out = {}
        for key, sub in (schema.get("properties") or {}).items():
            out[key] = _from_schema(sub, task, prompt + key)
        return out
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
    return f"[mock:{task}] generated value"
