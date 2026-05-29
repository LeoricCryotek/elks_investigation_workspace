# Investigation Committee Guide

A practical walkthrough of how membership-applicant background investigations work in this tool, who does what, and why the steps are designed the way they are.

This guide is for:
- New committee members learning the workflow
- Chairs onboarding new investigators
- Lodge Secretaries auditing past investigations
- Anyone who needs to understand a recommendation that's already been submitted

If you only have five minutes, read the **Overview**, **Roles**, and **One Investigation Start to Finish** sections.

---

## Overview

This Odoo application gives the Investigation Committee a structured way to vet new membership applicants. It plugs into the existing **elkscontacts** membership-application workflow — your committee doesn't operate in a separate tool; the workspace lives on the application record itself.

### What the tool does

- Pulls the applicant's identity and history straight off the Membership Application — no re-typing.
- Pre-populates a checklist of background-check sources based on every state the applicant disclosed living or working in.
- Automatically screens the applicant against the federal OFAC sanctions list.
- Lets the investigator open each portal in their browser, do the search by hand, and record what they find — using a bulk-paste wizard when results are voluminous.
- Cross-checks captured findings against the applicant's identity to surface name/date/address inconsistencies.
- Produces a one-page summary report and a detailed report for the Exalted Ruler and Lodge Secretary.

### What the tool does NOT do

- It does not scrape state court portals or other government sites. Those terms of service forbid automated access, and producing fully automated consumer reports for membership eligibility would turn the Lodge into a "consumer reporting agency" under the federal Fair Credit Reporting Act. Only OFAC's published CSV is fully automated, because Treasury distributes it for exactly this purpose.
- It does not make the membership decision. It produces a recommendation; the Lodge votes.

---

## Roles

Investigation roles live in the **Productivity** section of each user's Access Rights tab, as a row labeled **Elks Investigation Committee**. Four levels:

| Level | Sees | Can do |
|---|---|---|
| **(blank — no permission)** | Nothing investigation-related | Default for regular Lodge members |
| **Committee Member** | Own + unassigned investigations only | Claim unassigned cases, work assigned cases, capture findings, submit Approve/Deny |
| **Chairman** | All investigations including past ones | Everything Committee Member can do, plus reassign cases and override recommendations |
| **Administration** | Everything Chairman can see, plus Secretary backup | Manage portal directory, manage user roles, override committee decisions |

The roles auto-assign from Lodge state:

- Members of the **Investigation** committee (in `elks.committee`) → Committee Member
- The Investigation committee's **chair** → Chairman
- The current **Exalted Ruler** + anyone holding **Lodge Secretary** → Administration

A nightly cron reconciles, plus model hooks fire immediately when the committee composition or ER changes. You can also manually grant any role to anyone via their user form, or click **Investigations → Configuration → Sync Roles Now** to force a reconcile.

---

## Application Lifecycle (Stages)

A Membership Application moves through these stages — the investigation work happens in stage 2:

```
┌──────────┐    ┌────────────────────┐    ┌──────────┐    ┌─────────┐    ┌────────────┐
│ Proposed │ -> │ Under Investigation│ -> │ Balloting│ -> │ Elected │ -> │ Initiated  │
└──────────┘    └────────────────────┘    └──────────┘    └─────────┘    └────────────┘
                          │
                          └─> (Rejected) or (Withdrawn)
```

### 1. Proposed
A current Lodge member proposes the applicant. The application form captures name, address, sponsorship, attestations (US citizen, no felony, etc.). The chair clicks **Start Investigation** to advance.

### 2. Under Investigation  
This is where the Investigation Committee does its work. The committee verifies the applicant's information, runs background checks across every state in their history, and decides whether to recommend Approve or Deny. When the investigator submits a recommendation, the application advances to Balloting.

### 3. Balloting
The Lodge votes. The Recommendation (Approve or Deny) and the investigator's notes are visible to voters. If the investigator denied, voters see both the denial reason and the basis on file.

### 4. Elected
The ballot passed. The applicant is now elected to membership but hasn't gone through the initiation ceremony yet.

### 5. Initiated
The applicant attends initiation and becomes a full member. The Membership Application is complete; the linked contact is now flagged as a member.

### Off-ramps
- **Rejected** — the ballot failed, or the chair formally rejected.
- **Withdrawn** — the applicant withdrew their application, or the Lodge withdrew it.

---

## One Investigation Start to Finish

Here's the full path from "an application enters Under Investigation" to "the committee submits a recommendation," step by step.

### Step 1: The chair starts the investigation

