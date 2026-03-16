"""
Our World in Data (OWID) COVID-19 dataset integration.

Fetches the full OWID COVID-19 CSV from GitHub and filters/normalises it
into the standard MedFusion epidemiology series schema.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

import httpx

OWID_CSV_URL = (
    "https://raw.githubusercontent.com/owid/covid-19-data/"
    "master/public/data/owid-covid-data.csv"
)

# In-memory cache to avoid re-downloading the ~40 MB CSV on every request.
_cache: Dict[str, Any] = {"data": None, "ts": 0}

# Map user-facing country names → OWID location strings.
OWID_LOCATION_MAP: Dict[str, str] = {
    "united states": "United States",
    "united kingdom": "United Kingdom",
    "south africa": "South Africa",
    "south korea": "South Korea",
    "new zealand": "New Zealand",
    "saudi arabia": "Saudi Arabia",
}


def _normalize_location(country: str) -> str:
    """Resolve user input to OWID location name."""
    lowered = country.strip().lower()
    if lowered in OWID_LOCATION_MAP:
        return OWID_LOCATION_MAP[lowered]
    # Title-case fallback works for most single-name countries.
    return country.strip().title()


async def _fetch_owid_csv() -> List[Dict[str, str]]:
    """Download and parse the OWID CSV (cached in-memory)."""
    import time

    now = time.time()
    # Re-fetch at most once per 10 minutes.
    if _cache["data"] is not None and (now - _cache["ts"]) < 600:
        return _cache["data"]

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(OWID_CSV_URL)
        resp.raise_for_status()

    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    _cache["data"] = rows
    _cache["ts"] = now
    return rows


async def get_owid_country_series(
    disease: str, country: str, days: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Return a normalised time-series for a country from the OWID dataset.

    Each point: {date, cases, deaths, new_cases, new_deaths, source}.
    """
    if disease.lower() not in {"covid-19", "covid", "coronavirus"}:
        return []
        
    location = _normalize_location(country)

    try:
        rows = await _fetch_owid_csv()
    except Exception:
        return []

    filtered = [r for r in rows if r.get("location") == location]

    points: List[Dict[str, Any]] = []
    for row in filtered:
        date = row.get("date", "")
        total_cases = row.get("total_cases", "")
        total_deaths = row.get("total_deaths", "")
        new_cases = row.get("new_cases", "")
        new_deaths = row.get("new_deaths", "")
        if not date or not total_cases:
            continue
        try:
            points.append({
                "date": date,
                "cases": int(float(total_cases)),
                "deaths": int(float(total_deaths)) if total_deaths else 0,
                "new_cases": int(float(new_cases)) if new_cases else 0,
                "new_deaths": int(float(new_deaths)) if new_deaths else 0,
                "source": "owid",
            })
        except (ValueError, TypeError):
            continue

    points.sort(key=lambda p: p["date"])

    if days and len(points) > days:
        points = points[-days:]

    return points
