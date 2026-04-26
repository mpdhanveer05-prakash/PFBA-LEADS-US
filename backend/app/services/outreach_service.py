"""
OutreachService — generate and send property tax appeal pitch emails.

Environment variables consumed (all optional; ValueError raised if SMTP is
called when not configured):
    SMTP_HOST   e.g. smtp.gmail.com
    SMTP_PORT   e.g. 587
    SMTP_USER   sender address
    SMTP_PASS   sender password / app-token
"""
from __future__ import annotations

import logging
import os
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.comparable_sale import ComparableSale
from app.models.county import County
from app.models.lead_score import LeadScore
from app.models.outreach_campaign import OutreachCampaign
from app.models.property import Property

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Email template
# ---------------------------------------------------------------------------

_SUBJECT_TEMPLATE = (
    "Your property at {address} may be over-assessed — potential savings of ${savings:,.0f}"
)

_BODY_TEMPLATE = """\
Dear Property Owner,

We are writing on behalf of O'Connor & Associates, one of the nation's leading property
tax consulting firms, regarding your property located at:

    {address}
    {city}, {state} {zip}
    Parcel Number (APN): {apn}

─────────────────────────────────────────────
ASSESSMENT SUMMARY — Tax Year {tax_year}
─────────────────────────────────────────────
  Current Assessed Value : ${assessed:>14,.2f}
  Estimated Market Value : ${market:>14,.2f}
  Over-Assessment Gap    : ${gap:>14,.2f}  ({gap_pct:.1f}%)
  Estimated Annual Savings: ${savings:>13,.2f}

Our analysis is based on {num_comps} comparable sales within your area.
{deadline_line}

─────────────────────────────────────────────
HOW O'CONNOR CAN HELP YOU
─────────────────────────────────────────────
O'Connor has successfully reduced property taxes for thousands of homeowners
and commercial property owners across the country. Our team handles every step
of the appeal process — at no upfront cost to you. We only charge a contingency
fee if we win.

NEXT STEPS:
  1. Reply to this email or call us at 1-800-856-PROP (7767)
  2. We will conduct a full review of your assessment at no charge
  3. If we identify grounds to appeal, we file on your behalf before the deadline

There is no risk and no upfront cost. If we don't save you money, you owe us nothing.

Sincerely,

O'Connor & Associates
Property Tax Consulting
www.poconnor.com  |  1-800-856-PROP (7767)

─────────────────────────────────────────────
This communication was generated based on publicly available assessment data.
To opt out of future communications, reply with "UNSUBSCRIBE" in the subject line.
─────────────────────────────────────────────
"""


