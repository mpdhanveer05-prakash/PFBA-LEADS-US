"""
AppealPacketService — generate professional PDF appeal packets using ReportLab
and store them in MinIO.

PDF structure (4 pages):
  1. Cover page  — petition header, property info, assessment summary, O'Connor branding
  2. Assessment analysis — assessed vs market value, gap, assessment history stub
  3. Comparable sales evidence table — up to 5 comps
  4. Certification / signature page

Color scheme: dark navy (#0D1B2A) headers, white body, steel-blue (#4A7FB5) accents.
"""
from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appeal_packet import AppealPacket
from app.models.assessment import Assessment
from app.models.comparable_sale import ComparableSale
from app.models.county import County
from app.models.lead_score import LeadScore
from app.models.property import Property

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ReportLab imports (optional dependency — fail gracefully at import time)
# ---------------------------------------------------------------------------
try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        HRFlowable,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    # Color / style constants (defined here so they're in scope only when reportlab is available)
    _NAVY = colors.HexColor("#0D1B2A")
    _STEEL = colors.HexColor("#4A7FB5")
    _LIGHT_GREY = colors.HexColor("#F2F4F8")
    _WHITE = colors.white
    _BLACK = colors.black

    _REPORTLAB_AVAILABLE = True
except ImportError:
    _REPORTLAB_AVAILABLE = False
    _NAVY = _STEEL = _LIGHT_GREY = _WHITE = _BLACK = None
    logger.warning(
        "reportlab is not installed. AppealPacketService will raise on generate()."
    )

# ---------------------------------------------------------------------------
# MinIO / storage imports
# ---------------------------------------------------------------------------
try:
    import minio as _minio_module
    from app.config import settings as _settings

    def _minio_client():
        return _minio_module.Minio(
            _settings.minio_endpoint,
            access_key=_settings.minio_access_key,
            secret_key=_settings.minio_secret_key,
            secure=False,
        )

    _MINIO_AVAILABLE = True
except Exception:
    _MINIO_AVAILABLE = False


def _styles():
    """Return a dict of named ParagraphStyles."""
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Title"],
            fontSize=22,
            textColor=_WHITE,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["Normal"],
            fontSize=12,
            textColor=_WHITE,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "section_header": ParagraphStyle(
            "section_header",
            parent=base["Heading2"],
            fontSize=13,
            textColor=_NAVY,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontSize=10,
            textColor=_BLACK,
            spaceAfter=4,
        ),
        "body_bold": ParagraphStyle(
            "body_bold",
            parent=base["Normal"],
            fontSize=10,
            textColor=_BLACK,
            fontName="Helvetica-Bold",
            spaceAfter=4,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER,
        ),
        "cert_body": ParagraphStyle(
            "cert_body",
            parent=base["Normal"],
            fontSize=10,
            textColor=_BLACK,
            leading=16,
            spaceAfter=8,
        ),
    }


# ---------------------------------------------------------------------------
# PDF builder helpers
# ---------------------------------------------------------------------------


