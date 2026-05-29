from odoo import fields, models


class InvestigationAddressHistory(models.Model):
    """Past residence row attached to a membership application.

    The Elks investigator uses these to know which state repositories to
    search for this applicant. Captured during the investigation, not from
    the proposal form (the proposal form only has current address).
    """

    _name = "elks.investigation.address.history"
    _description = "Investigation: applicant residential history (10 years)"
    _order = "sequence, date_to desc, date_from desc"

    application_id = fields.Many2one(
        "elks.membership.application", required=True, ondelete="cascade",
        string="Application",
    )
    sequence = fields.Integer(default=10)
    street = fields.Char(required=True)
    city = fields.Char()
    state_id = fields.Many2one("res.country.state", string="State")
    state_code = fields.Char(related="state_id.code", store=True,
                              string="State (code)",
                              help="2-letter state code, used by the check seeding logic.")
    zip = fields.Char()
    date_from = fields.Char(string="From (MM/YYYY)")
    date_to = fields.Char(string="To (MM/YYYY or 'present')")


class InvestigationEmploymentHistory(models.Model):
    _name = "elks.investigation.employment.history"
    _description = "Investigation: applicant employment history (10 years)"
    _order = "sequence, date_to desc, date_from desc"

    application_id = fields.Many2one(
        "elks.membership.application", required=True, ondelete="cascade",
        string="Application",
    )
    sequence = fields.Integer(default=10)
    employer = fields.Char(required=True)
    city = fields.Char()
    state_id = fields.Many2one("res.country.state", string="State")
    state_code = fields.Char(related="state_id.code", store=True,
                              string="State (code)")
    role = fields.Char(string="Role / title")
    date_from = fields.Char(string="From (MM/YYYY)")
    date_to = fields.Char(string="To (MM/YYYY or 'present')")


class InvestigationReference(models.Model):
    """Personal references collected for the investigation (separate from
    the existing proposer/endorser — these are 3+ non-related references
    the committee actually contacts and documents)."""

    _name = "elks.investigation.reference"
    _description = "Investigation: applicant reference contact"
    _order = "sequence, id"

    application_id = fields.Many2one(
        "elks.membership.application", required=True, ondelete="cascade",
        string="Application",
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    relationship = fields.Char()
    phone = fields.Char()
    email = fields.Char()
    years_known = fields.Char()
    contacted_on = fields.Date()
    recommendation = fields.Selection(
        [("for", "FOR — recommends admission"),
         ("against", "AGAINST"),
         ("neutral", "NEUTRAL"),
         ("no_response", "NO RESPONSE / unreachable")],
    )
    notes = fields.Text(string="Quote / notes from reference call")
