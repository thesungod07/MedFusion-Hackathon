## MedFusion Hackfest Prototype – Interactive Disease Surveillance Backend

**Backend language**: Python  
**Backend framework**: FastAPI  
**Frontend stack**: Static HTML/CSS, vanilla JavaScript, Chart.js  
**Data integration**: disease.sh (live), scaffold for CDC, WHO GHO, FluView, HealthMap, ProMED, IHME GHDx India, ECDC, UK Gov  
**Prototype focus**: Real-time disease surveillance backend and an interactive web UI with global and country views, built to be extended with additional data sources (CDC, WHO, HealthMap, etc.).

---

### Tech Stack (End-to-End)

- **Backend**
  - **Language**: Python 3
  - **Framework**: FastAPI
  - **ASGI server**: Uvicorn (with reload for development)
  - **HTTP client**: httpx (async)
  - **Data modelling / validation**: Pydantic v2
  - **Static files**: FastAPI `StaticFiles` for serving the UI at `/ui`

- **Frontend**
  - **Structure**: Single-page app (`frontend/index.html`) served as static assets
  - **Technologies**:
    - Semantic HTML5
    - Modern CSS (custom design system, responsive layout, dark theme)
    - Vanilla JavaScript (no framework) for state, API calls, and UI interactions
    - Charting: Chart.js (via CDN) for interactive line charts
  - **UX elements**:
    - Dropdowns for disease and country selection
    - Visible-window controls for narrowing the time-range rendered
    - KPI tiles and health/status indicators

- **Data sources and integrations**
  - **Implemented live source**:
    - `disease.sh` COVID‑19 API for:
      - Global snapshot (`/all`)
      - Country snapshots (`/countries/{country}`)
      - Historical timelines (`/historical/{country}`)
       - Global historical timelines (`/historical/all`)
  - **Scaffolded sources (service modules ready)**:
    - CDC Open Data Portal + FluView (`cdc_service.py`)
    - WHO GHO OData (`who_service.py`)
    - HealthMap (`healthmap_service.py`)
    - ProMED Mail RSS (`promed_service.py`)
    - IHME GHDx India (`ihme_service.py`)
    - ECDC databases (`ecdc_service.py`)
    - UK Gov health statistics (`ukgov_service.py`)
  - **Additional open data sources (planned)**
    - Our World In Data COVID‑19 dataset (CSV/API export) for enriched indicators and testing rates.
    - Global.health line-list data for detailed case-level analytics (where licensing permits).
    - Country-level open data portals (e.g. data.gov.in, data.gov for US/UK) for supplementary indicators.

- **Deployment / runtime (prototype)**
  - Local development via `uvicorn app.main:app --reload`
  - Browser access to:
    - JSON APIs under `/health`, `/surveillance/*`, `/analytics/query`
    - UI under `/ui/`

---

### 1. High-Level Overview

- **Goal**: Provide a unified, queryable backend API that can power an interactive disease surveillance dashboard for public health users.
- **Current prototype**:
  - Integrates a real-time disease surveillance source (`disease.sh` API – from the open global disease surveillance ecosystem).
  - Defines a pluggable architecture for all the **required hackfest sources** listed in the event PDF:
    - **CDC Open Data Portal**
    - **WHO GHO OData API**
    - **CDC FluView**
    - **HealthMap**
    - **ProMED Mail**
    - **IHME GHDx India**
    - **ECDC Databases**
    - **UK Gov Health Statistics**
  - Exposes prototype endpoints for:
    - **Global surveillance snapshot** (`/surveillance/global`)
    - **Country-level snapshot + time-series trend** (`/surveillance/country/{country}`)
    - **Interactive analytics query** (`/analytics/query`) that combines filters (disease, region, time window) with derived indicators.
    - **Health / ping endpoints** for observability.
- **Extensibility**: Each external source is represented as its own service module with a standardized interface, so that adding or swapping sources does not require changing the public API shape.

Directory layout:

