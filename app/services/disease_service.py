from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import httpx
from pydantic import BaseModel, Field


DISEASE_SH_BASE = "https://disease.sh/v3/covid-19"


class GlobalSummary(BaseModel):
    updated: int
    cases: int
    today_cases: int = Field(alias="todayCases")
    deaths: int
    today_deaths: int = Field(alias="todayDeaths")
    recovered: int
    active: int
    critical: int
    affected_countries: int = Field(alias="affectedCountries")


class CountrySummary(BaseModel):
    country: str
    iso2: str | None = None
    iso3: str | None = None

    population: int

    cases: int
    today_cases: int = Field(alias="todayCases")
    deaths: int
    today_deaths: int = Field(alias="todayDeaths")
    recovered: int
    active: int
    critical: int

    cases_per_million: float = Field(alias="casesPerOneMillion")
    deaths_per_million: float = Field(alias="deathsPerOneMillion")


async def _get_json(url: str, params: Dict[str, Any] | None = None) -> Any:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, params=params)
        if response.status_code == 404:
            raise ValueError("Requested resource not found on upstream API.")
        response.raise_for_status()
        return response.json()


async def get_global_disease_summary() -> Dict[str, Any]:
    """
    Fetches a global surveillance snapshot from disease.sh.

    This can be extended later to merge with WHO / CDC sources.
    """
    url = f"{DISEASE_SH_BASE}/all"
    payload = await _get_json(url)
    summary = GlobalSummary.model_validate(payload)

    return {
        "timestamp": summary.updated,
        "timestamp_iso": datetime.utcfromtimestamp(summary.updated / 1000).isoformat() + "Z",
        "cases": summary.cases,
        "todayCases": summary.today_cases,
        "deaths": summary.deaths,
        "todayDeaths": summary.today_deaths,
        "recovered": summary.recovered,
        "active": summary.active,
        "critical": summary.critical,
        "affectedCountries": summary.affected_countries,
        "source": "disease.sh",
    }


async def get_country_disease_summary(country: str) -> CountrySummary:
    """
    Country-level snapshot for disease burden from disease.sh.
    """
    url = f"{DISEASE_SH_BASE}/countries/{country}"
    payload = await _get_json(url, params={"strict": "true"})
    return CountrySummary.model_validate(payload)


async def get_country_disease_trend(country: str, days: int = 30) -> List[Dict[str, Any]]:
    """
    Time series trend for a country's cases and deaths.
    """
    url = f"{DISEASE_SH_BASE}/historical/{country}"
    payload = await _get_json(url, params={"lastdays": days})

    timeline = payload.get("timeline", {})
    cases_ts: Dict[str, int] = timeline.get("cases", {})
    deaths_ts: Dict[str, int] = timeline.get("deaths", {})

    points: List[Dict[str, Any]] = []
    for date_str, cases_value in cases_ts.items():
        deaths_value = deaths_ts.get(date_str, 0)
        # disease.sh dates are in M/D/YY format
        parsed_date = datetime.strptime(date_str, "%m/%d/%y").date()
        points.append(
            {
                "date": parsed_date.isoformat(),
                "cases": cases_value,
                "deaths": deaths_value,
            }
        )

    points.sort(key=lambda p: p["date"])
    return points


async def get_global_disease_trend(days: int = 3650) -> List[Dict[str, Any]]:
    """
    Time series trend for global cases and deaths, aggregated across all countries.
    """
    url = f"{DISEASE_SH_BASE}/historical/all"
    # disease.sh supports 'all' to indicate full history; we cap with `days`.
    lastdays = "all" if days >= 3650 else days
    payload = await _get_json(url, params={"lastdays": lastdays})

    cases_ts: Dict[str, int] = payload.get("cases", {})
    deaths_ts: Dict[str, int] = payload.get("deaths", {})

    points: List[Dict[str, Any]] = []
    for date_str, cases_value in cases_ts.items():
        deaths_value = deaths_ts.get(date_str, 0)
        parsed_date = datetime.strptime(date_str, "%m/%d/%y").date()
        points.append(
            {
                "date": parsed_date.isoformat(),
                "cases": cases_value,
                "deaths": deaths_value,
            }
        )

    points.sort(key=lambda p: p["date"])
    return points

