"""Demo catalogue: five banking IT projects, each with a messy, human, contradictory evidence base.

The point of this data is not that it is plausible — it is that it is *flawed* in the specific ways
real discovery material is flawed. Every project carries:

  * a genuine CONFLICT: two sources that disagree on a material decision, which Agent 1 must
    escalate rather than silently resolve;
  * a real GAP: something a bank obviously needs that nobody in the evidence thought to say, which
    Agent 1 must flag rather than invent;
  * at least one soft claim the model should mark as low-confidence.

A seed corpus where every source agrees would make the agents look brilliant and prove nothing.
"""

from __future__ import annotations

from typing import Any

from app.models import SourceKind

# ══════════════════════════════════════════════════════════════════════════════
# 1 · UPI AutoPay Self-Service — Retail Banking / Digital Channels
# ══════════════════════════════════════════════════════════════════════════════
UPI_NOTES = """Discovery Workshop — UPI AutoPay Self-Service
Date: 18 June 2026 | Room: Kanjurmarg 4F-B | Chair: Head of Payments

1  Attendees: Head of Payments, Digital Channels PO, Payments Engineering Lead, Compliance
   Officer, Digital Support Manager, NPCI relationship manager (dial-in).

5  Context: mandate creation is currently an assisted journey. The call centre handles ~12,400
   mandate tickets/month, AHT 7.4 min. Completion rate on the assisted flow is 62%. Customers are
   moving recurring payments to third-party UPI apps.

12 DECISION: retail customers must be able to create a UPI AutoPay mandate directly in
   MobileBanking, with no branch visit and no call to the contact centre.

18 Compliance flagged the RBI e-mandate framework. Mandates up to Rs 1,00,000 can execute without
   additional factor authentication. Above that, AFA is mandatory on every execution.

23 Pre-debit notification is a hard regulatory requirement — the customer must be told 24 hours
   before the debit. Compliance was emphatic that an SLA breach here is a reportable observation.

31 Customers must be able to pause a mandate, change the cap, or revoke it entirely. Revocation
   must not require the merchant's cooperation. Changes must land before the next debit cycle.

38 Retry on failed debit: Payments Engineering proposed a fixed policy — 3 retries within 72 hours
   on insufficient funds. Agreed in the room.

44 Out of scope for release 1: NetBanking, corporate/current-account mandates, e-NACH, card-on-file.
   The merchant onboarding portal is a separate programme.

49 Success measure proposed: cut call-centre mandate volume by 40% within two quarters.

52 ACTION: Digital Channels PO to circulate the concept note for sign-off by Head of Payments and
   Compliance before any build starts.
"""

UPI_EMAIL = """From: Head of Payments <payments.head@hdfcbank.com>
To: Digital Channels PO <po.digital@hdfcbank.com>; Payments Engineering Lead
Cc: Compliance <compliance@hdfcbank.com>
Date: 20 June 2026, 21:14 IST
Subject: RE: UPI AutoPay — release 1 scope

Following the workshop, three things I want locked before we spend a rupee on build:

1. The mandate dashboard is table stakes. A customer should open AutoPay and instantly see every
   mandate, what it will cost them, and when. If they cannot see it, they will not trust it.

2. Target is 1.1 active mandates per retail customer, up from 0.4. That is the number the board
   will be shown, so the product needs to be good enough to actually move it.

3. Latency: if mandate creation takes more than about 2.5 seconds we will bleed customers at the
   last step. Treat that as a requirement, not an aspiration.

On retries — I am not convinced a bank-fixed 3-retry policy is right. Large merchants will want
their own retry cadence and we will lose them to competitors if we cannot offer it. Please look at
making the retry policy merchant-configurable within a bank-set ceiling.

---
From: Compliance <compliance@hdfcbank.com>
Date: 22 June 2026, 10:02 IST
Subject: RE: RE: UPI AutoPay — release 1 scope

Adding for the record:
- Pre-debit notification: 24h ahead, over BOTH push and SMS. Push alone is not sufficient evidence
  of notification for our purposes.
- A full immutable audit trail of every mandate state transition, retained 8 years per bank policy.
- All mandate and customer data must remain within India. No exceptions, no offshore processing.
- Anything above the Rs 1,00,000 threshold requires AFA. Please do not design a UX that tries to
  work around this.
"""