def _build_deadline_line(county: County) -> str:
    if county.appeal_deadline_days:
        return (
            f"The appeal deadline is typically {county.appeal_deadline_days} days from the "
            "assessment notice date. Acting promptly protects your rights."
        )
    return "Please act promptly — appeal deadlines are strictly enforced."


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class OutreachService:
    """Create, send, and manage outreach campaigns linked to lead scores."""

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------

    def generate_campaign(self, lead_score_id: uuid.UUID, db: Session) -> OutreachCampaign:
        """
        Load the lead score + related data, build a pitch email, and persist
        an OutreachCampaign record with status=DRAFT.

        Raises ValueError if the lead score does not exist.
        """
        lead = db.get(LeadScore, lead_score_id)
        if not lead:
            raise ValueError(f"LeadScore {lead_score_id} not found")

        prop: Property = db.get(Property, lead.property_id)
        if not prop:
            raise ValueError(f"Property {lead.property_id} not found")

        assessment: Assessment = db.get(Assessment, lead.assessment_id)
        county: County = db.get(County, prop.county_id)

        # Count comps
        num_comps = db.execute(
            select(ComparableSale.id).where(ComparableSale.property_id == prop.id)
        ).scalar() or 0
        # Re-count properly
        num_comps_rows = db.execute(
            select(ComparableSale).where(ComparableSale.property_id == prop.id)
        ).scalars().all()
        num_comps = len(num_comps_rows)

        assessed_val = float(assessment.assessed_total) if assessment else 0.0
        market_val = float(lead.market_value_est) if lead.market_value_est else 0.0
        gap_val = float(lead.assessment_gap) if lead.assessment_gap else (assessed_val - market_val)
        gap_pct = float(lead.gap_pct) if lead.gap_pct else 0.0
        savings_val = float(lead.estimated_savings) if lead.estimated_savings else 0.0
        tax_year = assessment.tax_year if assessment else datetime.now(timezone.utc).year

        deadline_line = _build_deadline_line(county) if county else ""

        subject = _SUBJECT_TEMPLATE.format(
            address=prop.address,
            savings=savings_val,
        )

        body = _BODY_TEMPLATE.format(
            address=prop.address,
            city=prop.city,
            state=prop.state,
            zip=prop.zip,
            apn=prop.apn,
            tax_year=tax_year,
            assessed=assessed_val,
            market=market_val,
            gap=gap_val,
            gap_pct=gap_pct,
            savings=savings_val,
            num_comps=num_comps,
            deadline_line=deadline_line,
        )

        campaign = OutreachCampaign(
            lead_score_id=lead_score_id,
            property_id=prop.id,
            status="DRAFT",
            channel="EMAIL",
            recipient_email=prop.owner_email,
            recipient_phone=prop.owner_phone,
            subject=subject,
            body=body,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        logger.info("Created DRAFT campaign %s for lead %s", campaign.id, lead_score_id)
        return campaign

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    def send_campaign(self, campaign_id: uuid.UUID, db: Session) -> OutreachCampaign:
        """
        Send the campaign email via SMTP.

        Reads SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS from environment.
        Raises ValueError if SMTP is not configured or recipient email is missing.
        """
        smtp_host = os.getenv("SMTP_HOST", "")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_pass = os.getenv("SMTP_PASS", "")

        if not smtp_host or not smtp_user:
            raise ValueError(
                "SMTP not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, and SMTP_PASS "
                "environment variables before sending campaigns."
            )

        campaign = db.get(OutreachCampaign, campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        if not campaign.recipient_email:
            raise ValueError(
                f"Campaign {campaign_id} has no recipient_email. "
                "Update the property owner email first."
            )

        # Build MIME message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = campaign.subject or "(No subject)"
        msg["From"] = smtp_user
        msg["To"] = campaign.recipient_email

        text_part = MIMEText(campaign.body or "", "plain", "utf-8")
        msg.attach(text_part)

        # Send via SMTP with STARTTLS
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [campaign.recipient_email], msg.as_string())
            logger.info(
                "Sent campaign %s to %s", campaign_id, campaign.recipient_email
            )
        except smtplib.SMTPException as exc:
            logger.error("SMTP error sending campaign %s: %s", campaign_id, exc)
            raise

        campaign.status = "SENT"
        campaign.sent_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(campaign)
        return campaign

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_campaigns(
        self,
        db: Session,
        lead_score_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
    ) -> list[OutreachCampaign]:
        """Return campaigns, optionally filtered by lead_score_id and/or status."""
        stmt = select(OutreachCampaign).order_by(OutreachCampaign.created_at.desc())
        if lead_score_id is not None:
            stmt = stmt.where(OutreachCampaign.lead_score_id == lead_score_id)
        if status is not None:
            stmt = stmt.where(OutreachCampaign.status == status.upper())
        return list(db.execute(stmt).scalars().all())

    # ------------------------------------------------------------------
    # Update status
    # ------------------------------------------------------------------

    def update_status(
        self, campaign_id: uuid.UUID, status: str, db: Session
    ) -> OutreachCampaign:
        """Update the status field of a campaign. Raises ValueError if not found."""
        campaign = db.get(OutreachCampaign, campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        new_status = status.upper()
        campaign.status = new_status

        now = datetime.now(timezone.utc)
        if new_status == "OPENED" and campaign.opened_at is None:
            campaign.opened_at = now
        elif new_status == "RESPONDED" and campaign.responded_at is None:
            campaign.responded_at = now

        db.commit()
        db.refresh(campaign)
        logger.info("Campaign %s status updated to %s", campaign_id, new_status)
        return campaign