def _cover_page(
    elements: list,
    s: dict,
    prop: Property,
    assessment: Optional[Assessment],
    lead: LeadScore,
    county: Optional[County],
) -> None:
    """Append cover-page flowables to elements."""
    # Navy banner block via a 1-cell table
    banner_data = [
        [Paragraph("PROPERTY TAX APPEAL PETITION", s["cover_title"])],
        [Paragraph("Prepared by O'Connor &amp; Associates — Property Tax Consulting", s["cover_sub"])],
    ]
    banner = Table(banner_data, colWidths=[6.5 * inch])
    banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 18),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    elements.append(banner)
    elements.append(Spacer(1, 0.3 * inch))

    # Property info
    elements.append(Paragraph("SUBJECT PROPERTY", s["section_header"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=_STEEL))
    elements.append(Spacer(1, 0.1 * inch))

    info_rows = [
        ["Address", prop.address],
        ["City / State / ZIP", f"{prop.city}, {prop.state} {prop.zip}"],
        ["Parcel Number (APN)", prop.apn],
        ["County", f"{county.name}, {county.state}" if county else "N/A"],
        ["Property Type", prop.property_type],
        ["Building Sq Ft", f"{prop.building_sqft:,}" if prop.building_sqft else "N/A"],
        ["Year Built", str(prop.year_built) if prop.year_built else "N/A"],
        ["Tax Year", str(assessment.tax_year) if assessment else "N/A"],
    ]
    info_table = Table(info_rows, colWidths=[2.0 * inch, 4.5 * inch])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_LIGHT_GREY, _WHITE]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(info_table)
    elements.append(Spacer(1, 0.25 * inch))

    # Assessment summary
    elements.append(Paragraph("ASSESSMENT SUMMARY", s["section_header"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=_STEEL))
    elements.append(Spacer(1, 0.1 * inch))

    assessed = float(assessment.assessed_total) if assessment else 0.0
    market = float(lead.market_value_est) if lead.market_value_est else 0.0
    gap = float(lead.assessment_gap) if lead.assessment_gap else (assessed - market)
    gap_pct = float(lead.gap_pct) if lead.gap_pct else 0.0
    savings = float(lead.estimated_savings) if lead.estimated_savings else 0.0

    summary_rows = [
        ["Current Assessed Value", f"${assessed:,.2f}"],
        ["Claimed Market Value", f"${market:,.2f}"],
        ["Over-Assessment Gap", f"${gap:,.2f}  ({gap_pct:.1f}%)"],
        ["Estimated Annual Savings", f"${savings:,.2f}"],
        ["Appeal Probability", f"{float(lead.appeal_probability or 0) * 100:.1f}%"],
        ["Priority Tier", str(lead.priority_tier.value if lead.priority_tier else "D")],
    ]
    summary_table = Table(summary_rows, colWidths=[2.5 * inch, 4.0 * inch])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_LIGHT_GREY, _WHITE]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(summary_table)

    # Footer branding
    elements.append(Spacer(1, 0.4 * inch))
    elements.append(
        Paragraph(
            "O'Connor &amp; Associates | www.poconnor.com | 1-800-856-PROP (7767)",
            s["footer"],
        )
    )
    elements.append(PageBreak())


def _analysis_page(
    elements: list,
    s: dict,
    assessment: Optional[Assessment],
    lead: LeadScore,
) -> None:
    """Append assessment analysis flowables."""
    elements.append(Paragraph("ASSESSMENT ANALYSIS", s["section_header"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=_STEEL))
    elements.append(Spacer(1, 0.15 * inch))

    assessed = float(assessment.assessed_total) if assessment else 0.0
    land = float(assessment.assessed_land) if assessment and assessment.assessed_land else 0.0
    improvement = (
        float(assessment.assessed_improvement)
        if assessment and assessment.assessed_improvement
        else 0.0
    )
    market = float(lead.market_value_est) if lead.market_value_est else 0.0
    gap = float(lead.assessment_gap) if lead.assessment_gap else (assessed - market)
    gap_pct = float(lead.gap_pct) if lead.gap_pct else 0.0

    elements.append(
        Paragraph(
            "The subject property's current assessed value materially exceeds its estimated "
            "fair market value based on comparable sales data. The analysis below quantifies "
            "the over-assessment and provides the basis for this appeal.",
            s["body"],
        )
    )
    elements.append(Spacer(1, 0.1 * inch))

    detail_rows = [
        ["Component", "Amount"],
        ["Assessed Land Value", f"${land:,.2f}"],
        ["Assessed Improvement Value", f"${improvement:,.2f}"],
        ["Total Assessed Value", f"${assessed:,.2f}"],
        ["Estimated Market Value (Comps)", f"${market:,.2f}"],
        ["Over-Assessment Amount", f"${gap:,.2f}"],
        ["Over-Assessment Percentage", f"{gap_pct:.2f}%"],
    ]
    detail_table = Table(detail_rows, colWidths=[3.5 * inch, 3.0 * inch])
    detail_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_LIGHT_GREY, _WHITE]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(detail_table)
    elements.append(Spacer(1, 0.25 * inch))

    elements.append(Paragraph("APPLICABLE STANDARD", s["section_header"]))
    elements.append(
        Paragraph(
            "Under applicable state property tax law, assessed values must reflect fair market "
            "value — the price a willing buyer would pay a willing seller in an arm's-length "
            "transaction. Where the assessed value exceeds market value, the property owner is "
            "entitled to a reduction. The comparable sales presented on the following page "
            "establish the fair market value of the subject property.",
            s["body"],
        )
    )
    elements.append(PageBreak())