UPI_TRANSCRIPT = """Voice transcript — Sponsor review call
Date: 21 June 2026 | HoP = Head of Payments, PO = Digital Channels PO, ENG = Payments Eng Lead
Duration: 00:31:12

00:03:15 HoP: ...the thing that kills us today is that a customer wants to set up an autopay for
         their Netflix or their SIP and they end up on the phone for seven minutes. That is the
         whole problem. Everything else is detail.

00:08:40 PO: For release one I want the create journey, the dashboard, and manage — pause, modify
         the cap, revoke. That is the minimum that is actually useful.

00:14:30 HoP: And on the limit — anything at or below one lakh goes through without the extra
         authentication step. Above one lakh, the customer authenticates. That is RBI, we do not
         have a choice, and frankly I do not want us to have a choice.

00:19:05 ENG: The switch integration is the long pole. NPCI certification is a hard dependency and
         the slot booking takes weeks. If we do not book it in sprint one we will slip.

00:22:10 HoP: On retries — look, I said three in the room but I have thought about it. It should be
         the merchant's policy within a ceiling we set. A subscription business and a lender have
         completely different collection behaviour. Take that away as an action.

00:25:47 PO: What happens if the account is frozen or dormant and there is an active mandate?

00:26:02 HoP: Good question. I do not think we discussed it. Do not just revoke it — the customer
         did not ask for that. Park it. Someone needs to write that down properly.

00:29:30 ENG: We also have not decided how long we keep a revoked mandate's data. Compliance will
         ask.
"""

# ══════════════════════════════════════════════════════════════════════════════
# 2 · Corporate FX Booking Portal — Wholesale Banking / Treasury
# ══════════════════════════════════════════════════════════════════════════════
FX_NOTES = """Discovery Workshop — Corporate FX Self-Service Booking Portal
Date: 03 July 2026 | Chair: MD, Wholesale Banking | Location: BKC 12F

3  Attendees: MD Wholesale, Head of Treasury, FX Dealing Desk Head, Corporate Channels PO,
   Treasury Technology Lead, Compliance (FEMA), Market Risk.

7  Problem: every corporate FX quote goes through the dealing desk by phone. 340 dealer-hours a
   month are spent on tickets under USD 50,000 — trades that carry almost no margin. Corporates
   with treasury teams of their own are routing that flow to foreign banks with portals.

15 DECISION: build a self-service FX booking portal for corporate clients. Live rate streaming,
   quote, book, confirm, and download the deal ticket.

21 Head of Treasury: rates must be streamed with a hard quote-validity window. If a corporate books
   against a stale rate we carry the loss. He suggested a 15-second quote validity.

26 Market Risk: any single deal above USD 1,000,000 must route to a dealer for manual approval.
   Below that, straight-through processing.

33 FEMA compliance: every trade must be tagged to an underlying exposure and a purpose code.
   Without a valid purpose code the trade cannot be booked. This is not negotiable.

40 Corporate Channels PO: corporates want forward contracts too, not just spot. Head of Treasury
   pushed back — forwards mean margining and credit-line checks, which is a much bigger build.

46 UNRESOLVED: spot only in release 1, or spot + forwards? MD asked for a costed option on both.

52 Out of scope: options, swaps, retail FX, remittances.

58 Target: FX booking turnaround under 90 seconds. Digital share of FX volume above 45% within
   three quarters.
"""

FX_EMAIL = """From: Head of Treasury <treasury.head@hdfcbank.com>
To: Corporate Channels PO <po.corporate@hdfcbank.com>
Cc: MD Wholesale; Market Risk; Compliance-FEMA
Date: 07 July 2026, 08:41 IST
Subject: FX Portal — my red lines

Three things, and I will not move on them:

1. The quote validity window. 15 seconds was my suggestion in the room, but having looked at our
   INR/USD volatility in the last two quarters, I want it at 10 seconds for majors and 5 seconds
   for exotics. A stale-rate booking is a direct P&L hit and it lands on my desk.

2. Credit-line check BEFORE the quote is shown, not after the corporate clicks book. If we show a
   price we cannot honour because the client has no line left, that is a relationship problem.

3. Forwards are in scope. I know I pushed back in the workshop — I have since spoken to four of our
   top-20 corporates and every single one of them said a spot-only portal is not worth logging into.
   We do forwards or we do not bother.

On the dealer-approval threshold: Market Risk said USD 1mn. I think that is too low and it will put
the dealing desk right back in the loop for exactly the flow we are trying to automate. I would
argue for USD 2mn for investment-grade clients, tiered by internal rating.

---
From: Compliance-FEMA <compliance.fema@hdfcbank.com>
Date: 08 July 2026, 15:20 IST
Subject: RE: FX Portal — my red lines

Noted, but the purpose code and underlying-exposure declaration are mandatory regardless of ticket
size or client rating. Please do not build a "fast path" that skips them. Also: FEMA documentation
must be retrievable per trade for 10 years, and the audit trail must show which human approved any
deal that bypassed STP.
"""

