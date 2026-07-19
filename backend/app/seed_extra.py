"""Five further demo projects.

Same discipline as the original five: real-sounding evidence with a PLANTED CONFLICT (two sources
that disagree) and a PLANTED GAP (something everyone assumed and nobody stated). Those are what the
Requirement Gathering agent is supposed to catch — a corpus where every source agrees proves
nothing, and a demo that only shows happy paths is a brochure.
"""

from typing import Any

from app.models import SourceKind

# ── 1. Trade Finance Digitisation ─────────────────────────────────────────────
TF_NOTES = """Discovery Workshop — Trade Finance Digitisation
Date: 09 Jul 2026 | Room: Lower Parel 7F | Chair: Head of Trade & Supply Chain

1  Attendees: Head of Trade, Trade Ops Manager, Corporate Banking RM lead, Compliance (Sanctions),
   Trade Engineering Lead, two pilot corporate clients (dial-in).

6  Context: an import Letter of Credit takes 3.5 working days from client instruction to SWIFT
   MT700 issuance. 68% of that is re-keying and document chasing. Volumes are flat while two
   foreign banks have taken share with same-day issuance.

14 DECISION: corporate clients must raise LC and Bank Guarantee applications digitally, with the
   application pre-filled from the underlying purchase order where one exists.

21 Every application must be screened against sanctions lists before it reaches Trade Ops. Compliance
   was explicit: screening is on the applicant, the beneficiary, the vessel and every named port.
   A hit must block the application, not warn on it.

29 UCP 600 discrepancy checking stays with Trade Ops. The system may highlight likely discrepancies
   but must never auto-approve a document set.

36 Trade Ops asked for a maker-checker on every issuance above USD 500,000.

42 Target: LC issuance same-day for clean applications; 24 hours where documents need chasing.

48 OPEN: nobody could say what happens to a part-shipped LC amendment when the underlying PO has
   already been closed in the client's ERP.
"""

TF_EMAIL = """From: Head of Trade & Supply Chain <trade.head@hdfcbank.com>
To: Trade Engineering; Compliance; Corporate Banking
Subject: RE: Trade digitisation — issuance thresholds
Date: 14 Jul 2026

Two things after this morning's steering call.

First, the maker-checker threshold. The workshop minuted USD 500,000. Group Risk has since come
back and set it at USD 250,000 for all new digital channels. Please build to 250k — and make the
threshold configurable, because I expect it to move again.

Second, on sanctions screening: legal are clear that a screening hit must stop the application
dead. No override in the channel, no "proceed with caution" path. If Trade Ops want to release it,
they do that in the sanctions platform with its own audit trail, not in our portal.

We are also being asked to support Bank Guarantees in the same release, not the one after.

Regards,
Head of Trade & Supply Chain
"""

# ── 2. Digital Personal Loan Origination ──────────────────────────────────────
LOAN_NOTES = """Discovery Workshop — Digital Personal Loan Origination
Date: 02 Jul 2026 | Room: Chandivali 3F | Chair: Head of Retail Assets

1  Attendees: Head of Retail Assets, Credit Policy Head, Collections Head, Digital Lending PO,
   Risk Analytics, Compliance, Core Banking Integration Lead.

7  Context: a personal loan takes 4.2 days from application to disbursal. 41% of applicants drop
   out before completing documentation. Fintech lenders are approving in minutes.

15 DECISION: pre-approved customers must be able to complete a personal loan end to end in the
   app — application, KYC re-use, e-sign, and disbursal to their own account.

22 Credit Policy: the decision engine may auto-approve only where the customer is pre-qualified AND
   the bureau score is above the cut-off AND the requested amount is within the pre-approved limit.
   Anything else routes to a credit officer.

30 Disbursal is only ever to a verified account in the applicant's own name. No third-party payouts.

36 Compliance: the Key Fact Statement must be shown and acknowledged before e-sign, per RBI's
   digital lending directions. Cooling-off period applies and must be honoured in the system.

44 Collections asked to be brought in early: they want the repayment mandate set up during
   origination, not after first disbursal.

51 OPEN: what happens if the customer's bureau score changes between approval and disbursal was
   raised and not resolved.
"""