def _comps_page(elements: list, s: dict, comps: list[ComparableSale], prop: Property) -> None:
    """Append comparable sales evidence page."""
    elements.append(Paragraph("COMPARABLE SALES EVIDENCE", s["section_header"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=_STEEL))
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(
        Paragraph(
            f"The following {len(comps)} comparable sale(s) were identified within the subject "
            f"property's market area. These sales represent arm's-length transactions of "
            f"similar properties and establish the basis for the claimed market value.",
            s["body"],
        )
    )
    elements.append(Spacer(1, 0.15 * inch))

    header = ["Address / APN", "Sale Date", "Sale Price", "Sq Ft", "$/Sq Ft", "Similarity"]
    rows = [header]
    for comp in comps:
        apn_display = getattr(comp, "comp_address", None) or comp.comp_apn
        rows.append(
            [
                apn_display[:35] if apn_display else comp.comp_apn,
                comp.sale_date.strftime("%m/%d/%Y") if comp.sale_date else "N/A",
                f"${float(comp.sale_price):,.0f}",
                f"{comp.sqft:,}" if comp.sqft else "N/A",
                f"${float(comp.price_per_sqft):,.2f}" if comp.price_per_sqft else "N/A",
                f"{float(comp.similarity_score or 0):.2f}" if comp.similarity_score else "N/A",
            ]
        )

    col_widths = [2.0 * inch, 1.0 * inch, 1.0 * inch, 0.7 * inch, 0.8 * inch, 0.9 * inch]
    comp_table = Table(rows, colWidths=col_widths)
    comp_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_LIGHT_GREY, _WHITE]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(comp_table)
    elements.append(Spacer(1, 0.25 * inch))

    if prop.building_sqft and comps:
        ppsf_vals = [float(c.price_per_sqft) for c in comps if c.price_per_sqft]
        if ppsf_vals:
            avg_ppsf = sum(ppsf_vals) / len(ppsf_vals)
            implied = avg_ppsf * prop.building_sqft
            elements.append(
                Paragraph(
                    f"Average price per square foot from comps: ${avg_ppsf:,.2f}  "
                    f"× Subject sq ft ({prop.building_sqft:,}) = "
                    f"Implied Market Value: <b>${implied:,.0f}</b>",
                    s["body"],
                )
            )
    elements.append(PageBreak())


