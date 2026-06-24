"""Install / upgrade hooks.

Verifies that critical base views in `elkscontacts` exist before the module
is loaded, so the user gets a clear remediation message rather than an
opaque view-inheritance failure deep in the loading log.
"""

import logging

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


REQUIRED_BASE_VIEWS = (
    "elkscontacts.view_elks_membership_application_form",
)


def pre_init_check(env):
    """Called before module install/upgrade. Verifies required base views
    from `elkscontacts` are present in the database."""
    IrModelData = env["ir.model.data"].sudo()
    missing = []
    for xmlid in REQUIRED_BASE_VIEWS:
        module, name = xmlid.split(".", 1)
        rec = IrModelData.search(
            [("module", "=", module), ("name", "=", name)], limit=1
        )
        if not rec:
            missing.append(xmlid)
    if missing:
        raise UserError(
            "Base view '%s' not found. Install or update `elkscontacts` first, "
            "then update this module." % missing[0]
        )
    _logger.info(
        "elks_investigation_workspace: base view check passed (%d view(s) verified).",
        len(REQUIRED_BASE_VIEWS),
    )