LOAN_EMAIL = """From: Credit Policy Head <credit.policy@hdfcbank.com>
To: Digital Lending PO; Head of Retail Assets
Subject: RE: Auto-approval limits — correction
Date: 08 Jul 2026

The workshop note says auto-approval is capped at the pre-approved limit. That was the position
before the June policy review. It has changed.

Auto-approval is now capped at INR 5 lakh regardless of the pre-approved limit. Above that, a
credit officer signs off even for pre-qualified customers. Please treat 5 lakh as the hard ceiling.

Also — and this is not negotiable — the cooling-off period is four days, not the two days someone
mentioned in the workshop. RBI's directions are explicit and we have been examined on it.

One more: we cannot disburse against a bureau pull older than 30 days. If the file has aged, it
re-pulls or it does not disburse.

Credit Policy Head
"""

# ── 3. Real-Time Payment Fraud Detection ──────────────────────────────────────
FRAUD_NOTES = """Discovery Workshop — Real-Time Payment Fraud Detection
Date: 11 Jul 2026 | Room: Kanjurmarg 2F (Restricted) | Chair: Chief Risk Officer

1  Attendees: CRO, Head of Fraud Risk, Payments Engineering, Data Science, Customer Service Head,
   Compliance, Information Security.

8  Context: fraud losses on UPI and IMPS reached INR 63 Cr last financial year. The current rules
   engine scores in batch; a mule transfer is typically flagged 40 minutes after settlement, by
   which time funds are gone through three hops.

17 DECISION: transaction scoring must be real time and inline — a decision before the payment is
   released, not after.

23 CRO set the latency budget: scoring must add no more than 150 milliseconds at p99. Payments
   Engineering pushed back that anything above 100ms risks breaching the NPCI response window.

31 Fraud Risk want three outcomes, not two: release, hold-for-step-up, and block. A held payment
   asks the customer for an additional factor and releases on success.

39 Customer Service raised the cost of false positives: every wrongly blocked payment is a call and
   often a complaint. Current rules engine false-positive rate is 1 in 14.

46 Data Science asked for a champion-challenger setup so a new model can run in shadow against live
   traffic before it decides anything.

53 OPEN: nobody agreed who can override a block, or how a customer disputes one.
"""

FRAUD_TRANSCRIPT = """Voice transcript — CRO review call
Date: 16 Jul 2026 | Participants: CRO, Head of Fraud Risk, Payments Engineering Lead

CRO: ...I want to revisit the latency number. I said 150 milliseconds in the workshop. Engineering
     has come back and said the NPCI window makes that unsafe.

Payments Engineering: At p99 we have roughly 100 milliseconds of headroom before we start timing
     out at the switch. A timeout is worse than a missed fraud — the payment fails for a good
     customer and we own the complaint.

CRO: Then it is 100 milliseconds and the model has to fit inside it. If the model cannot score in
     time, the transaction releases and we catch it in the near-real-time queue. We do not hold
     payments because our own infrastructure was slow.

Head of Fraud Risk: That is a fail-open. I want that written down as a conscious decision, because
     it will be asked about after the first incident.

CRO: Write it down. Fail-open on our latency, fail-closed on a confirmed sanctions hit. Those are
     different things and I do not want them conflated.
"""

# ── 4. Corporate Cash Management Portal ───────────────────────────────────────
CASH_NOTES = """Discovery Workshop — Corporate Cash Management Portal
Date: 07 Jul 2026 | Room: BKC 11F | Chair: Head of Transaction Banking

1  Attendees: Head of Transaction Banking, Corporate Onboarding Lead, Payments Ops, Channel
   Engineering, Information Security, two corporate treasurers (dial-in).

7  Context: corporates upload bulk payment files by SFTP with no visibility until settlement. Ops
   handle 900 status queries a month. Two large clients have asked for host-to-host with real-time
   acknowledgements or they will move their float.

16 DECISION: a corporate portal with bulk upload, real-time file validation, payment status
   tracking, and host-to-host (H2H) integration for clients who want it.

24 Authorisation: corporates configure their own approval matrix — single, dual or triple
   authorisation by amount band. The bank does not dictate it beyond a mandatory second approver
   above INR 1 crore.

33 Information Security: file transfers must be signed and encrypted. Portal access requires the
   corporate's own SSO where they have one, and hardware tokens where they do not.

41 Payments Ops asked for a rejection reason on every failed record, at record level not file level.
   Today a 5,000-record file fails as one object and the client re-sends the lot.

49 Reconciliation files must go back to the client in the same format they uploaded.

55 OPEN: nobody defined the cut-off behaviour — what happens to a file uploaded at 17:59 for a
   17:00 NEFT cut-off.
"""