- `requirements.txt` – Python dependencies for the backend.
- `app/main.py` – FastAPI application definition and HTTP routes.
- `app/services/disease_service.py` – Data integration and transformation logic for the `disease.sh` surveillance source.
- `app/services/` (planned modules) – one module per external data source:
  - `cdc_service.py` – CDC Open Data and FluView ingestion.
  - `who_service.py` – WHO GHO OData indicators.
  - `healthmap_service.py` – HealthMap outbreak feeds.
  - `promed_service.py` – ProMED Mail RSS-based alerts.
  - `ihme_service.py` – IHME GHDx India datasets.
  - `ecdc_service.py` – ECDC European disease data.
  - `ukgov_service.py` – UK Gov health statistics.

---

### 2. Architectural Workflow

#### 2.1 Request Flow (Multi-Source, Interactive)

1. **Client dashboard / front-end** sends an HTTP request to the FastAPI backend:
   - Example surveillance call: `GET /surveillance/country/India?days=60`
   - Example interactive analytics call:  
     `POST /analytics/query` with a JSON body like:
     ```json
     {
       "disease": "COVID-19",
       "region": "India",
       "time_window": "90d",
       "metrics": ["incidence", "growth_rate", "7d_moving_avg"],
       "sources": ["disease_sh", "who", "cdc_fluview"]
     }
     ```
2. **FastAPI router (`app/main.py`)** receives the request and:
   - Validates path, query parameters, and request body schemas.
   - Delegates surveillance calls to `disease_service.py` (and, in the future, CDC/WHO/ECDC services).
   - Delegates analytics calls to an **analytics orchestrator** (e.g. `analytics_service.py`) which fans-out to multiple source modules.
3. **Service layer (`app/services/*.py`)**:
   - Uses async HTTP clients to call external APIs (REST, OData, RSS, CSV).
   - Validates and normalizes responses using Pydantic models per source.
   - Translates each upstream into a **standard internal schema**, e.g.:
     - `EpidemiologyPoint { date, location, disease, cases, deaths, source }`
     - `Alert { date, location, disease, severity, headline, source }`
4. **Analytics orchestration**:
   - Merges normalized data from multiple sources.
   - Applies interactive analytics operations requested by the client:
     - Filtering (disease, region, time window).
     - Aggregation (daily/weekly/monthly buckets).
     - Derived metrics (growth rate, moving averages, incidence per 100k).
   - Shapes the response as:
     - Time-series suitable for interactive charts.
     - Geo-binned aggregates suitable for heatmaps.
     - Alert timelines suitable for interactive event strips.
5. **Backend response**:
   - Returns a JSON payload tailored for interactive visualization, including:
     - Raw series (for zoomable charts and brushing).
     - Precomputed aggregates (for tooltips and summary panels).
     - Source metadata and confidence/coverage indicators.
6. **Client rendering**:
   - The front-end can render:
     - Zoomable time-series charts with hover tooltips.
     - Region-level heatmaps driven by aggregated metrics.
     - Interactive outbreak timelines and alert feeds with filters and search.

---

### 3. Components and Responsibilities

#### 3.1 FastAPI Application (`app/main.py`)

- **CORS layer**:
  - Configured to allow all origins for ease of prototyping; can be restricted later to specific front-end hosts.
- **Endpoints**:
  - `GET /health`
    - Simple health check; useful for uptime probes and CI checks.
  - `GET /surveillance/ping`
    - Lightweight endpoint for manual smoke tests.
  - `GET /surveillance/global`
    - Uses `get_global_disease_summary()` to return a global snapshot from `disease.sh`.
  - `GET /surveillance/country/{country}?days=N`
    - Uses:
      - `get_country_disease_summary(country)`
      - `get_country_disease_trend(country, days)`
    - Merges current snapshot + recent time-series into a single JSON object.
  - `POST /analytics/query` (planned interactive analytics endpoint)
    - Request body includes:
      - `disease` (free text, later mapped to ICD-10/ICD-11).
      - `region` (country/region codes).
      - `time_window` (e.g. `30d`, `12w`, `1y`).
      - `metrics` (e.g. `["incidence", "growth_rate", "7d_moving_avg"]`).
      - `sources` (subset of: `["cdc", "who", "healthmap", "promed", "ihme", "ecdc", "ukgov", "disease_sh"]`).
    - Response includes:
      - Multi-source, normalized time-series.
      - Aggregated metrics for interactive charts and heatmaps.
      - Alert timelines and event markers for outbreak visualization.
