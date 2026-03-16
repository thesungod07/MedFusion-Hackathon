<div align="center">

# 🧬 MedFusion

### Interactive Disease Surveillance Intelligence Dashboard

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Prototype-orange.svg)]()

*A multi-source epidemiological analytics platform with a premium dark-mode dashboard, powered by real-time data from disease.sh, WHO GHO, Our World in Data, and an integrated reference epidemiology engine covering all 13 tracked diseases.*

</div>

---

## 📖 Overview

**MedFusion** is a full-stack disease surveillance prototype built for the MedFusion Hackfest. It aggregates data from multiple public health APIs into a unified, interactive intelligence dashboard that enables:

- **Real-time monitoring** of global and country-level disease burden
- **Multi-source data fusion** from disease.sh, WHO Global Health Observatory, Our World in Data, and more
- **Full timelines for all 13 diseases** — backed by a reference epidemiology engine providing monthly estimates from 2000 → present, seeded from WHO/CDC/IHME published annual figures
- **Interactive analytics** with derived metrics (incidence, growth rate, 7-day moving averages)
- **Cross-region comparison** using per-capita normalization
- **Extensible architecture** designed for seamless plug-in of additional data providers (CDC, ECDC, HealthMap, ProMED, IHME, UK Gov)

> ⚠️ **Disclaimer**: This is a hackfest prototype and is **not intended for clinical use or public health decision-making**.

---

## 🏗️ Architecture

```mermaid
graph TB
    subgraph Client["🖥️ Browser Dashboard"]
        UI["Premium Dark-Mode UI<br/>HTML/CSS/JS + Chart.js + flag-icons"]
    end

    subgraph Backend["⚙️ FastAPI Backend"]
        Router["API Router<br/>/surveillance/* · /analytics/query · /sources/status"]
        Analytics["Analytics Orchestrator<br/>Multi-source fan-out & merge"]
        RefData["Reference Epidemiology Engine<br/>Monthly baseline for 13 diseases"]
    end

    subgraph Sources["📡 Data Sources"]
        DSH["disease.sh<br/>COVID-19 Real-Time"]
        WHO["WHO GHO OData<br/>Malaria, TB, Measles, etc."]
        OWID["Our World in Data<br/>COVID-19 Comprehensive CSV"]
        CDC["CDC Open Data<br/>(scaffolded)"]
        ECDC["ECDC Databases<br/>(scaffolded)"]
        MORE["HealthMap · ProMED<br/>IHME · UK Gov<br/>(scaffolded)"]
    end

    UI -->|HTTP/JSON| Router
    Router --> Analytics
    Analytics --> RefData
    Analytics --> DSH
    Analytics --> WHO
    Analytics --> OWID
    Analytics -.->|Future| CDC
    Analytics -.->|Future| ECDC
    Analytics -.->|Future| MORE

    style Client fill:#0a0f1e,stroke:#38bdf8,color:#e2e8f0
    style Backend fill:#0a0f1e,stroke:#34d399,color:#e2e8f0
    style Sources fill:#0a0f1e,stroke:#a78bfa,color:#e2e8f0
```

### Request Flow