The chair (or anyone with Officer permissions) opens the Proposed application and clicks **Start Investigation** in the header. This:

- Advances the stage to **Under Investigation**.
- Stamps `date_investigation_assigned` with today's date.
- Auto-creates one Check record for every portal that applies to the applicant's jurisdictions — both nationwide sources (OFAC, NSOPW, CourtListener, plus identity sites like BlackBookOnline and social media) and state portals for every state in the applicant's address and employment history.

The application now appears in **Investigations → My Investigations** for the committee.

### Step 2: A committee member claims it

When a Committee Member opens an unassigned investigation, a blue **Claim This Investigation** button appears in the header. Clicking it:

- Sets `investigator_id` to the current user's partner record.
- Stamps `date_investigation_assigned`.
- Posts to the chatter so the chair and other members can see who took it.

The application now disappears from other committee members' inboxes (record rule restricts visibility to own + unassigned).

### Step 3: The investigator fills in supplemental info

The proposal form captured the current address but not the 10-year history. Inside the Investigation Workspace tab, the investigator adds:

- **Aliases and former names** — maiden names, prior legal names, nicknames used legally.
- **Driver's license #** and **last 4 SSN** (for identity disambiguation only — these are not stored as authentication data).
- **Residential history** — every address for the past 10 years, with state codes. This is what drives the per-state portal seeding.
- **Employment history** — for the past 10 years.
- **References to contact** — three or more non-related references the investigator will phone.

Each new state added to the residential or employment history triggers the **Refresh Checks from Directory** button to optionally seed additional portals.

### Step 4: Run the automated OFAC screen

In the workspace header, the investigator clicks **Run OFAC Screen**. The module:

- Downloads the official Treasury Specially Designated Nationals CSV (~5.5 MB, ~7,500 individuals). Cached for 24 hours.
- Searches the SDN list against the applicant's name, aliases, and maiden name using fuzzy matching.
- Records the result as a Check row with `result_summary = "no records found"` (the common case) or `"match found"` (rare).

This step requires no operator interaction unless there's a match.

### Step 5: Work the per-jurisdiction checks

For each remaining Check row in the **Background Checks** section, the investigator clicks **Open Portal** to launch the official site in a new tab. The portal's URL is in the row; for state court portals, the row's `hint` field tells you about quirks (Washington's Disclaimer modal, Idaho's Smart Search format, etc.).

After running the search on the portal, the investigator returns to the workspace and:

- Clicks **No records** if nothing matched the applicant.
- Clicks the row to open its detail form and capture Hit records if matches came back.

For portals that return many results (Washington Person Search can return dozens for common names like "Anna Kim"), the investigator can use **Paste & Parse Bulk Results** — paste the search result block from the portal, the wizard extracts one Hit row per record with court, role, case number, and date filled in automatically.

### Step 6: Contact references

The investigator phones each reference and records:

- Date contacted
- Whether they recommend FOR, AGAINST, NEUTRAL, or were NO RESPONSE
- A quote or notes summarizing the conversation

### Step 7: Run cross-check

Once findings are recorded, the investigator clicks **Run Cross-Check** in the header. The cross-check engine looks at all captured Hit records and flags:

- **State-coverage gaps** — applicant lived in a state but no checks completed for it (HIGH).
- **Required nationwide sources** not completed: NSOPW, OFAC, CourtListener (MEDIUM).
- **Name mismatches** between hit and applicant (MEDIUM-HIGH depending on similarity score).
- **DOB mismatches** — hit DOB doesn't match applicant DOB → likely a different person (HIGH).
- **County / address inconsistencies** — hit court or address isn't in any city/state the applicant disclosed (MEDIUM).
- **Missing dispositions** on captured cases (INFO).
- **Exculpatory role tags** — applicant appears as Plaintiff or Petitioner (INFO; not concerning).

Flags appear in the **Cross-Check Flags** section grouped by severity. HIGH severity flags must be addressed before submitting a recommendation.

### Step 8: Submit Approve or Deny

When the investigator is satisfied that the investigation is complete:

- **Submit: APPROVE → Balloting** — sets `investigation_result = 'favorable'`, runs a final cross-check, and advances the application to the Balloting stage using the existing Lodge workflow (member-history logging, CLMS activity, chatter — all preserved).
- **Submit: DENY** — requires a written **Denial Reason** in the field below the workspace, sets `investigation_result = 'unfavorable'`, schedules a chair heads-up activity, and advances to Balloting with the unfavorable recommendation on file. The Lodge still votes — the investigator's "no" is captured so voters and the chair can weigh it.