FX_TRANSCRIPT = """Voice transcript — FX Portal sponsor call
Date: 09 July 2026 | MD = MD Wholesale, TH = Head of Treasury, DD = Dealing Desk Head
Duration: 00:24:38

00:02:10 MD: ...the number that bothers me is 340 dealer-hours on trades under fifty thousand
         dollars. That is our most expensive people doing our least valuable work.

00:06:55 DD: I will be honest, the desk is not against this. We would rather be pricing the large
         structured flow than quoting a hundred-thousand-dollar spot for the fifteenth time today.

00:11:20 TH: My worry is the rate. If the portal shows a price and the market moves before they hit
         book, who eats it? We need a very tight validity window and an explicit re-quote.

00:13:45 MD: And what about the approval threshold? Risk said a million.

00:14:02 DD: A million dollars is nothing for our top corporates. You will have the desk approving
         forty trades a day. Make it two million, tier it by rating, and let the good clients run.

00:14:30 TH: I agree with him. Risk will push back but the number should be rating-based.

00:18:15 MD: What about mid-market clients who do not have an internal rating?

00:18:40 DD: ...that is a fair point. I do not have a good answer for that today.

00:21:30 TH: One more thing nobody has asked. What happens when the rate feed goes down? Do we show
         a stale price, do we block booking, do we fall back to the desk? We have not decided that
         and it will happen at some point.
"""

# ══════════════════════════════════════════════════════════════════════════════
# 3 · Digital Account Opening & Video KYC Re-platform — Retail Liabilities
# ══════════════════════════════════════════════════════════════════════════════
VKYC_NOTES = """Discovery Workshop — Digital Savings Account Opening & V-CIP Re-platform
Date: 12 June 2026 | Chair: Head of Retail Liabilities

4  Problem: the current digital account-opening journey drops 58% of applicants. The worst single
   step is video KYC — customers wait an average of 11 minutes for an agent, and 34% abandon in the
   queue. NPS on the journey is -12.

11 The V-CIP platform is a 2019 vendor product. The vendor has announced end-of-support for
   December 2027. This is a forced migration, not a discretionary one.

17 DECISION: re-platform V-CIP and rebuild the account-opening journey end to end.

22 RBI Master Direction on KYC: V-CIP must be an unbroken live video interaction, agent-led, with
   liveness detection, geo-tagging inside India, and the customer's PAN verified against the
   Income Tax database in real time. Recording retained for 10 years.

29 Ops Head: the queue is the whole problem. Wants scheduled V-CIP appointments so customers pick a
   slot instead of waiting. Also wants agent capacity forecasting.

35 Head of Retail Liabilities disagreed — said appointments kill conversion because the customer
   never comes back. Wants on-demand only, with more agents.

41 UNRESOLVED: appointment-based V-CIP vs on-demand. Both agreed to model it.

47 Aadhaar-based e-KYC (OTP) is permitted for accounts under the small-account threshold, but full
   KYC requires V-CIP. Product wants a "start with e-KYC, upgrade to V-CIP later" path.

53 In scope: savings accounts. Out of scope: current accounts, NRI accounts, joint accounts,
   minors, credit cards.

59 Target: drop-off below 25%. V-CIP wait under 3 minutes. Straight-through account opening in
   under 12 minutes end to end.
"""

VKYC_EMAIL = """From: Head of Retail Liabilities <liabilities.head@hdfcbank.com>
To: Digital Onboarding PO; Ops Head — Onboarding
Cc: Compliance-KYC; CISO Office; Data Privacy Officer
Date: 15 June 2026, 19:05 IST
Subject: V-CIP re-platform — non-negotiables

The 58% drop-off is the single biggest leak in retail acquisition. Everything below is in service
of closing it.

- On-demand V-CIP, not appointments. I have seen the data from the appointment pilot at another
  bank: 40% no-show. An appointment is just a drop-off you have delayed.
- Resume-where-you-left-off. If a customer abandons at document upload, they come back to document
  upload — not to the start. Today they start again, which is why they never come back.
- The PAN and Aadhaar checks must happen before the video call, not during it. Do not waste an
  agent's time on an applicant who was never going to pass.

---
From: Data Privacy Officer <dpo@hdfcbank.com>
Date: 16 June 2026, 11:30 IST
Subject: RE: V-CIP re-platform — non-negotiables

Please loop me in early. Under the DPDP Act 2023 we need explicit, granular, revocable consent for
biometric and video processing, and a documented retention and erasure schedule. "We keep the
recording for 10 years because RBI says so" is a lawful basis for the recording — it is not a
lawful basis for everything else we might do with the face data.

Also: no facial-recognition model may be trained on customer V-CIP footage. If the vendor's contract
permits that, we renegotiate the contract.

---
From: CISO Office <ciso@hdfcbank.com>
Date: 17 June 2026, 09:12 IST
Subject: RE: RE: V-CIP re-platform

Deepfake and injection attacks on video KYC are up sharply across the industry. Liveness detection
must be presentation-attack-detection certified. A vendor claiming "AI liveness" without ISO 30107-3
certification does not clear our bar.
"""

