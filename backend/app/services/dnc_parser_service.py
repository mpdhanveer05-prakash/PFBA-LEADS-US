"""Parse DNC upload files (CSV, Excel, PDF) into normalised records."""
from __future__ import annotations

import csv
import io
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Headers we recognise (case-insensitive) → standard key
_HEADER_MAP: dict[str, str] = {
    # name
    "name": "name", "owner": "name", "owner name": "name", "owner_name": "name",
    "full name": "name", "full_name": "name", "taxpayer": "name",
    "client name": "name", "client": "name", "taxpayer name": "name",
    # email
    "email": "email", "e-mail": "email", "email address": "email",
    "email_address": "email", "owner email": "email", "contact email": "email",
    # phone
    "phone": "phone", "phone number": "phone", "mobile": "phone",
    "cell": "phone", "telephone": "phone", "phone_number": "phone",
    "mobile number": "phone", "contact number": "phone", "contact phone": "phone",
    # address
    "address": "address", "property address": "address",
    "property_address": "address", "street": "address",
    "street address": "address", "location": "address",
    "property location": "address", "site address": "address",
    # apn / parcel
    "apn": "apn", "parcel": "apn", "parcel number": "apn",
    "parcel_number": "apn", "pin": "apn", "tax id": "apn",
    "folio": "apn", "account number": "apn", "account_number": "apn",
    "tax account": "apn", "property id": "apn", "parcel id": "apn",
    "bbl": "apn", "tax lot": "apn",
}

_PHONE_STRIP = re.compile(r"[^\d]")


def _detect_columns(headers: list[str]) -> dict[str, str]:
    """Return mapping raw_column_name → std_key for recognised headers."""
    mapping: dict[str, str] = {}
    for col in headers:
        std = _HEADER_MAP.get(col.strip().lower())
        if std and std not in mapping.values():
            mapping[col] = std
    return mapping


def _build_record(raw_row: dict[str, Any], col_map: dict[str, str]) -> dict[str, str | None]:
    rec: dict[str, str | None] = {k: None for k in ("name", "email", "phone", "address", "apn")}
    for raw_col, std_key in col_map.items():
        val = str(raw_row.get(raw_col) or "").strip()
        if val:
            rec[std_key] = val
    if rec["phone"]:
        rec["phone"] = _PHONE_STRIP.sub("", rec["phone"])
    if rec["email"]:
        rec["email"] = rec["email"].lower()
    return rec


# ── CSV ───────────────────────────────────────────────────────────────────────

def parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = list(reader.fieldnames or [])
    col_map = _detect_columns(headers)
    if not col_map:
        raise ValueError(
            f"No recognised columns. Need at least one of: name, email, phone, address, apn. "
            f"Found: {headers}"
        )
    records = [_build_record(row, col_map) for row in reader]
    return [r for r in records if any(v for v in r.values())]


# ── Excel ─────────────────────────────────────────────────────────────────────

def parse_excel(content: bytes) -> list[dict]:
    try:
        import openpyxl
    except ImportError:
        raise ImportError("openpyxl required for Excel files. Install: pip install openpyxl")

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []

    headers = [str(c or "").strip() for c in rows[0]]
    col_map = _detect_columns(headers)
    if not col_map:
        raise ValueError(
            f"No recognised columns in Excel. Need: name/email/phone/address/apn. Found: {headers}"
        )

    records = []
    for raw_row in rows[1:]:
        row_dict = dict(zip(headers, [str(c or "").strip() for c in raw_row]))
        rec = _build_record(row_dict, col_map)
        if any(v for v in rec.values()):
            records.append(rec)
    return records


# ── PDF ───────────────────────────────────────────────────────────────────────

def parse_pdf(content: bytes) -> list[dict]:
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber required for PDF files.")

    records: list[dict] = []
    idx_map: dict[int, str] = {}
    headers_found = False

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for table in (page.extract_tables() or []):
                if not table:
                    continue
                for raw_row in table:
                    if raw_row is None:
                        continue
                    cells = [str(c or "").strip() for c in raw_row]
                    if not headers_found:
                        for j, cell in enumerate(cells):
                            std = _HEADER_MAP.get(cell.lower())
                            if std and std not in idx_map.values():
                                idx_map[j] = std
                        if idx_map:
                            headers_found = True
                        continue

                    rec: dict[str, str | None] = {k: None for k in ("name", "email", "phone", "address", "apn")}
                    for j, std_key in idx_map.items():
                        val = cells[j] if j < len(cells) else ""
                        if val:
                            rec[std_key] = val
                    if rec.get("phone"):
                        rec["phone"] = _PHONE_STRIP.sub("", rec["phone"])
                    if rec.get("email"):
                        rec["email"] = rec["email"].lower()
                    if any(v for v in rec.values()):
                        records.append(rec)

    if not records:
        raise ValueError("No table data found in PDF. Ensure the file contains a table with column headers.")
    return records


# ── Dispatcher ────────────────────────────────────────────────────────────────

def parse_file(filename: str, content: bytes) -> tuple[str, list[dict]]:
    """Detect file type, parse, return (file_type, records)."""
    lower = filename.lower()
    if lower.endswith(".csv"):
        return "csv", parse_csv(content)
    if lower.endswith((".xlsx", ".xls")):
        return "excel", parse_excel(content)
    if lower.endswith(".pdf"):
        return "pdf", parse_pdf(content)
    # Fallback: try CSV
    try:
        return "csv", parse_csv(content)
    except Exception:
        raise ValueError(f"Unsupported file type '{filename}'. Accepted: .csv, .xlsx, .xls, .pdf")
