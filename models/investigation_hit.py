from odoo import api, fields, models


class InvestigationHit(models.Model):
    _name = "elks.investigation.hit"
    _description = "Captured record from a portal search"
    _inherit = ["mail.thread"]
    _order = "id"

    check_id = fields.Many2one("elks.investigation.check", required=True,
                                ondelete="cascade", string="Check")
    application_id = fields.Many2one(related="check_id.application_id",
                                      store=True, readonly=True)

    # Source type relayed from the parent Check; drives which fields are shown
    source_type = fields.Selection(related="check_id.source_type", store=True, readonly=True)

    # ------------------------------------------------------------------
    # Court / sanctions / corrections fields (the "default" set)
    # ------------------------------------------------------------------
    name_on_record = fields.Char(string="Name on record")
    dob_on_record = fields.Char(string="DOB on record")
    address_on_record = fields.Char(string="Address on record")
    case_number = fields.Char(string="Case / docket #")
    offense_date = fields.Char(string="Offense / filing date")
    charges = fields.Text()
    disposition = fields.Char()
    notes = fields.Text()
    similarity_score = fields.Float(
        string="Name similarity",
        help="Similarity score (0-1) between this name and the applicant's. "
             ">= 0.85 is a strong match; < 0.70 likely a different person.",
        digits=(3, 2),
    )
    court = fields.Char(
        string="Specific Court",
        help="The specific court that filed the case (e.g., 'Pierce County Superior Court'). "
             "Separate from the state jurisdiction code on the parent Check.",
    )
    role = fields.Selection(
        [("defendant", "Defendant"),
         ("respondent", "Respondent"),
         ("plaintiff", "Plaintiff"),
         ("judgment_debtor", "Judgment Debtor"),
         ("petitioner", "Petitioner"),
         ("witness", "Witness"),
         ("other", "Other")],
        string="Applicant Role",
        help="The role in which the applicant appears in this case. Plaintiffs "
             "and Petitioners are usually NOT concerning; Defendants and Judgment "
             "Debtors are.",
    )

    # ------------------------------------------------------------------
    # Social media fields — shown only when parent check's source_type == 'social_media'
    # ------------------------------------------------------------------
    profile_url = fields.Char(
        string="Profile URL",
        help="Link to the public profile the operator located. Leave blank if "
             "the search returned no matching profile.",
    )
    account_visibility = fields.Selection(
        [("public", "Public (could view posts)"),
         ("private", "Private (locked / friends-only)"),
         ("not_found", "No matching account found"),
         ("removed_deactivated", "Account removed or deactivated")],
        string="Account visibility",
        help="What the operator saw when they reached the profile page.",
    )
    is_publicly_problematic = fields.Boolean(
        string="Publicly problematic?",
        help="Tick if any publicly-visible post, photo, or behavior raised a "
             "concern under the Elks manual's 'socially and fraternally "
             "acceptable' standard. Capture screenshots in the chatter and "
             "explain in Notes.",
    )

    # Display helper — uses the first social field that's populated for list views
    summary_label = fields.Char(compute="_compute_summary_label", store=False)

    @api.depends("source_type", "name_on_record", "profile_url",
                 "account_visibility", "is_publicly_problematic")
    def _compute_summary_label(self):
        for r in self:
            if r.source_type == "social_media":
                vis = dict(r._fields["account_visibility"].selection).get(
                    r.account_visibility, "(no result)"
                )
                flag = " ⚠ PROBLEMATIC" if r.is_publicly_problematic else ""
                r.summary_label = f"{r.profile_url or '(no profile)'} — {vis}{flag}"
            else:
                r.summary_label = r.name_on_record or "(unnamed)"


class InvestigationFlag(models.Model):
    _name = "elks.investigation.flag"
    _description = "Cross-check anomaly"
    _order = "severity, category"

    application_id = fields.Many2one("elks.membership.application",
                                      required=True, ondelete="cascade")
    severity = fields.Selection(
        [("high", "HIGH — review before recommending"),
         ("medium", "MEDIUM — verify before relying on this hit"),
         ("low", "LOW — minor inconsistency"),
         ("info", "INFO — completeness reminder")],
        required=True,
    )
    category = fields.Char(required=True)
    message = fields.Text(required=True)
