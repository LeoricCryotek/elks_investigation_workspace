"""Bulk paste-and-parse wizard.

Takes a chunk of text pasted from a court-records portal search result and
heuristically extracts one Hit row per record. Designed to be portal-agnostic
by trying several format strategies in order:

  1. Labeled fields format — records contain "Case No:", "Court Info:",
     "Name: X - Role" labels (matches WA dw.courts.wa.gov format).
  2. Tab-separated table — records have tab characters and look like a
     copy-paste from a table view (Idaho iCourt and many Tyler Odyssey
     portals look like this).
  3. CSV / pipe-separated lines.
  4. Best-effort line-by-line heuristic when nothing else matches.

The operator always sees a preview before committing.
"""

import json
import re

from odoo import _, api, fields, models


# Tokens that strongly suggest a court / institution name.
_COURT_TOKENS = re.compile(
    r'\b(Court|District|Tribunal|Justice|Magistrate|Superior|Municipal|Circuit|Supreme)\b',
    re.IGNORECASE,
)

# Tokens that look like role descriptors.
_ROLE_CANON = {
    "defendant": "defendant",
    "def.": "defendant",
    "def": "defendant",
    "respondent": "respondent",
    "resp.": "respondent",
    "resp": "respondent",
    "plaintiff": "plaintiff",
    "pl.": "plaintiff",
    "pltf": "plaintiff",
    "pltff": "plaintiff",
    "judgment debtor": "judgment_debtor",
    "judgment-debtor": "judgment_debtor",
    "judg. debtor": "judgment_debtor",
    "petitioner": "petitioner",
    "pet.": "petitioner",
    "witness": "witness",
}


def _canon_role(s):
    if not s:
        return False
    return _ROLE_CANON.get(s.strip().lower(), "other")


# ---------------------------------------------------------------------------
# Parser strategies
# ---------------------------------------------------------------------------
def parse_labeled_fields(text):
    """Parser for the 'Court name / Name: X - Role / Case No: NNN / Court Info: date'
    pattern used by Washington dw.courts.wa.gov among others."""
    records = []
    current = {}
    raw_buffer = []
    saw_label = False

    def flush():
        nonlocal current, raw_buffer
        if current.get("case_number") or current.get("court"):
            current["raw"] = "\n".join(raw_buffer).strip()
            records.append(current)
        current, raw_buffer = {}, []

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            flush()
            continue
        raw_buffer.append(line)

        m = re.match(r'^Case\s*(?:No|#)\.?\s*:\s*(.+)$', line, re.IGNORECASE)
        if m:
            current["case_number"] = m.group(1).strip()
            saw_label = True
            continue
        m = re.match(r'^(?:Court\s*Info|Court\s*Date|Filed|Filing\s*Date|Date)\s*:\s*(.+)$',
                     line, re.IGNORECASE)
        if m:
            current["offense_date"] = m.group(1).strip()
            saw_label = True
            continue
        m = re.match(r'^Name\s*:\s*(.+?)(?:\s*-\s*(.+))?$', line, re.IGNORECASE)
        if m:
            current["name_on_record"] = m.group(1).strip()
            if m.group(2):
                current["role"] = _canon_role(m.group(2))
            saw_label = True
            continue
        m = re.match(r'^Judgment\s+Available', line, re.IGNORECASE)
        if m:
            current.setdefault("disposition", "Judgment available")
            continue
        # Treat as the court-name line if no court captured yet AND looks like one.
        if not current.get("court") and _COURT_TOKENS.search(line):
            # New record starts here if we already have data — flush first.
            if current.get("case_number") or saw_label:
                flush()
                raw_buffer = [line]
            current["court"] = line
            continue
        # Otherwise: keep as extra notes (charges, etc.)
        current.setdefault("charges_or_notes", []).append(line)

    flush()

    # Stringify any list-valued notes
    for rec in records:
        if isinstance(rec.get("charges_or_notes"), list):
            rec["charges"] = " | ".join(rec.pop("charges_or_notes"))
    return records


def parse_tabular(text):
    """Parser for tab-separated table copy-paste (Idaho iCourt and most Tyler
    Odyssey portals when you select+copy the results grid)."""
    lines = [l for l in text.split("\n") if l.strip()]
    rows = []
    headers = []
    for line in lines:
        if "\t" not in line:
            continue
        cols = [c.strip() for c in line.split("\t")]
        if not headers:
            # First tabbed line — treat as header if any of these tokens appear
            header_tokens = {"case", "court", "name", "date", "type", "filed", "style",
                              "disposition", "charge"}
            lower = [c.lower() for c in cols]
            if any(any(t in c for t in header_tokens) for c in lower):
                headers = lower
                continue
            # Otherwise treat as data with positional defaults
            headers = ["case", "date", "name", "court", "charge"][:len(cols)]
        rec = {}
        for i, col in enumerate(cols):
            if i >= len(headers):
                break
            h = headers[i]
            # Most specific first. "case type" must not match case_number.
            if "charge" in h or "case type" in h or h == "type":
                rec["charges"] = col
            elif "case" in h and ("no" in h or "num" in h or "#" in h):
                rec["case_number"] = col
            elif "court" in h:
                rec["court"] = col
            elif "disposition" in h:
                rec["disposition"] = col
            elif "role" in h:
                rec["role"] = _canon_role(col)
            elif "date" in h or "filed" in h:
                rec["offense_date"] = col
            elif "name" in h or "party" in h or "style" in h:
                rec.setdefault("name_on_record", col)
            # Fallback: header is just "case" by itself
            elif h == "case":
                rec["case_number"] = col
        if rec.get("case_number") or rec.get("court"):
            rec["raw"] = line
            rows.append(rec)
    return rows


