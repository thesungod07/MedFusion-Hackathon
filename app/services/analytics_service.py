from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .disease_service import (
    get_country_disease_summary,
    get_country_disease_trend,
    get_global_disease_summary,
    get_global_disease_trend,
)
from .who_service import get_who_disease_series, get_who_disease_series_global
from .owid_service import get_owid_country_series
from .cdc_service import get_cdc_indicator_series
from .ecdc_service import get_ecdc_indicator_series
from .healthmap_service import get_healthmap_epi_series
from .promed_service import get_promed_epi_series
from .ihme_service import get_ihme_burden_series
from .ukgov_service import get_ukgov_health_series


MetricName = Literal["incidence", "growth_rate", "7d_moving_avg"]


class AnalyticsQuery(BaseModel):
    disease: str = Field(description="Disease name (free text; later mapped to ICD-10/ICD-11).")
    region: str = Field(description="Country or region identifier (e.g., 'India').")
    time_window: str = Field(
        default="30d",
        description="Time window such as '30d', '12w', or '1y'. Currently only 'Xd' supported.",
    )
    metrics: List[MetricName] = Field(
        default_factory=lambda: ["incidence", "7d_moving_avg"],
        description="Derived metrics to compute for interactive analytics.",
    )
    sources: List[str] = Field(
        default_factory=lambda: ["disease_sh"],
        description="Data sources to query. Supported: disease_sh, who, owid, cdc, ecdc, healthmap, promed, ihme, ukgov.",
    )


class AnalyticsSeriesPoint(BaseModel):
    date: str
    cases: int
    deaths: int
    new_cases: Optional[int] = None
    new_deaths: Optional[int] = None
    incidence_per_100k: Optional[float] = None
    growth_rate: Optional[float] = None
    moving_avg_7d: Optional[float] = None
    source: Optional[str] = None
    is_cumulative: Optional[bool] = None


class AnalyticsResult(BaseModel):
    disease: str
    region: str
    time_window: str
    sources: List[str]
    series: List[AnalyticsSeriesPoint]
    summary: Dict[str, Any]


def _parse_time_window(window: str) -> int:
    if window.endswith("d") and window[:-1].isdigit():
        return int(window[:-1])
    return 30


def _compute_incidence(series: List[Dict[str, Any]], population: int) -> None:
    if population <= 0:
        return
    for point in series:
        point["incidence_per_100k"] = (point["cases"] / population) * 100_000


def _compute_growth_rate(series: List[Dict[str, Any]]) -> None:
    prev_cases: Optional[int] = None
    for point in series:
        if point.get("is_cumulative") is False:
            point["growth_rate"] = None
            continue
        cases = point["cases"]
        if prev_cases is None or prev_cases == 0:
            point["growth_rate"] = None
        else:
            point["growth_rate"] = (cases - prev_cases) / prev_cases
        prev_cases = cases


def _compute_moving_avg_7d(series: List[Dict[str, Any]]) -> None:
    window: List[int] = []
    for point in series:
        base = point.get("new_cases")
        if base is None:
            base = point.get("cases", 0)
        window.append(int(base))
        if len(window) > 7:
            window.pop(0)
        point["moving_avg_7d"] = sum(window) / len(window)


