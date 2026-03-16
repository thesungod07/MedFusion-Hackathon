"""
UK Government health statistics integration.

Fetches COVID-19 surveillance data from the UK Gov Coronavirus Dashboard API
(api.coronavirus.data.gov.uk). This is a well-documented, public API that
provides daily case and death counts for the UK and its constituent nations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

# UK Gov COVID-19 Dashboard API v1.
UKGOV_API_BASE = "https://api.coronavirus.data.gov.uk/v1/data"

# Map user-facing names → UK Gov area types and names.
UK_AREA_MAP: Dict[str, Dict[str, str]] = {
    "united kingdom": {"areaType": "overview", "areaName": "United Kingdom"},
    "england": {"areaType": "nation", "areaName": "England"},
    "scotland": {"areaType": "nation", "areaName": "Scotland"},
    "wales": {"areaType": "nation", "areaName": "Wales"},
    "northern ireland": {"areaType": "nation", "areaName": "Northern Ireland"},
}


async def get_ukgov_health_series(
    disease: str, region: str | None = None
) -> List[Dict[str, Any]]:
    """
    Fetch daily COVID-19 case and death data from the UK Gov API.

    Only returns data for UK regions (returns empty for non-UK countries).
    The API provides cumulative and daily new counts.

    Returns normalised {date, cases, deaths, source} list.
    """
    if disease.lower() not in {"covid-19", "covid", "coronavirus"}:
        return []

    region_lower = (region or "united kingdom").strip().lower()
    area_config = UK_AREA_MAP.get(region_lower)
    if not area_config:
        # Not a UK region — skip.
        return []

    filters = [
        f"areaType={area_config['areaType']}",
    ]
    if area_config["areaType"] != "overview":
        filters.append(f"areaName={area_config['areaName']}")

    params = {
        "filters": ";".join(filters),
        "structure": '{"date":"date","cases":"cumCasesByPublishDate","deaths":"cumDeaths28DaysByPublishDate","newCases":"newCasesByPublishDate","newDeaths":"newDeaths28DaysByPublishDate"}',
        "format": "json",
        "page": "1",
    }

    all_points: List[Dict[str, Any]] = []

    try:
        page = 1
        while page <= 10:  # Safety limit.
            params["page"] = str(page)
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(UKGOV_API_BASE, params=params)

                if resp.status_code == 204:
                    break  # No more data.
                if resp.status_code != 200:
                    break

                data = resp.json()
                records = data.get("data", [])
                if not records:
                    break

                for row in records:
                    date = row.get("date", "")
                    cases = row.get("cases")
                    deaths = row.get("deaths")
                    if not date:
                        continue

                    all_points.append({
                        "date": date,
                        "cases": int(cases) if cases is not None else 0,
                        "deaths": int(deaths) if deaths is not None else 0,
                        "source": "ukgov",
                    })

                # Check for pagination.
                pagination = data.get("pagination", {})
                if not pagination.get("next"):
                    break
                page += 1

    except Exception:
        return []

    all_points.sort(key=lambda p: p["date"])
    return all_points