- **Error handling**:
  - External API errors are surfaced as `502 Bad Gateway` with human-readable messages.
  - Resource-not-found in upstream (e.g., invalid country) is surfaced as `404 Not Found`.

#### 3.2 Surveillance Service Layer (`app/services/disease_service.py`)

- **Responsibilities**:
  - Encapsulate all communication with external surveillance data providers (currently `disease.sh`).
  - Normalize upstream response shapes into stable internal models.
  - Provide higher-level, dashboard-ready abstractions:
    - Global snapshot.
    - Per-country snapshot.
    - Per-country time-series.

- **Key functions**:
  - `get_global_disease_summary()`
    - Calls `https://disease.sh/v3/covid-19/all`.
    - Normalizes into a `GlobalSummary` Pydantic model.
    - Returns a dictionary including:
      - Global totals, daily increments, active/critical counts.
      - Affected country count.
      - ISO timestamp of last update.
  - `get_country_disease_summary(country: str) -> CountrySummary`
    - Calls `https://disease.sh/v3/covid-19/countries/{country}?strict=true`.
    - Maps upstream payload into a typed `CountrySummary` model.
    - Captures population and per-million metrics.
  - `get_country_disease_trend(country: str, days: int)`
    - Calls `https://disease.sh/v3/covid-19/historical/{country}?lastdays={days}`.
    - Extracts `cases` and `deaths` timelines.
    - Converts upstream date strings (e.g. `3/15/25`) into ISO dates (`2025-03-15`).
    - Returns a sorted list of `{date, cases, deaths}` points ready for time-series visualization.

- **Shared utilities**:
  - `_get_json(url, params=None)`
    - Thin wrapper around `httpx.AsyncClient.get`.
    - Raises `ValueError` for `404` to allow routing layer to map it to `HTTP 404`.
    - Raises for any other non-success status.

- **Data models**:
  - `GlobalSummary` – typed view of the global status payload, with field aliases aligned to `disease.sh` keys.
  - `CountrySummary` – typed snapshot of a single country’s situation, including per-million indicators and ISO codes.

---

### 4. Extensibility to Full Problem Scope

This prototype focuses on one live source to demonstrate the end-to-end surveillance pipeline, with a full multi-source architecture scaffolded and ready. To fully align with the MedFusion Hackfest brief, the following extensions are planned / straightforward:

- **Additional upstreams**:
  - CDC Open Data, WHO GHO OData, HealthMap, ProMED, ECDC, IHME GHDx India, UK Gov Health Statistics.
  - Implement new service modules (e.g. `cdc_service.py`, `who_service.py`) that:
    - Fetch and normalize upstream data.
    - Expose high-level functions like `get_country_epidemiology(country, disease)` or `get_outbreak_alerts(region)`.
  - Compose them in new aggregator functions such as `get_surveillance_view(disease, region)` which:
    - Joins epidemiology, alerts, and contextual indicators into a single backend payload.

- **Disease classification and ontology**:
  - Introduce a small ICD-10/ICD-11 mapping table (local CSV or API-based).
  - Map user-entered disease names to canonical codes for consistent querying across APIs.

- **Genomic and therapeutic layers**:
  - Add services for:
    - Gene–disease associations (e.g. Open Targets).
    - Drug information and WHO Essential Medicines status (e.g. PubChem PUG-REST).
  - Extend response schema to include:
    - `genes: [{symbol, score, evidence}]`
    - `therapeutics: [{drug_name, mechanism, who_essential}]`

