import os
import sys
import time


def run_sainsburys():
    print("=" * 60)
    print("Sainsbury's Scraping Pipeline")
    print("=" * 60)

    sys.path.insert(0, os.path.dirname(__file__))
    from sainsburys.pipeline import load_hierarchy, get_all_urls
    from sainsburys.scraper import scrape_category, create_driver, accept_cookies
    from sainsburys.db import SainsburysDB

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

    total_products = 0
    success_count = 0
    fail_count = 0

    for i, (name, url) in enumerate(urls):
        print(f"\n[{i+1}/{len(urls)}]", end="", flush=True)
        result = scrape_category(url, name, db=db, driver=driver, max_loads=10)
        if isinstance(result, int):
            if result > 0:
                success_count += 1
                total_products += result
            else:
                try:
                    driver.title
                except Exception:
                    print(" (recreating driver)", end="", flush=True)
                    driver.quit()
                    time.sleep(3)
                    driver = create_driver()
                    driver.get("https://www.sainsburys.co.uk/shop/gb/groceries")
                    time.sleep(4)
                    accept_cookies(driver)
                fail_count += 1
        else:
            success_count += 1
            total_products += len(result)

    driver.quit()

    print(f"\n{'=' * 60}")
    print(f"Sainsbury's Pipeline Complete")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {fail_count}")
    print(f"  Total products: {total_products}")

    for s in db.get_category_stats():
        print(f"  {s['_id']}: {s['product_count']}")

    db.close()
    return total_products


def run_aldi():
    print("=" * 60)
    print("Aldi Scraping Pipeline")
    print("=" * 60)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from scrapper.aldi.pipeline import load_categories, scrape_worker
    from scrapper.aldi.db import AldiDB

    categories = load_categories()
    print(f"\nTotal categories: {len(categories)}")

    from scrapper.aldi.pipeline import SKIP_PATTERNS
    to_scrape = [c for c in categories
                 if not any(p in c["name"].lower() for p in SKIP_PATTERNS)]
    skipped = [c for c in categories if any(p in c["name"].lower() for p in SKIP_PATTERNS)]

    print(f"  Active:  {len(to_scrape)} categories")
    print(f"  Skipped: {len(skipped)} (seasonal/promo)")

    db = AldiDB()
    already = db.scrape_log.count_documents({"status": "success"})
    print(f"  Already scraped: {already} categories")
    db.close()

    # Run single-threaded in Docker
    results = scrape_worker(([(c["name"], c["url"]) for c in to_scrape], 1))

    completed = 0
    errors = 0
    for result in results:
        completed += 1
        if result["status"] == "success":
            print(f"  [{completed}/{len(to_scrape)}] {result['name']} — {result['products']} products")
        elif result["status"] == "skipped":
            print(f"  [{completed}/{len(to_scrape)}] {result['name']} — {result['products']} products (already scraped)")
        else:
            errors += 1
            print(f"  [{completed}/{len(to_scrape)}] {result['name']} — ERROR: {result.get('error','?')}")

    print(f"\n{'=' * 60}")
    print(f"Aldi Pipeline Complete")
    print(f"  Success: {completed - errors}  |  Errors: {errors}  |  Skipped: {len(skipped)}")

    db = AldiDB()
    total = db.get_total_product_count()
    cats = db.get_category_stats()
    print(f"  Total products in DB: {total}")
    for s in cats:
        print(f"    {s['_id']}: {s['product_count']} products")
    db.close()

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
