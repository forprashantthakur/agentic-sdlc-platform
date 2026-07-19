"""Sample discovery-interview answers for the seeded demo projects.

Typing ten interview answers live, on a stage, in front of a CEO, is not a demo — it is a typing
test. These are pre-written so the interview can be filled in one click.

They are written to be CONSISTENT with each project's seeded documents: the same baselines, the same
regulator, the same thresholds. An interview answer that contradicts the discovery-workshop minutes
would show up downstream as a conflict Agent 1 flags — impressive if intentional, embarrassing if
not. Where a genuine conflict IS planted in the seed corpus, it is left intact: those are the
conflicts the demo exists to surface.
"""

from __future__ import annotations

SECTIONS = [
    "Users & Actors",
    "Pain Points",
    "Systems & Integrations",
    "Business Rules",
    "Approvals & Controls",
    "Compliance",
    "Non-functional",
    "Data",
    "Success Metrics",
    "Risks & Dependencies",
]

SAMPLES: dict[str, dict[str, str]] = {
    "upi autopay": {
        "Users & Actors": (
            "Retail customers on the mobile banking app are the primary users. Internally: the "
            "call-centre mandate desk (who handle 12,400 tickets a month today), the UPI operations "
            "team, and merchant onboarding. NPCI is the external scheme actor."
        ),
        "Pain Points": (
            "A customer cannot create or pause a mandate themselves — every change is a call. Mandate "
            "creation completion is 62%, and 38% of customers who start abandon. Active mandates per "
            "retail customer sit at 0.4 against a target of 1.1."
        ),
        "Systems & Integrations": (
            "UPI switch, core banking (mandate debit), the mobile app, the CRM used by the call "
            "centre, and NPCI's mandate registry. Notification goes out via the existing SMS/push "
            "gateway."
        ),
        "Business Rules": (
            "A mandate carries a maximum debit cap and a frequency (monthly/quarterly). Debits above "
            "the cap must be rejected outright, not partially executed. A paused mandate resumes only "
            "on explicit customer action — never automatically."
        ),
        "Approvals & Controls": (
            "No maker-checker for the customer's own mandate. Internally, any change to the cap "
            "ceiling or scheme parameters needs product plus risk sign-off."
        ),
        "Compliance": (
            "NPCI UPI AutoPay circular: Additional Factor of Authentication is mandatory on every "
            "mandate execution, and the customer must receive a pre-debit notification 24 hours "
            "before each debit. Neither is negotiable."
        ),
        "Non-functional": (
            "Mandate creation under 3 seconds end to end. 99.9% availability during the 8am-11pm "
            "window. Peak is the 1st of the month — roughly 9x the daily average as salary-cycle "
            "mandates fire."
        ),
        "Data": (
            "Mandate reference, merchant VPA, cap, frequency, validity, and the full debit history. "
            "All mandate and customer data must remain within India. Retention follows the standard "
            "10-year financial-records rule."
        ),
        "Success Metrics": (
            "Call-centre mandate tickets down 40% from 12,400/month. Creation completion up to 85% "
            "from 62%. Active mandates per customer 0.4 to 1.1. INR 28 Cr from cost-to-serve "
            "reduction plus recurring-payment fee income."
        ),
        "Risks & Dependencies": (
            "Dependent on NPCI's mandate-registry API availability. The main risk is that AFA on every "
            "execution adds friction and suppresses the completion-rate gain we are underwriting the "
            "business case on."
        ),
    },
    "corporate fx": {
        "Users & Actors": (
            "Corporate treasurers at mid and large corporates are the primary users. Internally: the "
            "FX dealing desk (whose 340 hours a month we are trying to release), Treasury operations, "
            "Market Risk, and the trade-finance compliance team."
        ),
        "Pain Points": (
            "Every deal is a phone call to a dealer. Rates are quoted verbally, entered by hand, and "
            "reconciled the next day. Dealers spend 340 hours a month on small tickets that should be "
            "self-service, and the audit trail is a recording plus a spreadsheet."
        ),
        "Systems & Integrations": (
            "The FX pricing engine, Treasury's deal-capture system, core banking for settlement, the "
            "limits engine held by Market Risk, and the regulatory-reporting feed to the RBI."
        ),
        "Business Rules": (
            "Every trade must carry an FEMA purpose code before it can settle. Any single deal above "
            "USD 10 million escalates to Market Risk before booking — no exceptions, and Treasury has "
            "been explicit that this is a red line. Quotes are valid for a countdown window and expire."
        ),
        "Approvals & Controls": (
            "Maker-checker on any deal above the escalation threshold. The corporate's own authorised "
            "signatory list governs who may book on their behalf, and that list is maintained by "
            "Relationship Management, not by the portal."
        ),
        "Compliance": (
            "FEMA: purpose-code tagging on every trade, with the underlying document reference. RBI "
            "reporting obligations on the aggregate position. Every deal must be retrievable per trade "
            "for 10 years."
        ),
        "Non-functional": (
            "A live quote must reach the treasurer in under 2 seconds or the rate is stale. 99.95% "
            "availability during market hours. The blotter must stay responsive at 10,000 deals."
        ),
        "Data": (
            "Currency pair, notional, tenor, rate, spread, purpose code, underlying document, dealer "
            "ID, and the full quote-to-book audit trail. Retained 10 years, retrievable per trade."
        ),
        "Success Metrics": (
            "INR 42 Cr annual fee uplift, and 340 dealer-hours a month released back to high-value "
            "structuring work. Self-service booking share is the leading indicator."
        ),
        "Risks & Dependencies": (
            "Dependent on the pricing engine's latency under load. The material risk is that Treasury's "
            "USD 10M escalation rule and the promise of instant self-service booking are in tension — "
            "a treasurer who hits the limit gets a worse experience than a phone call."
        ),
    },
    "v-kyc": {
        "Users & Actors": (
            "Prospective retail customers opening an account on mobile or web. Internally: the V-CIP "
            "agent pool, the onboarding ops team, the DPO, and the CISO — both of whom have "
            "non-negotiables on this journey."
        ),
        "Pain Points": (
            "58% of applicants drop off before completing. The V-CIP wait is 11 minutes against a "
            "3-minute target, end-to-end opening takes far longer than the 12-minute goal, and journey "
            "NPS is -12."
        ),
        "Systems & Integrations": (
            "Aadhaar/UIDAI e-KYC, PAN verification (NSDL), the CKYC registry, the video-KYC vendor "
            "platform, core banking for account creation, and the CRM."
        ),
        "Business Rules": (
            "V-CIP must be conducted by a trained agent, live, with the customer's face and the "
            "original documents visible. Blurred or cropped document images are rejected at V-CIP. An "
            "account is only activated after successful verification, never provisionally."
        ),
        "Approvals & Controls": (
            "Maker-checker on the V-CIP disposition: the agent verifies, a supervisor samples. Any "
            "override of a failed verification requires ops-head approval and is logged."
        ),
        "Compliance": (
            "RBI Master Direction on KYC: V-CIP is mandatory and the session must be recorded, "
            "geo-tagged and retained. Liveness must be presentation-attack-detection certified — a "
            "vendor claiming 'AI liveness' without PAD certification does not qualify. DPDP consent "
            "must be captured before any data is collected."
        ),
        "Non-functional": (
            "V-CIP wait under 3 minutes at peak. The video session must hold at 720p on a 3G "
            "connection. Volume is spiky — we cannot solve peak by simply adding agents."
        ),
        "Data": (
            "Aadhaar (masked), PAN, proof of address, the recorded V-CIP session, geo-tag and liveness "
            "score. Session recordings retained per RBI V-CIP norms. All data resident in India."
        ),
        "Success Metrics": (
            "Drop-off below 25% from a 58% baseline. V-CIP wait under 3 minutes from 11. End-to-end "
            "account opening under 12 minutes. Journey NPS from -12 to at least +20. INR 61 Cr in "
            "incremental CASA acquisition."
        ),
        "Risks & Dependencies": (
            "Hard stop: the incumbent vendor reaches end of support in December 2027. Dependent on "
            "UIDAI availability. The unresolved tension is that volume is spiky and we cannot just add "
            "agents — so the 3-minute wait target needs a capacity answer nobody has given yet."
        ),
    },
    "dispute": {
        "Users & Actors": (
            "Credit card customers raising disputes. Internally: the dispute analyst team, the fraud "
            "team, the chargeback desk that deals with the networks, and customer service — who "
            "currently absorb the status calls."
        ),
        "Pain Points": (
            "Provisional credit takes 19 working days against a 3-day obligation. Only 29% of disputes "
            "are raised digitally; the rest arrive by phone. TAT breaches are costing INR 41 lakh a "
            "quarter in compensation, and status-chasing calls swamp the contact centre."
        ),
        "Systems & Integrations": (
            "Card management system, the Visa/Mastercard chargeback rails, core banking for the credit "
            "posting, the fraud case-management system, and the CRM."
        ),
        "Business Rules": (
            "Provisional credit must be posted within 3 working days of a valid dispute. A disputed "
            "transaction flagged as actual fraud routes to the fraud team immediately and does not sit "
            "in the dispute queue. Nothing is auto-approved above the auto-decision threshold. Where "
            "the merchant represents, somebody must review the representment evidence."
        ),
        "Approvals & Controls": (
            "Maker-checker on any credit above the auto-decision limit. Write-offs need dispute-head "
            "approval. Every disposition is logged with the analyst ID."
        ),
        "Compliance": (
            "RBI's harmonised TAT rules: breach of the prescribed turnaround triggers mandatory "
            "compensation to the customer. The chargeback trail must satisfy network evidence rules."
        ),
        "Non-functional": (
            "Dispute raised in under 2 minutes on the app. Status must be accurate in real time — a "
            "stale status is what generates the call we are trying to remove. Peak is post-festive."
        ),
        "Data": (
            "Transaction reference, reason code, customer narrative, uploaded evidence, provisional "
            "credit posting, network chargeback reference, and the full analyst trail."
        ),
        "Success Metrics": (
            "Provisional-credit TAT to 3 working days or less from 19. Disputes raised digitally to 90% "
            "from 29%. TAT-breach compensation to zero from INR 41 lakh a quarter. Status calls down "
            "60%. INR 22 Cr from compensation avoided, analyst capacity and chargeback recovery."
        ),
        "Risks & Dependencies": (
            "Dependent on network chargeback API timelines, which we do not control. The risk is that a "
            "3-day provisional-credit promise plus a no-auto-approval rule creates an analyst "
            "bottleneck we have not sized."
        ),
    },
    "trade finance": {
        "Users & Actors": "Corporate importers and their trade operations teams are the primary users. Internally: Trade Ops (issuance and document checking), the Corporate RM, Compliance for sanctions screening, and the SWIFT operations desk.",
        "Pain Points": "An import LC takes 3.5 working days from instruction to MT700, and 68% of that is re-keying and chasing documents. Two foreign banks now issue same-day and have taken share.",
        "Systems & Integrations": "The trade finance platform, SWIFT for MT700/MT760, the sanctions screening system, client ERPs for purchase-order data, and core banking for limits and margin.",
        "Business Rules": "Every application is screened against sanctions on applicant, beneficiary, vessel and named ports. A hit blocks the application outright. Maker-checker applies above the issuance threshold. UCP 600 discrepancy checking stays with Trade Ops — the system may highlight, never auto-approve.",
        "Approvals & Controls": "Maker-checker on issuance above the threshold. Sanctions releases happen only in the sanctions platform with its own audit trail, never in the portal.",
        "Compliance": "UCP 600 for documentary credits, FEMA for the underlying trade, and sanctions screening obligations. Every issuance must be reconstructable for audit.",
        "Non-functional": "Same-day issuance for clean applications. The portal must hold 200 concurrent corporate users. Screening must complete inline, not overnight.",
        "Data": "Application, underlying purchase order, LC terms, beneficiary and vessel details, screening results, and the issued SWIFT message. Retained per trade-documentation rules.",
        "Success Metrics": "Same-day issuance for clean applications against a 3.5-day baseline, re-keying effort down 80%, 100% of applications screened before Trade Ops receipt, and 5pp of trade fee share recovered.",
        "Risks & Dependencies": "Dependent on the sanctions platform's response time and on clients sharing structured PO data. The open risk is amendment handling when the underlying PO has already closed in the client's ERP.",
    },
    "personal loan": {
        "Users & Actors": "Pre-approved salaried customers in the mobile app. Internally: Credit Policy, credit officers for referred cases, Collections (who want the mandate set up at origination), and Compliance.",
        "Pain Points": "Disbursal takes 4.2 days and 41% of applicants abandon during documentation. Fintech lenders approve in minutes and are winning the salaried segment.",
        "Systems & Integrations": "The loan origination system, bureau (CIBIL), core banking for disbursal, e-sign and e-NACH providers, the KYC store for re-use, and the collections platform.",
        "Business Rules": "Auto-approval only where the customer is pre-qualified, the bureau score clears the cut-off, and the amount is within the ceiling — anything else routes to a credit officer. Disbursal only to a verified account in the applicant's own name; no third-party payouts. No disbursal against a bureau pull older than 30 days.",
        "Approvals & Controls": "Credit officer sign-off above the auto-approval ceiling. Any policy override is logged with the officer's identity and reason.",
        "Compliance": "RBI Digital Lending Directions: the Key Fact Statement must be shown and acknowledged before e-sign, and the cooling-off period must be honoured in the system, not just in policy.",
        "Non-functional": "End-to-end under 10 minutes for a pre-approved customer. Decisioning under 3 seconds. Peak is month-end salary credit.",
        "Data": "Application, bureau pull, KYC re-use record, KFS acknowledgement, e-sign artefact, repayment mandate, and the disbursal instruction. Retained per lending records policy.",
        "Success Metrics": "Time-to-disbursal under 10 minutes against 4.2 days, abandonment below 15% against 41%, cost per loan down 55%, and digital share of bookings above 60%.",
        "Risks & Dependencies": "Dependent on bureau and e-sign provider availability. The unresolved risk is what happens when a bureau score changes between approval and disbursal.",
    },
    "fraud": {
        "Users & Actors": "Fraud analysts working alerts, and every retail customer making a real-time payment. Internally: Fraud Risk, Data Science, Payments Engineering, Customer Service (who absorb false-positive complaints), and the CRO.",
        "Pain Points": "Fraud losses hit INR 63 Cr last year. Scoring runs in batch, so a mule transfer is flagged around 40 minutes after settlement — funds have already moved through three hops. The false-positive rate is 1 in 14.",
        "Systems & Integrations": "The payments switch (UPI and IMPS), the scoring engine, the customer and device profile store, the case management system, and the NPCI interface.",
        "Business Rules": "Three outcomes, not two: release, hold-for-step-up, and block. A held payment asks for an additional factor and releases on success. If the model cannot score inside the latency budget the transaction releases — fail-open on our own latency, but fail-closed on a confirmed sanctions hit. Those must never be conflated.",
        "Approvals & Controls": "Model changes require model-risk review before they decide anything. Every new model runs champion-challenger in shadow against live traffic first.",
        "Compliance": "RBI fraud reporting timelines, NPCI circulars on the response window, and internal model-risk governance.",
        "Non-functional": "Scoring must add no more than 100 milliseconds at p99 — above that we risk timing out at the switch, and a timeout is worse than a missed fraud because a good customer's payment fails.",
        "Data": "Transaction attributes, device and behavioural signals, customer profile, model score and the reason codes behind it, and the analyst disposition.",
        "Success Metrics": "Fraud loss on UPI/IMPS halved from INR 63 Cr, p99 scoring latency within 100ms, false positives better than 1 in 40, and every model shadow-tested before decisioning.",
        "Risks & Dependencies": "Dependent on switch headroom and on model-risk sign-off, which is not fast. The open question is who may override a block and how a customer disputes one.",
    },
    "cash management": {
        "Users & Actors": "Corporate treasurers and their payment makers and approvers. Internally: Transaction Banking, Payments Ops (who field 900 status queries a month), Corporate Onboarding, and Information Security.",
        "Pain Points": "Corporates upload bulk files by SFTP with no visibility until settlement. A 5,000-record file fails as a single object, so the client re-sends everything. Two large clients have threatened to move their float.",
        "Systems & Integrations": "The payments hub, NEFT/RTGS/IMPS rails, host-to-host channels, the corporate's ERP, core banking for balances, and the reconciliation engine.",
        "Business Rules": "Corporates configure their own approval matrix by amount band. Dual authorisation is the default for every payment file, with single authorisation only as a written exception. A file arriving after cut-off is held for the next window and the client is told immediately on upload — never silently.",
        "Approvals & Controls": "Client-side maker-checker per their matrix; bank-side controls on file integrity and duplicate detection. Every authorisation is logged with the corporate user's identity.",
        "Compliance": "RBI payment system requirements, information security standards for file transfer (signed and encrypted), and audit trails per transaction.",
        "Non-functional": "File validation feedback within seconds of upload, not at settlement. The portal must handle a 50,000-record file. Peak is month-end payroll.",
        "Data": "Payment files, record-level validation results and rejection reasons, authorisation trail, settlement status, and reconciliation output in the client's own format.",
        "Success Metrics": "Status queries down 70% from 900 a month, record-level rejection on 100% of failed records, host-to-host onboarding inside 4 weeks, and zero large-client float attrition.",
        "Risks & Dependencies": "Dependent on client ERP formats and on rail availability at cut-off. The gap is the precise cut-off behaviour for a file arriving minutes late.",
    },
    "regulatory reporting": {
        "Users & Actors": "The regulatory reporting team preparing 47 monthly returns. Internally: the Finance Controller, Data Governance, Risk Reporting, Technology, and Internal Audit as observer and challenger.",
        "Pain Points": "31 of 47 returns are assembled manually in Excel across four source systems. The last RBI inspection raised an observation that we could not evidence how a reported number was derived.",
        "Systems & Integrations": "The general ledger, the risk data mart, core banking, the customer master, and the RBI ADF submission channel.",
        "Business Rules": "The general ledger is the book of record for financial values. For non-financial regulatory data — exposure counts, borrower classifications — the risk system is the book of record, so a blanket 'GL wins' rule must not be implemented. Every manual adjustment during preparation carries a recorded reason.",
        "Approvals & Controls": "Maker-checker on every return is preserved — automation removes the assembly, not the human sign-off. Separate sign-off on any manual adjustment, with a reason.",
        "Compliance": "RBI ADF submission rules and validation, RBI Master Directions, and the audit commitment to demonstrate lineage by Q3 FY27. Submitted returns and their lineage are retained for eight years.",
        "Non-functional": "The monthly cycle must complete inside the regulatory window. Lineage must be queryable for any figure in any submitted return.",
        "Data": "Source-system extracts, the governed data layer, transformation lineage, manual adjustments with reasons, the submitted return, and the validation result.",
        "Success Metrics": "Lineage evidence for 100% of reported figures, manual consolidation returns from 31 to zero, all pre-submission validation failures caught before filing, and the inspection observation closed by Q3 FY27.",
        "Risks & Dependencies": "Dependent on source-system data quality and on Data Governance defining ownership. The risk is treating the GL as authoritative for data it does not actually own.",
    },
    "aml": {
        "Users & Actors": (
            "AML analysts working the alert queue — roughly 38 FTE today. Internally: the CCO, the "
            "financial-crime compliance team, model risk, and Internal Audit, who raised the finding "
            "that started this."
        ),
        "Pain Points": (
            "The false-positive rate is 96.4%. Analysts spend their day closing alerts that were never "
            "suspicious. The backlog stands at 11,000 alerts, and audit finding AUD-2026-114 is open "
            "against it."
        ),
        "Systems & Integrations": (
            "The transaction-monitoring engine, core banking transaction feeds, the KYC/customer master, "
            "the sanctions-screening system, and the FIU-IND filing channel."
        ),
        "Business Rules": (
            "Threshold and scenario tuning may reduce false positives, but no change may reduce true "
            "positives — the CCO has stated that as a red line and will not sign anything that risks "
            "it. Every model change requires a documented back-test."
        ),
        "Approvals & Controls": (
            "Model risk review plus CCO approval on any threshold change. Maker-checker on STR filing. "
            "Every analyst disposition is auditable, with reasoning captured."
        ),
        "Compliance": (
            "PMLA obligations and FIU-IND reporting. Audit finding AUD-2026-114 must be closed by Q4 "
            "FY27 — this is regulatory remediation, not a discretionary programme. The filing trail is "
            "itself evidence."
        ),
        "Non-functional": (
            "Overnight batch must complete inside the window. Alert triage screens must load the full "
            "customer context in under 3 seconds, or analysts revert to spreadsheets."
        ),
        "Data": (
            "Transaction history, customer risk band, linked parties, prior alerts and dispositions, "
            "the model's triggering rationale, and the STR narrative. Retained per PMLA."
        ),
        "Success Metrics": (
            "False-positive rate below 85% from 96.4%. True positives missed: no increase — this is the "
            "metric that actually matters. Backlog from 11,000 to zero. AUD-2026-114 closed by Q4 FY27. "
            "Around 38 analyst FTE redeployed."
        ),
        "Risks & Dependencies": (
            "Dependent on model-risk sign-off, which is not fast. The central risk is the one the CCO "
            "named: any tuning aggressive enough to hit the false-positive target may quietly cost us a "
            "true positive, and we would not know until a regulator told us."
        ),
    },
}


def sample_for(project_name: str) -> list[dict[str, str]]:
    """The interview answers for a seeded project, in section order. Empty if not a demo project."""
    p = (project_name or "").lower()
    for key, answers in SAMPLES.items():
        if key in p:
            return [{"section": s, "answer": answers[s]} for s in SECTIONS if s in answers]
    return []
