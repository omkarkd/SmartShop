# Audit Report — Pre-Refactor Baseline

Date: 2026-06-26
Commit: 27e3947 (HEAD of `docker-scraper`)

---

## 1. Repo Structure Today

```
/                       # Monolithic root — concerns are mixed
  admin_app.py          # Streamlit entrypoint (dashboard)
  main.py               # FastAPI entrypoint (REST backend — separate concern)
  utils.py              # SHARED (imports streamlit! used by dashboard pages)
  Dockerfile            # Builds ONE image containing BOTH scraper + dashboard
  docker-compose.yml    # Runs ONE service (includes Chrome)

  pages/                # Streamlit pages (dashboard only)
    control.py          # Has scraper-triggering code + Chrome detection
    dashboard.py
    runs.py
    database.py

  scrapper/             # Scraper logic
    docker_entry.py     # Entrypoint: runs one full scrape cycle
    scraper_metrics.py  # Writes metrics to Mongo
    aldi/
      scraper.py        # Selenium/UC scrapers
      db.py             # AldiDB class (Mongo connection)
      pipeline.py
    sainsburys/
      scraper.py        # Selenium/UC scrapers
      db.py             # SainsburysDB class (Mongo connection)
      pipeline.py
      build_hierarchy.py # Selenium/UC — builds category hierarchy

  backend/              # FastAPI REST API (separate concern — not in scope)
    ...

  app/                  # DEPRECATED old Streamlit app (dead code)
    cart.py             # imports streamlit
    main.py             # imports streamlit
```

**Key finding:** The repo is a monolith where scraper code and dashboard code live
in the same tree, share one `Dockerfile`, one `docker-compose.yml`, and one
`requirements.txt`. The dashboard Docker image currently includes Chromium
(~400MB+), and the scraper can be triggered from inside the Streamlit UI.

---

## 2. Shared Modules — Cross-Contamination Analysis

Every Python file was analyzed for imports of `streamlit` vs `selenium`/`uc`:

| File | Streamlit? | Selenium/UC? | Verdict |
|---|---|---|---|
| `admin_app.py` | yes | no | **dashboard** |
| `pages/control.py` | yes | no | **dashboard** (has Chrome detection but no Selenium import) |
| `pages/dashboard.py` | yes | no | **dashboard** |
| `pages/runs.py` | yes | no | **dashboard** |
| `pages/database.py` | yes | no | **dashboard** |
| `app/cart.py` | yes | no | dead code (deprecated) |
| `app/main.py` | yes | no | dead code (deprecated) |
| `utils.py` | **yes** | no | **CROSS-CONTAMINATION** — imports streamlit at module level |
| `scrapper/aldi/scraper.py` | no | **yes** | **scraper** |
| `scrapper/sainsburys/scraper.py` | no | **yes** | **scraper** |
| `scrapper/sainsburys/build_hierarchy.py` | no | **yes** | **scraper** |
| `scrapper/docker_entry.py` | no | no | **scraper** (orchestrator, no direct Selenium import) |
| `scrapper/aldi/db.py` | no | no | **shared candidate** (Mongo helper) |
| `scrapper/sainsburys/db.py` | no | no | **shared candidate** (Mongo helper) |
| `scrapper/scraper_metrics.py` | no | no | **shared candidate** (Mongo metrics writer) |
| `scrapper/cleanse.py` | no | no | utility script |
| `backend/**/*.py` | no | no | FastAPI — separate concern |

### Files that legitimately belong in `/shared`

| Module | Used by dashboard | Used by scraper | Notes |
|---|---|---|---|
| `utils.py:get_db()` | ✓ | — | But currently imports `streamlit` — must be extracted |
| `utils.py:ensure_aware()` | ✓ | — | Dashboard-only datetime helper |
| `utils.py:get_dashboard_overview()` | ✓ | — | Dashboard-only |
| `utils.py:get_scraping_runs()` | ✓ | — | Dashboard-only |
| `utils.py:get_run_detail()` | ✓ | — | Dashboard-only |
| `utils.py:queue_scrape_run()` | ✓ | — | Queue operations for dashboard |
| `utils.py:update_queue_status()` | ✓ | — | Called by run_scraper_background |
| `utils.py:run_scraper_background()` | ✓ | — | Launches scraper subprocess (will be eliminated) |
| `utils.py:can_run_scraper()` | ✓ | — | Chrome detection (will be eliminated) |
| `scrapper/aldi/db.py: AldiDB` | — | ✓ | Mongo connection + CRUD for aldi |
| `scrapper/sainsburys/db.py: SainsburysDB` | — | ✓ | Mongo connection + CRUD for sainsburys |
| `scrapper/scraper_metrics.py` | — | ✓ | Writes performance_metrics to Mongo |