CASH_EMAIL = """From: Head of Transaction Banking <txb.head@hdfcbank.com>
To: Channel Engineering; Payments Ops
Subject: RE: CMS portal — authorisation and cut-offs
Date: 13 Jul 2026

Following the treasurer feedback sessions.

The mandatory second approver: the workshop said above INR 1 crore. Two of our largest clients
already operate dual authorisation from the first rupee and were surprised we would allow single
authorisation at any level. Group Operational Risk agrees with them. Please make dual authorisation
the default for ALL payment files, with single authorisation as an exception the client has to
request in writing.

On cut-offs — a file arriving after cut-off must be held for the next window and the client told
immediately, on upload. It must never sit silently until the next morning. That is the single
biggest complaint we have.

Head of Transaction Banking
"""

# ── 5. RBI Regulatory Reporting Automation ────────────────────────────────────
REG_NOTES = """Discovery Workshop — RBI Regulatory Reporting Automation
Date: 04 Jul 2026 | Room: Kanjurmarg 5F | Chair: Head of Regulatory Reporting

1  Attendees: Head of Regulatory Reporting, Finance Controller, Data Governance Lead, Risk
   Reporting, Technology Lead, Internal Audit (observer).

8  Context: 47 regulatory returns are produced monthly. 31 involve manual Excel consolidation from
   four source systems. The last RBI inspection raised an observation on data lineage — we could
   not evidence how a number in a return was derived.

18 DECISION: returns must be generated from a governed data layer with end-to-end lineage from
   source system to submitted figure. Every number must be traceable to its origin.

26 Finance Controller: the general ledger is the single source of truth for anything with a
   financial value. Where a risk system disagrees with the GL, the GL wins and the difference is
   explained, not silently reconciled.

35 Automated Data Flow (ADF) submissions to RBI must be validated before submission — schema,
   completeness and the RBI validation rules — and a failed validation must block submission.

43 Internal Audit want the maker-checker preserved. Automation must not remove the human sign-off
   on a return; it should remove the manual assembly.

50 Timeline is driven by the audit commitment: lineage evidence must be demonstrable by Q3 FY27.

57 OPEN: nobody stated the retention period for a submitted return and its supporting lineage.
"""

REG_EMAIL = """From: Internal Audit <internal.audit@hdfcbank.com>
To: Head of Regulatory Reporting; Technology Lead
Subject: RE: Reporting automation — audit position
Date: 10 Jul 2026

To put our position in writing before build starts.

The workshop minutes say the GL wins where a risk system disagrees. We accept that for financial
values. For non-financial regulatory data — exposure counts, borrower classifications — the risk
system is the book of record, not the GL. Please do not implement a blanket "GL wins" rule.

Second, on sign-off: a maker-checker on the return is necessary but not sufficient. We also need
sign-off on any manual adjustment applied during preparation, with a reason recorded. Adjustments
without a reason are precisely what the last inspection criticised.

Third: retention. Submitted returns and their lineage must be retained for eight years, not the
"standard" period someone referenced. This is a specific requirement and it has been missed before.

Internal Audit
"""