def _merge_series(
    primary: List[Dict[str, Any]],
    secondary: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge two series by date, preferring primary data where available."""
    primary_dates = {p["date"] for p in primary}
    merged = list(primary)
    for pt in secondary:
        if pt["date"] not in primary_dates:
            merged.append(pt)
    merged.sort(key=lambda p: p["date"])
    return merged


def _compute_deltas(series: List[Dict[str, Any]]) -> None:
    """
    Populate new_cases/new_deaths.

    - If is_cumulative is True: deltas are day-over-day diffs (clamped at >=0)
    - If is_cumulative is False: treat cases/deaths as already "per-period"
    """
    prev_cases: Optional[int] = None
    prev_deaths: Optional[int] = None

    for pt in series:
        is_cum = pt.get("is_cumulative", True)
        cases = int(pt.get("cases", 0))
        deaths = int(pt.get("deaths", 0))

        if is_cum:
            if prev_cases is None:
                pt["new_cases"] = None
            else:
                pt["new_cases"] = max(0, cases - prev_cases)

            if prev_deaths is None:
                pt["new_deaths"] = None
            else:
                pt["new_deaths"] = max(0, deaths - prev_deaths)
        else:
            pt["new_cases"] = cases
            pt["new_deaths"] = deaths

        prev_cases = cases
        prev_deaths = deaths


# ---------------------------------------------------------------------------
# Data source availability registry
# ---------------------------------------------------------------------------

DATA_SOURCES = {
    "disease_sh": {
        "name": "disease.sh",
        "description": "Open disease surveillance API — real-time COVID-19 data",
        "status": "active",
        "url": "https://disease.sh",
    },
    "who": {
        "name": "WHO GHO",
        "description": "World Health Organization Global Health Observatory OData API",
        "status": "active",
        "url": "https://ghoapi.who.int",
    },
    "owid": {
        "name": "Our World in Data",
        "description": "OWID COVID-19 dataset — comprehensive global indicators",
        "status": "active",
        "url": "https://ourworldindata.org",
    },
    "cdc": {
        "name": "CDC",
        "description": "US CDC Open Data Portal — COVID-19 case surveillance + FluView ILINet",
        "status": "active",
        "url": "https://data.cdc.gov",
    },
    "ecdc": {
        "name": "ECDC",
        "description": "European Centre for Disease Prevention and Control — weekly case/death data",
        "status": "active",
        "url": "https://opendata.ecdc.europa.eu",
    },
    "healthmap": {
        "name": "HealthMap",
        "description": "Real-time automated disease outbreak alerts via RSS feeds",
        "status": "active",
        "url": "https://healthmap.org",
    },
    "promed": {
        "name": "ProMED Mail",
        "description": "Human-curated infectious disease outbreak reports via RSS",
        "status": "active",
        "url": "https://promedmail.org",
    },
    "ihme": {
        "name": "IHME GHDx",
        "description": "Institute for Health Metrics — COVID projections + Global Burden of Disease",
        "status": "active",
        "url": "https://ghdx.healthdata.org",
    },
    "ukgov": {
        "name": "UK Gov",
        "description": "UK Government COVID-19 Dashboard API — daily UK case/death data",
        "status": "active",
        "url": "https://coronavirus.data.gov.uk",
    },
}


def get_sources_status() -> Dict[str, Any]:
    """Return availability and metadata of all registered data sources."""
    return {
        "sources": DATA_SOURCES,
        "active_count": sum(1 for s in DATA_SOURCES.values() if s["status"] == "active"),
        "total_count": len(DATA_SOURCES),
    }


async def run_analytics_query(query: AnalyticsQuery) -> AnalyticsResult:
    """
    Interactive analytics orchestration.

    Fans out to all requested data sources, merges time-series data,
    computes derived metrics, and returns a unified result.
    """
    region_normalized = query.region.strip()
    is_global = region_normalized.lower() in {"global", "world", "all"}
    is_covid = query.disease.lower() in {"covid-19", "covid", "coronavirus"}

    # ── Fetch basic metadata (population) from disease.sh ────────────────
    # We fetch this even for non-COVID queries to get accurate population numbers.
    try:
        if is_global:
            dsh_summary = await get_global_disease_summary()
            population = 0
            country_name = "Global"
        else:
            country_summary = await get_country_disease_summary(region_normalized)
            population = country_summary.population
            country_name = country_summary.country
            dsh_summary = {
                "cases": country_summary.cases,
                "deaths": country_summary.deaths,
                "active": country_summary.active,
                "critical": country_summary.critical,
                "recovered": country_summary.recovered,
            }
    except Exception:
        # Fallback if disease.sh API completely fails for this country
        population = 0
        country_name = region_normalized.title()
        dsh_summary = {"cases": 0, "deaths": 0, "active": 0, "critical": 0, "recovered": 0}

    filtered: List[Dict[str, Any]] = []

    # ── Primary data from disease.sh ────────────────────────────────────
    if "disease_sh" in query.sources and is_covid:
        try:
            if is_global:
                trend = await get_global_disease_trend(days=3650)
            else:
                trend = await get_country_disease_trend(region_normalized, days=3650)
                
            filtered = [
                {
                    "date": p["date"],
                    "cases": p["cases"],
                    "deaths": p["deaths"],
                    "source": "disease_sh",
                    "is_cumulative": True,
                }
                for p in trend
            ]
        except Exception:
            pass

    # ── WHO GHO enrichment ──────────────────────────────────────────────
    if "who" in query.sources:
        try:
            if is_global:
                who_series = await get_who_disease_series_global(query.disease)
            else:
                who_series = await get_who_disease_series(query.disease, region_normalized)
            if who_series:
                # WHO indicators are typically per-year counts/rates, not cumulative.
                for p in who_series:
                    p["is_cumulative"] = False
                filtered = _merge_series(filtered, who_series)
        except Exception:
            pass

    # ── OWID enrichment ─────────────────────────────────────────────────
    if "owid" in query.sources and not is_global:
        try:
            owid_series = await get_owid_country_series(query.disease, region_normalized)
            if owid_series:
                owid_normalised = [
                    {
                        "date": p["date"],
                        "cases": p["cases"],
                        "deaths": p["deaths"],
                        "source": "owid",
                        "is_cumulative": True,
                        "new_cases": p.get("new_cases"),
                        "new_deaths": p.get("new_deaths"),
                    }
                    for p in owid_series
                ]
                filtered = _merge_series(filtered, owid_normalised)
        except Exception:
            pass

    # ── CDC enrichment ──────────────────────────────────────────────────
    if "cdc" in query.sources:
        try:
            cdc_series = await get_cdc_indicator_series(query.disease, region_normalized)
            if cdc_series:
                filtered = _merge_series(filtered, cdc_series)
        except Exception:
            pass

    # ── ECDC enrichment ─────────────────────────────────────────────────
    if "ecdc" in query.sources and not is_global:
        try:
            ecdc_series = await get_ecdc_indicator_series(query.disease, region_normalized)
            if ecdc_series:
                filtered = _merge_series(filtered, ecdc_series)
        except Exception:
            pass

    # ── HealthMap alert enrichment ──────────────────────────────────────
    if "healthmap" in query.sources:
        try:
            hm_series = await get_healthmap_epi_series(query.disease, region_normalized)
            if hm_series:
                filtered = _merge_series(filtered, hm_series)
        except Exception:
            pass

    # ── ProMED alert enrichment ─────────────────────────────────────────
    if "promed" in query.sources:
        try:
            pm_series = await get_promed_epi_series(query.disease, region_normalized)
            if pm_series:
                filtered = _merge_series(filtered, pm_series)
        except Exception:
            pass

    # ── IHME enrichment ─────────────────────────────────────────────────
    if "ihme" in query.sources and not is_global:
        try:
            ihme_series = await get_ihme_burden_series(query.disease, state=region_normalized)
            if ihme_series:
                filtered = _merge_series(filtered, ihme_series)
        except Exception:
            pass

    # ── UK Gov enrichment ───────────────────────────────────────────────
    if "ukgov" in query.sources:
        try:
            ukgov_series = await get_ukgov_health_series(query.disease, region=region_normalized)
            if ukgov_series:
                filtered = _merge_series(filtered, ukgov_series)
        except Exception:
            pass

    # ── Compute derived metrics ─────────────────────────────────────────
    _compute_deltas(filtered)
    _compute_incidence(filtered, population=population)
    _compute_growth_rate(filtered)
    _compute_moving_avg_7d(filtered)

    series_models = [AnalyticsSeriesPoint(**p) for p in filtered]

    # Active sources that actually contributed data.
    active_sources = list({p.get("source", "disease_sh") for p in filtered if p.get("source")})

    # Summary values computed from series, or from real-time API if applicable.
    latest_cases = filtered[-1]["cases"] if filtered else 0
    latest_deaths = filtered[-1]["deaths"] if filtered else 0
    
    # Use real-time active/critical from disease.sh if for COVID-19, else estimate/zero.
    if "disease_sh" in active_sources and is_covid:
        active = dsh_summary.get("active", 0)
        critical = dsh_summary.get("critical", 0)
        recovered = dsh_summary.get("recovered", 0)
    else:
        active = 0
        critical = 0
        recovered = 0

    # High-level summary for UI cards/panels.
    result_summary: Dict[str, Any] = {
        "country": country_name,
        "population": population,
        "latest_cases": latest_cases,
        "latest_deaths": latest_deaths,
        "active": active,
        "critical": critical,
        "recovered": recovered,
        "cases_per_million": (latest_cases / population * 1_000_000) if population > 0 else None,
        "deaths_per_million": (latest_deaths / population * 1_000_000) if population > 0 else None,
        "points_returned": len(series_models),
        "active_sources": active_sources,
    }

    return AnalyticsResult(
        disease=query.disease,
        region=query.region,
        time_window=query.time_window,
        sources=active_sources,
        series=series_models,
        summary=result_summary,
    )