VKYC_TRANSCRIPT = """Voice transcript — Onboarding journey review
Date: 18 June 2026 | HRL = Head of Retail Liabilities, OPS = Ops Head, PO = Digital Onboarding PO
Duration: 00:27:50

00:04:20 OPS: ...eleven minutes in a queue. Would you wait eleven minutes staring at a screen to
         open a bank account? Nobody would. That is why a third of them leave.

00:07:10 HRL: So we add agents.

00:07:25 OPS: We cannot just add agents, the volume is spiky. Monday morning and Saturday afternoon
         we are drowning; Wednesday at 3pm the agents are idle. That is why I want appointments.

00:09:40 HRL: And I am telling you appointments will not work. The customer is sitting there ready
         to open an account. Tell them to come back on Thursday and they never come back.

00:10:05 OPS: Then we need surge capacity, which means an outsourced agent pool, which means a whole
         compliance conversation about who is allowed to conduct a V-CIP.

00:10:30 HRL: ...that is a fair point. Park it, but somebody needs to answer it.

00:16:45 PO: What about customers who fail V-CIP? Today they just get an error and they are gone. Is
         there a fallback to a branch?

00:17:10 HRL: There should be. Nobody has designed that journey. Write it down.

00:22:35 PO: And accessibility — we have had complaints about V-CIP from customers with hearing
         impairments. The agent-led video call assumes the customer can hear the agent.

00:23:00 HRL: I did not know that. That needs to be in the requirements.
"""

# ══════════════════════════════════════════════════════════════════════════════
# 4 · Credit Card Dispute & Chargeback Automation — Payments & Cards
# ══════════════════════════════════════════════════════════════════════════════
DISPUTE_NOTES = """Discovery Workshop — Credit Card Dispute & Chargeback Automation
Date: 25 June 2026 | Chair: Head of Cards

2  Problem: 18,600 dispute cases a month. 71% are raised over the phone. Average resolution is 19
   days against an RBI-expected turnaround of 7 working days for the provisional credit. We are
   breaching TAT on roughly a third of cases and paying compensation under the Harmonisation of
   TAT circular.

9  Root cause per Ops: the dispute is captured in a spreadsheet, chased over email with the
   acquiring bank, and reconciled manually against the network files. Nothing is automated.

15 DECISION: build a self-service dispute journey in the app and NetBanking, plus a case-management
   workbench for the back office, plus automated chargeback filing to Visa/Mastercard/RuPay.

23 RBI: provisional credit within 7 working days for failed transactions where the customer's
   account was debited. Compensation of Rs 100/day beyond that.

30 Fraud team: a disputed transaction that is actually fraud must be routed into the fraud workflow
   immediately, not sit in a dispute queue. Card must be blocked.

37 Ops Head wants auto-approval of low-value disputes — anything under Rs 5,000 gets provisional
   credit instantly without an analyst touching it. Says it would clear 60% of the volume.

44 Risk pushed back — auto-approval is an abuse vector. Serial disputers will find it.

48 UNRESOLVED: auto-approve threshold, and what controls sit around it.

54 In scope: credit cards. Out of scope: debit cards (phase 2), UPI disputes (separate rail).

60 Target: 90% of disputes raised digitally. Provisional credit TAT within 3 working days.
"""

DISPUTE_EMAIL = """From: Head of Cards <cards.head@hdfcbank.com>
To: Cards Technology Lead; Ops Head — Disputes
Cc: Fraud Risk; Compliance; Customer Experience
Date: 28 June 2026, 22:40 IST
Subject: Disputes — we are paying compensation every single month

We paid Rs 41 lakh in TAT-breach compensation last quarter. That is not a technology budget, that
is a fine we are choosing to pay. This programme pays for itself in two quarters.

What I want:
- The customer raises a dispute from the transaction line in the app. Two taps. Not a phone call,
  not a form, not a branch visit.
- The status of that dispute is visible to the customer at all times, like a courier tracking page.
  Most of our call volume on disputes is people asking "what is happening with my case".
- Automated chargeback filing against the network. No human retyping a reference number into a
  Visa portal at 11pm.

On Ops' auto-approval idea — I support it in principle but Risk is right that it is an abuse vector.
My view: auto-approve under Rs 5,000 BUT only for customers with no dispute in the last 6 months and
a clean account history. That is a rules engine, not a blanket threshold.

---
From: Fraud Risk <fraud.risk@hdfcbank.com>
Date: 29 June 2026, 10:15 IST
Subject: RE: Disputes

Agreed on the rules engine. One addition: any dispute where the customer says "I did not make this
transaction" is a fraud claim, not a service dispute, and must leave the dispute workflow entirely.
Card blocked, replacement issued, fraud case opened. The current process treats these identically
and it costs us.

Also — we must not auto-approve anything on a card that already has a fraud marker.
"""

