"""Scraper entrypoint — runs one full scrape cycle then exits.

Designed for Render Cron Job: runs Aldi and/or Sainsbury's scraping,
writes a status document to MongoDB on every run, and exits with code 0
on success or non-zero on failure.
"""
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _write_run_status(results: dict):
    """Write a run-status document to performance_metrics collection."""
    from shared.db import get_db
    try:
        db = get_db()
        for retailer, info in results.get("retailers", {}).items():
            doc = {
                "type": "scraper_run",
                "retailer": retailer,
                "status": info.get("status", "unknown"),
                "timestamp": info.get("timestamp"),
                "duration_seconds": info.get("duration_seconds"),
                "categories_total": info.get("categories_total", 0),
                "categories_success": info.get("categories_success", 0),
                "categories_failed": info.get("categories_failed", 0),
                "products_total": info.get("products_total", 0),
                "errors": info.get("errors", []),
            }
            db["performance_metrics"].insert_one(doc)
            print(f"  [status] Wrote {retailer} run status: {info.get('status')}")
    except Exception as e:
        print(f"  [status] Failed to write run status: {e}", file=sys.stderr)


def run_aldi():
    """Run Aldi scraper. Returns a result dict."""
    from scraper.scrapers.aldi_db import AldiDB
    from scraper.scrapers.aldi import create_driver
    from scraper.scrapers.aldi_pipeline import load_categories, SKIP_PATTERNS

    start = time.time()
    categories = load_categories()
    to_scrape = [
        c for c in categories
        if not any(p in c["name"].lower() for p in SKIP_PATTERNS)
    ]

    db = AldiDB()
    driver = create_driver()
    total_products = 0
    success_count = 0
    fail_count = 0
    errors = []

    try:
        from scraper.scrapers.aldi import scrape_category

        for name, url in [(c["name"], c["url"]) for c in to_scrape]:
            try:
                cat_start = time.time()
                result = scrape_category(url, name, db=db, driver=driver)
                cat_elapsed = time.time() - cat_start
                if isinstance(result, int) and result > 0:
                    total_products += result
                    success_count += 1
                elif isinstance(result, int):
                    fail_count += 1
                else:
                    total_products += len(result)
                    success_count += 1

                from scraper.scrapers.metrics import record_category_scrape
                record_category_scrape(
                    "aldi", name, url,
                    result if isinstance(result, int) else len(result),
                    cat_elapsed,
                    "success" if (isinstance(result, int) and result > 0) or not isinstance(result, int) else "failed"
                )
            except Exception as e:
                fail_count += 1
                errors.append({"category": name, "error": str(e)})
                print(f"    ERROR scraping {name}: {e}")
    finally:
        driver.quit()
        db.close()

    total = db.get_total_product_count()
    elapsed = time.time() - start

    from scraper.scrapers.metrics import record_scraper_run
    record_scraper_run("aldi", len(to_scrape), success_count, fail_count,
                       total, elapsed)

    return {
        "status": "completed" if fail_count == 0 else "partial",
        "categories_total": len(to_scrape),
        "categories_success": success_count,
        "categories_failed": fail_count,
        "products_total": total,
        "duration_seconds": round(elapsed, 2),
        "errors": errors,
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    }


