"""Wizard: assign existing internal users to Investigation Committee roles.

The standard res.users action's "New" button opens a new-user creation form,
which is not what the chair wants. Instead this wizard lets them pick one
or more existing internal users from a dropdown and bulk-assign them to a
role level (Committee Member / Chairman / Administration).
"""

from odoo import _, api, fields, models


class CommitteeAssignWizard(models.TransientModel):
    _name = "elks.investigation.committee.assign.wizard"
    _description = "Add internal users to the Investigation Committee"

    user_ids = fields.Many2many(
        "res.users",
        string="Internal Users",
        domain="[('share', '=', False), ('active', '=', True)]",
        required=True,
        help="Pick one or more internal users from the dropdown. Each will "
             "be granted the chosen role.",
    )
    role_level = fields.Selection(
        [("committee", "Committee Member"),
         ("chair", "Chairman"),
         ("admin", "Administration")],
        default="committee",
        required=True,
        string="Role Level",
        help="Committee Member: works own + unassigned investigations. "
             "Chairman: sees all investigations. "
             "Administration: same as Chair plus Secretary backup access.",
    )

    def action_assign(self):
        self.ensure_one()
        group_xmlid = {
            "committee": "elks_investigation_workspace.group_elks_investigation_committee",
            "chair": "elks_investigation_workspace.group_elks_investigation_chair",
            "admin": "elks_investigation_workspace.group_elks_investigation_admin",
        }[self.role_level]
        group = self.env.ref(group_xmlid)
        role_label = dict(self._fields["role_level"].selection)[self.role_level]

        added = 0
        for user in self.user_ids:
            if group not in user.group_ids:
                user.sudo().write({"group_ids": [(4, group.id)]})
                added += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Roles assigned"),
                "message": _("%(n)d user(s) granted '%(role)s'.") % {
                    "n": added, "role": role_label,
                },
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