In both cases the investigator can first preview the report via **Print Summary (1 page)** or **Print Detailed Report** before submitting.

---

## Workspace Sections Explained

### Assignment
Tracks who's investigating, when they were assigned, when they finished, and what they recommended. Read-only for everyone except the investigator (and the chair, who can reassign).

### Workspace overview
At-a-glance counts: how many checks total, how many still pending, how many hits captured, how many cross-check flags. The **States in applicant history** field summarizes what jurisdictions the cross-check engine is comparing against.

### Identity supplements
Identity data collected during the investigation but not on the original application:

- **Aliases / former names** — comma-separated, fed to the OFAC screen and cross-check
- **Last 4 SSN** — for identity disambiguation only
- **Driver's license # / state**

### Residential history (10 years, most recent first — drives which states get checked)
Every place the applicant has lived in the past decade. The state code on each row drives which portals get auto-seeded into the Background Checks list.

### Employment history
Past 10 years of employers. Like residential, this also drives state seeding.

### References to contact
Personal references the investigator phones. Track the call date, the reference's recommendation, and notes.

### Background Checks
The per-jurisdiction worklist. Each row represents one portal. Use **Open Portal** to launch the search; **Paste & Parse Bulk Results** to capture multiple findings at once. Color coding:

- Green: no records found
- Amber: match found
- Blue: pending
- Grey: skipped

### Cross-Check Flags
Anomalies the engine surfaces. Severity-graded HIGH / MEDIUM / LOW / INFO. Address HIGH flags before submitting a recommendation.

### Investigator notes
Free-form notes for the committee chair. Anything the investigator wants to communicate that doesn't fit elsewhere.

### Denial reason
Required if the investigator clicks **Submit: DENY**. Must be a clear, factual basis — it goes on the report and may be required for FCRA adverse-action notice if a third-party screening service was used.

---

## Background Check Sources Explained

### Nationwide

| Source | What it shows | Cost | Notes |
|---|---|---|---|
| **OFAC SDN** | US Treasury sanctioned individuals | Free, automated | Run once per applicant; ~7,500 entries |
| **NSOPW** | National Sex Offender Public Website | Free | Searches all 50 states + DC + territories + tribal at once |
| **CourtListener** | Federal court records (PACER cases) | Free | By Free Law Project |
| **PACER** | Federal Case Locator | $30 setup + per-page fees | Usually skip — CourtListener covers most of the same data free |
| **BlackBookOnline** | Aggregator of public records links | Free | Identity-verification only, not for criminal screening |
| **Anywho** | Phone directory and reverse address | Free | Verify disclosed phone number matches |
| **Facebook / Instagram / X / LinkedIn** | Public social media profiles | Free | Public posts only; do not friend-request to see private content |

### Per-state

Each state in the applicant's history adds:

- **Statewide court portal** — civil and criminal case search
- **State sex offender registry**
- **State Department of Correction inmate search**
- **Statewide criminal history** (where available — Washington WATCH, Idaho ISP-BCI, etc.)

### Local (county recorder)

For applicants who lived in specific counties, the directory also includes county recorder offices (King County LandmarkWeb, Pierce, Snohomish, Spokane, Nez Perce, etc.) for property ownership, liens, marriage records, UCC filings, and recorded judgments. Useful for identity verification and financial-reliability flags rather than criminal screening.

---

## Cross-Check Engine

The engine runs every time you click **Run Cross-Check** (and automatically before Submit). Severity levels:

### HIGH severity
- State in applicant's history wasn't checked
- Hit's DOB doesn't match applicant's DOB → likely a different person

**These must be addressed before recommending.**

### MEDIUM severity
- Required nationwide source (NSOPW / OFAC / CourtListener) not yet completed
- Hit name has low similarity to applicant (<70%) — verify it's the same person
- Hit address not in applicant's disclosed history
- Hit court is in a county the applicant didn't disclose

### LOW severity
- DOB is close but not exact (could be transcription error)

### INFO severity
- Captured hit has no recorded disposition (look it up before scoring)
- Applicant appears as Plaintiff or Petitioner (exculpatory context; usually not concerning)

---

## Approve vs Deny

### Approve
Use when the investigation surfaces no disqualifying findings and the applicant's identity and history check out. The Lodge will likely vote yes. The recommendation is recorded on the application and visible to voters.

### Deny
Use when the investigation surfaces material concerns: undisclosed criminal history, identity inconsistencies that the applicant can't explain, references who declined to vouch, or anything else that meaningfully bears on whether the applicant is "socially and fraternally acceptable" (per the Elks manual).

