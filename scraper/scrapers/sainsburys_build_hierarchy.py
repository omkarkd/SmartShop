import time
import json
import os
import tempfile
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By


def create_driver():
    options = uc.ChromeOptions()
    options.headless = False
    user_data_dir = tempfile.mkdtemp(prefix="sains_hier_")
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = uc.Chrome(options=options, version_main=148, use_subprocess=True)
    return driver


def accept_cookies(driver):
    for text in ["Continue and accept", "Accept All"]:
        try:
            btn = driver.find_element(By.XPATH, f"//button[contains(text(), '{text}')]")
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)
            return True
        except:
            pass
    return False


def navigate(driver, url):
    try:
        driver.get("about:blank")
    except:
        pass
    time.sleep(2)
    try:
        driver.execute_script(f"window.location.assign('{url}');")
    except:
        return False
    time.sleep(10)
    return True


def extract_subcats_from_page(driver, final_url):
    """Extract subcategory links from the current page"""
    time.sleep(3)
    subcats = []
    seen = set()
    for attempt in range(3):
        try:
            all_links = driver.find_elements(By.TAG_NAME, "a")
            for link in all_links:
                try:
                    href = link.get_attribute("href") or ""
                    text = link.text.strip()
                except:
                    continue
                if not href or not text:
                    continue
                if "/gol-ui/groceries/" in href and "/c:" in href:
                    if href.rstrip("/") == final_url.rstrip("/"):
                        continue
                    if href not in seen:
                        seen.add(href)
                        subcats.append({"name": text, "url": href})
            break
        except Exception as e:
            print(f"    Retry {attempt+1}: {e}")
            time.sleep(3)
    return subcats


def main():
    output_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(output_dir, exist_ok=True)

    driver = create_driver()
    time.sleep(2)

    # Open main page
    navigate(driver, "https://www.sainsburys.co.uk/gol-ui/groceries")
    accept_cookies(driver)

    # Step 1: Scan main page for ALL category links (both top-level and sub-categories)
    print("=== SCANNING MAIN PAGE ===")
    all_cat_links = {}
    try:
        all_links = driver.find_elements(By.TAG_NAME, "a")
        for link in all_links:
            try:
                href = link.get_attribute("href") or ""
                text = link.text.strip()
            except:
                continue
            if not href or not text:
                continue
            if "/gol-ui/groceries/" in href and "/c:" in href:
                path = href.replace("https://www.sainsburys.co.uk/gol-ui/groceries/", "")
                parts = path.split("/")
                top_slug = parts[0]
                if top_slug not in all_cat_links:
                    all_cat_links[top_slug] = []
                all_cat_links[top_slug].append({"name": text, "url": href})
    except:
        print("  Window closed, cannot scan main page")

    if all_cat_links:
        print(f"\nCategories found on main page:")
        for slug, links in sorted(all_cat_links.items()):
            print(f"  {slug.replace('-',' ').title():30s} {len(links):3d} links")

    # Step 2: Navigate to each category page that had 0 subcats and extract
    # These are the categories we need to fix
    fix_categories = {
        "Food Cupboard":   "https://www.sainsburys.co.uk/gol-ui/groceries/food-cupboard/c:1019883",
        "Fruit Vegetables":"https://www.sainsburys.co.uk/gol-ui/groceries/fruit-and-vegetables/c:1020082",
        "Household":       "https://www.sainsburys.co.uk/gol-ui/groceries/household/c:1020324",
        "Drinks":          "https://www.sainsburys.co.uk/gol-ui/groceries/drinks",
    }

    fixed_data = {}
    for name, url in fix_categories.items():
        print(f"\n=== {name} ===")
        if not navigate(driver, url):
            print("  Window closed, trying one more time...")
            driver.quit()
            time.sleep(3)
            driver = create_driver()
            time.sleep(2)
            navigate(driver, url)

        try:
            final_url = driver.current_url
            print(f"  Final: {final_url}")
        except:
            print("  Window closed")
            fixed_data[name] = []
            continue

        subcats = extract_subcats_from_page(driver, final_url)
        print(f"  Subcategories: {len(subcats)}")
        for s in subcats[:30]:
            print(f"    - {s['name'][:60]}")
        if len(subcats) > 30:
            print(f"    ... and {len(subcats)-30} more")
        fixed_data[name] = subcats

    # Step 3: Load existing data and merge with new data
    existing_file = os.path.join(output_dir, "all_subcategories.json")
    if os.path.exists(existing_file):
        with open(existing_file, "r") as f:
            existing_data = json.load(f)
    else:
        existing_data = {}

    # Update with fixed data
    existing_data.update(fixed_data)

    # Also add the correct URLs for categories that had 0 but aren't in fix_categories
    # Fish Seafood and Offers still need investigation
    if "Fish Seafood" in existing_data and not existing_data["Fish Seafood"]:
        existing_data["Fish Seafood"] = [{"name": "Fish & seafood is under Meat & Fish category", "url": "https://www.sainsburys.co.uk/gol-ui/groceries/meat-and-fish/fish-and-seafood/c:1020363"}]
    if "Offers" in existing_data and not existing_data["Offers"]:
        existing_data["Offers"] = [{"name": "Offers page (no fixed subcategories)", "url": "https://www.sainsburys.co.uk/gol-ui/offers"}]

    # Save merged data
    with open(os.path.join(output_dir, "all_subcategories.json"), "w") as f:
        json.dump(existing_data, f, indent=2, default=str)

    # Save fixed data separately
    with open(os.path.join(output_dir, "fixed_subcategories.json"), "w") as f:
        json.dump(fixed_data, f, indent=2, default=str)

    # Step 4: Build and save the full hierarchy
    hierarchy = build_hierarchy(existing_data)
    hierarchy_file = os.path.join(output_dir, "category_hierarchy.json")
    with open(hierarchy_file, "w") as f:
        json.dump(hierarchy, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"Updated: all_subcategories.json")
    print(f"Fixed:   fixed_subcategories.json")
    print(f"Hierarchy: category_hierarchy.json")
    print_hierarchy(hierarchy)

    driver.quit()


def build_hierarchy(data):
    """Build a clean hierarchical structure"""
    hierarchy = {}
    for cat_name, subcats in sorted(data.items()):
        if not subcats:
            hierarchy[cat_name] = []
            continue
        cat_entry = []
        for sc in subcats:
            cat_entry.append({
                "name": sc["name"],
                "url": sc["url"]
            })
        hierarchy[cat_name] = cat_entry
    return hierarchy


def print_hierarchy(hierarchy):
    """Print human-readable hierarchy"""
    total_subcats = 0
    for cat, subs in sorted(hierarchy.items()):
        count = len(subs)
        total_subcats += count
        print(f"\n{cat}")
        print(f"  {'─'*40}")
        if count == 0:
            print(f"  (no subcategories)")
        else:
            for s in subs[:5]:
                print(f"  ├─ {s['name'][:55]}")
            if count > 5:
                print(f"  └─ ... and {count-5} more")
            else:
                print(f"  └─ Total: {count} subcategories")
    print(f"\n{'='*60}")
    print(f"Total: {len(hierarchy)} categories, {total_subcats} subcategories")


if __name__ == "__main__":
    main()
