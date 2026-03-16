"""
CDC Open Data Portal + FluView integration.

Fetches real surveillance data from the CDC Socrata (SODA) API:
- COVID-19 case surveillance via data.cdc.gov
- ILINet influenza data via the CDC FluView API

Both endpoints are public and require no API key.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

import httpx

# CDC COVID-19 case surveillance — aggregate weekly counts by state.
# Dataset: "United States COVID-19 Cases and Deaths by State over Time"
CDC_COVID_URL = "https://data.cdc.gov/resource/9mfq-cb36.json"

# CDC FluView ILINet — influenza-like illness surveillance.
CDC_FLUVIEW_URL = "https://data.cdc.gov/resource/vqg4-jctw.json"

# Map user-facing region names → CDC state abbreviations (subset).
STATE_MAP: Dict[str, str] = {
    "united states": "",  # empty = all states combined
}


async def _fetch_cdc_json(url: str, params: Optional[Dict[str, str]] = None) -> Any:
    """Thin HTTP wrapper for CDC SODA API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        if resp.status_code == 404:
            raise ValueError(f"CDC resource not found: {url}")
        resp.raise_for_status()
        return resp.json()


async def get_cdc_indicator_series(
    disease: str, region: str
) -> List[Dict[str, Any]]:
    """
    Fetch COVID-19 case surveillance data from the CDC SODA API.

    Returns a normalised list of {date, cases, deaths, source} dicts.
    The data covers US states / territories aggregated over time.
    """
    if disease.lower() not in {"covid-19", "covid", "coronavirus"}:
        return []

    try:
        params: Dict[str, str] = {
            "$order": "submission_date ASC",
            "$limit": "5000",
        }

        # If a specific US state is requested, filter; otherwise aggregate.
        state_code = STATE_MAP.get(region.lower())
        if state_code is None:
            # Not a US region — CDC data won't apply.
            # Still return data tagged to "US" that the merge can use if the
            # user has selected "United States" as region.
            if region.lower() not in {"united states", "us", "usa"}:
                return []

        if state_code:
            params["state"] = state_code

        data = await _fetch_cdc_json(CDC_COVID_URL, params=params)
    except Exception:
        return []

    # Aggregate by date across states when no single-state filter is used.
    date_agg: Dict[str, Dict[str, int]] = {}
    for row in data:
        date_raw = row.get("submission_date", "")[:10]  # "2021-03-15T00:00:00.000"
        if not date_raw:
            continue
        try:
            new_cases = int(float(row.get("new_case", 0) or 0))
            new_deaths = int(float(row.get("new_death", 0) or 0))
            tot_cases = int(float(row.get("tot_cases", 0) or 0))
            tot_deaths = int(float(row.get("tot_death", 0) or 0))
        except (ValueError, TypeError):
            continue

        if date_raw not in date_agg:
            date_agg[date_raw] = {"cases": 0, "deaths": 0}
        date_agg[date_raw]["cases"] = max(date_agg[date_raw]["cases"], tot_cases)
        date_agg[date_raw]["deaths"] = max(date_agg[date_raw]["deaths"], tot_deaths)

    points: List[Dict[str, Any]] = [
        {"date": d, "cases": v["cases"], "deaths": v["deaths"], "source": "cdc"}
        for d, v in date_agg.items()
    ]
    points.sort(key=lambda p: p["date"])
    return points


async def get_fluview_influenza_series(region: str) -> List[Dict[str, Any]]:
    """
    Fetch CDC FluView ILINet influenza-like illness data.

    Returns weekly ILI counts normalised as {date, cases, deaths, source}.
    Deaths are set to 0 since ILINet reports ILI%, not mortality.
    """
    try:
        params = {
            "$order": "weekend ASC",
            "$limit": "5000",
        }
        data = await _fetch_cdc_json(CDC_FLUVIEW_URL, params=params)
    except Exception:
        return []

    points: List[Dict[str, Any]] = []
    for row in data:
        date_raw = row.get("weekend", "")[:10]
        ili_total = row.get("ilitotal")
        if not date_raw or ili_total is None:
            continue
        try:
            points.append({
                "date": date_raw,
                "cases": int(float(ili_total)),
                "deaths": 0,
                "source": "cdc_fluview",
            })
        except (ValueError, TypeError):
            continue

    points.sort(key=lambda p: p["date"])
    return points