def run_sainsburys():
    """Run Sainsbury's scraper. Returns a result dict."""
    from scraper.scrapers.sainsburys_db import SainsburysDB
    from scraper.scrapers.sainsburys import create_driver, accept_cookies
    from scraper.scrapers.sainsburys_pipeline import load_hierarchy, get_all_urls
    from scraper.scrapers.sainsburys import scrape_category

    start = time.time()
    hierarchy = load_hierarchy("scraper/scrapers/category_hierarchy.json")
    urls = get_all_urls(hierarchy)

    db = SainsburysDB()
    driver = create_driver()
    total_products = 0
    success_count = 0
    fail_count = 0
    errors = []

    try:
        for attempt in range(5):
            try:
                driver.get("https://www.sainsburys.co.uk/shop/gb/groceries")
                break
            except Exception as e:
                print(f"  Retry {attempt+1}: {type(e).__name__}")
                if attempt < 4:
                    driver.quit()
                    time.sleep(3)
                    driver = create_driver()
                else:
                    raise
        time.sleep(5)
        accept_cookies(driver)

        for name, url in urls:
            try:
                cat_start = time.time()
                result = scrape_category(url, name, db=db, driver=driver, max_loads=10)
                cat_elapsed = time.time() - cat_start
                if isinstance(result, int):
                    if result > 0:
                        total_products += result
                        success_count += 1
                    else:
                        fail_count += 1
                else:
                    total_products += len(result)
                    success_count += 1

                from scraper.scrapers.metrics import record_category_scrape
                record_category_scrape(
                    "sainsburys", name, url,
                    result if isinstance(result, int) else len(result),
                    cat_elapsed,
                    "success" if (isinstance(result, int) and result > 0) or not isinstance(result, int) else "failed"
                )
            except Exception as e:
                fail_count += 1
                errors.append({"category": name, "error": str(e)})
                print(f"    ERROR scraping {name}: {e}")
    finally:
        driver.quit()
        db.close()

    elapsed = time.time() - start

    from scraper.scrapers.metrics import record_scraper_run
    record_scraper_run("sainsburys", len(urls), success_count, fail_count,
                       total_products, elapsed)

    return {
        "status": "completed" if fail_count == 0 else "partial",
        "categories_total": len(urls),
        "categories_success": success_count,
        "categories_failed": fail_count,
        "products_total": total_products,
        "duration_seconds": round(elapsed, 2),
        "errors": errors,
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    }


def _write_running_status(retailer: str):
    """Write a 'running' status document before the scrape starts.

    Ensures the cron job leaves a trace even if it crashes mid-way.
    Updated to 'completed' or 'failed' by _write_run_status on completion.
    """
    from shared.db import get_db
    retailers = ["aldi", "sainsburys"] if retailer == "all" else [retailer]
    try:
        db = get_db()
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        for r in retailers:
            db["performance_metrics"].insert_one({
                "type": "scraper_run",
                "retailer": r,
                "status": "running",
                "timestamp": now,
            })
    except Exception as e:
        print(f"  [status] Failed to write running status: {e}", file=sys.stderr)


def main():
    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        print("FATAL: MONGO_URI environment variable is required")
        sys.exit(1)

    retailer = os.environ.get("RETAILER", "all").lower()
    overall_start = time.time()
    results = {"retailers": {}, "exit_code": 0}

    # Write 'running' status upfront so a crash still leaves a trace
    _write_running_status(retailer)

    if retailer in ("all", "aldi"):
        print(f"\n{'=' * 60}")
        print("Aldi Scraping Pipeline")
        print(f"{'=' * 60}")
        try:
            results["retailers"]["aldi"] = run_aldi()
        except Exception as e:
            print(f"FATAL: Aldi scraper crashed: {e}")
            traceback.print_exc()
            results["retailers"]["aldi"] = {
                "status": "failed",
                "errors": [{"fatal": str(e)}],
                "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            }
            results["exit_code"] = 1

    if retailer in ("all", "sainsburys"):
        print(f"\n{'=' * 60}")
        print("Sainsbury's Scraping Pipeline")
        print(f"{'=' * 60}")
        try:
            results["retailers"]["sainsburys"] = run_sainsburys()
        except Exception as e:
            print(f"FATAL: Sainsbury's scraper crashed: {e}")
            traceback.print_exc()
            results["retailers"]["sainsburys"] = {
                "status": "failed",
                "errors": [{"fatal": str(e)}],
                "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            }
            results["exit_code"] = 1

    # Write run status to MongoDB
    _write_run_status(results)

    overall_elapsed = time.time() - overall_start
    print(f"\n{'=' * 60}")
    print(f"Total time: {overall_elapsed / 60:.1f} minutes")

    # Exit with proper code — Render Cron Job surfaces non-zero exits
    for rname, rinfo in results["retailers"].items():
        status = rinfo.get("status", "unknown")
        print(f"  {rname}: {status} ({rinfo.get('categories_success', 0)} ok / {rinfo.get('categories_failed', 0)} failed)")
        if status == "failed":
            results["exit_code"] = 1

    print(f"Exit code: {results['exit_code']}")
    sys.exit(results["exit_code"])


if __name__ == "__main__":
    main()