1. **Dashboard** sends requests to the FastAPI backend (e.g., `POST /analytics/query`)
2. **API Router** validates parameters and delegates to the analytics orchestrator
3. **Analytics Orchestrator** fans out to selected data sources in parallel
4. **Reference Epidemiology Engine** seeds a full monthly baseline (2000–present) for non-COVID diseases; real API data overrides matching months
5. **Service Layer** fetches, normalizes, and caches upstream data
6. **Merge & Compute** — series from multiple sources are merged by date; derived metrics (incidence, growth rate, 7d moving average) computed server-side
7. **Response** — structured JSON payload optimized for chart rendering and KPI display

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.10+, FastAPI, Uvicorn |
| **HTTP Client** | httpx (async) |
| **Validation** | Pydantic v2 |
| **Frontend** | HTML5, CSS3 (dark glassmorphism), vanilla JavaScript |
| **Charting** | Chart.js (via CDN) |
| **Flag Icons** | [flag-icons](https://flagicons.lipis.dev/) CSS library (cross-platform, no emoji font needed) |
| **Data Sources** | disease.sh, WHO GHO OData, Our World in Data CSV, Reference Engine |

---

## 📂 Project Structure

```
MedFusion/
├── app/
│   ├── main.py                  # FastAPI app, routes, CORS, static mount
│   └── services/
│       ├── disease_service.py   # disease.sh COVID-19 API integration
│       ├── analytics_service.py # Multi-source orchestrator + derived metrics
│       ├── reference_data.py    # Reference epidemiology engine (13 diseases, 2000→present)
│       ├── who_service.py       # WHO GHO OData API integration
│       ├── owid_service.py      # Our World in Data CSV integration
│       ├── cdc_service.py       # CDC Open Data (scaffolded)
│       ├── ecdc_service.py      # ECDC databases (scaffolded)
│       ├── healthmap_service.py # HealthMap alerts (scaffolded)
│       ├── promed_service.py    # ProMED Mail RSS (scaffolded)
│       ├── ihme_service.py      # IHME GHDx (scaffolded)
│       └── ukgov_service.py     # UK Gov health stats (scaffolded)
├── frontend/
│   └── index.html               # Single-page dashboard (dark glassmorphism)
├── requirements.txt
└── README.md
```

---

## 🚀 Setup & Installation

### Prerequisites

- Python 3.10+ (recommended on Windows: **Python 3.12**)
- pip / venv

### 1. Clone the Repository

```bash
git clone <repository-url>
cd MedFusion-Hackathon
```

### 2. Create & Activate Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the Backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Open the Dashboard

Navigate to **[http://localhost:8000/ui/](http://localhost:8000/ui/)** in your browser.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/surveillance/ping` | Smoke test |
| `GET` | `/surveillance/global` | Global disease snapshot |
| `GET` | `/surveillance/country/{country}?days=N` | Country snapshot + trend |
| `POST` | `/analytics/query` | Interactive multi-source analytics |
| `GET` | `/sources/status` | Data source availability |

### Example: Analytics Query

```bash
curl -X POST http://localhost:8000/analytics/query \
  -H "Content-Type: application/json" \
  -d '{
    "disease": "Yellow Fever",
    "region": "Global",
    "time_window": "full",
    "sources": ["who", "healthmap", "promed"]
  }'
```

### Example: Data Sources Status

```bash
curl http://localhost:8000/sources/status
```

---

## 🎨 Dashboard Features

- **Premium dark-mode UI** with glassmorphism effects and animated gradients
- **6 KPI cards**: Global Cases, Global Deaths, Region Active, Cases/1M, Deaths/1M, Recovery Rate
- **4 interactive charts**: Epidemiological Curve, Deaths Trend, Incidence/100k, Growth Rate
- **13 diseases**: COVID-19, Influenza, Dengue, Malaria, Tuberculosis, Measles, Cholera, HIV/AIDS, Ebola, Hepatitis B, Polio, Yellow Fever, Zika — all with full 2000→present timelines
- **30+ countries** grouped by continent with real flag icons (CSS-based, Windows-compatible)
- **Custom flag dropdown** — uses `flag-icons` CSS library instead of emoji for cross-platform rendering
- **Data source toggles** — select which providers to include
- **Time window pills** — 14d, 30d, 90d, 180d, 1y, Full
- **Live backend status** indicator in the navbar
- **Responsive layout** for desktop, tablet, and mobile

---

## 📊 Data Sources

| Source | Status | Coverage |
|--------|--------|----------|
| **disease.sh** | ✅ Active | Real-time COVID-19 (global + 200+ countries) |
| **WHO GHO** | ✅ Active | Malaria, TB, Measles, Cholera, Hepatitis B, HIV/AIDS, Polio, Yellow Fever |
| **Our World in Data** | ✅ Active | COVID-19 comprehensive (cases, deaths, testing, vaccinations) |
| **Reference Engine** | ✅ Built-in | All 13 diseases — monthly estimates 2000→present, based on WHO/CDC/IHME published figures |
| **CDC Open Data** | 🔶 Scaffolded | US CDC surveillance + FluView |
| **ECDC** | 🔶 Scaffolded | European disease monitoring |
| **HealthMap** | 🔶 Scaffolded | Automated outbreak alerts |
| **ProMED Mail** | 🔶 Scaffolded | Curated outbreak reports |
| **IHME GHDx** | 🔶 Scaffolded | Global Burden of Disease estimates |
| **UK Gov** | 🔶 Scaffolded | UK health statistics |

### Reference Epidemiology Engine

`app/services/reference_data.py` provides a built-in fallback/baseline for **all 13 tracked diseases**:

- **Coverage**: Monthly granularity from each disease's earliest recorded history to the present
- **Methodology**: Annual burden anchors from WHO/CDC/IHME publications, linearly interpolated and distributed monthly, with disease-appropriate seasonality curves (e.g., influenza peaks in winter, dengue peaks in monsoon season) and ±15% realistic jitter
- **Country scaling**: Pre-computed burden share factors for 8 major countries + Global; generic 2% share for unlisted countries
- **Integration**: Acts as the baseline layer — real API data overrides reference data on matching months so live data always takes precedence

---

## 🧩 Extending with New Sources

Each data source is a self-contained module in `app/services/`. To add a new source:

1. Create `app/services/your_source_service.py`
2. Implement async functions that return `List[Dict]` with `{date, cases, deaths, source}` schema
3. Register the source in `DATA_SOURCES` within `analytics_service.py`
4. Add fan-out logic in `run_analytics_query()` to call your service
5. Add a toggle in the sidebar of `frontend/index.html`

---

## 📝 License

This project is a hackfest prototype. See individual data source APIs for their respective terms of use.
