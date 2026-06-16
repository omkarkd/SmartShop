import os
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By


SAINSBURYS_OWN_BRANDS = {
    "sainsbury's", "sainsbury's so organic", "so organic",
    "taste the difference", "love life", "my goodness!",
    "habitat", "by sainsbury's",
}


def create_driver(retries=3):
    for attempt in range(retries):
        try:
            options = uc.ChromeOptions()
            if os.environ.get("CHROME_HEADLESS", "").lower() in ("1", "true", "yes"):
                options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
            kwargs = {"options": options}
            chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
            if chromedriver_path:
                kwargs["driver_executable_path"] = chromedriver_path
            version_main = os.environ.get("CHROME_VERSION_MAIN")
            if version_main:
                kwargs["version_main"] = int(version_main)
            driver = uc.Chrome(**kwargs)
            for nav_retry in range(3):
                try:
                    driver.get("about:blank")
                    break
                except Exception:
                    if nav_retry < 2:
                        time.sleep(2)
                        continue
            return driver
        except Exception:
            if attempt < retries - 1:
                time.sleep(3)
                continue
            raise


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


def navigate_to(driver, url):
    driver.execute_script(f"window.location.assign('{url}');")
    time.sleep(6)
    try:
        _ = driver.title
        return True
    except:
        return False


def parse_price(text):
    if not text:
        return None
    text = text.strip().lstrip("£").replace(",", "").replace("p", "")
    try:
        return float(text)
    except:
        return None


OWN_BRAND_LOWERCASE = {b.lower() for b in SAINSBURYS_OWN_BRANDS}


def is_sainsburys_own_brand(brand_text):
    if not brand_text:
        return True
    lower = brand_text.strip().lower()
    return lower in OWN_BRAND_LOWERCASE


def extract_brand_from_name(name):
    if not name:
        return None
    first_part = name.strip().split()[0].rstrip(",")
    lower = first_part.lower()
    if lower in OWN_BRAND_LOWERCASE:
        return first_part
    for brand in ["Sainsbury's", "Taste the Difference", "Love Life", "My Goodness!", "Habitat"]:
        if name.lower().startswith(brand.lower()):
            return brand
    return None


def scroll_and_load(driver, max_loads=20):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    loads = 0
    for i in range(max_loads):
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Load more')]")
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(2)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                loads += 1
            else:
                break
        except:
            break
    return loads


def scrape_page_products(driver, category_name):
    tiles = driver.find_elements(By.CSS_SELECTOR, "[data-testid^='product-tile-']")
    results = []
    seen_urls = set()

    for tile in tiles:
        try:
            name_el = tile.find_element(By.CSS_SELECTOR, "[data-testid='product-tile-description']")
            name = name_el.text.strip()
        except:
            name = None

        if not name:
            continue

        try:
            product_link = tile.find_element(By.CSS_SELECTOR, "a[href*='/gol-ui/product/']")
            product_url = product_link.get_attribute("href")
        except:
            product_url = None

        if product_url and product_url in seen_urls:
            continue
        if product_url:
            seen_urls.add(product_url)

        # Regular retail price
        try:
            price_el = tile.find_element(By.CSS_SELECTOR, "[data-testid='pt-retail-price']")
            price_text = price_el.text.strip()
        except:
            price_text = None

        # Nectar price label (e.g. "Nectar Price")
        nectar_label = None
        nectar_price_text = None
        try:
            nectar_label_el = tile.find_element(By.CSS_SELECTOR, "[data-testid='nectar-price-label']")
            nectar_label = nectar_label_el.text.strip()
            # If nectar label exists, the contextual price IS the nectar price
            try:
                nectar_price_el = tile.find_element(By.CSS_SELECTOR, "[data-testid='contextual-price-text']")
                nectar_price_text = nectar_price_el.text.strip()
            except:
                pass
        except:
            pass

        # If no regular price found, fallback to contextual price
        if not price_text:
            try:
                fallback_el = tile.find_element(By.CSS_SELECTOR, "[data-testid='contextual-price-text']")
                price_text = fallback_el.text.strip()
            except:
                price_text = None

        try:
            unit_price_el = tile.find_element(By.CSS_SELECTOR, "[data-testid='pt-unit-price']")
            price_per_unit = unit_price_el.text.strip()
        except:
            price_per_unit = None

        try:
            image_el = tile.find_element(By.CSS_SELECTOR, "img[src*='/products/']")
            image_url = image_el.get_attribute("src")
        except:
            image_url = None

        try:
            promo_el = tile.find_element(By.CSS_SELECTOR, "[data-testid='product-promo']")
            was_price_text = promo_el.text.strip()
            was_price = parse_price(was_price_text)
        except:
            was_price = None

        try:
            badge_el = tile.find_element(By.CSS_SELECTOR, "[data-testid='product-badge']")
            badge = badge_el.text.strip()
        except:
            badge = None

        brand = extract_brand_from_name(name)
        own_brand = is_sainsburys_own_brand(brand)

        price_num = parse_price(price_text)
        nectar_price_num = parse_price(nectar_price_text)

        price_with_promotion = round(float(was_price) - float(price_num), 2) if was_price and price_num else None

        product = {
            "url": product_url,
            "product_name": name,
            "category": category_name,
            "brand": brand,
            "price": price_num,
            "was_price": was_price,
            "price_with_promotion": price_num if was_price else None,
            "price_per_unit": price_per_unit,
            "image_url": image_url,
            "promotion_badge": badge,
            "is_own_brand": own_brand,
            "nectar_price": nectar_price_num,
            "nectar_price_label": nectar_label,
        }
        results.append(product)

    return results


def scrape_category(url, category_name, db=None, driver=None, max_loads=20):
    print(f"\n  Scraping: {category_name}")
    print(f"  URL: {url}")

    own_driver = False
    if driver is None:
        driver = create_driver()
        own_driver = True

    try:
        if not navigate_to(driver, url):
            print("    SKIPPED: Window closed")
            if db:
                db.log_scrape(url, category_name, 0, status="failed", error="Window closed during navigation")
            return 0 if db else []

        accept_cookies(driver)

        tiles = driver.find_elements(By.CSS_SELECTOR, "[data-testid^='product-tile-']")
        if not tiles:
            print("    No product tiles found")
            if db:
                db.log_scrape(url, category_name, 0, status="failed", error="No product tiles found")
            return 0 if db else []

        loads = scroll_and_load(driver, max_loads)
        if loads > 0:
            print(f"    Loaded {loads} more pages")

        products = scrape_page_products(driver, category_name)
        print(f"    {len(products)} products")

        if db:
            existing = 0
            new_prods = []
            for p in products:
                if p["url"] and db.product_exists(p["url"]):
                    existing += 1
                else:
                    new_prods.append(p)
            if new_prods:
                db.insert_products(new_prods)
            db.log_scrape(url, category_name, len(products))
            print(f"      ({existing} existing, {len(new_prods)} new)")
            return len(products)
        else:
            return products

    except Exception as e:
        print(f"    ERROR: {e}")
        if db:
            db.log_scrape(url, category_name, 0, status="failed", error=str(e))
        return 0 if db else []

    finally:
        if own_driver:
            driver.quit()
