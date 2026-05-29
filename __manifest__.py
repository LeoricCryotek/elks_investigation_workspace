{
    "name": "Elks Investigation Workspace",
    "version": "19.0.1.7.2",
    "category": "Membership / Investigation",
    "summary": "Investigator workspace for Elks membership applications: "
               "ticket-style worklist, FCRA-aware background checks, automated "
               "OFAC screen, Accept/Deny recommendations.",
    "description": """
Elks Investigation Workspace
============================

Adds a dedicated worklist + workspace UI for the Investigation Committee
on top of the existing `elks.membership.application` workflow.

What it adds
------------
* **My Investigations inbox** — a ticket-style worklist menu showing every
  application in the 'Under Investigation' stage assigned to the current
  user, plus an "Unassigned" bucket they can claim from.
* **"Claim This Investigation"** button — first investigator to open an
  unassigned investigation becomes the assigned investigator.
* **Investigation Workspace tab** on the application form: all applicant
  info on one screen, plus residential history, employment history,
  per-jurisdiction background checks, cross-check flags, and recommendation
  controls.
* **Residential and Employment history** models (10-year lookback) so the
  investigator knows which state repositories to search.
* **Automated OFAC SDN screen** — downloads Treasury's official Specially
  Designated Nationals CSV and searches it locally against the applicant
  name and aliases. Zero operator input on clean matches.
* **Portal directory** seeded with the official .gov / .us records portals
  for nationwide and per-state lookups (NSOPW, CourtListener, state court
  records, state sex offender registries, state DOC inmate search, plus the
  FCRA-safe Elks-manual sites: BlackBookOnline, Anywho, Facebook,
  Instagram, X, LinkedIn).
* **Per-check workflow** — for each portal, an "Open Portal" button
  launches the official site in a new tab; the operator does the search by
  hand (no scraping) and records findings.
* **Cross-check engine** flags state-coverage gaps, name/DOB mismatches
  between hits and applicant identity, address inconsistencies, etc.
* **Accept / Deny buttons** on the workspace:
    - **Accept**: sets investigation_result = 'favorable' and calls
      `action_move_to_balloting()` on the existing application workflow.
    - **Deny**: sets investigation_result = 'unfavorable' and captures a
      written denial reason; leaves the application in 'investigation'
      stage so the committee chair can decide whether to formally reject
      or send back for more info.
* **PDF report** (QWeb) + **Word report** (python-docx) for the chair.

What this module DOES NOT do — and why
--------------------------------------
It does not scrape state court portals, NSOPW, or other government records
sites. Those sites' terms of service prohibit automated access, and producing
fully automated consumer reports for membership-eligibility decisions would
turn the lodge into a "consumer reporting agency" under the federal Fair
Credit Reporting Act. Only OFAC's published CSV is fully automated, because
Treasury distributes it specifically for this purpose.
""",
    "author": "Lewiston Elks Lodge #896 / Tooling",
    "website": "https://dannysantiago.info",
    "license": "LGPL-3",
    "depends": ["elkscontacts", "mail"],
    "external_dependencies": {
        # Use the PyPI name; the module is imported as `docx` but pip-installed as `python-docx`.
        "python": ["python-docx"],
    },
    "data": [
        "security/elks_investigation_groups.xml",
        "security/ir.model.access.csv",
        "data/portal_directory_data.xml",
        "views/bulk_parse_wizard_views.xml",
        "views/committee_assign_wizard_views.xml",
        "views/investigation_workspace_views.xml",
        "views/portal_views.xml",
        "views/menu.xml",
        "reports/investigation_report_actions.xml",
        "reports/investigation_report_summary_templates.xml",
        "reports/investigation_report_templates.xml",
    ],
    "installable": True,
    "application": True,
}
