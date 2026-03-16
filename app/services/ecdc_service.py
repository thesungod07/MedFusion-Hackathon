"""
ECDC (European Centre for Disease Prevention and Control) data integration.

Fetches COVID-19 and other disease data from the ECDC's open data portal.
The ECDC publishes weekly COVID-19 case counts by country as downloadable
JSON/CSV. We use their public data distribution endpoint.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

# ECDC COVID-19 weekly case data — distributed via opendata.ecdc.europa.eu
# This endpoint delivers case/death counts per country per week.
ECDC_COVID_URL = (
    "https://opendata.ecdc.europa.eu/covid19/nationalcasedeath/json/"
)

# Map user-facing country names → ECDC country identifiers.
ECDC_COUNTRY_MAP: Dict[str, str] = {
    "germany": "Germany",
    "france": "France",
    "italy": "Italy",
    "spain": "Spain",
    "united kingdom": "United Kingdom",
    "russia": "Russia",
    "turkey": "Türkiye",
    "india": "India",
    "brazil": "Brazil",
    "south africa": "South Africa",
    "united states": "United States of America",
    "japan": "Japan",
    "china": "China",
    "australia": "Australia",
    "canada": "Canada",
    "mexico": "Mexico",
    "argentina": "Argentina",
    "colombia": "Colombia",
    "nigeria": "Nigeria",
    "kenya": "Kenya",
    "egypt": "Egypt",
    "indonesia": "Indonesia",
    "thailand": "Thailand",
    "south korea": "South Korea",
    "saudi arabia": "Saudi Arabia",
    "pakistan": "Pakistan",
    "bangladesh": "Bangladesh",
    "philippines": "Philippines",
    "vietnam": "Vietnam",
    "new zealand": "New Zealand",
}

# In-memory cache (the JSON file is ~5 MB, so we cache it).
_cache: Dict[str, Any] = {"data": None, "ts": 0}


async def _fetch_ecdc_data() -> List[Dict[str, Any]]:
    """Download ECDC weekly case data (cached for 15 minutes)."""
    import time

    now = time.time()
    if _cache["data"] is not None and (now - _cache["ts"]) < 900:
        return _cache["data"]

    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        resp = await client.get(ECDC_COVID_URL)
        resp.raise_for_status()

    rows = resp.json()
    _cache["data"] = rows
    _cache["ts"] = now
    return rows


async def get_ecdc_indicator_series(
    disease: str, country: str
) -> List[Dict[str, Any]]:
    """
    Fetch weekly COVID-19 case and death counts from ECDC for a specific country.

    Returns normalised {date, cases, deaths, source} list.
    """
    if disease.lower() not in {"covid-19", "covid", "coronavirus"}:
        return []

    ecdc_country = ECDC_COUNTRY_MAP.get(country.lower())
    if not ecdc_country:
        # Try title-case fallback
        ecdc_country = country.strip().title()

    try:
        data = await _fetch_ecdc_data()
    except Exception:
        return []

    # Filter to matching country; ECDC uses "country" field.
    filtered = [
        r for r in data
        if r.get("country", "").lower() == ecdc_country.lower()
    ]

    # ECDC records have: year_week ("2021-W10"), country, indicator, weekly_count, cumulative_count
    # There are two indicators per week: "cases" and "deaths".
    week_data: Dict[str, Dict[str, int]] = {}
    for row in filtered:
        year_week = row.get("year_week", "")
        indicator = row.get("indicator", "").lower()
        weekly_count = row.get("weekly_count")
        cumulative = row.get("cumulative_count")
        if not year_week:
            continue

        if year_week not in week_data:
            week_data[year_week] = {"cases": 0, "deaths": 0}

        try:
            val = int(float(cumulative or weekly_count or 0))
        except (ValueError, TypeError):
            val = 0

        if indicator == "cases":
            week_data[year_week]["cases"] = val
        elif indicator == "deaths":
            week_data[year_week]["deaths"] = val

    # Convert year-week to approximate ISO date (Monday of that week).
    points: List[Dict[str, Any]] = []
    for yw, vals in week_data.items():
        try:
            from datetime import datetime
            # Format: "2021-W10"
            dt = datetime.strptime(yw + "-1", "%Y-W%W-%w")
            iso_date = dt.date().isoformat()
        except (ValueError, TypeError):
            continue

        points.append({
            "date": iso_date,
            "cases": vals["cases"],
            "deaths": vals["deaths"],
            "source": "ecdc",
        })

    points.sort(key=lambda p: p["date"])
    return points
