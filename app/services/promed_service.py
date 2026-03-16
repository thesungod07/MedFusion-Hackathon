"""
ProMED Mail RSS integration.

ProMED (Program for Monitoring Emerging Diseases) is a human-moderated
reporting system for outbreaks. It publishes alerts via an RSS feed that
is publicly accessible without API keys.

This module fetches the ProMED RSS feed and extracts disease-relevant
outbreak reports, normalised into the MedFusion alert schema.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List

import httpx

PROMED_RSS_URL = "https://promedmail.org/feed/"


async def _fetch_promed_rss() -> str:
    """Fetch raw ProMED RSS XML."""
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(PROMED_RSS_URL)
        resp.raise_for_status()
        return resp.text


def _parse_date(date_str: str) -> str:
    """Parse RSS pubDate into ISO date string."""
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.date().isoformat()
    except Exception:
        pass
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str[:25], fmt).date().isoformat()
        except (ValueError, TypeError):
            continue
    return ""


async def get_promed_alerts(
    disease: str, region: str
) -> List[Dict[str, Any]]:
    """
    Fetch outbreak alerts from ProMED Mail RSS feed.

    Filters by disease keyword match in the title and description.
    Returns normalised alerts: {date, location, disease, severity, headline, source, link}.
    """
    try:
        xml_text = await _fetch_promed_rss()
    except Exception:
        return []

    alerts: List[Dict[str, Any]] = []
    disease_lower = disease.lower()
    region_lower = region.lower()

    try:
        root = ET.fromstring(xml_text)
        for item in root.iter("item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "").strip()
            description = item.findtext("description", "").strip()[:500]

            # Check for disease relevance.
            text_blob = (title + " " + description).lower()

            # Map common disease aliases for better matching.
            disease_aliases = {
                "covid-19": ["covid", "coronavirus", "sars-cov-2"],
                "influenza": ["flu", "influenza", "h1n1", "h5n1", "avian flu"],
                "dengue": ["dengue"],
                "malaria": ["malaria", "plasmodium"],
                "tuberculosis": ["tuberculosis", "tb"],
                "measles": ["measles"],
                "cholera": ["cholera", "vibrio"],
                "hiv/aids": ["hiv", "aids"],
                "ebola": ["ebola", "evd"],
                "hepatitis b": ["hepatitis", "hbv"],
                "polio": ["polio", "poliovirus"],
                "yellow fever": ["yellow fever"],
                "zika": ["zika"],
            }

            keywords = disease_aliases.get(disease_lower, [disease_lower])
            is_disease_match = any(kw in text_blob for kw in keywords)

            if not is_disease_match:
                continue

            date = _parse_date(pub_date)
            if not date:
                continue

            region_match = region_lower in text_blob or region_lower == "global"

            alerts.append({
                "date": date,
                "location": region if region_match else "Global",
                "disease": disease,
                "severity": "high",
                "headline": title[:200],
                "source": "promed",
                "link": link,
                "region_match": region_match,
            })
    except ET.ParseError:
        return []

    alerts.sort(key=lambda a: a["date"], reverse=True)
    return alerts


async def get_promed_epi_series(
    disease: str, region: str
) -> List[Dict[str, Any]]:
    """
    Convert ProMED alerts into a pseudo-epi-series by counting
    disease-relevant alerts per day.
    """
    alerts = await get_promed_alerts(disease, region)
    date_counts: Dict[str, int] = {}
    for alert in alerts:
        d = alert.get("date", "")
        if d and alert.get("region_match", True):
            date_counts[d] = date_counts.get(d, 0) + 1

    points: List[Dict[str, Any]] = [
        {"date": d, "cases": count, "deaths": 0, "source": "promed"}
        for d, count in date_counts.items()
    ]
    points.sort(key=lambda p: p["date"])
    return points
