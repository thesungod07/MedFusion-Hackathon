from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .services.disease_service import (
    get_global_disease_summary,
    get_country_disease_summary,
    get_country_disease_trend,
)
from .services.analytics_service import AnalyticsQuery, run_analytics_query, get_sources_status


app = FastAPI(
    title="MedFusion Disease Surveillance Backend",
    description="Prototype backend for an interactive intelligence dashboard for disease surveillance.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the static frontend dashboard at /ui
app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@app.get("/surveillance/global")
async def surveillance_global():
    """
    High-level global disease surveillance snapshot.
    """
    try:
        return await get_global_disease_summary()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/surveillance/country/{country}")
async def surveillance_country(
    country: str,
    days: int = Query(30, ge=1, le=365, description="Number of days of history for trends."),
):
    """
    Country-level view combining current snapshot + recent trend.
    """
    try:
        summary = await get_country_disease_summary(country)
        trend = await get_country_disease_trend(country, days=days)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "country": summary.country,
        "iso2": summary.iso2,
        "iso3": summary.iso3,
        "population": summary.population,
        "current_burden": {
            "cases": summary.cases,
            "todayCases": summary.today_cases,
            "deaths": summary.deaths,
            "todayDeaths": summary.today_deaths,
            "recovered": summary.recovered,
            "active": summary.active,
            "critical": summary.critical,
            "casesPerOneMillion": summary.cases_per_million,
            "deathsPerOneMillion": summary.deaths_per_million,
        },
        "trend": trend,
        "source": "disease.sh",
    }


@app.get("/surveillance/ping")
async def surveillance_ping() -> dict:
    """
    Convenience endpoint for quick smoke tests that backend is running.
    """
    return {"message": "MedFusion surveillance backend is alive"}


@app.get("/sources/status")
async def sources_status():
    """
    Returns status and metadata for all registered data sources.
    """
    return get_sources_status()


@app.post("/analytics/query")
async def analytics_query(query: AnalyticsQuery):
    """
    Interactive analytics endpoint.

    Currently powered by disease.sh, WHO GHO, and OWID data; the orchestration
    layer is designed so additional sources (CDC, HealthMap, ProMED, IHME,
    ECDC, UK Gov) can be plugged in later without changing this contract.
    """
    try:
        result = await run_analytics_query(query)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
