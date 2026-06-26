# SmartShop

Grocery price comparison platform — compares prices between **Aldi** and **Sainsbury's** in the UK.

## Architecture

```
┌─────────────┐     ┌──────────────────────────┐     ┌──────────────┐
│   Browser    │────▶│    FastAPI Server         │────▶│   MongoDB     │
│  (Static FE) │     │  • API (REST)             │     │  (Atlas/Local)│
│              │     │  • Static frontend         │     └──────────────┘
│  /admin      │     │  • Admin dashboard         │
│  Dashboard   │     │  • Prometheus /metrics     │
└─────────────┘     │  • Performance middleware   │
                    └──────────────────────────┘
                    ┌──────────────────────────┐
                    │  Scraper (Docker/CLI)     │
                    │  • undetected-chromedriver │
                    │  • Aldi + Sainsbury's      │
                    │  • Per-category timing     │
                    │  • Metrics in MongoDB      │
                    └──────────────────────────┘
```

## Features

- **Product Search** — search across both retailers with category, brand, and retailer filters
- **Price Comparison** — side-by-side prices with cross-retailer product matching
- **Shopping Cart** — build a basket and compare Aldi vs Sainsbury's totals with matched savings
- **Nectar Pricing** — Sainsbury's Nectar loyalty prices displayed alongside regular prices
- **Authentication** — JWT-based signup/login with bcrypt password hashing
- **Admin Dashboard** — performance monitoring and operational visibility
- **Performance Metrics** — real-time API latency tracking (p50/p95/p99)
- **Prometheus Endpoint** — `/metrics` for external monitoring integration

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start MongoDB (local)
mongod --dbpath local-mongodb

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000

# Open in browser
open http://localhost:8000
```

## Admin Dashboard

Two admin interfaces available:

### FastAPI Admin (Web)
Accessible at **`/admin/`** with credentials `admin` / `admin`.

| Page | Description |
|------|-------------|
| **Parent Dashboard** | Today's scraping activity, run history, database overview |
| **Data Collection** | Scraping runs with date/retailer/status filters, per-category timing visualizations |
| **Database** | MongoDB stats, collections categorized as consumer-facing vs internal |
| **Service Health** | MongoDB ping latency, dependency checks, server status |

### Streamlit Admin App
A richer admin interface at **`http://localhost:8501`** with the same credentials.

```bash
# Start the Streamlit admin app
streamlit run admin_app.py
```

| Tab | Description |
|-----|-------------|
| **Dashboard** | Stats cards (runs, products, categories, DB size), today's activity, run history |
| **Scraping Runs** | Filterable run history with pagination, per-category timing bar charts, run detail viewer |
| **Database** | DB size stats, collections split by consumer/internal with bar chart visualization |
| **Scraper Control** | Start scraping on-click (queues to MongoDB, runs via subprocess if Chrome available), schedule config, run queue history |

## Performance Metrics

API endpoints tracked in real-time via ASGI middleware:

- **Request counts** per endpoint + method
- **Latency** — min, max, avg, p50, p95, p99
- **Error rates** — 4xx/5xx per endpoint
- **Active requests** — current in-flight gauge

Endpoints:

- `GET /api/metrics` — JSON snapshot
- `GET /metrics` — Prometheus format

Disable via `METRICS_ENABLED=false`.

## Scraper

Dockerized Selenium scraper for Aldi and Sainsbury's.

```bash
# Build and run with Docker
docker-compose up --build

# Or run locally
python -m scrapper.docker_entry

# Scrape a specific retailer
RETAILER=aldi python -m scrapper.docker_entry
RETAILER=sainsburys python -m scrapper.docker_entry
```

Per-category timing and run metrics are recorded to MongoDB `performance_metrics` collection and visible in the Admin Dashboard.

## API Endpoints

| Endpoint                              | Description                     |
| ------------------------------------- | ------------------------------- |
| `POST /api/auth/signup`             | Create account                  |
| `POST /api/auth/login`              | Login (returns JWT)             |
| `GET /api/products/search?q=`       | Search products                 |
| `GET /api/products/categories`      | List categories                 |
| `GET /api/products/category/{name}` | Browse by category              |
| `POST /api/cart/create`             | Create cart                     |
| `GET /api/cart/active`              | Active cart with matched prices |
| `POST /api/cart/add`                | Add item to cart                |
| `GET /api/admin/dashboard`          | Admin dashboard overview        |
| `GET /api/admin/scraping-runs`      | Scraping run history            |
| `GET /api/admin/database`           | MongoDB collection stats        |
| `GET /api/admin/health`             | Service health checks           |

## Database

MongoDB with collections organized by type:

**Consumer-facing:** `users`, `carts`, `cart_items`, `aldi_products`, `sainsburys_products`

**Internal:** `aldi_scrape_log`, `sainsburys_scrape_log`, `performance_metrics`

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed strategy covering VPS, MongoDB Atlas, Docker, CI/CD, and monitoring.

Recommended stack: **VPS + MongoDB Atlas** (Option B in deployment guide).

## Project Status

- [X] FastAPI backend with full REST API
- [X] Web frontend (vanilla HTML/CSS/JS)
- [X] Aldi scraper (Dockerized)
- [X] Sainsbury's scraper (Dockerized)
- [X] Cross-retailer product matching
- [X] Brand extraction pipeline
- [X] Nectar price integration
- [X] JWT authentication
- [X] Performance metrics middleware
- [X] Prometheus `/metrics` endpoint
- [X] Admin dashboard
- [X] Per-category scraper timing
- [ ] Automated testing
- [ ] CI/CD pipeline
- [ ] Price history tracking
