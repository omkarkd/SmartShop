import time
import re
import random
import os
import tempfile
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


ALDI_OWN_BRANDS = {
    "naturya", "mamia", "specially selected", "the fishmonger",
    "the butcher", "the bakery", "the pizza chef", "cowbelle",
    "gianni's", "emporium", "dairy manor", "big & lovely",
    "purely belgian", "brooklea", "dairy manor", "braintree",
    "little angels", "milsani", "alberto", "vossi", "corale",
    "floral Fresh", "the food market", "love fresh",
    "ashfields", "bramwells", "delicieux", "di Napoli",
    "el Puente", "falcon", "Fortezza", "grandessa",
    "harvest morn", "holli", "hughmanity", "ivory",
    "jaffa cakes is a trademark", "kingsland", "little treasures",
    "l'oven fresh", "L'Oven Fresh", "L'oven ready", "la colpa",
    "la gina", "L'Ardennais", "marcus", "melt in the middle",
    "millcott", "milli", "monte dining", "mornflake is a trademark",
    "natco", "natures garden", "newgate", "oakhurst",
    "paula's choice", "pavilion", "pearse", "the pantry",
    "portinari", "pure & crisp", "roam", "robert osborne",
    "roman roots", "rosemont", "savarium", "schloss gold",
    "silverbrook", "simply unfiltered", "sir gino",
    "so organic", "solo", "south island", "splendid",
    "stamford st.", "suttons", "tall", "the collection",
    "the deli", "the fish market", "the foodie market",
    "the fruit bowl", "the gourmet" , "the greengrocer",
    "the herd", "the lush", "the meat market", "the noodle",
    "the nut house", "the pickle works", "the smokehouse",
    "the soup factory", "the sweet", "the truffle",
    "the wholefish", "tony's", "touch of", "triangle",
    "veetals", "village bakery", "vivera", "warrendorf",
    "way to go", "whirl", "wild about", "wolds", "york", "zebra",
}


_DRIVER_LOCK_FILE = os.path.join(tempfile.gettempdir(), ".aldi_driver_lock")


def _cleanup_stale_chrome():
    """Kill stale Chrome/ChromeDriver processes from previous runs on this PID"""
    try:
        pid = os.getpid()
        import subprocess
        # Only kill chromedriver instances (not user's actual Chrome browser)
        subprocess.run(
            ["pkill", "-f", f"undetected_chromedriver.*{pid}"],
            capture_output=True, timeout=5
        )
    except:
        pass


def _acquire_patch_lock(timeout=30):
    start = time.time()
    while True:
        try:
            fd = os.open(_DRIVER_LOCK_FILE, os.O_CREAT | os.O_EXCL)
            os.close(fd)
            return True
        except FileExistsError:
            if time.time() - start > timeout:
                return False
            time.sleep(random.uniform(0.3, 1.0))


def _release_patch_lock():
    try:
        os.unlink(_DRIVER_LOCK_FILE)
    except:
        pass


def create_driver():
    _cleanup_stale_chrome()
    time.sleep(random.uniform(1.0, 3.0))
    options = uc.ChromeOptions()
    options.headless = os.environ.get("CHROME_HEADLESS", "").lower() in ("1", "true", "yes")
    user_data_dir = tempfile.mkdtemp(prefix=f"aldi_{os.getpid()}_")
    options.add_argument(f"--user-data-dir={user_data_dir}")
    port = random.randint(20000, 60000)
    options.add_argument(f"--remote-debugging-port={port}")
    _acquire_patch_lock()
    try:
        driver = uc.Chrome(options=options)
        return driver
    finally:
        _release_patch_lock()


OWN_BRAND_LOWERCASE = {b.lower() for b in ALDI_OWN_BRANDS}


def is_aldi_own_brand(brand_text):
    if not brand_text:
        return True
    lower = brand_text.strip().lower()
    # If no brand is shown or it's one of Aldi's own labels
    return lower in OWN_BRAND_LOWERCASE


PAGE_REGEX = re.compile(r"[?&]page=(\d+)", re.IGNORECASE)


