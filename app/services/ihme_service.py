"""
IHME GHDx (Global Health Data Exchange) integration.

The IHME publishes COVID-19 projections and historical burden estimates.
Their data is distributed as downloadable CSV files. For the prototype,
we use the IHME COVID-19 projections dataset which provides modelled
estimates of infections, deaths, and hospital resource usage.

The IHME also publishes the Global Burden of Disease (GBD) data for
other diseases (malaria, TB, etc.) — we integrate those where available.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

import httpx

# IHME COVID-19 projections — summary CSV hosted on IHME's data portal.
# This is the reference-scenario summary with key metrics per location per day.
IHME_COVID_SUMMARY_URL = (
    "https://ihmecovid19storage.blob.core.windows.net/latest/data_download_file_reference_2020.csv"
)

# Alternative: IHME COVID-19 results at broader scope.
IHME_COVID_RESULTS_URL = (
    "https://raw.githubusercontent.com/ihmeuw-demographics/covid-modeling/"
    "main/data/summary_stats_all_locs.csv"
)

# IHME Global Burden of Disease — select indicator URLs.
# These provide country-level burden estimates for major diseases.
IHME_GBD_BASE = "https://ghdx.healthdata.org"

# Country name mapping for IHME location matching.
IHME_LOCATION_MAP: Dict[str, str] = {
    "india": "India",
    "united states": "United States of America",
    "united kingdom": "United Kingdom",
    "south africa": "South Africa",
    "south korea": "Republic of Korea",
    "saudi arabia": "Saudi Arabia",
    "new zealand": "New Zealand",
}

# In-memory cache.
_cache: Dict[str, Any] = {"data": None, "ts": 0}


def _normalize_location(country: str) -> str:
    """Resolve user input to IHME location name."""
    lowered = country.strip().lower()
    return IHME_LOCATION_MAP.get(lowered, country.strip().title())


async def _fetch_ihme_csv(url: str) -> List[Dict[str, str]]:
    """Download and parse an IHME CSV file with caching."""
    import time

    now = time.time()
    cache_key = url
    if _cache.get(cache_key) is not None and (now - _cache.get(f"{cache_key}_ts", 0)) < 900:
        return _cache[cache_key]

    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        _cache[cache_key] = rows
        _cache[f"{cache_key}_ts"] = now
        return rows
    except Exception:
        return []


async def get_ihme_burden_series(
    disease: str, state: str | None = None
) -> List[Dict[str, Any]]:
    """
    Fetch IHME burden/projection data for a specific disease and location.

    For COVID-19: attempts to fetch IHME projection data.
    For other diseases: returns modelled GBD estimates if available.

    Returns normalised {date, cases, deaths, source} list.
    """
    location = _normalize_location(state or "India")

    if disease.lower() in {"covid-19", "covid", "coronavirus"}:
        return await _fetch_ihme_covid(location)

    # For non-COVID diseases, attempt GBD-style estimates.
    return await _fetch_ihme_gbd_estimates(disease, location)


async def _fetch_ihme_covid(location: str) -> List[Dict[str, Any]]:
    """Fetch IHME COVID-19 projection data for a location."""
    try:
        rows = await _fetch_ihme_csv(IHME_COVID_SUMMARY_URL)
    except Exception:
        rows = []

    if not rows:
        # Fallback: try alternative URL.
        try:
            rows = await _fetch_ihme_csv(IHME_COVID_RESULTS_URL)
        except Exception:
            return []

    if not rows:
        return []

    # Filter for the target location.
    location_lower = location.lower()
    filtered = [
        r for r in rows
        if r.get("location_name", "").lower() == location_lower
        or r.get("location", "").lower() == location_lower
    ]

    points: List[Dict[str, Any]] = []
    for row in filtered:
        date = row.get("date", "")
        if not date:
            continue

        # IHME provides various metrics: totdea_mean, inf_mean, etc.
        try:
            deaths = int(float(row.get("totdea_mean", 0) or 0))
            infections = int(float(row.get("inf_mean", 0) or row.get("confirmed_infections", 0) or 0))
        except (ValueError, TypeError):
            continue

        if infections == 0 and deaths == 0:
            continue

        points.append({
            "date": date[:10],
            "cases": infections,
            "deaths": deaths,
            "source": "ihme",
        })

    points.sort(key=lambda p: p["date"])
    return points


async def _fetch_ihme_gbd_estimates(
    disease: str, location: str
) -> List[Dict[str, Any]]:
    """
    Fetch Global Burden of Disease estimates for non-COVID diseases.

    GBD data is primarily available as downloadable CSV; for the prototype
    we return estimates from the IHME Results Tool API if accessible.
    """
    # The IHME GBD Results Tool doesn't have a simple public REST API —
    # data is typically downloaded through their web portal. For the prototype,
    # we construct estimates from known GBD reference data.

    # Disease → GBD cause mapping (for future expansion).
    gbd_cause_map = {
        "malaria": "Malaria",
        "tuberculosis": "Tuberculosis",
        "hiv/aids": "HIV/AIDS",
        "measles": "Measles",
        "dengue": "Dengue",
        "cholera": "Diarrheal diseases",
    }

    cause = gbd_cause_map.get(disease.lower())
    if not cause:
        return []

    # GBD estimates are typically annual; we return yearly estimates.
    # For a real integration, this would pull from the IHME API or
    # pre-loaded CSV data.
    try:
        # Attempt to query the IHME Viz Hub API for GBD estimates.
        url = f"https://vizhub.healthdata.org/gbd-results/api/data"
        params = {
            "cause": cause,
            "location": location,
            "metric": "Number",
            "measure": "Incidence",
        }
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                points = []
                for entry in data.get("data", []):
                    year = entry.get("year")
                    value = entry.get("val")
                    if year and value:
                        points.append({
                            "date": f"{year}-01-01",
                            "cases": int(float(value)),
                            "deaths": 0,
                            "source": "ihme",
                        })
                points.sort(key=lambda p: p["date"])
                return points
    except Exception:
        pass

    return []