DISPUTE_TRANSCRIPT = """Voice transcript — Disputes programme kick-off
Date: 01 July 2026 | HC = Head of Cards, OPS = Ops Head Disputes, RISK = Fraud Risk
Duration: 00:22:15

00:03:30 OPS: ...nineteen days. And the customer calls us on day three, day seven, day twelve. Each
         of those calls is a person, and none of those calls move the case forward by a single day.

00:08:15 HC: If we did nothing else but show them a status page we would take out a third of the
         call volume.

00:12:40 RISK: My concern with the auto-approve is simple. The moment word gets out that anything
         under five thousand is instant credit, you will see exactly that pattern emerge. We have
         seen it at other banks.

00:13:20 OPS: So we cap it. Two auto-approvals per customer per year.

00:13:35 RISK: That is better. But you also need to claw back the provisional credit when the
         chargeback fails, and today we are terrible at that. We give the credit and we never take
         it back.

00:14:10 HC: How much are we leaking on that?

00:14:25 RISK: I do not have that number in front of me. It is not small.

00:18:50 OPS: Nobody has mentioned the merchant side. When we file a chargeback and the merchant
         represents, somebody has to review the representment evidence. That is analyst work and it
         does not go away.

00:20:05 HC: What is the SLA on that today?

00:20:15 OPS: There isn't one.
"""

# ══════════════════════════════════════════════════════════════════════════════
# 5 · AML Transaction Monitoring Uplift — Risk & Compliance
# ══════════════════════════════════════════════════════════════════════════════
AML_NOTES = """Discovery Workshop — AML Transaction Monitoring Uplift
Date: 30 June 2026 | Chair: Chief Compliance Officer | Classification: Internal — Restricted

3  Driver: the current transaction-monitoring system generates 42,000 alerts a month. 96.4% are
   false positives. The financial-intelligence team of 61 analysts spends most of its time closing
   noise, and genuine suspicious activity is being found late.

10 An internal audit finding (AUD-2026-114) requires remediation of alert quality by Q4 FY27. This
   is a committed regulatory remediation, with a date.

16 DECISION: uplift the monitoring platform — risk-based segmentation, behavioural baselines per
   customer segment, and ML-assisted alert triage.

24 CCO was explicit: ML may PRIORITISE alerts. It may not CLOSE them. Every alert that is closed is
   closed by a named human analyst, and that decision is auditable.

31 Data Science lead proposed auto-closing the lowest-risk decile of alerts to cut volume by 30%.
   CCO rejected it in the room. Data Science asked to revisit with a supervised-model precision
   study.

38 Model risk: any model influencing an AML outcome falls under model governance. It needs
   documentation, validation by an independent team, ongoing performance monitoring, and it must be
   explainable to a regulator. "The model said so" is not an audit answer.

45 STR filing to FIU-IND remains manual and stays manual in release 1.

51 In scope: retail and SME transaction monitoring. Out of scope: trade-based money laundering,
   correspondent banking, sanctions screening (separate platform).

57 Target: false-positive rate below 85%. No increase in true positives missed — this is the
   metric that matters, and degrading it to make the first number look good is a fireable outcome.
"""

AML_EMAIL = """From: Chief Compliance Officer <cco@hdfcbank.com>
To: Head of Financial Crime Technology; Data Science Lead
Cc: Chief Risk Officer; Internal Audit; Model Risk Management
Date: 02 July 2026, 07:55 IST
Subject: AML monitoring uplift — what I will and will not sign

To be unambiguous, because I do not want this relitigated in three months:

1. I will not sign off on a model that closes alerts autonomously. Not at any confidence threshold.
   A human closes every alert. The model may rank, score, and route. It may not decide.

2. I will not sign off on a model I cannot explain to the regulator. If the answer to "why was this
   alert deprioritised" is a SHAP plot nobody in the room understands, we do not ship it.

3. The false-positive number is not the goal. The goal is finding the suspicious activity we are
   currently missing. If we cut false positives by 40% and miss one more genuine case, we have made
   things worse, and I will say so.

On segmentation — yes, absolutely. A salaried retail customer and an SME jeweller should not be
measured against the same baseline. That is the single highest-value change here and it needs no ML
at all.

---
From: Model Risk Management <mrm@hdfcbank.com>
Date: 03 July 2026, 14:22 IST
Subject: RE: AML monitoring uplift

For the record, per our model-governance policy: any model in this pathway requires independent
validation before production, a documented model-development file, champion/challenger monitoring,
and annual re-validation. Expect 8–12 weeks for validation. Please plan for it rather than
discovering it in UAT.

Also: training data lineage must be documented. If the model is trained on historical analyst
dispositions, and those dispositions were themselves biased, we are automating that bias and we
will be asked about it.
"""

