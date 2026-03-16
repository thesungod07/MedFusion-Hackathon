"""
WHO Global Health Observatory (GHO) OData integration.

Fetches real indicator data from the WHO GHO API for disease-specific
surveillance metrics. Normalises results into the shared internal
epidemiology schema used across all MedFusion services.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

WHO_GHO_BASE = "https://ghoapi.who.int/api"

# Mapping from user-facing disease names → WHO GHO indicator codes.
# Each entry maps to a tuple: (indicator_code, value_field).
DISEASE_INDICATOR_MAP: Dict[str, str] = {
    "malaria": "MALARIA_EST_CASES",
    "tuberculosis": "MDG_0000000020",
    "measles": "WHS8_110",
    "cholera": "CHOLERA_0000000001",
    "hepatitis b": "WHS4_128",
    "yellow fever": "WHS3_56",
    "polio": "POLIO_REPORTED_CASES",
    "hiv/aids": "MDG_0000000029",
}

# ISO-3 → country-name fallback (subset used in MedFusion).
COUNTRY_ISO3_MAP: Dict[str, str] = {
    "india": "IND",
    "united states": "USA",
    "united kingdom": "GBR",
    "germany": "DEU",
    "france": "FRA",
    "italy": "ITA",
    "spain": "ESP",
    "brazil": "BRA",
    "south africa": "ZAF",
    "japan": "JPN",
    "china": "CHN",
    "australia": "AUS",
    "russia": "RUS",
    "canada": "CAN",
    "mexico": "MEX",
    "nigeria": "NGA",
    "kenya": "KEN",
    "egypt": "EGY",
    "indonesia": "IDN",
    "thailand": "THA",
    "south korea": "KOR",
    "turkey": "TUR",
    "saudi arabia": "SAU",
    "argentina": "ARG",
    "colombia": "COL",
    "pakistan": "PAK",
    "bangladesh": "BGD",
    "philippines": "PHL",
    "vietnam": "VNM",
    "new zealand": "NZL",
}


async def _fetch_gho_json(url: str, params: Optional[Dict[str, str]] = None) -> Any:
    """Thin HTTP wrapper for WHO GHO API calls."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        if resp.status_code == 404:
            raise ValueError(f"WHO GHO resource not found: {url}")
        resp.raise_for_status()
        return resp.json()


async def get_who_indicator_series(
    indicator_code: str, country: str
) -> List[Dict[str, Any]]:
    """
    Fetch time-series data from the WHO GHO OData API for a specific
    indicator and country.

    Returns a list of {date, cases, deaths} dicts (deaths fixed at 0 since
    WHO indicators are typically single-metric).
    """
    iso3 = COUNTRY_ISO3_MAP.get(country.lower(), country.upper()[:3])

    filter_expr = f"SpatialDim eq '{iso3}'"
    url = f"{WHO_GHO_BASE}/{indicator_code}"
    params = {"$filter": filter_expr}

    try:
        data = await _fetch_gho_json(url, params=params)
    except Exception:
        # Graceful degradation – return empty series so orchestrator continues.
        return []

    values = data.get("value", [])
    points: List[Dict[str, Any]] = []
    for entry in values:
        year = entry.get("TimeDim") or entry.get("TimeDimensionValue")
        numeric = entry.get("NumericValue")
        if year is None or numeric is None:
            continue
        try:
            year_int = int(str(year)[:4])
            value = float(numeric)
        except (ValueError, TypeError):
            continue
        points.append({
            "date": f"{year_int}-01-01",
            "cases": int(value),
            "deaths": 0,
            "source": "who_gho",
        })

    points.sort(key=lambda p: p["date"])
    return points


async def get_who_disease_series(
    disease: str, country: str
) -> List[Dict[str, Any]]:
    """
    High-level helper: resolves a disease name to its WHO indicator code
    and fetches the series for the given country.
    """
    indicator = DISEASE_INDICATOR_MAP.get(disease.lower())
    if not indicator:
        return []
    return await get_who_indicator_series(indicator, country)
