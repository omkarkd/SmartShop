import os
import sys
import time


def _recreate_sainsburys_driver(driver):
    """Check if driver is alive; if dead, return a fresh one with cookies accepted."""
    try:
        _ = driver.title
        return driver
    except Exception:
        print(" (recreating driver)", end="", flush=True)
        try:
            driver.quit()
        except Exception:
            pass
        time.sleep(3)
        from sainsburys.scraper import create_driver, accept_cookies
        driver = create_driver()
        driver.get("https://www.sainsburys.co.uk/shop/gb/groceries")
        time.sleep(4)
        accept_cookies(driver)
        return driver


def _run_urls(urls, db, driver, max_retries=2):
    total_products = 0
    success_count = 0
    fail_count = 0
    pending = list(urls)
    total_count = len(urls)

    for retry in range(max_retries + 1):
        if not pending:
            break

        if retry > 0:
            print(f"\n{'─' * 50}")
            print(f"Retry round {retry}/{max_retries} — {len(pending)} URLs")
            print(f"{'─' * 50}")
            driver = _recreate_sainsburys_driver(driver)

        still_pending = []
        processed = 0

        for name, url in pending:
            processed += 1
            idx = f"[{retry * total_count + processed}]" if retry > 0 else f"[{processed}]"
            print(f"\n{idx}", end="", flush=True)
            cat_start = time.time()
            from sainsburys.scraper import scrape_category
            result = scrape_category(url, name, db=db, driver=driver, max_loads=10)
            cat_elapsed = time.time() - cat_start

            if isinstance(result, int):
                if result > 0:
                    success_count += 1
                    total_products += result
                    try:
                        from scraper_metrics import record_category_scrape
                        record_category_scrape("sainsburys", name, url, result, cat_elapsed, "success")
                    except Exception:
                        pass
                else:
                    driver = _recreate_sainsburys_driver(driver)
                    fail_count += 1
                    try:
                        from scraper_metrics import record_category_scrape
                        record_category_scrape("sainsburys", name, url, 0, cat_elapsed, "failed", str(result) if isinstance(result, int) else None)
                    except Exception:
                        pass
                    if retry < max_retries:
                        still_pending.append((name, url))
            else:
                success_count += 1
                total_products += len(result)

        pending = still_pending

    return total_products, success_count, fail_count, pending


def run_sainsburys():
    print("=" * 60)
    print("Sainsbury's Scraping Pipeline")
    print("=" * 60)

    sys.path.insert(0, os.path.dirname(__file__))
    from sainsburys.pipeline import load_hierarchy, get_all_urls
    from sainsburys.scraper import create_driver, accept_cookies
    from sainsburys.db import SainsburysDB

    start_time = time.time()
    hierarchy = load_hierarchy()
    urls = get_all_urls(hierarchy)
    print(f"\nTotal categories/subcategories to scrape: {len(urls)}")
    for name, url in urls:
        print(f"  {name}")

    db = SainsburysDB()
    driver = create_driver()

    print(f"\nOpening Sainsbury's home page...")
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
    time.sleep(2)

    total_products, success_count, fail_count, still_failed = _run_urls(
        urls, db, driver, max_retries=2
    )

    driver.quit()

    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"Sainsbury's Pipeline Complete")
    print(f"  Duration: {elapsed:.1f}s")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {fail_count}")
    if still_failed:
        print(f"  Still failed after retries:")
        for name, url in still_failed:
            print(f"    - {name}")
    print(f"  Total products: {total_products}")

    for s in db.get_category_stats():
        print(f"  {s['_id']}: {s['product_count']}")

    db.close()

    try:
        from scraper_metrics import record_scraper_run
        record_scraper_run("sainsburys", len(urls), success_count, fail_count,
                          total_products, elapsed)
    except Exception:
        pass

    return total_products


def _recreate_aldi_driver(driver):
    """Check if Aldi driver is alive; if dead, return a fresh one."""
    try:
        _ = driver.title
        return driver
    except Exception:
        print(" (recreating driver)", end="", flush=True)
        try:
            driver.quit()
        except Exception:
            pass
        time.sleep(3)
        from scrapper.aldi.scraper import create_driver
        driver = create_driver()
        return driver