**The connection string** (`MONGO_URI`) and `DB_NAME` are currently in:
- `utils.py` (via `_get_config()`)
- `backend/config.py` (separate)
- `scrapper/aldi/db.py` (via env var)
- `scrapper/sainsburys/db.py` (via env var)
- `scrapper/scraper_metrics.py` (via env var)
- `Dockerfile` (ENV default)
- `docker-compose.yml` (env var)

**Duplicate code identified:**
- `utils.py` and `backend/services/admin_service.py` both have their own versions of:
  - `get_dashboard_overview()`
  - `get_scraping_runs()`
  - `_get_collection_info()`
  - `_bytes_to_human()`
  - `verify_admin()`
  - These are NOT the same code paths — the Streamlit admin and the FastAPI backend
    each maintain their own copy of dashboard queries.

---

## 3. Current Entrypoints

There are **three independent entrypoints** in the repo today:

| Entrypoint | File | Type | How triggered |
|---|---|---|---|
| **Streamlit admin app** | `admin_app.py` | Web UI | `streamlit run admin_app.py` (Docker CMD) |
| **FastAPI REST API** | `main.py` | Web API | `uvicorn main:app` |
| **Scraper** | `scrapper/docker_entry.py` | CLI script | Subprocess launched from `utils.py:run_scraper_background()`, also runnable directly |

The scraper is currently launched **from inside the Streamlit process** as a
subprocess via `start_scraper_thread()` in `utils.py`. This means:
- The dashboard image MUST include Chrome + chromedriver (+400MB)
- A hang in the scraper can affect the Streamlit process
- The "Start Scraping" button blocks the Streamlit UI thread with `time.sleep(3)`

**After refactor:** The scraper will be a standalone Render Cron Job. The
dashboard will never trigger it. The `run_scraper_background()`,
`start_scraper_thread()`, `can_run_scraper()`, `queue_scrape_run()`, and
`update_queue_status()` functions will be **eliminated** from the dashboard code.

---

## 4. Current Auth State

| Component | Auth mechanism | Credentials | Status |
|---|---|---|---|
| **Streamlit admin app** | `st.session_state` session check | `ADMIN_USER`/`ADMIN_PASS` env vars, **fallback to `admin`/`admin`** | Uses env vars (fixed in 27e3947) |
| **FastAPI backend** | JWT + bcrypt | `ADMIN_PASSWORD_HASH` of `"admin"` + `SECRET_KEY` | Uses bcrypt but still defaults to `admin` password |
| `utils.py:verify_admin()` | String compare | Hardcoded `"admin"` / `"admin"` | Dead code path (not called by admin_app.py since 27e3947) |

**No user model exists.** There is no `users` collection, no role system, no
registration. Auth is a single shared credential.

---

## 5. MongoDB Schema (Atlas — production)

Collections currently in Atlas (connected via `MONGO_URI` above):

### `sainsburys_products` — 5,813 docs
```
Fields: _id, url, brand, category, image_url, is_own_brand, nectar_price,
        nectar_price_label, price, price_per_unit, price_with_promotion,
        product_name, promotion_badge, scraped_at, was_price
Indexes: _id_, url_1 (unique, sparse), category_1, scraped_at_-1
```

### `sainsburys_scrape_log` — 1,369 docs
```
Fields: _id, url, category, product_count, page, status, error, scraped_at
Indexes: _id_, url_1, scraped_at_-1
```

### Collections NOT in Atlas (exist only in local MongoDB — will appear after scraper runs against Atlas):
- `aldi_products` — Aldi product catalog
- `aldi_scrape_log` — Aldi scrape audit log
- `performance_metrics` — Type-discriminated collection with:
  - `{type: "scraper_run"}` — Run-level summaries
  - `{type: "category_scrape"}` — Per-category timing/product counts
- `scrape_requests` — Job queue (will be eliminated; scraper no longer queued from UI)

---

## Summary of Changes Required by the Refactor Plan

| # | What changes | Impact |
|---|---|---|
| 1 | `utils.py` split into dashboard-only (`get_dashboard_overview`, etc.) and shared (`get_db`, `ensure_aware`) | Extract a clean `shared/db.py` without streamlit import |
| 2 | `run_scraper_background()` eliminated from dashboard | Remove subprocess launch code from `utils.py` |
| 3 | `pages/control.py` rewritten — no "Start Scraping" button | Show "Scraper runs as Render Cron Job" message |
| 4 | `scrapper/docker_entry.py` repackaged as `scraper/main.py` | Add `sys.exit()` with proper exit codes, write status on every run |
| 5 | FastAPI `backend/` left untouched | Not in scope for this refactor |
| 6 | `app/` directory removed | Dead code |
| 7 | Auth upgraded from shared credential to `users` collection with bcrypt + roles | Add user model, login/logout, session management |

---

## Baseline Diff

This audit is committed before any refactor changes. The next commit will begin
the restructure. Compare against commit `27e3947`.