The Lodge still votes after a Deny recommendation. The investigator's "no" appears on the ballot record. The Lodge can vote yes anyway — the Lodge has final say.

Two reasons we don't auto-reject on Deny:
- Membership is a Lodge prerogative, not a single investigator's decision.
- Auto-rejection without a vote could create FCRA "adverse action" issues if a third-party screening service informed the decision.

### What if the cross-check still has HIGH flags?

The Submit buttons don't enforce a "no HIGH flags" rule, but they will run a final cross-check and the results appear on the printed report. If HIGH flags remain, the investigator's recommendation will be visibly weakened on the report — the chair can ask the investigator to address them before the ballot.

---

## FCRA Compliance Reminders

The Fair Credit Reporting Act applies whenever a Lodge uses information from a **third-party consumer reporting agency** (Checkr, Sterling, GoodHire, etc.) to make a membership-eligibility decision. It does not apply when the committee gathers information directly from public-government records (state courts, NSOPW, etc.) or from the applicant's own disclosure.

If the decision is **Deny** and was informed by a third-party consumer report:

1. **Pre-adverse-action notice** — give the applicant a copy of the report, a copy of the FTC "Summary of Your Rights Under the FCRA," and a reasonable time (typically 5 business days) to dispute its accuracy.

2. **Final adverse-action notice** — if the decision stands, identify the consumer reporting agency (name, address, phone) and tell the applicant of their right to a free copy of the report within 60 days and to dispute its accuracy directly with the agency.

The detailed report includes a Section 8 with this procedure restated as a reminder.

---

## Reports

| Report | Contents | When to use |
|---|---|---|
| **Summary (1 page)** | Coverage strip, jurisdictions checked, HIGH and MEDIUM flags, recommendation + reason, sign-off line | Standard committee deliverable to the Exalted Ruler |
| **Detailed Report** | Full per-jurisdiction findings with all captured hits, every cross-check flag, full disclosures, FCRA adverse-action procedure | For the Lodge file and if anyone questions the investigation later |
| **Word (.docx)** | Same as Detailed, but editable | If you want to add commentary or merge into a larger document |

The Summary is the default — it fits on one Letter page and is what the Lodge Secretary attaches to the meeting minutes. The Detailed is for the file.

---

## Common Questions

**Why am I not seeing the Investigations menu?**
Your user account doesn't have any Investigation role yet. Ask the chair to grant Committee Member from the Productivity section of your Access Rights tab, or to add you to the Investigation committee in the elks.committee record (auto-syncs nightly, plus you can force it from Configuration → Sync Roles Now).

**Why doesn't anything appear in My Investigations?**
The list only shows applications in the Under Investigation stage. If everything is Proposed, ask the chair to start an investigation first. Also, Committee Members only see their own + unassigned — if all active investigations are assigned to other people, your inbox is empty.

**Can I unclaim an investigation?**
Yes — clear the **Investigator** field in the Assignment section and save. The investigation goes back to unassigned and other committee members can claim it.

**What if I find something during the investigation that the chair needs to know now?**
Use the chatter at the bottom of the application — @mention the chair. They get a notification.

**How long should an investigation take?**
There's no hard rule, but most should finish in under a week of elapsed time. The bottleneck is usually reaching references by phone.

**Can multiple committee members work the same investigation?**
No — only the assigned investigator can submit a recommendation. But you can collaborate by leaving comments in the chatter.

**What if I'm not sure whether to Approve or Deny?**
Use the **Investigator Notes** field to write up your uncertainty and flag it for the chair before submitting. The chair can also reassign or extend the investigation.

---

## Glossary

- **Application** — the Membership Application record (elks.membership.application). The investigation lives on this record.
- **Background Check** — one row in the Background Checks section; represents one portal lookup.
- **Cross-Check Flag** — a single anomaly raised by the cross-check engine.
- **Hit** — a record captured from a portal search (a court case, sex-offender entry, sanctions match, etc.).
- **Investigator** — the committee member assigned to a specific investigation.
- **OFAC SDN** — Office of Foreign Assets Control Specially Designated Nationals list.
- **NSOPW** — National Sex Offender Public Website (nsopw.gov).
- **Portal** — one of the records-search websites in the Background-Check Portal Directory.
- **CRA** — Consumer Reporting Agency. Third-party paid screening services like Checkr.
- **FCRA** — Fair Credit Reporting Act. Federal law governing CRAs.
- **Adverse action** — the FCRA two-step notice procedure required when denying based on a CRA report.
