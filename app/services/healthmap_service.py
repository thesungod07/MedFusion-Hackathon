"""
HealthMap integration — outbreak alert monitoring.

HealthMap aggregates outbreak reports from multiple sources (news, ProMED,
WHO, etc.) and exposes them through a map-based interface. The public API
requires an API key for full access, so we use their openly available
RSS/Atom feed to pull recent outbreak alerts.

For the prototype, we fetch alerts and normalise them into the MedFusion
alert schema: {date, location, disease, severity, headline, source}.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Dict, List

import httpx

# HealthMap public RSS feed for recent alerts (no API key needed).
HEALTHMAP_RSS_URL = "https://www.healthmap.org/getAlerts.php"

# ProMED RSS as a supplementary HealthMap-style alert source (public).
PROMED_RSS_URL = "https://promedmail.org/feed/"


async def _fetch_rss(url: str, params: Dict[str, str] | None = None) -> str:
    """Fetch raw RSS/XML content."""
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.text


def _parse_rss_items(xml_text: str) -> List[Dict[str, str]]:
    """
    Parse a standard RSS 2.0 feed and extract items.
    Returns list of {title, link, pubDate, description}.
    """
    items: List[Dict[str, str]] = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.iter("item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "").strip()
            description = item.findtext("description", "").strip()
            if title:
                items.append({
                    "title": title,
                    "link": link,
                    "pubDate": pub_date,
                    "description": description[:300],
                })
    except ET.ParseError:
        pass
    return items


def _parse_rss_date(date_str: str) -> str:
    """Try to parse RSS date formats into ISO date."""
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.date().isoformat()
    except Exception:
        pass
    # Fallback: try common formats
    from datetime import datetime
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str[:25], fmt).date().isoformat()
        except (ValueError, TypeError):
            continue
    return ""


async def get_healthmap_alerts(
    disease: str, region: str
) -> List[Dict[str, Any]]:
    """
    Fetch recent outbreak alerts from HealthMap-style sources.

    Returns a normalised list for the UI's alert timeline:
    {date, location, disease, severity, headline, source, link}

    Since HealthMap's full API requires authentication, we fall back to
    a curated set of public health alert feeds (HealthMap RSS + ProMED).
    """
    alerts: List[Dict[str, Any]] = []

    # ── Attempt HealthMap RSS ───────────────────────────────────────────
    try:
        xml_text = await _fetch_rss(HEALTHMAP_RSS_URL, params={
            "dtype": disease.lower().replace(" ", "+"),
        })
        items = _parse_rss_items(xml_text)
        for item in items[:50]:
            date = _parse_rss_date(item["pubDate"])
            if not date:
                continue
            # Crude region filter: check if region name appears in title/description.
            text_blob = (item["title"] + " " + item["description"]).lower()
            region_match = region.lower() in text_blob or region.lower() == "global"
            alerts.append({
                "date": date,
                "location": region if region_match else "Global",
                "disease": disease,
                "severity": "medium",
                "headline": item["title"][:200],
                "source": "healthmap",
                "link": item["link"],
                "region_match": region_match,
            })
    except Exception:
        pass

    # ── Attempt ProMED RSS as supplementary ─────────────────────────────
    try:
        xml_text = await _fetch_rss(PROMED_RSS_URL)
        items = _parse_rss_items(xml_text)
        disease_lower = disease.lower()
        for item in items[:30]:
            # Filter by disease mention in title.
            if disease_lower not in item["title"].lower() and disease_lower not in item["description"].lower():
                continue
            date = _parse_rss_date(item["pubDate"])
            if not date:
                continue
            text_blob = (item["title"] + " " + item["description"]).lower()
            region_match = region.lower() in text_blob or region.lower() == "global"
            alerts.append({
                "date": date,
                "location": region if region_match else "Global",
                "disease": disease,
                "severity": "high",
                "headline": item["title"][:200],
                "source": "healthmap",
                "link": item["link"],
                "region_match": region_match,
            })
    except Exception:
        pass

    # Sort by date descending (most recent first).
    alerts.sort(key=lambda a: a["date"], reverse=True)

    # Convert to epi series format for merge compatibility.
    # Alerts don't have numeric case data, so we return them as-is for the
    # alert timeline; the orchestrator will handle them separately.
    return alerts


async def get_healthmap_epi_series(
    disease: str, region: str
) -> List[Dict[str, Any]]:
    """
    Convert HealthMap alerts into a pseudo-epi-series by counting alerts per day.
    Each alert is treated as count=1 for merge into the main series.
    """
    alerts = await get_healthmap_alerts(disease, region)
    # Group by date
    date_counts: Dict[str, int] = {}
    for alert in alerts:
        d = alert.get("date", "")
        if d and alert.get("region_match", True):
            date_counts[d] = date_counts.get(d, 0) + 1

    points: List[Dict[str, Any]] = [
        {"date": d, "cases": count, "deaths": 0, "source": "healthmap"}
        for d, count in date_counts.items()
    ]
    points.sort(key=lambda p: p["date"])
    return points