def _run_aldi_urls(urls, db, driver, max_retries=2):
    total_products = 0
    success_count = 0
    fail_count = 0
    skip_count = 0
    pending = list(urls)

    for retry in range(max_retries + 1):
        if not pending:
            break

        if retry > 0:
            print(f"\n{'─' * 50}")
            print(f"Retry round {retry}/{max_retries} — {len(pending)} URLs")
            print(f"{'─' * 50}")
            driver = _recreate_aldi_driver(driver)

        still_pending = []

        for name, url in pending:
            existing = db.scrape_log.find_one({"url": url, "status": "success"})
            if existing and retry == 0:
                count = db.products.count_documents({"category": name})
                print(f"  - {name} — {count} products (already scraped)")
                skip_count += 1
                continue

            cat_start = time.time()
            from scrapper.aldi.scraper import scrape_category
            result = scrape_category(url, name, db=db, driver=driver)
            cat_elapsed = time.time() - cat_start

            if isinstance(result, int):
                if result > 0:
                    success_count += 1
                    total_products += result
                    try:
                        from scraper_metrics import record_category_scrape
                        record_category_scrape("aldi", name, url, result, cat_elapsed, "success")
                    except Exception:
                        pass
                else:
                    driver = _recreate_aldi_driver(driver)
                    fail_count += 1
                    try:
                        from scraper_metrics import record_category_scrape
                        record_category_scrape("aldi", name, url, 0, cat_elapsed, "failed", str(result) if isinstance(result, int) else None)
                    except Exception:
                        pass
                    if retry < max_retries:
                        still_pending.append((name, url))
            else:
                success_count += 1
                total_products += len(result)

        pending = still_pending

    return total_products, success_count, fail_count + skip_count, pending


def run_aldi():
    print("=" * 60)
    print("Aldi Scraping Pipeline")
    print("=" * 60)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from scrapper.aldi.pipeline import load_categories
    from scrapper.aldi.scraper import create_driver
    from scrapper.aldi.db import AldiDB

    categories = load_categories()
    print(f"\nTotal categories: {len(categories)}")

    from scrapper.aldi.pipeline import SKIP_PATTERNS
    to_scrape = [c for c in categories
                 if not any(p in c["name"].lower() for p in SKIP_PATTERNS)]
    skipped_names = [c["name"] for c in categories if any(p in c["name"].lower() for p in SKIP_PATTERNS)]

    print(f"  Active:  {len(to_scrape)} categories")
    print(f"  Skipped: {len(skipped_names)} (seasonal/promo)")

    start_time = time.time()
    db = AldiDB()
    driver = create_driver()

    total_products, success_count, fail_count, still_failed = _run_aldi_urls(
        [(c["name"], c["url"]) for c in to_scrape], db, driver
    )

    driver.quit()

    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"Aldi Pipeline Complete")
    print(f"  Duration: {elapsed:.1f}s")
    print(f"  Success: {success_count}  |  Failed: {fail_count}  |  Skipped: {len(skipped_names)}")
    if still_failed:
        print(f"  Still failed after retries:")
        for name, url in still_failed:
            print(f"    - {name}")

    total = db.get_total_product_count()
    cats = db.get_category_stats()
    print(f"  Total products in DB: {total}")
    for s in cats:
        print(f"    {s['_id']}: {s['product_count']} products")
    db.close()

    try:
        from scraper_metrics import record_scraper_run
        record_scraper_run("aldi", len(to_scrape), success_count, fail_count,
                          total, elapsed)
    except Exception:
        pass

    return total


def main():
    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        print("FATAL: MONGO_URI environment variable is required")
        sys.exit(1)

    retailer = os.environ.get("RETAILER", "all").lower()

    start = time.time()

    if retailer in ("all", "sainsburys"):
        run_sainsburys()
    if retailer in ("all", "aldi"):
        run_aldi()

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"Total time: {elapsed/60:.1f} minutes")
    print(f"All done!")


if __name__ == "__main__":
    main()
