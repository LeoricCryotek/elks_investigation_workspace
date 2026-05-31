"""Backfill source_type on existing elks.portal and elks.investigation.check rows.

The source_type field was added in v19.0.1.8.0 but data/portal_directory_data.xml
uses noupdate="1", so existing rows in upgraded installs never received the new
values. This migration maps source_code → source_type for every pre-existing
record so the conditional Hit form view (court vs social-media) takes effect.
"""

import logging

_logger = logging.getLogger(__name__)


_SOCIAL = ("Facebook", "Instagram", "X-Twitter", "LinkedIn")
_IDENTITY = ("BlackBookOnline", "Anywho")
_SANCTIONS = ("OFAC SDN",)
_FEDERAL = ("CourtListener", "PACER")
_SEX_OFFENDER = ("NSOPW", "SOR", "SVOR")
_CORRECTIONS = ("DOC",)


def _update(cr, table, source_type, source_codes=None, like_pattern=None):
    if source_codes:
        cr.execute(
            f"UPDATE {table} SET source_type = %s "
            f"WHERE source_code IN %s AND (source_type IS NULL OR source_type = '' OR source_type = 'court')",
            (source_type, tuple(source_codes)),
        )
    elif like_pattern:
        cr.execute(
            f"UPDATE {table} SET source_type = %s "
            f"WHERE source_code LIKE %s AND (source_type IS NULL OR source_type = '' OR source_type = 'court')",
            (source_type, like_pattern),
        )
    return cr.rowcount


def migrate(cr, version):
    if not version:
        return  # fresh install — data file already sets source_type explicitly

    for table in ("elks_portal", "elks_investigation_check"):
        # Defensive — skip if the column doesn't exist
        cr.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = 'source_type'",
            (table,),
        )
        if not cr.fetchone():
            _logger.warning("Skipping %s — source_type column not present", table)
            continue

        counts = {
            "social_media": _update(cr, table, "social_media", source_codes=_SOCIAL),
            "identity": _update(cr, table, "identity", source_codes=_IDENTITY),
            "sanctions": _update(cr, table, "sanctions", source_codes=_SANCTIONS),
            "federal_court": _update(cr, table, "federal_court", source_codes=_FEDERAL),
            "sex_offender": _update(cr, table, "sex_offender", source_codes=_SEX_OFFENDER),
            "corrections": _update(cr, table, "corrections", source_codes=_CORRECTIONS),
            "recorder": _update(cr, table, "recorder", like_pattern="%Recorder"),
        }

        # Everything else gets 'court' as the explicit fallback
        cr.execute(
            f"UPDATE {table} SET source_type = 'court' "
            f"WHERE source_type IS NULL OR source_type = ''"
        )
        counts["court (fallback)"] = cr.rowcount

        _logger.info(
            "Backfilled %s.source_type: %s",
            table,
            ", ".join(f"{k}={v}" for k, v in counts.items() if v),
        )