def _cert_page(elements: list, s: dict, prop: Property, county: Optional[County]) -> None:
    """Append certification and signature page."""
    elements.append(Paragraph("CERTIFICATION AND PETITION", s["section_header"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=_STEEL))
    elements.append(Spacer(1, 0.2 * inch))

    county_name = f"{county.name} County, {county.state}" if county else "the applicable county"
    tax_year_label = datetime.now(timezone.utc).year

    cert_text = (
        f"The undersigned hereby petitions the Appraisal Review Board of {county_name} "
        f"for a reduction in the assessed value of the above-described property for tax "
        f"year {tax_year_label}. The petitioner contends that the assessed value assigned "
        f"by the appraisal district does not reflect the fair market value of the property "
        f"as of January 1 of the tax year in question, as evidenced by the comparable sales "
        f"data presented herein.<br/><br/>"
        f"The petitioner respectfully requests that the assessed value be reduced to an "
        f"amount consistent with the fair market value indicated by the comparable sales "
        f"evidence, in accordance with applicable state law."
    )
    elements.append(Paragraph(cert_text, s["cert_body"]))
    elements.append(Spacer(1, 0.5 * inch))

    sig_rows = [
        ["Property Owner / Authorized Agent", "Date"],
        ["", ""],
        ["Printed Name", "Phone Number"],
        ["", ""],
        ["Mailing Address", "Email Address"],
        ["", ""],
    ]
    sig_table = Table(sig_rows, colWidths=[4.0 * inch, 2.5 * inch])
    sig_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 2), (-1, 2), colors.grey),
                ("TEXTCOLOR", (0, 4), (-1, 4), colors.grey),
                ("LINEBELOW", (0, 1), (-1, 1), 0.8, _BLACK),
                ("LINEBELOW", (0, 3), (-1, 3), 0.8, _BLACK),
                ("LINEBELOW", (0, 5), (-1, 5), 0.8, _BLACK),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(sig_table)
    elements.append(Spacer(1, 0.4 * inch))
    elements.append(
        Paragraph(
            "Prepared by O'Connor &amp; Associates | www.poconnor.com | 1-800-856-PROP (7767)<br/>"
            "This petition is submitted on behalf of the property owner in accordance with "
            "applicable state and local tax protest procedures.",
            s["footer"],
        )
    )


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class AppealPacketService:
    """Generate and retrieve PDF appeal packets."""

    def generate(self, lead_score_id: uuid.UUID, db: Session) -> AppealPacket:
        """
        Build a 4-page PDF appeal packet for the given lead score, upload to
        MinIO (if available), and persist an AppealPacket record.

        Raises ImportError if reportlab is not installed.
        Raises ValueError if the lead score does not exist.
        """
        if not _REPORTLAB_AVAILABLE:
            raise ImportError(
                "reportlab is required to generate appeal packets. "
                "Install it with: pip install reportlab"
            )

        lead = db.get(LeadScore, lead_score_id)
        if not lead:
            raise ValueError(f"LeadScore {lead_score_id} not found")

        prop: Property = db.get(Property, lead.property_id)
        if not prop:
            raise ValueError(f"Property {lead.property_id} not found")

        assessment: Optional[Assessment] = db.get(Assessment, lead.assessment_id)
        county: Optional[County] = db.get(County, prop.county_id)

        comps = list(
            db.execute(
                select(ComparableSale)
                .where(ComparableSale.property_id == prop.id)
                .order_by(ComparableSale.similarity_score.desc())
                .limit(5)
            ).scalars().all()
        )

        # Build PDF in memory
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        s = _styles()
        elements: list = []

        _cover_page(elements, s, prop, assessment, lead, county)
        _analysis_page(elements, s, assessment, lead)
        _comps_page(elements, s, comps, prop)
        _cert_page(elements, s, prop, county)

        doc.build(elements)
        pdf_bytes = pdf_buffer.getvalue()

        packet_id = uuid.uuid4()
        county_slug = county.scraper_adapter if county else "unknown"
        s3_key = f"packets/{county_slug}/{prop.apn}/{packet_id}.pdf"

        # Upload to MinIO (optional)
        stored_key: Optional[str] = None
        if _MINIO_AVAILABLE:
            try:
                client = _minio_client()
                from app.config import settings as _settings  # noqa: PLC0415

                if not client.bucket_exists(_settings.minio_bucket):
                    client.make_bucket(_settings.minio_bucket)
                client.put_object(
                    _settings.minio_bucket,
                    s3_key,
                    data=io.BytesIO(pdf_bytes),
                    length=len(pdf_bytes),
                    content_type="application/pdf",
                )
                stored_key = s3_key
                logger.info("Appeal packet uploaded to MinIO: %s", s3_key)
            except Exception as exc:
                logger.warning("MinIO upload failed, proceeding without storage: %s", exc)
        else:
            logger.info("MinIO unavailable — packet not persisted to object storage")

        # Persist the AppealPacket record
        claimed_value = lead.market_value_est
        packet = AppealPacket(
            id=packet_id,
            lead_score_id=lead_score_id,
            property_id=prop.id,
            county_id=prop.county_id,
            s3_key=stored_key,
            claimed_value=claimed_value,
            evidence_comps=len(comps),
            status="READY" if stored_key else "DRAFT",
        )
        db.add(packet)
        db.commit()
        db.refresh(packet)

        # Stash bytes on the object so the caller can return them directly if needed
        packet._pdf_bytes = pdf_bytes  # type: ignore[attr-defined]

        logger.info(
            "Generated appeal packet %s for lead %s (%d comps)",
            packet_id,
            lead_score_id,
            len(comps),
        )
        return packet

    def get_pdf_bytes(self, packet_id: uuid.UUID, db: Session) -> bytes:
        """
        Retrieve the PDF bytes for the given packet from MinIO.

        Raises ValueError if the packet is not found or has no s3_key.
        Raises RuntimeError if MinIO is unavailable or the download fails.
        """
        packet = db.get(AppealPacket, packet_id)
        if not packet:
            raise ValueError(f"AppealPacket {packet_id} not found")

        if not packet.s3_key:
            raise ValueError(
                f"AppealPacket {packet_id} has no stored PDF (s3_key is null). "
                "Regenerate the packet."
            )

        if not _MINIO_AVAILABLE:
            raise RuntimeError("MinIO client is not available in this environment.")

        try:
            from app.config import settings as _settings  # noqa: PLC0415

            client = _minio_client()
            response = client.get_object(_settings.minio_bucket, packet.s3_key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except Exception as exc:
            raise RuntimeError(f"Failed to retrieve PDF from MinIO: {exc}") from exc