def get_page_numbers(driver):
    """Extract all page numbers from pagination nav"""
    try:
        nav = driver.find_element(By.CSS_SELECTOR, "nav.base-pagination")
        links = nav.find_elements(By.CSS_SELECTOR, ".base-pagination__count")
        nums = []
        for link in links:
            text = link.text.strip()
            if text.isdigit():
                nums.append(int(text))
        return sorted(set(nums))
    except:
        return []


def get_total_pages(driver):
    nums = get_page_numbers(driver)
    return max(nums) if nums else 1


def page_url(base_url, page):
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}page={page}"


def parse_price(text):
    if not text:
        return None
    text = text.strip().lstrip("£").replace(",", "")
    try:
        return float(text)
    except:
        return text


def scrape_page_products(driver, category_name):
    products = driver.find_elements(By.CSS_SELECTOR, ".product-teaser-item")
    results = []

    for p in products:
        try:
            name = p.find_element(By.CSS_SELECTOR, ".product-tile__name p").text.strip()
        except:
            name = None
        try:
            brand_el = p.find_element(By.CSS_SELECTOR, ".product-tile__brandname p")
            brand = brand_el.text.strip()
        except:
            brand = None
        try:
            size = p.find_element(By.CSS_SELECTOR, ".product-tile__unit-of-measurement p").text.strip()
        except:
            size = None
        try:
            price = p.find_element(By.CSS_SELECTOR, ".base-price__regular").text.strip()
        except:
            price = None
        # Try alternative selectors if price not found
        if not price:
            try:
                price = p.find_element(By.CSS_SELECTOR, ".base-price__regular span").text.strip()
            except:
                pass
        try:
            was_price_el = p.find_element(By.CSS_SELECTOR, ".base-price__was-price")
            was_price = parse_price(was_price_el.text)
        except:
            was_price = None
        try:
            price_per_el = p.find_element(By.CSS_SELECTOR, ".product-tile__comparison-price p")
            price_per_unit = price_per_el.text.strip()
        except:
            price_per_unit = None
        try:
            product_url = p.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
        except:
            product_url = None

        price_num = parse_price(price)

        # Determine if this is an Aldi own brand
        own_brand = is_aldi_own_brand(brand)

        # If was_price exists, current price IS the promotion price
        price_with_promotion = float(was_price) - float(price_num) if was_price and price_num else None
        price_with_promotion = round(price_with_promotion, 2) if price_with_promotion else None

        product = {
            "url": product_url,
            "category": category_name,
            "brand": brand,
            "product_name": name,
            "size": size,
            "price": price_num,
            "was_price": was_price,
            "price_with_promotion": price_num if was_price else None,
            "price_per_unit": price_per_unit,
            "is_own_brand": own_brand,
        }
        results.append(product)

    return results


def scrape_category(url, category_name, db=None, driver=None):
    """
    Scrape an Aldi category. If `driver` is provided, reuse it (avoids
    create/quit overhead between categories in a pipeline). Otherwise,
    create and quit a new driver per call.
    """
    print(f"\n  Scraping: {category_name}")
    print(f"  URL: {url}")

    own_driver = False
    if driver is None:
        driver = create_driver()
        own_driver = True
    wait = WebDriverWait(driver, 20)

    try:
        driver.get(url)
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".product-teaser-item")))
        time.sleep(2)

        total_pages = get_total_pages(driver)
        total_products = 0
        all_products = []

        for page_num in range(1, total_pages + 1):
            if page_num > 1:
                driver.get(page_url(url, page_num))
                wait.until(EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, ".product-teaser-item")))
                time.sleep(2)

            print(f"    Page {page_num}/{total_pages}...", end=" ")
            products = scrape_page_products(driver, category_name)
            print(f"{len(products)} products")

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
                db.log_scrape(url, category_name, len(products), page=page_num)
                total_products += len(products)
                print(f"      ({existing} existing, {len(new_prods)} new)")
            else:
                all_products.extend(products)
                total_products += len(products)

        print(f"    Total: {total_products} products across {total_pages} page(s)")
        return all_products if not db else total_products

    except Exception as e:
        print(f"  ERROR scraping {category_name}: {e}")
        if db:
            db.log_scrape(url, category_name, 0, status="failed", error=str(e))
        return [] if not db else 0

    finally:
        if own_driver:
            driver.quit()