AML_TRANSCRIPT = """Voice transcript — AML uplift technical review
Date: 04 July 2026 | CCO = Chief Compliance Officer, DS = Data Science Lead,
FCT = Head of Financial Crime Technology | Classification: Internal — Restricted
Duration: 00:35:40

00:05:10 DS: ...ninety-six point four percent false positives. Every analyst hour is being spent on
         noise. I can cut the bottom decile with a supervised model at ninety-nine percent precision
         on held-out data.

00:06:00 CCO: And the one percent?

00:06:08 DS: ...statistically, some of those would be genuine.

00:06:15 CCO: Then the answer is no. I am not explaining to the FIU that we missed a case because a
         model was ninety-nine percent sure it was nothing. Rank them. Route them. Do not close them.

00:11:30 FCT: There is a middle path. The model deprioritises rather than closes — the alert still
         exists, still ages, still gets worked, but it goes to the bottom of the queue.

00:12:05 CCO: That I can live with, provided the alert is still worked within the regulatory window
         and the deprioritisation is logged with a reason.

00:19:45 DS: The segmentation work does not need any of this. Salaried, self-employed, SME, high
         net worth — four baselines instead of one would cut the noise substantially on its own.

00:20:30 CCO: Then do that first. Ship the thing that does not need a model-governance argument.

00:27:15 FCT: We have not talked about what happens to the alerts already open. There is a backlog
         of about eleven thousand.

00:27:40 CCO: ...no, we have not. That needs a plan of its own.

00:31:20 DS: One more thing — the historical dispositions we would train on. If analysts were closing
         alerts under time pressure, we would be learning to close alerts under time pressure.
"""

