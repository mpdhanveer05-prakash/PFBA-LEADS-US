"""
Groq-powered AI service (free tier — llama-3.3-70b-versatile).
Set GROQ_API_KEY in .env.  Sign up at https://console.groq.com (no credit card needed).
"""
from __future__ import annotations

import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_MODEL = "llama-3.3-70b-versatile"


def _chat(messages: list[dict], temperature: float = 0.3, max_tokens: int = 2048) -> str:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured. Add it to your .env file.")
    resp = httpx.post(
        _GROQ_URL,
        headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
        json={"model": _MODEL, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def generate_appeal_letter(lead: dict) -> str:
    comps_text = ""
    for i, c in enumerate(lead.get("comparable_sales", [])[:5], 1):
        comps_text += (
            f"  {i}. APN {c.get('comp_apn','N/A')} — "
            f"Sale Price: ${float(c.get('sale_price', 0)):,.0f} — "
            f"${float(c.get('price_per_sqft', 0)):,.0f}/sqft — "
            f"Distance: {c.get('distance_miles', 0):.2f} mi\n"
        )
    if not comps_text:
        comps_text = "  No comparable sales data available.\n"

    assessed = float(lead.get("assessed_total", 0))
    market = float(lead.get("market_value_est") or 0)
    gap = float(lead.get("assessment_gap") or 0)
    gap_pct = float(lead.get("gap_pct") or 0) * 100
    savings = float(lead.get("estimated_savings") or 0)
    prob = float(lead.get("appeal_probability") or 0) * 100
    owner = lead.get("owner_name") or "Property Owner"
    deadline_days = lead.get("appeal_deadline_days", 30)
    approval_rate = float(lead.get("approval_rate_hist") or 0.30) * 100

    prompt = f"""You are a professional property tax appeal attorney. Write a formal, compelling property tax appeal letter.

Property Details:
- Owner: {owner}
- Address: {lead.get("address")}, {lead.get("city")}, {lead.get("state")} {lead.get("zip", "")}
- APN (Parcel Number): {lead.get("apn", "N/A")}
- Property Type: {lead.get("property_type")}
- Year Built: {lead.get("year_built", "N/A")}
- Building Size: {lead.get("building_sqft", "N/A")} sq ft
- Bedrooms/Bathrooms: {lead.get("bedrooms", "N/A")}/{lead.get("bathrooms", "N/A")}

Assessment vs. Market Evidence:
- Current Assessed Value: ${assessed:,.0f}
- Independent Market Value Estimate: ${market:,.0f}
- Over-Assessment Amount: ${gap:,.0f} ({gap_pct:.1f}% above market)
- Estimated Annual Tax Savings if Corrected: ${savings:,.0f}

Comparable Sales (Nearby Properties Sold at Market Rate):
{comps_text}
Appeal Strength: {prob:.0f}% probability of success
County Historical Approval Rate: {approval_rate:.0f}%

Write a complete, formal appeal letter that:
1. Is addressed to the {lead.get("county_name")} County Appraisal Review Board
2. Clearly states the assessed value is above market value
3. Cites the comparable sales as supporting evidence
4. Requests a reduction to ${market:,.0f} (the market-supported value)
5. Is professional, persuasive, and legally appropriate
6. Includes a formal closing with signature block for {owner}
7. Mentions the {deadline_days}-day appeal window

Write only the letter, starting with the date line."""

    return _chat([{"role": "user", "content": prompt}], temperature=0.4, max_tokens=1500)


def parse_nl_search(query: str, county_names: list[str]) -> dict:
    county_list = ", ".join(county_names[:20])
    prompt = f"""Convert this property search query into structured JSON filters.

Available counties: {county_list}
Available property types: RESIDENTIAL, COMMERCIAL, INDUSTRIAL
Available tiers: A (highest), B, C, D (lowest)

Query: "{query}"

Return a JSON object with ONLY the fields that are clearly specified:
{{
  "tier": ["A"],                        // array of tier letters
  "county_name": "Travis",              // exact name from available counties
  "property_type": "RESIDENTIAL",       // exact type
  "min_gap_pct": 0.15,                  // minimum over-assessment as decimal
  "min_estimated_savings": 5000,        // minimum annual savings in dollars
  "min_appeal_probability": 0.6,        // minimum probability as decimal
  "sort_by": "estimated_savings",       // field to sort by
  "sort_dir": "desc",                   // asc or desc
  "interpretation": "Tier A residential properties in Travis County over-assessed by more than 15%"
}}

Return ONLY valid JSON. No explanation, no markdown."""

    raw = _chat([{"role": "user", "content": prompt}], temperature=0.1, max_tokens=400)
    # Strip possible markdown code fences
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())
