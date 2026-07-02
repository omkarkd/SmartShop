import json
import time
import sys
import os
from multiprocessing import Pool

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, ROOT)

from scrapper.aldi.scraper import scrape_category, create_driver
from scrapper.aldi.db import AldiDB

CATEGORIES_FILE = os.path.join(os.path.dirname(__file__), "categories.json")

SKIP_PATTERNS = ["father", "summer", "specialbuys", "price drops", "picky bits",
                 "higher protein", "specially selected"]


def load_categories():
    with open(CATEGORIES_FILE) as f:
        return json.load(f)


def scrape_worker(args):
    """
    Worker process: opens ONE Chrome driver, scrapes its assigned categories,
    then quits. Avoids create/quit penalty and 'target window already closed' errors.
    """
    cat_list, worker_id = args
    from scrapper.aldi.scraper import scrape_category, create_driver
    from scrapper.aldi.db import AldiDB

    db = AldiDB()
    driver = create_driver()
    results = []

    for name, url in cat_list:
        try:
            existing_log = db.scrape_log.find_one({"url": url, "status": "success"})
            if existing_log:
                count = db.products.count_documents({"category": name})
                results.append({"name": name, "status": "skipped", "products": count, "worker": worker_id})
                continue

            total = scrape_category(url, name, db=db, driver=driver)
            results.append({"name": name, "status": "success", "products": total, "worker": worker_id})

        except Exception as e:
            print(f"  [W{worker_id}] UNEXPECTED ERROR: {e}", flush=True)
            try:
                db.log_scrape(url, name, 0, status="failed", error=str(e))
            except:
                pass
            results.append({"name": name, "status": "error", "error": str(e), "worker": worker_id})

    driver.quit()
    db.close()
    return results


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    categories = load_categories()

    print(f"Aldi Pipeline — {len(categories)} categories, {workers} parallel workers", flush=True)

    to_scrape = [c for c in categories
                 if not any(p in c["name"].lower() for p in SKIP_PATTERNS)]
    skipped = [c for c in categories if any(p in c["name"].lower() for p in SKIP_PATTERNS)]

    print(f"  Active:  {len(to_scrape)} categories", flush=True)
    print(f"  Skipped: {len(skipped)} (seasonal/promo)", flush=True)
    print(flush=True)

    db = AldiDB()
    already = db.scrape_log.count_documents({"status": "success"})
    print(f"  Already scraped: {already} categories", flush=True)
    db.close()

    # Split categories among workers (round-robin)
    chunks = [[] for _ in range(workers)]
    for i, entry in enumerate(to_scrape):
        chunks[i % workers].append((entry["name"], entry["url"]))

    args = [(chunks[i], i + 1) for i in range(workers)]

    start_time = time.time()
    completed = 0
    errors = 0

    with Pool(processes=workers) as pool:
        for worker_results in pool.imap_unordered(scrape_worker, args):
            for result in worker_results:
                completed += 1
                elapsed = time.time() - start_time
                name = result["name"]
                if result["status"] == "success":
                    print(f"  ✓ [{completed}/{len(to_scrape)}] {name} — {result['products']} products "
                          f"(W{result['worker']})", flush=True)
                elif result["status"] == "skipped":
                    print(f"  - [{completed}/{len(to_scrape)}] {name} — {result['products']} products "
                          f"(already scraped)", flush=True)
                else:
                    errors += 1
                    print(f"  ✗ [{completed}/{len(to_scrape)}] {name} — ERROR: {result.get('error','?')} "
                          f"(W{result['worker']})", flush=True)

    elapsed = time.time() - start_time
    print(f"\n{'='*60}", flush=True)
    print(f"Done — {completed} categories in {elapsed/60:.1f} mins", flush=True)
    print(f"  Success: {completed - errors}  |  Errors: {errors}  |  Skipped: {len(skipped)}", flush=True)

    db = AldiDB()
    total = db.get_total_product_count()
    cats = db.get_category_stats()
    print(f"  Total products in DB: {total}", flush=True)
    for s in cats:
        print(f"    {s['_id']}: {s['product_count']} products", flush=True)
    db.close()


if __name__ == "__main__":
    main()
