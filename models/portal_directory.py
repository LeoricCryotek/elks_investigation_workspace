from odoo import fields, models


class Portal(models.Model):
    """A records-access portal the committee can search.

    Includes nationwide federal sources, identity-verification sites, social
    media, and per-state portals (court records, sex offender registry,
    Department of Correction inmate search). Seeded from
    `data/portal_directory_data.xml` on install; editable from the UI
    afterward by Investigation Committee chairs / Secretary.
    """

    _name = "elks.portal"
    _description = "Records-access portal (state or federal)"
    _order = "jurisdiction_code, sequence, source_code"
    _rec_name = "display_name"

    jurisdiction_code = fields.Char(
        string="Jurisdiction", required=True,
        help="'NATIONAL' for federal/nationwide; 2-letter state code otherwise (e.g., 'ID', 'WA').",
    )
    source_code = fields.Char(string="Source code", required=True)
    source_label = fields.Char(string="Source label", required=True)
    url = fields.Char(string="URL", required=True)
    hint = fields.Text(
        string="Operator hint",
        help="What the committee member should know before opening the portal "
             "(e.g., 'Click Accept on the Disclaimer modal first', 'Use separate "
             "First/Last fields').",
    )
    sequence = fields.Integer(default=10)
    is_automated = fields.Boolean(
        string="Automated",
        help="True if the module can screen this source without operator input "
             "(currently only OFAC SDN).",
    )
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
        required=True,
        string="Source Type",
        help="Drives which fields are shown on the Hit form. Social media "
             "checks need profile URL + visibility; court records need case "
             "number + role + disposition.",
    )
    active = fields.Boolean(default=True)

    display_name = fields.Char(compute="_compute_display_name", store=True)

    _sql_constraints = [
        ("portal_uniq", "unique(jurisdiction_code, source_code)",
         "Each (jurisdiction, source code) pair must be unique."),
    ]

    def _compute_display_name(self):
        for r in self:
            r.display_name = f"{r.jurisdiction_code} — {r.source_code}: {r.source_label or ''}"
