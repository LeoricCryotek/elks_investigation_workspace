"""Auto-sync of Investigation Committee roles from the Lodge org state.

Three signals drive role assignment:

  1. Membership in the Investigation `elks.committee` —
     grants the Committee Member role.
  2. The Investigation committee `chair_id` —
     grants the Chairman role.
  3. The current Exalted Ruler (per `elks.officer.term`) plus anyone in
     the Lodge Secretary group — grants the Administration role.

Plus: anyone manually added to the Administration row in their Access
Rights tab keeps the role even if they don't match any of the above
(additive-only sync; never revokes).

A daily cron is the safety net. Write hooks on the source models trigger
an immediate re-sync so role changes are visible within seconds of the
Lodge changing the committee composition or the ER.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# res.users — owns the sync method
# ---------------------------------------------------------------------------
class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _sync_investigation_roles(self):
        """Add Investigation-related groups based on current Lodge state.

        Additive only. Idempotent. Safe to run from cron, hooks, or by
        clicking the Settings → 'Sync Now' button.
        """
        # Resolve the three target groups (may not exist if module not fully installed)
        try:
            g_committee = self.env.ref(
                "elks_investigation_workspace.group_elks_investigation_committee",
                raise_if_not_found=False,
            )
            g_chair = self.env.ref(
                "elks_investigation_workspace.group_elks_investigation_chair",
                raise_if_not_found=False,
            )
            g_admin = self.env.ref(
                "elks_investigation_workspace.group_elks_investigation_admin",
                raise_if_not_found=False,
            )
        except ValueError:
            return False
        if not (g_committee and g_chair and g_admin):
            return False

        Users = self.env["res.users"].sudo()
        Committee = self.env["elks.committee"].sudo()
        OfficerTerm = self.env["elks.officer.term"].sudo() if "elks.officer.term" in self.env else None

        added_committee = added_chair = added_admin = 0

        # --- 1) Investigation committee members → Committee Member group ---
        inv_committee = Committee.search([("name", "ilike", "investigation")], limit=1)
        if inv_committee:
            current_assignments = inv_committee.member_ids.filtered("is_current")
            cmte_partner_ids = current_assignments.mapped("partner_id").ids
            for user in Users.search([("partner_id", "in", cmte_partner_ids)]):
                if g_committee not in user.group_ids:
                    user.write({"group_ids": [(4, g_committee.id)]})
                    added_committee += 1

            # --- 2) Committee chair → Chairman group ---
            if inv_committee.chair_id:
                chair_user = Users.search(
                    [("partner_id", "=", inv_committee.chair_id.id)], limit=1
                )
                if chair_user and g_chair not in chair_user.group_ids:
                    chair_user.write({"group_ids": [(4, g_chair.id)]})
                    added_chair += 1

        # --- 3) Current Exalted Ruler → Administration ---
        if OfficerTerm is not None:
            er_term = OfficerTerm.search(
                [("position", "=", "exalted_ruler"), ("active", "=", True)],
                order="lodge_year desc", limit=1,
            )
            if er_term and er_term.partner_id:
                er_user = Users.search(
                    [("partner_id", "=", er_term.partner_id.id)], limit=1
                )
                if er_user and g_admin not in er_user.group_ids:
                    er_user.write({"group_ids": [(4, g_admin.id)]})
                    added_admin += 1

        # --- 4) Lodge Secretary holders → Administration (via group implication
        #        on the Admin group itself; nothing to do here, Odoo handles it).

        _logger.info(
            "Investigation-role sync: +%d Committee, +%d Chair, +%d Admin",
            added_committee, added_chair, added_admin,
        )
        return True

    def action_sync_investigation_roles(self):
        """User-callable: button on the Settings panel."""
        self._sync_investigation_roles()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Investigation roles synced"),
                "message": _("Committee, Chair, and Administration roles reconciled "
                             "with the current Lodge state. See server log for counts."),
                "type": "success",
                "sticky": False,
            },
        }


# ---------------------------------------------------------------------------
# Write-hooks on the source models — fire an immediate sync after relevant
# changes so role visibility is correct within seconds.
# ---------------------------------------------------------------------------
class ElksCommittee(models.Model):
    _inherit = "elks.committee"

    def write(self, vals):
        res = super().write(vals)
        # Re-sync if the chair or active flag changed on the Investigation committee
        if {"chair_id", "active", "name"} & set(vals.keys()):
            for rec in self:
                if rec.name and "investigation" in rec.name.lower():
                    self.env["res.users"]._sync_investigation_roles()
                    break
        return res


class ElksCommitteeAssignment(models.Model):
    _inherit = "elks.committee.assignment"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if any("investigation" in (r.committee_id.name or "").lower() for r in records):
            self.env["res.users"]._sync_investigation_roles()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {"partner_id", "committee_id", "is_current", "active"} & set(vals.keys()):
            if any("investigation" in (r.committee_id.name or "").lower() for r in self):
                self.env["res.users"]._sync_investigation_roles()
        return res


class ElksOfficerTerm(models.Model):
    _inherit = "elks.officer.term"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if any(r.position == "exalted_ruler" for r in records):
            self.env["res.users"]._sync_investigation_roles()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {"position", "partner_id", "active", "lodge_year"} & set(vals.keys()):
            if any(r.position == "exalted_ruler" for r in self):
                self.env["res.users"]._sync_investigation_roles()
        return res