def parse_csv_or_pipe(text):
    """Parser for CSV or pipe-delimited content."""
    for delim in (",", "|"):
        rows = []
        for line in text.split("\n"):
            if delim not in line or "Case" in line and "No" in line:
                continue
            cols = [c.strip().strip('"') for c in line.split(delim)]
            if len(cols) < 3:
                continue
            rec = {
                "court": cols[0] if cols and _COURT_TOKENS.search(cols[0]) else "",
                "case_number": next((c for c in cols if re.search(r'\d{4,}', c)), ""),
                "name_on_record": next((c for c in cols if "," in c and not c.startswith("Case")), ""),
                "offense_date": next((c for c in cols if re.match(r'\d{1,4}[/\-]\d{1,2}[/\-]\d{1,4}', c)), ""),
                "raw": line,
            }
            if rec["case_number"] or rec["court"]:
                rows.append(rec)
        if rows:
            return rows
    return []


def parse_best_effort(text):
    """Last-resort line-by-line heuristic — groups every 2-5 non-empty lines
    into a probable record and extracts what it can."""
    blocks = re.split(r'\n\s*\n+', text.strip())
    records = []
    for block in blocks:
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        rec = {"raw": block.strip()}
        for line in lines:
            if not rec.get("court") and _COURT_TOKENS.search(line):
                rec["court"] = line
                continue
            m = re.search(r'\b([A-Z0-9]{2,4}-?\d{2,}[-A-Z0-9]*)\b', line)
            if m and not rec.get("case_number"):
                rec["case_number"] = m.group(1)
            m = re.search(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b', line)
            if m and not rec.get("offense_date"):
                rec["offense_date"] = m.group(1)
            if "," in line and not rec.get("name_on_record"):
                # Likely "Last, First [Middle]"
                m = re.match(r'^([A-Z][a-zA-Z\'\-]+,\s*[A-Z][a-zA-Z\'\-\s\.]+)', line)
                if m:
                    rec["name_on_record"] = m.group(1).strip()
                    # If "- Role" appears later in the line, capture it
                    role_m = re.search(r'-\s*([A-Za-z\s]+)$', line)
                    if role_m:
                        rec["role"] = _canon_role(role_m.group(1))
        if rec.get("case_number") or rec.get("court") or rec.get("name_on_record"):
            records.append(rec)
    return records


def parse_bulk_text(text):
    """Top-level dispatcher. Tries strategies in order, returns the first one
    that produces at least one record."""
    if not text or not text.strip():
        return [], "empty"
    if re.search(r'Case\s*No\.?\s*:', text, re.IGNORECASE) or re.search(
        r'Court\s*Info\s*:', text, re.IGNORECASE,
    ):
        recs = parse_labeled_fields(text)
        if recs:
            return recs, "labeled-fields"
    if "\t" in text:
        recs = parse_tabular(text)
        if recs:
            return recs, "tab-separated"
    recs = parse_csv_or_pipe(text)
    if recs:
        return recs, "csv-or-pipe"
    recs = parse_best_effort(text)
    return recs, "best-effort"


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------
class BulkParseWizard(models.TransientModel):
    _name = "elks.investigation.bulk_parse.wizard"
    _description = "Bulk paste-and-parse: turn pasted search results into Hit rows"

    check_id = fields.Many2one(
        "elks.investigation.check", required=True, ondelete="cascade",
        string="Check",
    )
    pasted_text = fields.Text(
        string="Paste search results here",
        required=True,
        help="Copy the search results from the portal page and paste here. "
             "The wizard tries to recognize the format automatically and "
             "extracts one Hit row per record.",
    )
    parsed_json = fields.Text(string="Parsed (preview, edit to fix)", default="[]")
    parser_used = fields.Char(string="Parser strategy", readonly=True)
    parsed_count = fields.Integer(string="# records parsed", readonly=True)

    def action_preview(self):
        """Run the parser and show the preview JSON for the operator to review/edit."""
        self.ensure_one()
        records, strategy = parse_bulk_text(self.pasted_text or "")
        self.write({
            "parsed_json": json.dumps(records, indent=2, ensure_ascii=False),
            "parser_used": strategy,
            "parsed_count": len(records),
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def action_commit(self):
        """Create the Hit records from the parsed preview."""
        self.ensure_one()
        try:
            records = json.loads(self.parsed_json or "[]")
        except json.JSONDecodeError as e:
            from odoo.exceptions import UserError
            raise UserError(_("Parsed JSON is malformed: %s") % e)
        Hit = self.env["elks.investigation.hit"]
        for r in records:
            Hit.create({
                "check_id": self.check_id.id,
                "name_on_record": r.get("name_on_record") or _("(unknown)"),
                "dob_on_record": r.get("dob_on_record") or "",
                "address_on_record": r.get("address_on_record") or "",
                "court": r.get("court") or "",
                "role": r.get("role") if r.get("role") in dict(Hit._fields["role"].selection) else False,
                "case_number": r.get("case_number") or "",
                "offense_date": r.get("offense_date") or "",
                "charges": r.get("charges") or "",
                "disposition": r.get("disposition") or "",
                "notes": r.get("raw") and f"[Bulk-imported]\n{r['raw']}" or "",
            })
        # If at least one hit was added, set the check's result to match_found.
        if records and self.check_id.result_summary in ("pending", "no_records"):
            self.check_id.result_summary = "match_found"
        # Run cross-check on the parent application so flags are refreshed.
        self.check_id.application_id.action_investigation_run_cross_check()
        return {
            "type": "ir.actions.act_window",
            "res_model": "elks.investigation.check",
            "res_id": self.check_id.id,
            "view_mode": "form",
            "target": "current",
        }
