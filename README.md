# SmartShop

Multi-retailer price comparison platform with automated scraping and a Streamlit admin dashboard.

## Architecture

```
┌─────────────────────┐         ┌──────────────────┐         ┌───────────────────────┐
│  GitHub Actions      │  writes │                  │  reads  │  Render Web Service    │
│  Scraper Cron Job    │ ──────▶ │  MongoDB Atlas   │ ◀────── │  Streamlit Dashboard   │
│  (Docker, Chrome)    │         │  (shared)        │         │  (no Chrome, slim)     │
└─────────────────────┘         └──────────────────┘         └───────────────────────┘
```

- **Scraper** — Runs every 6 hours via GitHub Actions. Launches headless Chrome (Selenium + undetected-chromedriver) to scrape Aldi and Sainsbury's product catalogs. Updates prices on existing products and adds new ones.
- **Dashboard** — Streamlit admin panel deployed on Render. Read-only views of scraping runs, product stats, database overview. Login with role-based access (admin/viewer).
- **Database** — MongoDB Atlas (free M0 cluster). All persistent state.

## Project Structure

```
/
├── scraper/              # GitHub Actions Cron Job
│   ├── Dockerfile        # Chromium + Python deps
│   ├── main.py           # One-shot entrypoint, exits with code 0/1
│   ├── requirements.txt  # selenium, uc, pymongo only
│   └── scrapers/         # Aldi + Sainsbury's scraping logic
│
├── dashboard/            # Render Web Service
│   ├── Dockerfile        # Slim, NO Chrome
│   ├── app.py            # Streamlit entrypoint with login
│   ├── auth.py           # bcrypt users collection, admin/viewer roles
│   ├── requirements.txt  # streamlit, pandas, plotly, pymongo, bcrypt
│   └── pages/            # Dashboard, Runs, Database, Control
│
├── shared/               # Shared between both services
│   ├── config.py         # MONGO_URI/DB_NAME from env vars
│   └── db.py             # get_db(), ensure_aware()
│
├── backend/              # Legacy FastAPI REST API (not currently deployed)
├── scrapper/             # Legacy scraper (moved to scraper/)
└── .github/workflows/
    └── scrape.yml        # GitHub Actions: builds + runs scraper every 6h
```

## Quick Start

### Prerequisites
- Python 3.11+
- MongoDB Atlas (or local MongoDB)
- Docker (optional, for local testing)

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `MONGO_URI` | Yes | — | MongoDB connection string |
| `DB_NAME` | No | `smartshop` | Database name |
| `ADMIN_SEED_USER` | No | `admin` | Initial admin username (first deploy only) |
| `ADMIN_SEED_PASS` | No | `admin` | Initial admin password (first deploy only) |

### Run Dashboard Locally

```bash
pip install -r dashboard/requirements.txt
MONGO_URI="your_atlas_uri" streamlit run dashboard/app.py --server.port=8501
```

### Run Scraper Locally

```bash
docker build -t scraper -f scraper/Dockerfile .
docker run --rm -e MONGO_URI="your_atlas_uri" -e RETAILER=all --shm-size=2gb scraper
```

### Run Scraper via GitHub Actions

1. Add `MONGO_URI` as a repository secret (Settings → Secrets and variables → Actions)
2. Go to Actions tab → Scraper → Run workflow
3. Or wait for the scheduled run (every 6 hours)

## Deployment

### Dashboard (Render)

1. Create a new **Web Service** with **Docker** runtime
2. Set Dockerfile path to `dashboard/Dockerfile`
3. Add env vars: `MONGO_URI`, `DB_NAME`, `ADMIN_SEED_USER`, `ADMIN_SEED_PASS`
4. Deploy — auto-deploys on push to `main`

### Scraper (GitHub Actions)

The workflow at `.github/workflows/scrape.yml` runs automatically every 6 hours.
No additional deployment needed — it builds from source on each run.

## Features

- **Automated scraping** — Aldi and Sainsbury's product catalogs, categories, prices
- **Price updates** — Existing products get updated prices, new products are added
- **Own brand detection** — Identifies retailer own-brand products
- **Nectar price tracking** — Sainsbury's Nectar member prices captured
- **Performance metrics** — Per-category timing, run history, success/failure tracking
- **Role-based access** — Admin users see scraper controls; viewers see dashboard only
- **Session management** — 8-hour session expiry, secure bcrypt password storage

## Tech Stack

| Component | Technology |
|---|---|
| Dashboard | Python, Streamlit, Pandas, Plotly |
| Scraper | Python, Selenium, undetected-chromedriver |
| Database | MongoDB Atlas (M0 free tier) |
| CI/CD | GitHub Actions (scraper) |
| Hosting | Render (dashboard) |
| Auth | bcrypt, MongoDB users collection |
