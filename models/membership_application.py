"""Extend elks.membership.application with the Investigation Workspace.

This module adds the investigator-facing workspace fields and actions to the
existing application model owned by `elkscontacts`. We intentionally do NOT
create a separate "investigation" record — the application IS the case.
"""

import re
from difflib import SequenceMatcher

from odoo import _, api, fields, models
from odoo.exceptions import UserError


# ---------- text/date helpers (also used by ofac_screen) ----------
def _normalize_name(n):
    n = (n or "").lower()
    n = re.sub(r"[^a-z\s]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def name_similarity(a, b):
    def variants(s):
        s = (s or "").strip()
        if not s:
            return []
        v = [_normalize_name(s)]
        if "," in s:
            last, _sep, rest = s.partition(",")
            if last and rest:
                v.append(_normalize_name(f"{rest.strip()} {last.strip()}"))
        return [x for x in v if x]

    va, vb = variants(a), variants(b)
    if not va or not vb:
        return 0.0
    return max(SequenceMatcher(None, x, y).ratio() for x in va for y in vb)


def parse_dob(s):
    s = (s or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$", s)
    if m:
        mo, da, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yr < 100:
            yr += 1900 if yr > 30 else 2000
        return yr, mo, da
    return None


def compare_dobs(a, b):
    pa, pb = parse_dob(a), parse_dob(b)
    if not pa or not pb:
        return "unknown"
    if pa == pb:
        return "exact"
    if pa[0] == pb[0]:
        return "near"
    return "mismatch"


class ElksMembershipApplication(models.Model):
    _inherit = "elks.membership.application"

    # ------------------------------------------------------------------
    # Workspace data: histories, references, aliases, checks, hits, flags
    # ------------------------------------------------------------------
    applicant_aliases = fields.Char(
        string="Aliases / Former Names",
        help="Comma-separated. Includes maiden name, nicknames used legally, "
             "prior legal names. Searched in the OFAC screen and cross-check engine.",
    )
    applicant_last4_ssn = fields.Char(
        string="Last 4 SSN", size=4,
        help="Last 4 digits of SSN, kept for identity disambiguation only.",
    )
    applicant_drivers_license = fields.Char(string="Driver's License # / State")

    investigation_address_history_ids = fields.One2many(
        "elks.investigation.address.history", "application_id",
        string="Residential history (10 years)",
    )
    investigation_employment_history_ids = fields.One2many(
        "elks.investigation.employment.history", "application_id",
        string="Employment history (10 years)",
    )
    investigation_reference_ids = fields.One2many(
        "elks.investigation.reference", "application_id",
        string="Investigation references",
    )

    investigation_check_ids = fields.One2many(
        "elks.investigation.check", "application_id",
        string="Background checks performed",
    )
    investigation_flag_ids = fields.One2many(
        "elks.investigation.flag", "application_id",
        string="Cross-check flags",
    )

    # ------------------------------------------------------------------
    # Counts & convenience
    # ------------------------------------------------------------------
    investigation_check_count = fields.Integer(compute="_compute_investigation_counts")
    investigation_hit_count = fields.Integer(compute="_compute_investigation_counts")
    investigation_flag_count = fields.Integer(compute="_compute_investigation_counts")
    investigation_pending_check_count = fields.Integer(compute="_compute_investigation_counts")

    investigation_states_in_history = fields.Char(
        compute="_compute_states_in_history",
        string="States in applicant history",
        help="Computed from the current applicant_state_id plus all residential "
             "and employment history rows. Drives which state portals get seeded.",
    )

    investigation_denial_reason = fields.Text(
        string="Denial Reason",
        help="Written explanation when the investigator submits an 'AGAINST' "
             "recommendation. Required for Deny.",
        tracking=True,
    )

    # Claim button — visible when the application is in 'investigation' stage,
    # the investigator slot is empty, AND the current user is on the Investigation
    # Committee.
    investigation_can_claim = fields.Boolean(
        compute="_compute_investigation_can_claim",
        help="True if the current user can claim this unassigned investigation.",
    )

    # Workspace "is mine" filter helper for the inbox view
    investigation_is_mine = fields.Boolean(
        compute="_compute_investigation_is_mine",
        search="_search_investigation_is_mine",
        help="True for investigations assigned to the current user.",
    )

    @api.depends("investigation_check_ids", "investigation_check_ids.hit_ids",
                 "investigation_flag_ids", "investigation_check_ids.result_summary")
    def _compute_investigation_counts(self):
        for r in self:
            r.investigation_check_count = len(r.investigation_check_ids)
            r.investigation_hit_count = sum(len(c.hit_ids) for c in r.investigation_check_ids)
            r.investigation_flag_count = len(r.investigation_flag_ids)
            r.investigation_pending_check_count = sum(
                1 for c in r.investigation_check_ids if c.result_summary == "pending"
            )

    @api.depends("applicant_state_id",
                 "investigation_address_history_ids.state_code",
                 "investigation_employment_history_ids.state_code")
    def _compute_states_in_history(self):
        for r in self:
            codes = []
            if r.applicant_state_id and r.applicant_state_id.code:
                codes.append(r.applicant_state_id.code)
            for a in r.investigation_address_history_ids:
                if a.state_code and a.state_code not in codes:
                    codes.append(a.state_code)
            for e in r.investigation_employment_history_ids:
                if e.state_code and e.state_code not in codes:
                    codes.append(e.state_code)
            r.investigation_states_in_history = ", ".join(codes)

    @api.depends("stage", "investigator_id", "investigation_committee_member_ids")
    def _compute_investigation_can_claim(self):
        my_partner = self.env.user.partner_id
        for r in self:
            r.investigation_can_claim = (
                r.stage == "investigation"
                and not r.investigator_id
                and my_partner in r.investigation_committee_member_ids
            )

    def _compute_investigation_is_mine(self):
        my_partner = self.env.user.partner_id
        for r in self:
            r.investigation_is_mine = r.investigator_id and r.investigator_id == my_partner

    def _search_investigation_is_mine(self, operator, value):
        my_partner = self.env.user.partner_id
        if operator == "=" and value:
            return [("investigator_id", "=", my_partner.id)]
        if operator == "=" and not value:
            return [("investigator_id", "!=", my_partner.id)]
        if operator == "!=" and value:
            return [("investigator_id", "!=", my_partner.id)]
        return []

    # ------------------------------------------------------------------
    # Helper: which states should we search for this applicant?
    # ------------------------------------------------------------------
    def _investigation_state_codes(self):
        self.ensure_one()
        codes = []
        if self.applicant_state_id and self.applicant_state_id.code:
            codes.append(self.applicant_state_id.code)
        for a in self.investigation_address_history_ids:
            if a.state_code and a.state_code not in codes:
                codes.append(a.state_code)
        for e in self.investigation_employment_history_ids:
            if e.state_code and e.state_code not in codes:
                codes.append(e.state_code)
        return codes

    # ------------------------------------------------------------------
    # Workspace actions
    # ------------------------------------------------------------------
    def action_investigation_claim(self):
        """First investigator to open an unassigned investigation claims it."""
        self.ensure_one()
        if self.stage != "investigation":
            raise UserError(_("Application is not currently in the investigation stage."))
        if self.investigator_id:
            raise UserError(
                _("This investigation is already assigned to %s.") % self.investigator_id.name
            )
        if self.env.user.partner_id not in self.investigation_committee_member_ids:
            raise UserError(
                _("Only Investigation Committee members can claim an investigation.")
            )
        self.write({
            "investigator_id": self.env.user.partner_id.id,
            "date_investigation_assigned": fields.Date.context_today(self),
        })
        self.message_post(
            body=_("<strong>Investigation claimed</strong> by %s.") % self.env.user.name,
            message_type="comment", subtype_xmlid="mail.mt_note",
        )

    def action_investigation_seed_checks(self):
        """Pre-create a Check record for every portal that applies to this
        applicant's jurisdictions. Called automatically when the application
        enters the investigation stage, but can be re-run if histories change.

        Uses sudo() because the user advancing the application (often a
        Secretary or proposer) may not be in the Investigation Committee
        groups that have direct write access to Check records. The seeding
        is a system-managed side effect of the workflow transition; the
        Check ACLs still govern who can later edit those records.
        """
        Portal = self.env["elks.portal"].sudo()
        Check = self.env["elks.investigation.check"].sudo()
        for rec in self:
            existing = {(c.jurisdiction_code, c.source_code) for c in rec.investigation_check_ids}
            jurisdictions = ["NATIONAL"] + rec._investigation_state_codes()
            for juris in jurisdictions:
                for p in Portal.search([("jurisdiction_code", "=", juris),
                                         ("active", "=", True)]):
                    if (p.jurisdiction_code, p.source_code) in existing:
                        continue
                    Check.create({
                        "application_id": rec.id,
                        "jurisdiction_code": p.jurisdiction_code,
                        "source_code": p.source_code,
                        "source_label": p.source_label,
                        "source_type": p.source_type or "court",
                        "url": p.url,
                        "hint": p.hint,
                        "is_automated": p.is_automated,
                        "result_summary": "pending",
                    })
        return True

    def action_investigation_run_ofac(self):
        """Run the automated OFAC SDN screen for this application."""
        self.ensure_one()
        result = self.env["elks.ofac.screen"].screen_application(self)
        # Remove any previous OFAC check
        prev = self.investigation_check_ids.filtered(
            lambda c: c.jurisdiction_code == "NATIONAL" and c.source_code == "OFAC SDN"
        )
        prev.sudo().unlink()
        # Create the new check (sudo — system-driven, not a manual user create)
        check_vals = {
            "application_id": self.id,
            "jurisdiction_code": "NATIONAL",
            "source_code": "OFAC SDN",
            "source_label": "OFAC SDN (automated, official Treasury CSV)",
            "url": "https://www.treasury.gov/ofac/downloads/sdn.csv",
            "date_checked": fields.Date.today(),
            "operator_id": self.env.user.id,
            "is_automated": True,
            "result_summary": "no_records" if not result["hits"] else "match_found",
            "operator_notes": result["summary"],
            "hit_ids": [(0, 0, {
                "name_on_record": h["sdn_name"],
                "case_number": f"OFAC#{h['ent_num']}",
                "charges": f"OFAC SDN — Program: {h['program']}",
                "disposition": f"Listed (Title: {h.get('title','-')})",
                "notes": (h.get("remarks") or "")[:500],
                "similarity_score": h["score"],
            }) for h in result["hits"]],
        }
        self.env["elks.investigation.check"].sudo().create(check_vals)
        if not result["hits"]:
            self.message_post(
                body=_("Automated OFAC screen — no matches above 0.85 similarity. "
                       "%s individuals searched.") % result["searched"],
                message_type="comment", subtype_xmlid="mail.mt_note",
            )
        else:
            self.message_post(
                body=_("⚠ Automated OFAC screen — %d possible match(es) require review.")
                % len(result["hits"]),
                message_type="comment", subtype_xmlid="mail.mt_note",
            )
        return True

    def action_investigation_run_cross_check(self):
        """Compute flags based on the current set of checks/hits vs applicant data."""
        self.ensure_one()
        # sudo — flags are a system-managed audit trail; any user authorized
        # to write to the application can trigger a cross-check refresh.
        self.investigation_flag_ids.sudo().unlink()
        flag_vals = []
        Flag = self.env["elks.investigation.flag"].sudo()

        names = [self.applicant_display_name or ""]
        if self.applicant_first_name and self.applicant_last_name:
            names.append(f"{self.applicant_first_name} {self.applicant_last_name}")
        names += [
            x.strip() for x in (self.applicant_aliases or "").split(",") if x.strip()
        ]
        if self.applicant_maiden_name and self.applicant_first_name:
            names.append(f"{self.applicant_first_name} {self.applicant_maiden_name}")
        names = [n for n in names if n]

        states_in_history = set(self._investigation_state_codes())
        states_checked = {
            c.jurisdiction_code for c in self.investigation_check_ids
            if c.jurisdiction_code and c.jurisdiction_code != "NATIONAL"
            and c.result_summary not in ("pending", "skipped")
        }

        # 1) State coverage
        for s in sorted(states_in_history - states_checked):
            flag_vals.append({
                "application_id": self.id,
                "severity": "high",
                "category": "coverage",
                "message": _("Applicant has history in %s but no checks completed for that state.") % s,
            })

        # 2) Nationwide essentials
        nat_codes_done = {
            c.source_code for c in self.investigation_check_ids
            if c.jurisdiction_code == "NATIONAL"
            and c.result_summary not in ("pending", "skipped")
        }
        for required in ("NSOPW", "OFAC SDN", "CourtListener"):
            if required not in nat_codes_done:
                flag_vals.append({
                    "application_id": self.id,
                    "severity": "medium",
                    "category": "coverage",
                    "message": _("Nationwide source not yet completed: %s.") % required,
                })

        # 3) Hit-level checks
        dob_str = fields.Date.to_string(self.applicant_date_of_birth) if self.applicant_date_of_birth else ""
        history_tokens = set()
        for a in self.investigation_address_history_ids:
            if a.state_code:
                history_tokens.add(a.state_code.lower())
            if a.city:
                history_tokens.add(a.city.lower())
        if self.applicant_state_id and self.applicant_state_id.code:
            history_tokens.add(self.applicant_state_id.code.lower())
        if self.applicant_city:
            history_tokens.add(self.applicant_city.lower())

        for chk in self.investigation_check_ids:
            for hit in chk.hit_ids:
                # Name similarity
                sims = [name_similarity(hit.name_on_record, n) for n in names if n]
                best = max(sims) if sims else 0.0
                # Save similarity back to the hit for display
                hit.sudo().similarity_score = round(best, 2)
                if best < 0.70:
                    flag_vals.append({
                        "application_id": self.id,
                        "severity": "medium",
                        "category": "identity",
                        "message": _(
                            "[%(j)s/%(s)s] case %(c)s — name on record '%(n)s' has low "
                            "similarity to applicant (%(b).2f). Verify hit belongs to applicant."
                        ) % {"j": chk.jurisdiction_code, "s": chk.source_code,
                             "c": hit.case_number or "(no #)",
                             "n": hit.name_on_record, "b": best},
                    })
                cmp = compare_dobs(hit.dob_on_record, dob_str)
                if cmp == "mismatch":
                    flag_vals.append({
                        "application_id": self.id,
                        "severity": "high",
                        "category": "identity",
                        "message": _(
                            "[%(j)s/%(s)s] case %(c)s — DOB on record '%(d)s' does NOT match "
                            "applicant DOB '%(p)s'. LIKELY NOT the same person."
                        ) % {"j": chk.jurisdiction_code, "s": chk.source_code,
                             "c": hit.case_number or "(no #)",
                             "d": hit.dob_on_record, "p": dob_str},
                    })
                elif cmp == "near":
                    flag_vals.append({
                        "application_id": self.id,
                        "severity": "low",
                        "category": "identity",
                        "message": _(
                            "[%(j)s/%(s)s] case %(c)s — DOB '%(d)s' close but not exact match "
                            "to applicant '%(p)s'. Could be transcription error."
                        ) % {"j": chk.jurisdiction_code, "s": chk.source_code,
                             "c": hit.case_number or "(no #)",
                             "d": hit.dob_on_record, "p": dob_str},
                    })
                if hit.address_on_record and history_tokens:
                    addr_low = hit.address_on_record.lower()
                    if not any(t in addr_low for t in history_tokens):
                        flag_vals.append({
                            "application_id": self.id,
                            "severity": "medium",
                            "category": "history",
                            "message": _(
                                "[%(j)s/%(s)s] case %(c)s — address on record '%(a)s' not in "
                                "applicant's disclosed history. Verify."
                            ) % {"j": chk.jurisdiction_code, "s": chk.source_code,
                                 "c": hit.case_number or "(no #)", "a": hit.address_on_record},
                        })
                # County-mismatch flag — the specific court isn't in any city
                # / state the applicant disclosed living or working in.
                if hit.court and history_tokens:
                    court_low = hit.court.lower()
                    if not any(t in court_low for t in history_tokens):
                        flag_vals.append({
                            "application_id": self.id,
                            "severity": "medium",
                            "category": "history",
                            "message": _(
                                "[%(j)s/%(s)s] case %(c)s in '%(court)s' — that court is in a "
                                "county the applicant did not disclose living or working in. "
                                "Likely a different person sharing the name, OR an undisclosed "
                                "presence in that jurisdiction. Triage manually."
                            ) % {"j": chk.jurisdiction_code, "s": chk.source_code,
                                 "c": hit.case_number or "(no #)", "court": hit.court},
                        })
                # Role-based context — Plaintiff/Petitioner hits are usually
                # exculpatory, so demote them to INFO so they're not weighted
                # the same as Defendant/Judgment-Debtor hits.
                if hit.role in ("plaintiff", "petitioner"):
                    flag_vals.append({
                        "application_id": self.id,
                        "severity": "info",
                        "category": "context",
                        "message": _(
                            "[%(j)s/%(s)s] case %(c)s — applicant appears as %(role)s "
                            "(usually exculpatory, not concerning)."
                        ) % {"j": chk.jurisdiction_code, "s": chk.source_code,
                             "c": hit.case_number or "(no #)", "role": hit.role},
                    })
                if hit.case_number and not hit.disposition:
                    flag_vals.append({
                        "application_id": self.id,
                        "severity": "info",
                        "category": "completeness",
                        "message": _("[%(j)s/%(s)s] case %(c)s has no recorded disposition.")
                        % {"j": chk.jurisdiction_code, "s": chk.source_code, "c": hit.case_number},
                    })

        if flag_vals:
            Flag.create(flag_vals)
        self.message_post(
            body=_("Cross-check produced %d flag(s).") % len(flag_vals),
            message_type="comment", subtype_xmlid="mail.mt_note",
        )
        return True

    def action_investigation_accept(self):
        """Recommend FOR membership. Sets investigation_result and moves the
        application to Balloting using the existing workflow action."""
        self.ensure_one()
        if self.stage != "investigation":
            raise UserError(_("Only applications in the investigation stage can be accepted."))
        if self.investigator_id != self.env.user.partner_id:
            raise UserError(_(
                "Only the assigned investigator (%s) can submit a recommendation."
            ) % (self.investigator_id.name or "(none)"))
        # Run cross-check one more time so the final report reflects current state
        self.action_investigation_run_cross_check()
        self.write({
            "investigation_result": "favorable",
            "date_investigation_complete": fields.Date.context_today(self),
        })
        self.message_post(
            body=_("<strong>Investigation recommendation: APPROVE.</strong> "
                   "Moving to Balloting."),
            message_type="comment", subtype_xmlid="mail.mt_note",
        )
        # Delegate to the existing workflow transition (handles activities, history, etc.)
        return self.action_move_to_balloting()

    def action_investigation_deny(self):
        """Recommend AGAINST. Requires a written denial reason. Advances the
        application to Balloting with investigation_result='unfavorable' so
        the membership can still vote — the unfavorable recommendation
        appears on the report and the chair sees the basis on the ballot
        record."""
        self.ensure_one()
        if self.stage != "investigation":
            raise UserError(_("Only applications in the investigation stage can be denied."))
        if self.investigator_id != self.env.user.partner_id:
            raise UserError(_(
                "Only the assigned investigator (%s) can submit a recommendation."
            ) % (self.investigator_id.name or "(none)"))
        if not (self.investigation_denial_reason or "").strip():
            raise UserError(_(
                "Please enter a written Denial Reason before submitting a Deny "
                "recommendation. The Lodge needs this in writing to act on the "
                "recommendation at balloting and to comply with FCRA adverse-action "
                "procedures if a third-party report informed the decision."
            ))
        self.action_investigation_run_cross_check()
        self.write({
            "investigation_result": "unfavorable",
            "date_investigation_complete": fields.Date.context_today(self),
        })
        self.message_post(
            body=_("<strong>Investigation recommendation: DENY.</strong><br/>"
                   "<em>Reason: %s</em><br/><br/>"
                   "Moving to Balloting with unfavorable recommendation. "
                   "The Lodge will vote with this recommendation on file.")
                 % self.investigation_denial_reason,
            message_type="comment", subtype_xmlid="mail.mt_note",
        )
        # Schedule a heads-up activity for the chair so they know an
        # unfavorable application is about to be balloted on.
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            summary=_("Unfavorable investigation moved to Balloting — review before vote"),
            user_id=self.env.user.id,
            note=_("Application: %(ref)s<br/>Applicant: %(name)s<br/>"
                   "Investigator: %(inv)s<br/>Reason: %(reason)s",
                   ref=self.name, name=self.applicant_display_name,
                   inv=self.investigator_id.name or "(none)",
                   reason=self.investigation_denial_reason),
        )
        # Delegate to the existing workflow transition (same as APPROVE path)
        return self.action_move_to_balloting()

    def action_investigation_print_summary(self):
        """Print the 1-page Investigation Summary (default)."""
        self.ensure_one()
        return self.env.ref(
            "elks_investigation_workspace.action_report_investigation_summary"
        ).report_action(self)

    def action_investigation_print_pdf(self):
        """Print the multi-page Detailed Investigation Findings Report."""
        self.ensure_one()
        return self.env.ref(
            "elks_investigation_workspace.action_report_investigation"
        ).report_action(self)

    def action_investigation_download_docx(self):
        self.ensure_one()
        return self.env["elks.investigation.docx.builder"].build_attachment_action(self)

    # ------------------------------------------------------------------
    # Hook: when application moves to investigation, auto-seed checks
    # ------------------------------------------------------------------
    def write(self, vals):
        res = super().write(vals)
        if vals.get("stage") == "investigation":
            for rec in self:
                if not rec.investigation_check_ids:
                    rec.action_investigation_seed_checks()
        return res