# ══════════════════════════════════════════════════════════════════════════════
CATALOG: dict[str, dict[str, Any]] = {
    "upi_autopay": {
        "name": "UPI AutoPay Self-Service",
        "business_unit": "Retail Banking — Digital Channels",
        "description": "Enable retail customers to create, pause, modify and revoke UPI AutoPay mandates in MobileBanking.",
        "context": {
            "business_owner": "Head of Payments",
            "project_sponsor": "Head of Payments",
            "priority": "Critical",
            "business_objective": "Reduce mandate-related call-centre volume by 40% within two quarters of launch.",
            "problem_statement": "Mandate creation is an assisted journey: 12,400 tickets/month, AHT 7.4 min, 62% completion. Customers are moving recurring payments to third-party UPI apps.",
            "current_challenges": "No self-service path; customers abandon at authentication; agents have no mandate view.",
            "desired_outcome": "A customer creates, pauses and revokes a mandate without ever contacting the bank.",
            "expected_benefits": "Lower cost-to-serve, higher recurring-payment penetration, improved NPS.",
            "business_kpis": [
                "Call-centre mandate tickets ↓40% (baseline 12,400/month)",
                "Mandate creation completion rate ≥85% (baseline 62%)",
                "Active mandates per retail customer 0.4 → 1.1",
                "p95 mandate creation latency ≤2.5s",
            ],
            "estimated_business_value": "INR 28 Cr — cost-to-serve reduction + recurring-payment fee income",
            "timeline": "Q3–Q4 FY27",
            "budget": "INR 6.5 Cr",
            "regulatory_scope": ["RBI e-Mandate", "RBI Master Direction", "Data Localisation"],
        },
        "sources": [
            (SourceKind.MEETING_NOTES, "Discovery Workshop — 18 Jun 2026", UPI_NOTES),
            (SourceKind.EMAIL, "Email thread — release 1 scope", UPI_EMAIL),
            (SourceKind.VOICE_TRANSCRIPT, "Sponsor review call — 21 Jun 2026", UPI_TRANSCRIPT),
        ],
        "planted_conflict": "Retry cap: the workshop fixed it at 3 (bank-set); the sponsor's call says merchant-configurable.",
        "planted_gap": "Nobody specifies behaviour for frozen/dormant accounts, or the retention period for revoked mandates.",
    },
    "corporate_fx": {
        "name": "Corporate FX Booking Portal",
        "business_unit": "Wholesale Banking",
        "description": "Self-service FX quoting and booking for corporate clients, with straight-through processing below the dealer-approval threshold.",
        "context": {
            "business_owner": "Head of Treasury",
            "project_sponsor": "MD, Wholesale Banking",
            "priority": "High",
            "business_objective": "Cut FX booking turnaround to under 90 seconds and lift the digital share of FX volume above 45% within three quarters.",
            "problem_statement": "Every corporate FX quote goes through the dealing desk by phone. 340 dealer-hours a month are spent on sub-USD-50k tickets carrying almost no margin, while corporates route that flow to foreign banks with portals.",
            "current_challenges": "Phone-based quoting; no straight-through processing; dealers doing low-value work; clients defecting to competitors with portals.",
            "desired_outcome": "A corporate treasurer quotes, books and confirms spot FX without speaking to a dealer.",
            "expected_benefits": "Dealer capacity released to structured flow; FX fee income defended; corporate relationship stickiness.",
            "business_kpis": [
                "FX booking TAT <90 seconds",
                "Digital share of FX volume >45% (baseline 11%)",
                "Dealer-hours on sub-USD-50k tickets ↓80% (baseline 340/month)",
                "Zero stale-rate booking losses",
            ],
            "estimated_business_value": "INR 42 Cr annual fee uplift + 340 dealer-hours/month released",
            "timeline": "Q2–Q4 FY27",
            "budget": "INR 9.2 Cr",
            "regulatory_scope": ["FEMA", "RBI Master Direction"],
        },
        "sources": [
            (SourceKind.MEETING_NOTES, "Discovery Workshop — 03 Jul 2026", FX_NOTES),
            (SourceKind.EMAIL, "Email thread — Treasury red lines", FX_EMAIL),
            (SourceKind.VOICE_TRANSCRIPT, "Sponsor call — 09 Jul 2026", FX_TRANSCRIPT),
        ],
        "planted_conflict": "Dealer-approval threshold: Market Risk says USD 1mn flat; Treasury and the Dealing Desk want USD 2mn tiered by internal rating. Also spot-only vs spot+forwards is openly unresolved.",
        "planted_gap": "No decision on rate-feed failure (stale price / block booking / fall back to desk), and no threshold defined for unrated mid-market clients.",
    },
    "vkyc_onboarding": {
        "name": "Digital Account Opening & V-KYC Re-platform",
        "business_unit": "Retail Banking — Liabilities",
        "description": "Rebuild the digital savings-account journey and re-platform Video CIP ahead of vendor end-of-support.",
        "context": {
            "business_owner": "Head of Retail Liabilities",
            "project_sponsor": "Head of Retail Liabilities",
            "priority": "Critical",
            "business_objective": "Cut digital account-opening drop-off from 58% to below 25%, and migrate off the V-CIP platform before vendor end-of-support in December 2027.",
            "problem_statement": "58% of digital applicants abandon. The worst step is video KYC: an 11-minute average agent wait, with 34% abandoning in the queue. Journey NPS is -12. The 2019 V-CIP vendor product goes end-of-support in Dec 2027.",
            "current_challenges": "V-CIP queue wait; no resume-where-you-left-off; PAN/Aadhaar checks happen too late; no branch fallback for failed V-CIP.",
            "desired_outcome": "An applicant opens a savings account end to end in under 12 minutes without abandoning.",
            "expected_benefits": "Retail acquisition uplift; lower cost per account; forced migration de-risked ahead of EOS.",
            "business_kpis": [
                "Digital account-opening drop-off <25% (baseline 58%)",
                "V-CIP wait <3 minutes (baseline 11 minutes)",
                "End-to-end account opening <12 minutes",
                "Journey NPS ≥ +20 (baseline -12)",
            ],
            "estimated_business_value": "INR 61 Cr — incremental CASA acquisition",
            "timeline": "Q1 FY27 – Q3 FY28 (hard stop: vendor EOS Dec 2027)",
            "budget": "INR 14 Cr",
            "regulatory_scope": ["RBI Master Direction", "PMLA / KYC-AML", "DPDP Act 2023", "Data Localisation"],
        },
        "sources": [
            (SourceKind.MEETING_NOTES, "Discovery Workshop — 12 Jun 2026", VKYC_NOTES),
            (SourceKind.EMAIL, "Email thread — non-negotiables (DPO, CISO)", VKYC_EMAIL),
            (SourceKind.VOICE_TRANSCRIPT, "Onboarding journey review — 18 Jun 2026", VKYC_TRANSCRIPT),
        ],
        "planted_conflict": "Appointment-based V-CIP (Ops, to smooth spiky capacity) vs on-demand only (Head of Retail Liabilities, who says appointments are just delayed drop-offs).",
        "planted_gap": "No journey designed for customers who FAIL V-CIP; accessibility for hearing-impaired customers raised but unresolved; outsourced-agent compliance question parked.",
    },
    "card_disputes": {
        "name": "Credit Card Dispute & Chargeback Automation",
        "business_unit": "Payments & Cards",
        "description": "Self-service dispute raising, a back-office case workbench, and automated chargeback filing to the card networks.",
        "context": {
            "business_owner": "Head of Cards",
            "project_sponsor": "Head of Cards",
            "priority": "High",
            "business_objective": "Bring provisional-credit TAT within 3 working days and move 90% of dispute raising to digital, ending TAT-breach compensation.",
            "problem_statement": "18,600 disputes a month, 71% raised by phone. Average resolution is 19 days against an RBI-expected 7 working days for provisional credit. Roughly a third of cases breach TAT; INR 41 lakh was paid in compensation last quarter.",
            "current_challenges": "Disputes captured in spreadsheets, chased by email, reconciled manually against network files; no customer-facing status; no clawback discipline on failed chargebacks.",
            "desired_outcome": "A customer disputes a transaction in two taps and tracks it like a courier shipment; the back office files chargebacks automatically.",
            "expected_benefits": "Compensation eliminated; dispute call volume cut; analyst capacity released; recovery on failed chargebacks.",
            "business_kpis": [
                "Provisional-credit TAT ≤3 working days (baseline 19 days)",
                "Disputes raised digitally ≥90% (baseline 29%)",
                "TAT-breach compensation → INR 0 (baseline INR 41 lakh/quarter)",
                "Dispute-status call volume ↓60%",
            ],
            "estimated_business_value": "INR 22 Cr — compensation avoided + analyst capacity + chargeback recovery",
            "timeline": "Q2–Q4 FY27",
            "budget": "INR 7.8 Cr",
            "regulatory_scope": ["RBI Master Direction", "PCI-DSS"],
        },
        "sources": [
            (SourceKind.MEETING_NOTES, "Discovery Workshop — 25 Jun 2026", DISPUTE_NOTES),
            (SourceKind.EMAIL, "Email thread — TAT-breach compensation", DISPUTE_EMAIL),
            (SourceKind.VOICE_TRANSCRIPT, "Programme kick-off — 01 Jul 2026", DISPUTE_TRANSCRIPT),
        ],
        "planted_conflict": "Auto-approval of low-value disputes: Ops wants a flat INR 5,000 threshold; Risk calls it an abuse vector; the Head of Cards wants a rules engine (clean history, no recent dispute). Unresolved in the evidence.",
        "planted_gap": "No SLA exists for reviewing merchant representments; the clawback leakage on failed chargebacks is admitted to be unmeasured ('It is not small').",
    },
    "aml_monitoring": {
        "name": "AML Transaction Monitoring Uplift",
        "business_unit": "Risk & Compliance",
        "description": "Risk-based segmentation, behavioural baselines and ML-assisted alert triage — with humans retaining every close decision.",
        "context": {
            "business_owner": "Chief Compliance Officer",
            "project_sponsor": "Chief Compliance Officer",
            "priority": "Critical",
            "business_objective": "Cut the AML false-positive rate below 85% with no degradation in true positives, closing internal audit finding AUD-2026-114 by Q4 FY27.",
            "problem_statement": "42,000 alerts a month at a 96.4% false-positive rate. 61 analysts spend most of their time closing noise, and genuine suspicious activity is found late. Internal audit has raised a dated remediation finding.",
            "current_challenges": "One monitoring baseline for every customer type; no risk-based segmentation; an 11,000-alert backlog; manual STR filing.",
            "desired_outcome": "Analysts spend their time on alerts that matter, with every close decision made and owned by a named human.",
            "expected_benefits": "Audit finding closed; analyst capacity redeployed to genuine investigation; suspicious activity found earlier.",
            "business_kpis": [
                "False-positive rate <85% (baseline 96.4%)",
                "True positives missed: no increase — this is the metric that matters",
                "Alert backlog cleared from 11,000 to 0",
                "Audit finding AUD-2026-114 closed by Q4 FY27",
            ],
            "estimated_business_value": "Regulatory remediation (non-discretionary) + ~38 analyst-FTE redeployed",
            "timeline": "Q1–Q4 FY27 (audit-committed date)",
            "budget": "INR 11.5 Cr",
            "regulatory_scope": ["PMLA / KYC-AML", "RBI Master Direction"],
        },
        "sources": [
            (SourceKind.MEETING_NOTES, "Discovery Workshop — 30 Jun 2026 (Restricted)", AML_NOTES),
            (SourceKind.EMAIL, "Email thread — what the CCO will and will not sign", AML_EMAIL),
            (SourceKind.VOICE_TRANSCRIPT, "Technical review — 04 Jul 2026 (Restricted)", AML_TRANSCRIPT),
        ],
        "planted_conflict": "Data Science wants to auto-close the lowest-risk decile (99% precision); the CCO refuses autonomous closure at any threshold. A 'deprioritise, never close' middle path is proposed but not ratified.",
        "planted_gap": "No plan for the 11,000-alert backlog; training-data bias in historical analyst dispositions raised and unanswered; the 8–12 week model-validation window is not in any plan.",
    },
}

# Five further demo projects live in seed_extra so this file stays readable.
from app.seed_extra import EXTRA_CATALOG  # noqa: E402

CATALOG.update(EXTRA_CATALOG)

# Backwards compatibility: the original POST /api/projects/seed seeded this one.
SEED_SOURCES = [
    {"kind": k, "title": t, "content": c} for k, t, c in CATALOG["upi_autopay"]["sources"]
]


def catalog_summary() -> list[dict[str, Any]]:
    """What the UI shows in the demo-data picker."""
    return [
        {
            "key": key,
            "name": p["name"],
            "business_unit": p["business_unit"],
            "description": p["description"],
            "priority": p["context"]["priority"],
            "regulatory_scope": p["context"]["regulatory_scope"],
            "source_count": len(p["sources"]),
            "planted_conflict": p["planted_conflict"],
            "planted_gap": p["planted_gap"],
        }
        for key, p in CATALOG.items()
    ]
