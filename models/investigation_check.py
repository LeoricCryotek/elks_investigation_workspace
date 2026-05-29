from odoo import api, fields, models


class InvestigationCheck(models.Model):
    """One record per source consulted during the investigation of a
    membership application. Bound directly to elks.membership.application
    (no separate investigation case record — the application IS the case)."""

    _name = "elks.investigation.check"
    _description = "Investigation Check (single portal lookup)"
    _order = "jurisdiction_code, source_code"

    application_id = fields.Many2one(
        "elks.membership.application", required=True, ondelete="cascade",
        string="Application", index=True,
    )

    jurisdiction_code = fields.Char(required=True,
                                     help="'NATIONAL' or 2-letter state code")
    source_code = fields.Char(required=True)
    source_label = fields.Char(required=True)
    source_type = fields.Selection(
        [("court", "Court records"),
         ("sex_offender", "Sex offender registry"),
         ("corrections", "Department of Corrections"),
         ("federal_court", "Federal court records"),
         ("sanctions", "Sanctions / OFAC"),
         ("social_media", "Social media"),
         ("identity", "Identity / public records aggregator"),
         ("recorder", "County recorder / property"),
         ("other", "Other")],
        default="court",
        help="Copied from the portal at seed time; controls which fields are "
             "shown on captured Hits.",
    )
    url = fields.Char(string="Portal URL")
    hint = fields.Text(string="Operator hint")

    date_checked = fields.Date()
    operator_id = fields.Many2one("res.users", string="Operator")
    is_automated = fields.Boolean(string="Automated source")

    result_summary = fields.Selection(
        [("pending", "Pending"),
         ("no_records", "No records found"),
         ("match_found", "Match found"),
         ("possible_match", "Possible match — needs verification"),
         ("portal_unavailable", "Portal unavailable"),
         ("skipped", "Skipped")],
        default="pending",
    )
    operator_notes = fields.Text(string="Operator notes")

    hit_ids = fields.One2many("elks.investigation.hit", "check_id",
                               string="Records captured")
    hit_count = fields.Integer(compute="_compute_hit_count")

    @api.depends("hit_ids")
    def _compute_hit_count(self):
        for r in self:
            r.hit_count = len(r.hit_ids)

    def action_open_portal(self):
        """Open the portal URL in a new tab. Operator does the search by hand."""
        self.ensure_one()
        if not self.url:
            return False
        # Auto-set operator + date when first opened.
        if not self.operator_id:
            self.operator_id = self.env.user.id
        if not self.date_checked:
            self.date_checked = fields.Date.today()
        return {
            "type": "ir.actions.act_url",
            "url": self.url,
            "target": "new",
        }

    def action_mark_no_records(self):
        for r in self:
            r.write({
                "result_summary": "no_records",
                "date_checked": fields.Date.today(),
                "operator_id": self.env.user.id,
            })

    def action_mark_skipped(self):
        for r in self:
            r.write({
                "result_summary": "skipped",
                "date_checked": fields.Date.today(),
                "operator_id": self.env.user.id,
            })

    def action_open_bulk_parse_wizard(self):
        """Open the Paste & Parse wizard pre-bound to this check.

        Implemented as a method (not a context-on-action button) so the
        Odoo 19 view validator doesn't complain about active_id not being
        a field on this model when the form is rendered embedded inside
        the application's One2many.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Paste & Parse Search Results",
            "res_model": "elks.investigation.bulk_parse.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_check_id": self.id},
        }