EXTRA_CATALOG: dict[str, dict[str, Any]] = {
    "trade_finance": {
        "name": "Trade Finance Digitisation",
        "business_unit": "Wholesale Banking — Trade & Supply Chain",
        "description": "Digital issuance of Letters of Credit and Bank Guarantees, with inline sanctions screening and same-day issuance for clean applications.",
        "context": {
            "business_owner": "Head of Trade & Supply Chain",
            "project_sponsor": "MD, Wholesale Banking",
            "priority": "High",
            "business_objective": "Cut LC issuance from 3.5 working days to same-day for clean applications and defend share against foreign banks.",
            "problem_statement": "An import LC takes 3.5 working days from instruction to MT700, 68% of it re-keying and document chasing. Two foreign banks have taken share with same-day issuance.",
            "current_challenges": "Paper-based applications; manual re-keying into the trade platform; sanctions screening after the fact; no client visibility.",
            "desired_outcome": "A corporate raises an LC or BG digitally, pre-filled from the purchase order, screened before it reaches Trade Ops.",
            "expected_benefits": "Faster issuance, lower operational cost, defended trade-finance share and float.",
            "business_kpis": [
                "LC issuance same-day for clean applications (baseline 3.5 days)",
                "Re-keying effort ↓80%",
                "Sanctions screening before Trade Ops receipt: 100%",
                "Trade fee income share recovered by 5pp",
            ],
            "estimated_business_value": "INR 38 Cr — fee income defended + Trade Ops capacity",
            "timeline": "Q2–Q4 FY27",
            "budget": "INR 8.4 Cr",
            "regulatory_scope": ["UCP 600", "FEMA", "Sanctions screening", "RBI Master Direction"],
        },
        "sources": [
            (SourceKind.MEETING_NOTES, "Discovery Workshop — 09 Jul 2026", TF_NOTES),
            (SourceKind.EMAIL, "Email thread — issuance thresholds", TF_EMAIL),
        ],
        "planted_conflict": "Maker-checker threshold: the workshop set USD 500,000; the sponsor's email overrides it to USD 250,000 and demands it be configurable.",
        "planted_gap": "No one defines what happens to a part-shipped LC amendment when the underlying PO is already closed in the client's ERP.",
    },
    "loan_origination": {
        "name": "Digital Personal Loan Origination",
        "business_unit": "Retail Banking — Retail Assets",
        "description": "End-to-end digital personal loan for pre-approved customers: application, KYC re-use, e-sign and same-session disbursal.",
        "context": {
            "business_owner": "Head of Retail Assets",
            "project_sponsor": "Head of Retail Banking",
            "priority": "Critical",
            "business_objective": "Reduce time-to-disbursal from 4.2 days to under 10 minutes for pre-approved customers.",
            "problem_statement": "Personal loans take 4.2 days to disburse and 41% of applicants abandon during documentation. Fintech lenders approve in minutes and are taking the salaried segment.",
            "current_challenges": "Manual documentation; repeated KYC; credit decisioning offline; disbursal dependent on branch operations.",
            "desired_outcome": "A pre-approved customer completes a loan end to end in the app, in one session.",
            "expected_benefits": "Higher conversion, lower cost per loan, defended share in the salaried segment.",
            "business_kpis": [
                "Time-to-disbursal <10 minutes for pre-approved (baseline 4.2 days)",
                "Application abandonment <15% (baseline 41%)",
                "Cost per loan originated ↓55%",
                "Digital share of personal loan bookings >60%",
            ],
            "estimated_business_value": "INR 74 Cr — incremental disbursal volume + cost per loan",
            "timeline": "Q2–Q4 FY27",
            "budget": "INR 11.0 Cr",
            "regulatory_scope": ["RBI Digital Lending Directions", "KYC Master Direction", "DPDP Act"],
        },
        "sources": [
            (SourceKind.MEETING_NOTES, "Discovery Workshop — 02 Jul 2026", LOAN_NOTES),
            (SourceKind.EMAIL, "Email thread — auto-approval limits", LOAN_EMAIL),
        ],
        "planted_conflict": "Auto-approval ceiling: the workshop says 'within the pre-approved limit'; Credit Policy's email caps it at INR 5 lakh regardless, and corrects the cooling-off period from two days to four.",
        "planted_gap": "What happens if the bureau score changes between approval and disbursal was raised in the workshop and never resolved.",
    },
    "payment_fraud": {
        "name": "Real-Time Payment Fraud Detection",
        "business_unit": "Risk — Fraud Risk Management",
        "description": "Inline transaction scoring for UPI and IMPS with release, step-up and block outcomes, inside the NPCI response window.",
        "context": {
            "business_owner": "Head of Fraud Risk",
            "project_sponsor": "Chief Risk Officer",
            "priority": "Critical",
            "business_objective": "Cut fraud losses on real-time rails by half without breaching the NPCI response window or raising false positives.",
            "problem_statement": "Fraud losses reached INR 63 Cr last year. Scoring runs in batch, so a mule transfer is flagged ~40 minutes after settlement — by which time funds have moved through three hops.",
            "current_challenges": "Batch scoring; no inline decision; false-positive rate of 1 in 14 driving complaints; no shadow testing for new models.",
            "desired_outcome": "Every real-time payment is scored before release, with a step-up path rather than a blunt block.",
            "expected_benefits": "Lower fraud losses, fewer wrongly blocked payments, defensible model governance.",
            "business_kpis": [
                "Fraud loss on UPI/IMPS ↓50% (baseline INR 63 Cr)",
                "Scoring latency ≤100ms at p99",
                "False-positive rate better than 1 in 40 (baseline 1 in 14)",
                "100% of models shadow-tested before decisioning",
            ],
            "estimated_business_value": "INR 31 Cr — fraud loss avoided + complaint handling",
            "timeline": "Q1–Q3 FY27",
            "budget": "INR 9.8 Cr",
            "regulatory_scope": ["RBI Fraud Reporting", "NPCI circulars", "Model Risk Governance"],
        },
        "sources": [
            (SourceKind.MEETING_NOTES, "Discovery Workshop — 11 Jul 2026 (Restricted)", FRAUD_NOTES),
            (SourceKind.VOICE_TRANSCRIPT, "CRO review call — 16 Jul 2026", FRAUD_TRANSCRIPT),
        ],
        "planted_conflict": "Latency budget: the CRO set 150ms in the workshop; the review call overrides it to 100ms and adds a fail-open rule that the workshop never contemplated.",
        "planted_gap": "Nobody agreed who may override a block, or how a customer disputes one.",
    },
    "cash_management": {
        "name": "Corporate Cash Management Portal",
        "business_unit": "Wholesale Banking — Transaction Banking",
        "description": "Bulk payments, real-time file validation, record-level rejection reasons and host-to-host integration for corporate clients.",
        "context": {
            "business_owner": "Head of Transaction Banking",
            "project_sponsor": "MD, Wholesale Banking",
            "priority": "High",
            "business_objective": "Retain corporate float by replacing blind SFTP uploads with a visible, validated payments channel.",
            "problem_statement": "Corporates upload bulk files by SFTP with no visibility until settlement. Ops handle 900 status queries a month, and a 5,000-record file fails as a single object so clients re-send everything.",
            "current_challenges": "No file-level visibility; file-level rather than record-level rejection; no host-to-host; approval matrices managed by the bank, not the client.",
            "desired_outcome": "A corporate treasurer uploads, sees validation immediately, tracks every record, and authorises within their own matrix.",
            "expected_benefits": "Float retained, Ops queries reduced, large-client attrition avoided.",
            "business_kpis": [
                "Payment status queries ↓70% (baseline 900/month)",
                "Record-level rejection on 100% of failed records",
                "H2H onboarding under 4 weeks per client",
                "Zero large-client float attrition",
            ],
            "estimated_business_value": "INR 52 Cr — float retained + Ops capacity",
            "timeline": "Q3 FY27 – Q1 FY28",
            "budget": "INR 12.5 Cr",
            "regulatory_scope": ["RBI Payment Systems", "Information Security guidelines"],
        },
        "sources": [
            (SourceKind.MEETING_NOTES, "Discovery Workshop — 07 Jul 2026", CASH_NOTES),
            (SourceKind.EMAIL, "Email thread — authorisation and cut-offs", CASH_EMAIL),
        ],
        "planted_conflict": "Authorisation: the workshop allows single authorisation below INR 1 crore; the sponsor's email makes dual authorisation the default for every file, single by written exception only.",
        "planted_gap": "Cut-off behaviour is undefined — what happens to a file uploaded at 17:59 against a 17:00 NEFT cut-off.",
    },
    "reg_reporting": {
        "name": "RBI Regulatory Reporting Automation",
        "business_unit": "Finance — Regulatory Reporting",
        "description": "Governed data layer with end-to-end lineage for 47 regulatory returns, with validated ADF submission and preserved maker-checker.",
        "context": {
            "business_owner": "Head of Regulatory Reporting",
            "project_sponsor": "Chief Financial Officer",
            "priority": "Critical",
            "business_objective": "Close the RBI inspection observation on data lineage and remove manual assembly from 31 of 47 returns.",
            "problem_statement": "47 returns are produced monthly, 31 by manual Excel consolidation across four source systems. The last RBI inspection raised an observation that we could not evidence how a reported number was derived.",
            "current_challenges": "Manual consolidation; no lineage; reconciliation differences resolved informally; submission errors found after filing.",
            "desired_outcome": "Every reported number traceable to its source system, with validation before submission and human sign-off preserved.",
            "expected_benefits": "Inspection observation closed; preparation effort reduced; submission errors eliminated.",
            "business_kpis": [
                "Lineage evidence for 100% of reported figures",
                "Manual consolidation returns 31 → 0",
                "Pre-submission validation failures caught before filing: 100%",
                "Inspection observation closed by Q3 FY27",
            ],
            "estimated_business_value": "Regulatory remediation (non-discretionary) + ~14 analyst-FTE released",
            "timeline": "Q1–Q3 FY27 (audit-committed)",
            "budget": "INR 7.6 Cr",
            "regulatory_scope": ["RBI ADF", "RBI Master Directions", "Internal Audit commitments"],
        },
        "sources": [
            (SourceKind.MEETING_NOTES, "Discovery Workshop — 04 Jul 2026", REG_NOTES),
            (SourceKind.EMAIL, "Email thread — audit position", REG_EMAIL),
        ],
        "planted_conflict": "Source of truth: the Finance Controller says the GL wins wherever a risk system disagrees; Internal Audit says that holds only for financial values, and the risk system is the book of record for non-financial regulatory data.",
        "planted_gap": "Retention of submitted returns and their lineage was left unstated in the workshop — Audit puts it at eight years.",
    },
}
