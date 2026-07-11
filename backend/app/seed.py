"""Demo evidence base: three messy, contradictory, human sources — exactly what Agent 1 is for."""

from app.models import SourceKind

MEETING_NOTES = """Discovery Workshop — UPI AutoPay Self-Service
Date: 18 June 2026 | Room: Kanjurmarg 4F-B | Chair: Head of Payments

1  Attendees: Head of Payments, Digital Channels PO, Payments Engineering Lead,
   Compliance Officer, Digital Support Manager, NPCI relationship manager (dial-in).

5  Context: mandate creation is currently an assisted journey. Call centre handles
   ~12,400 mandate tickets/month, AHT 7.4 min. Completion rate on the assisted flow is 62%.
   Customers are moving recurring payments to third-party UPI apps. Head of Payments wants
   this closed in this financial year.

12 DECISION: retail customers must be able to create a UPI AutoPay mandate directly in
   MobileBanking, with no branch visit and no call to the contact centre.

18 Compliance flagged the RBI e-mandate framework. Mandates up to Rs 1,00,000 can execute
   without additional factor authentication. Above that, AFA is mandatory on every execution.

23 Pre-debit notification is a hard regulatory requirement — customer must be told 24 hours
   before the debit. Compliance was emphatic that this is not negotiable and an SLA breach here
   is a reportable observation.

31 Customers must be able to pause a mandate, change the cap, or revoke it entirely. Revocation
   must not require the merchant's cooperation. Changes must land before the next debit cycle.

38 Retry on failed debit: Payments Engineering proposed a fixed policy — 3 retries within 72 hours
   on insufficient funds. Agreed in the room.

44 Out of scope for release 1: NetBanking, corporate/current account mandates, e-NACH, card-on-file.
   Merchant onboarding portal is a separate programme.

49 Success measure proposed: cut call-centre mandate volume by 40% within two quarters.

52 ACTION: Digital Channels PO to circulate concept note for sign-off by Head of Payments and
   Compliance before any build starts.
"""

EMAIL_THREAD = """From: Head of Payments <payments.head@hdfcbank.com>
To: Digital Channels PO <po.digital@hdfcbank.com>; Payments Engineering Lead
Cc: Compliance <compliance@hdfcbank.com>
Date: 20 June 2026, 21:14 IST
Subject: RE: UPI AutoPay — release 1 scope

Following the workshop, three things I want locked before we spend a rupee on build:

1. The mandate dashboard is table stakes. A customer should open AutoPay and instantly see
   every mandate, what it will cost them, and when. If they cannot see it, they will not trust it.

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
- Full immutable audit trail of every mandate state transition, retained 8 years per bank policy.
- All mandate and customer data must remain within India. No exceptions, no offshore processing.
- Anything above the Rs 1,00,000 threshold requires AFA. Please do not design a UX that tries to
  work around this.
"""

VOICE_TRANSCRIPT = """Voice transcript — Sponsor review call
Date: 21 June 2026 | Participants: Head of Payments (HoP), Digital Channels PO (PO),
Payments Engineering Lead (ENG) | Duration: 00:31:12

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

SEED_SOURCES = [
    {"kind": SourceKind.MEETING_NOTES, "title": "Discovery Workshop — 18 Jun 2026", "content": MEETING_NOTES},
    {"kind": SourceKind.EMAIL, "title": "Email thread — release 1 scope", "content": EMAIL_THREAD},
    {"kind": SourceKind.VOICE_TRANSCRIPT, "title": "Sponsor review call — 21 Jun 2026", "content": VOICE_TRANSCRIPT},
]
