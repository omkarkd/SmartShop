import json
import time
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sainsburys.scraper import scrape_category, create_driver
from sainsburys.db import SainsburysDB


NOISE_PATTERNS = {
    "see all", "list of partners", "shop now", "occasions",
    "your favourite", "crafted for better", "step away from the peeler",
    "fresh-picked jersey royals",
}


def is_noise(name):
    lower = name.strip().lower()
    for pat in NOISE_PATTERNS:
        if pat in lower:
            return True
    return False


def load_hierarchy(path="scrapper/sainsburys/category_hierarchy.json"):
    with open(path) as f:
        return json.load(f)


def get_all_urls(hierarchy):
    urls = []
    seen_urls = set()

    for top_cat, subcats in hierarchy.items():
        top_skip = {"drinks", "fish seafood", "offers"}
        if top_cat.lower() in top_skip:
            print(f"  Skipping {top_cat} (no standalone page)")
            continue

        for sub in subcats:
            name = sub["name"]
            url = sub["url"]

            if is_noise(name):
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            full_name = f"{top_cat} > {name}" if not name.lower().startswith(top_cat.lower().replace("&", "and")) else top_cat
            urls.append((full_name, url))

    return urls


def main():
    print("=" * 60)
    print("Sainsbury's Scraping Pipeline")
    print("=" * 60)

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
    from sainsburys.scraper import accept_cookies
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
                # Check if driver is still alive
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
    print(f"Pipeline Complete")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {fail_count}")
    print(f"  Total products: {total_products}")

    for s in db.get_category_stats():
        print(f"  {s['_id']}: {s['product_count']}")

    db.close()


if __name__ == "__main__":
    main()
