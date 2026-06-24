# Elks Investigation Workspace — Odoo Module Hardening Tasks

## Context
Target module: `/Users/dannyadmin/Documents/GitHub/elks_investigation_workspace/`
Dependent module: `elkscontacts` (must be installed first)
Odoo version: 19
Python env: use the same venv as the Odoo MCP server unless told otherwise

Goal: harden the module before production use. Do NOT change behavior without explicit instruction. Preserve all existing fields, views, workflows, and report templates unless a task says to modify them. Add code; do not remove working logic.

## Task 1 — Required-field gate before checks can be seeded

In `models/membership_application.py`, update `action_investigation_seed_checks` so it raises `UserError` if any of these are missing on `self`:
- `applicant_first_name`
- `applicant_last_name`
- `applicant_date_of_birth`
- `applicant_state_id`
- `applicant_street` OR `applicant_city`

Message must name the missing fields. Do not block entering investigation stage; only block auto-seeding checks until the required data exists.

## Task 2 — Stage transition enforcement

In `models/membership_application.py`, add a constraint or write-time guard so that moving `stage` to `balloting` only succeeds if:
- `investigation_result` is set (`favorable` or `unfavorable`), OR
- the user explicitly holds the Investigation Chair role (use the same group logic already in the module if available; if not, fall back to raising UserError with a clear message “Investigation recommendation is required before balloting.”)

Do not break the existing `action_move_to_balloting` workflow hook.

## Task 3 — Record-level access rules for Investigation Committee

Create new `security/ir.model.access.csv` entries (or append to the existing file) that add `ir.rule` records restricting read/write on these models to committee members only:
- `elks.membership.application` when `stage = 'investigation'`
- `elks.investigation.check`
- `elks.investigation.hit`
- `elks.investigation.flag`
- `elks.investigation.address.history`
- `elks.investigation.employment.history`
- `elks.investigation.reference`

Non-committee members should still be able to read records once the application leaves investigation stage. Use existing groups in the module as the base; if those groups don’t exist, define them in `security/elks_investigation_groups.xml` first.

## Task 4 — OFAC screen failure handling

In `models/ofac_screen.py`, update the screen logic so that if the Treasury CSV download fails or cURL/HTTP raises, the module creates the OFAC check with:
- `result_summary = 'portal_unavailable'`
- `operator_notes` explaining the failure (“OFAC CSV download failed: <error reason>”)
- No hit rows created

If download succeeds but parsing yields zero individuals, keep the current behavior (`no_records`).

## Task 5 — Claim logic user-partner validation

In `models/membership_application.py`, update `action_investigation_claim` to check whether `self.env.user.partner_id` exists before the committee membership `in` check. If partner is missing, raise `UserError("Your user account is not linked to a member record. Ask the Secretary to update your Access Rights before claiming investigations.")`.

## Task 6 — Idempotent seed + chatter logging

Update `action_investigation_seed_checks` to post a chatter message after seeding:
- “Investigation checks seeded for jurisdictions: <comma list>”
- Include how many new checks were created
- Do not duplicate existing checks

## Task 7 — One-way recommendation lock

In `models/membership_application.py`, after `action_investigation_accept` and `action_investigation_deny` set `investigation_result` and `date_investigation_complete`, add a write-time guard that prevents editing those two fields again unless:
- the current user is the Investigation Chair, AND
- a new field `investigation_reopen_reason` is filled in

Add `investigation_reopen_reason` as a new `text` field on the model. If `investigation_result` is already set and the user lacks chair role, raise `UserError("Investigation recommendation is already submitted. Only the Chair can reopen this investigation, and must provide a reason.")`

## Task 8 — Base view install validation

In `__manifest__.py` or in a new `models/install_hooks.py`, add a post-init hook that checks whether `elkscontacts.view_elks_membership_application_form` exists. If not, raise `UserError` with: "Base view 'elkscontacts.view_elks_membership_application_form' not found. Install or update `elkscontacts` first, then update this module." If found, log success.

If `models/install_hooks.py` is created, import it in `__init__.py`.

## Task 9 — Manifest and missing report audit

Review `reports/` directory. The manifest references three reports (summary PDF, detailed PDF, Word docx). If the Python builder for Word is not present in the repo, either:
- add a stub builder under `models/investigation_docx_builder.py` that raises `UserError("Word report builder is not installed. Install python-docx or use the PDF reports.")` when called, OR
- remove the “Download Word” button/view reference until the builder exists

Do not silently break the button.

## Verification
After all changes:
1. Run `python3 -m py_compile` on every `.py` file under `models/`, `wizards/`, and `__init__.py`
2. Start Odoo and try to install/upgrade the module in a test database
3. Verify:
   - Cannot seed checks on an application missing required fields
   - Cannot move to balloting without a recommendation (or chair role)
   - OFAC failure produces a portal_unavailable check row
   - Claim fails with a clear message when user has no partner link
   - Re-submitting a recommendation requires chair + reopen reason

## Constraints
- Do not modify models, fields, or views in `elkscontacts`
- Do not change existing report templates unless the task explicitly says to
- Do not remove or rename existing fields
- Preserve existing XML IDs; if you add new records, use `elks_investigation_workspace.` prefix
- Commit or diff should be clean against current master; do not leave backup files or stray edits
