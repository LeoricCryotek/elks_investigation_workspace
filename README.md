# Elks Investigation Workspace

An Odoo 19 add-on for `elkscontacts` that gives the Investigation Committee a ticket-style worklist and one-screen workspace for membership background investigations.

## What it adds

**My Investigations inbox** — under Contacts → My Investigations, every committee member sees the applications in the `Under Investigation` stage assigned to them, plus any unassigned ones they can claim. Sorted oldest-first so nothing falls through the cracks.

**Investigation Workspace tab** on every membership application — replaces the existing simple Investigation page with a rich workspace that holds:
- Applicant identity supplements (aliases, last-4 SSN, driver's license)
- 10-year residential history (drives which state portals get checked)
- 10-year employment history
- References to contact (in addition to the existing proposer/endorser)
- A pre-seeded list of background checks (one row per portal that applies, based on the applicant's history)
- Cross-check flags (state-coverage gaps, name/DOB mismatches, address inconsistencies)
- Investigator notes + denial reason field

**Workflow buttons in the form header** (visible only in the Investigation stage):
- **Claim This Investigation** — the first committee member to open an unassigned investigation claims it (matches your "whoever opens it first" preference)
- **Refresh Checks from Directory** — re-seed pending check records (safe to re-run after editing history)
- **Run OFAC Screen** — fully automated; downloads the official Treasury Specially Designated Nationals CSV and searches all ~7,500 listed individuals locally against the applicant's name and aliases
- **Run Cross-Check** — analyzes the captured hits against the applicant's stated identity, surfaces inconsistencies as severity-graded flags
- **Submit: ACCEPT → Balloting** — sets `investigation_result = 'favorable'` and calls the existing `action_move_to_balloting()` so the application advances using your existing workflow (member-history logging, CLMS activity, chatter — all preserved)
- **Submit: DENY** — requires a written Denial Reason; sets `investigation_result = 'unfavorable'` and **leaves the application in the Investigation stage** for chair review (per your preference). Auto-schedules a to-do activity for follow-up.
- **Print Findings (PDF)** — QWeb report
- **Download Word (.docx)** — python-docx report

**Portal Directory** — under Contacts → Background-Check Portal Directory (Secretary access). Seeded with all the nationwide sources (NSOPW, OFAC, CourtListener, plus the FCRA-safe Elks-manual sites: BlackBookOnline, Anywho, Facebook, Instagram, X, LinkedIn) and per-state portals (court records, sex offender registry, DOC inmate search) for ID/WA/OR/MT/CA/TX/NY/FL. Add more states through the UI without code changes.

## Installation

Drop the folder into your Odoo `addons_path` alongside `elkscontacts/`:

```
~/Documents/GitHub/elkscontacts/
~/Documents/GitHub/elks_investigation_workspace/      ← here
```

Then:
1. `pip install python-docx` in Odoo's Python environment (required for the Word report; the PDF report works without it).
2. Restart Odoo.
3. **Apps → Update Apps List** → search "Elks Investigation Workspace" → Install.

The module declares `elkscontacts` as a dependency, so it will fail to install if `elkscontacts` isn't already installed.

## How the workflow now looks

```
Proposed → Under Investigation → Balloting → Elected → Initiated
              ▲                       ▲
              │                       │
          Chair clicks            Investigator clicks
          "Start Investigation"   "Submit: ACCEPT"
          (existing button)        (new button)
                  │
                  └─ Module auto-seeds the check list
                     based on applicant's history
```

On the **DENY** path, the application stays in the Under Investigation stage with an unfavorable recommendation. The chair sees it in **All Investigations (Chair)**, reads the denial reason in the chatter, and either calls the existing `action_reject` button to formally reject, or moves it back to Proposed for more info, or overrides and moves it to Balloting anyway.

## Architecture

- **Application IS the case** — no separate `elks.investigation` record. The investigation lives as fields on the existing `elks.membership.application`.
- **History lines** (`elks.investigation.address.history`, `elks.investigation.employment.history`, `elks.investigation.reference`) are O2M children of the application.
- **Checks** (`elks.investigation.check`) and **Hits** (`elks.investigation.hit`) are O2M children of the application.
- **Flags** (`elks.investigation.flag`) are O2M children too — recomputed every time you click Run Cross-Check.
- **Portals** (`elks.portal`) are a directory the Secretary can edit through the UI.
- **OFAC** is an `AbstractModel` that handles download + caching + local screen.
- **Docx report** is another `AbstractModel` that produces an `ir.attachment` and returns a download action.

## Files

```
elks_investigation_workspace/
├── __manifest__.py
├── __init__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── portal_directory.py            elks.portal
│   ├── history_lines.py               address/employment/reference O2M models
│   ├── investigation_check.py         one row per portal lookup
│   ├── investigation_hit.py           records captured + flags
│   ├── membership_application.py      extends elks.membership.application
│   └── ofac_screen.py                 OFAC automation + docx report builder
├── security/
│   └── ir.model.access.csv            uses elkscontacts.group_elks_* groups
├── data/
│   └── portal_directory_data.xml      seed portals (nationwide + key states)
├── views/
│   ├── investigation_workspace_views.xml   form inheritance + inbox lists
│   ├── portal_views.xml                    portal admin
│   └── menu.xml
└── reports/
    ├── investigation_report_actions.xml    QWeb PDF action
    └── investigation_report_templates.xml  QWeb template
```

## Caveats / what to verify on first install

- The module assumes `contacts.menu_contacts` exists as the parent menu for top-level Contacts items. If your Odoo install renames it, update `views/menu.xml`.
- Field references in the form inheritance (`view_elks_membership_application_form`) are by XML ID — match your installed `elkscontacts` version.
- The "claim" logic uses `self.env.user.partner_id`; ensure each committee member's Odoo user is linked to their `res.partner` member record (which is the existing elkscontacts norm).
- This is the first proper v1 — expect some friction on the very first install (a missed xpath, a permission case I didn't think of). Report what breaks and I'll fix it.