- **Interactive analytics patterns**:
  - The `analytics_service.py` module defines:
    - `AnalyticsQuery` – user-selected disease, region, time-window, metrics, and sources.
    - `AnalyticsResult` – unified time-series plus a summary block for UI cards.
  - Built-in derived metrics:
    - **Incidence per 100k** – for relative burden comparison across regions.
    - **Growth rate** – day-over-day change, useful for early acceleration detection.
    - **7-day moving average** – smoothing noisy daily reports for readable charts.
  - These metrics are computed server-side so the front-end can remain thin and interactive (just plotting and filter changes).

- **Caching, performance, and robustness (future)**:
  - Add an in-memory or Redis cache for:
    - Frequently requested country/disease combinations.
    - Latest snapshots and short time windows (e.g. last 30 days).
  - Introduce rate-limiting and circuit breakers to protect both:
    - The upstream APIs (CDC/WHO/HealthMap etc.).
    - Your own backend from overload.
  - Schedule background refresh jobs that hydrate local caches so dashboard requests remain fast and resilient.

- **Interactive UI ideas enabled by this backend**:
  - Disease- and region-level drill-down:
    - Start with a global/India overview.
    - Click a country or state to fetch `/analytics/query` with a narrower region and longer window.
  - Time-window sliders and zoomable charts:
    - Front-end updates `time_window` (e.g. `30d` → `90d`) and refreshes series.
  - Multi-source toggles:
    - Allow users to select which sources to include (e.g. WHO + CDC only) and visualize differences/overlaps.
  - Alert timelines:
    - Once ProMED/HealthMap modules are implemented, show an interactive strip of alerts along the epidemiology curve.

---

### 5. Running the Prototype

#### 5.1 Backend setup

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 5.2 Start the FastAPI backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 5.3 Access the interactive UI

- Open the sleek dashboard UI in your browser:

```text
http://localhost:8000/ui/
```

The UI is a static single-page app served directly by FastAPI from the `frontend/` directory. It provides:

- **Left control rail**:
  - Disease input (free text).
  - Region input (country / region name).
  - Time window pills (14d, 30d, 90d, 180d).
  - Metric toggles (incidence, growth rate, 7d moving average).
  - Source toggles (currently `disease.sh` live; others marked as planned).
  - “Run analysis” button that calls the backend `/analytics/query` endpoint.
- **Main analytics canvas**:
  - KPI tiles for:
    - Global cases and new cases.
    - Region active cases and cases per million.
    - Population coverage and number of time-series points.
  - **Interactive charts** powered by Chart.js:
    - Daily cases + 7d moving average.
    - Incidence per 100k inhabitants.
  - Backend health indicator and provenance badges (“Prototype · Not for clinical use”).

#### 5.4 Backend API examples (for testing and integration)

- Health check:

```bash
curl http://localhost:8000/health
```

- Global surveillance snapshot:

```bash
curl http://localhost:8000/surveillance/global
```

- Country-level snapshot and trend for India (last 60 days):

```bash
curl "http://localhost:8000/surveillance/country/India?days=60"
```

- Interactive analytics query (used by the UI under the hood):

```bash
curl -X POST http://localhost:8000/analytics/query \
  -H "Content-Type: application/json" \
  -d '{
    "disease": "COVID-19",
    "region": "India",
    "time_window": "30d",
    "metrics": ["incidence", "7d_moving_avg"],
    "sources": ["disease_sh"]
  }'
```

These JSON responses can be wired directly into:

- Line charts (cases/deaths vs. time, moving averages).
- Interactive tiles/cards for regions and KPIs.
- Future map views and outbreak timelines.

---

### 6. How This Satisfies the Hackfest Backend Requirements

- **Real-world data integration**:
  - Uses the `disease.sh` surveillance API for live global and country-level disease burden, satisfying the requirement for real surveillance data integration.
- **Unified query interface**:
  - Country-based query (`/surveillance/country/{country}`) acts as a unified entry point to fetch multiple layers (snapshot + trend) in one call.
- **Intelligent presentation**:
  - Returns normalized, time-ordered trend data and per-million metrics, which are directly interpretable as epidemiological signals.
- **Visual intelligence readiness**:
  - Response payloads are specifically shaped for maps, trend lines, and outbreak timelines, which a front-end can visualize without additional heavy processing.

