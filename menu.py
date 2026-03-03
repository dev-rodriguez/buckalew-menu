from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import csv
import json
import re
import time
from datetime import date, timedelta, datetime
from urllib.parse import unquote
from html import escape

# 1. Setup the browser (Headless means no window pops up)
options = webdriver.ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--window-size=1920,1080')
options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
driver = webdriver.Chrome(options=options)


def extract_fooditem_image_urls(perf_logs):
    image_urls = []
    for entry in perf_logs:
        message_text = entry.get("message", "")
        if not message_text:
            continue

        try:
            payload = json.loads(message_text)
        except Exception:
            continue

        message = payload.get("message", {})
        if message.get("method") != "Network.requestWillBeSent":
            continue

        request = message.get("params", {}).get("request", {})
        url = request.get("url", "")
        if "/fooditemimages/" not in url:
            continue

        cleaned_url = unquote(url.rstrip(");")).replace("&quot", "").replace("\"", "")
        if cleaned_url not in image_urls:
            image_urls.append(cleaned_url)

    return image_urls


def extract_fooditem_image_urls_from_dom(driver):
    html = driver.page_source
    matches = re.findall(
        r"https://(?:appassets|custcdn)\.mealviewer\.com/fooditemimages/[^\"'\s<)]+",
        html,
        flags=re.IGNORECASE,
    )
    urls = []
    for match in matches:
        cleaned_url = (
            unquote(match.rstrip(");"))
            .replace("&amp;", "&")
            .replace("&quot", "")
            .replace('"', "")
        )
        if cleaned_url not in urls:
            urls.append(cleaned_url)
    return urls


def next_school_day(from_day=None):
    base_day = from_day or date.today()
    candidate = base_day + timedelta(days=1)
    while candidate.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        candidate += timedelta(days=1)
    return candidate


def get_site_display_date(driver):
    try:
        date_display = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#dateDisplay"))
        )
        raw_text = date_display.text.strip()
        if not raw_text:
            raw_text = (driver.execute_script("return (document.getElementById('dateDisplay') || {}).textContent || ''") or "").strip()
        if not raw_text:
            return None

        # Example: "Tuesday Mar 3rd" -> "Tuesday Mar 3"
        cleaned = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", raw_text)
        parsed = datetime.strptime(cleaned, "%A %b %d")

        year = date.today().year
        try:
            heading = driver.find_element(By.CSS_SELECTOR, "div.heading").text.strip()
            heading_match = re.search(r"\b(\d{4})\b", heading)
            if heading_match:
                year = int(heading_match.group(1))
        except Exception:
            pass

        return parsed.replace(year=year).date()
    except Exception:
        return None


def accept_terms_if_present(driver):
    try:
        accept_button = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.tsandcs-modal-buttons-accept"))
        )
        driver.execute_script("arguments[0].click();", accept_button)
        WebDriverWait(driver, 8).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, ".tsandcs-modal-overlay"))
        )
        return True
    except Exception:
        return False


def select_lunch_menu(driver):
    wait = WebDriverWait(driver, 10)

    # Strategy 0: known menu block selector used on MealViewer
    try:
        menu_block = wait.until(EC.presence_of_element_located((By.ID, "menu-block")))
        meal_select = Select(menu_block)
        selected_text = meal_select.first_selected_option.text.strip().lower()
        if selected_text != "lunch":
            meal_select.select_by_visible_text("Lunch")
            wait.until(
                lambda d: Select(d.find_element(By.ID, "menu-block")).first_selected_option.text.strip().lower() == "lunch"
            )
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.item-name")))
        return True
    except Exception:
        pass

    # Strategy 1: native <select>
    select_elements = driver.find_elements(By.TAG_NAME, "select")
    for select_el in select_elements:
        try:
            meal_select = Select(select_el)
            for option in meal_select.options:
                text = option.text.strip().lower()
                value = (option.get_attribute("value") or "").strip().lower()
                if "lunch" in text or "lunch" in value:
                    meal_select.select_by_visible_text(option.text)
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.item-name")))
                    return True
        except Exception:
            continue

    # Strategy 2: button-based dropdowns/menus
    toggle_candidates = driver.find_elements(
        By.XPATH,
        "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'breakfast') or "
        "contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'meal') or "
        "contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'meal') or "
        "contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'breakfast')]"
    )
    for toggle in toggle_candidates:
        try:
            driver.execute_script("arguments[0].click();", toggle)
            lunch_option = wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//*[self::button or self::a or self::li or self::span][contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lunch')]"
                ))
            )
            driver.execute_script("arguments[0].click();", lunch_option)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.item-name")))
            return True
        except Exception:
            continue

    # Strategy 3: direct click on visible lunch controls
    lunch_controls = driver.find_elements(
        By.XPATH,
        "//*[self::button or self::a or self::span][contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lunch')]"
    )
    for control in lunch_controls:
        try:
            driver.execute_script("arguments[0].click();", control)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.item-name")))
            return True
        except Exception:
            continue

    return False


def go_to_next_menu_period(driver):
    try:
        nav_buttons = driver.find_elements(By.CSS_SELECTOR, "button.heading-button.month-change")
        if not nav_buttons:
            return False

        next_button = nav_buttons[-1]
        driver.execute_script("arguments[0].click();", next_button)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.calendar-grid-day"))
        )
        return True
    except Exception:
        return False


def extract_target_day_entries(soup, target_day_label):
    menu_data = []
    flat_items = []

    day_cards = soup.select("div.calendar-grid-item")
    for card in day_cards:
        day_el = card.select_one("div.calendar-grid-day")
        if not day_el:
            continue

        weekday = day_el.select_one("span.weekday")
        day_num = day_el.select_one("span.day")
        day_label = " ".join(
            part for part in [
                weekday.get_text(strip=True) if weekday else "",
                day_num.get_text(strip=True) if day_num else ""
            ] if part
        )

        if day_label != target_day_label:
            continue

        item_names = [item.get_text(strip=True) for item in card.select("div.item-name")]
        if not item_names:
            continue

        items_with_images = []
        for item_name in item_names:
            items_with_images.append({"name": item_name, "image_url": ""})
            flat_items.append((day_label, item_name))

        menu_data.append({"day": day_label, "items": items_with_images})

    return menu_data, flat_items


def get_target_day_card_element(driver, target_day_label):
    try:
        parts = target_day_label.split()
        if len(parts) < 2:
            return None

        weekday = parts[0]
        day_num = parts[-1]
        xpath = (
            "//div[contains(@class,'calendar-grid-item') and "
            ".//div[contains(@class,'calendar-grid-day')]"
            "//span[contains(@class,'weekday') and normalize-space()=$weekday] and "
            ".//div[contains(@class,'calendar-grid-day')]"
            "//span[contains(@class,'day') and normalize-space()=$day_num]]"
        )

        # Selenium XPath does not support custom variables; inject safely from controlled values.
        xpath = xpath.replace("$weekday", f"'{weekday}'").replace("$day_num", f"'{day_num}'")

        return WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
    except Exception:
        return None


def find_item_card_in_day(day_card_element, item_name):
    cards = day_card_element.find_elements(By.CSS_SELECTOR, "button.foodItem")
    for card in cards:
        try:
            if not card.is_displayed():
                continue
            name_el = card.find_element(By.CSS_SELECTOR, "div.item-name")
            if name_el.text.strip() == item_name:
                return card
        except Exception:
            continue
    return None


def build_widget_html(menu_data, date_suffix, fallback_day_label=""):
        day_sections = []
        if not menu_data and fallback_day_label:
                day_sections.append(
                        f"""
                        <section class=\"day\">
                            <h2>{escape(fallback_day_label)}</h2>
                            <div class=\"grid\">
                                <div class=\"item\">
                                    <div class=\"thumb thumb-empty\">No image</div>
                                    <div class=\"item-name\">No menu items found for this day yet.</div>
                                </div>
                            </div>
                        </section>
                        """
                )

        for day_entry in menu_data:
                day = escape(day_entry["day"])
                item_cards = []
                for item in day_entry["items"]:
                        item_name = escape(item.get("name", ""))
                        image_url = item.get("image_url", "").strip()

                        if image_url:
                                image_markup = (
                                        f'<img class="thumb" src="{escape(image_url, quote=True)}" '
                                        f'alt="{item_name}" loading="lazy" referrerpolicy="no-referrer">'
                                )
                        else:
                                image_markup = '<div class="thumb thumb-empty">No image</div>'

                        item_cards.append(
                                f"""
                                <div class=\"item\">
                                    {image_markup}
                                    <div class=\"item-name\">{item_name}</div>
                                </div>
                                """
                        )

                day_sections.append(
                        f"""
                        <section class=\"day\">
                            <h2>{day}</h2>
                            <div class=\"grid\">
                                {''.join(item_cards)}
                            </div>
                        </section>
                        """
                )

        return f"""<!doctype html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <meta http-equiv=\"Cache-Control\" content=\"no-cache, no-store, must-revalidate\">
    <meta http-equiv=\"Pragma\" content=\"no-cache\">
    <meta http-equiv=\"Expires\" content=\"0\">
    <title>Buckalew Menu</title>
    <style>
        :root {{
            --bg: #0f172a;
            --panel: #111827;
            --card: #1f2937;
            --text: #f9fafb;
            --muted: #cbd5e1;
            --accent: #f59e0b;
            --border: rgba(255,255,255,.12);
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            padding: 14px;
        }}
        .wrap {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 14px;
            padding: 12px 14px;
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
        }}
        .title {{ font-size: 1.15rem; font-weight: 700; }}
        .updated {{ color: var(--muted); font-size: .85rem; }}
        .day {{
            margin-bottom: 14px;
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 12px;
        }}
        h2 {{
            margin: 0 0 10px;
            font-size: 1rem;
            color: var(--accent);
            letter-spacing: .2px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 10px;
        }}
        .item {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
            min-height: 170px;
            display: flex;
            flex-direction: column;
        }}
        .thumb {{
            width: 100%;
            height: 120px;
            object-fit: cover;
            background: #0b1220;
            border-bottom: 1px solid var(--border);
        }}
        .thumb-empty {{
            display: grid;
            place-items: center;
            color: var(--muted);
            font-size: .82rem;
        }}
        .item-name {{
            padding: 9px 10px 11px;
            font-size: .9rem;
            line-height: 1.3;
            color: var(--text);
        }}
    </style>
</head>
<body>
    <div class=\"wrap\">
        <div class=\"header\">
            <div class=\"title\">Buckalew Elementary Lunch Menu</div>
            <div class=\"updated\">Updated {escape(date_suffix)}</div>
        </div>
        {''.join(day_sections)}
    </div>
</body>
</html>
"""

try:
    # 2. Navigate to the Buckalew Elementary page
    url = "https://schools.mealviewer.com/school/BuckalewElementary"
    driver.get(url)

    # 3. Wait for JavaScript-rendered menu content
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.calendar-grid-day"))
    )

    accepted_terms = accept_terms_if_present(driver)
    if accepted_terms:
        print("Accepted terms modal")

    site_date = get_site_display_date(driver)
    base_date = site_date or date.today()
    target_date = next_school_day(base_date)
    target_day_label = f"{target_date.strftime('%A')} {target_date.day}"
    if site_date:
        print(f"Site date: {site_date.isoformat()}")
    else:
        print("Site date unavailable; using local system date")
    print(f"Target menu date: {target_date.isoformat()} ({target_day_label})")

    lunch_selected = select_lunch_menu(driver)
    if lunch_selected:
        print("Selected meal: Lunch")
    else:
        print("Warning: Could not confirm lunch dropdown selection; continuing with current meal view.")

    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.item-name"))
    )

    # 4. Grab the HTML and parse target day (retry once in next menu period)
    printed = False
    menu_data = []
    flat_items = []

    for attempt in range(2):
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        menu_data, flat_items = extract_target_day_entries(soup, target_day_label)

        if menu_data:
            printed = True
            print(f"{target_day_label}: {[entry['name'] for entry in menu_data[0]['items']]}")
            break

        if attempt == 0 and go_to_next_menu_period(driver):
            print("Target day not visible in current view; moved to next menu period")
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.item-name"))
            )
            continue

        break

    if printed:
        day_card_element = get_target_day_card_element(driver, target_day_label)
        if not day_card_element:
            print(f"Warning: Could not locate day card element for {target_day_label}; image matching may be incomplete.")
        else:
            day_items = menu_data[0]["items"] if menu_data else []
            for item_entry in day_items:
                item_name = item_entry["name"]
                image_url = ""

                for _ in range(2):
                    try:
                        day_card_element = get_target_day_card_element(driver, target_day_label)
                        if not day_card_element:
                            continue

                        card = find_item_card_in_day(day_card_element, item_name)
                        if not card:
                            continue

                        dom_before = set(extract_fooditem_image_urls_from_dom(driver))
                        driver.get_log('performance')
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                        ActionChains(driver).move_to_element(card).pause(0.8).perform()

                        for selector in ["button.item-info", "button.notification-section"]:
                            try:
                                sub_button = card.find_element(By.CSS_SELECTOR, selector)
                                driver.execute_script("arguments[0].click();", sub_button)
                                time.sleep(0.35)
                            except Exception:
                                continue

                        recent_logs = driver.get_log('performance')
                        candidates = extract_fooditem_image_urls(recent_logs)
                        if not candidates:
                            dom_after = extract_fooditem_image_urls_from_dom(driver)
                            candidates = [url for url in dom_after if url not in dom_before]

                        if candidates:
                            image_url = candidates[-1]
                            break
                    except Exception:
                        continue

                item_entry["image_url"] = image_url

            # Second pass: retry only items still missing images with longer pauses
            for item_entry in day_items:
                if item_entry.get("image_url", "").strip():
                    continue

                item_name = item_entry["name"]
                for _ in range(2):
                    try:
                        day_card_element = get_target_day_card_element(driver, target_day_label)
                        if not day_card_element:
                            continue

                        card = find_item_card_in_day(day_card_element, item_name)
                        if not card:
                            continue

                        baseline_dom = set(extract_fooditem_image_urls_from_dom(driver))
                        driver.get_log('performance')

                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                        ActionChains(driver).move_to_element(card).pause(1.2).perform()

                        # Try a broader interaction sequence for stubborn items.
                        for selector in ["button.item-info", "button.notification-section"]:
                            try:
                                sub_button = card.find_element(By.CSS_SELECTOR, selector)
                                driver.execute_script("arguments[0].click();", sub_button)
                                time.sleep(0.6)
                            except Exception:
                                continue

                        try:
                            driver.execute_script("arguments[0].click();", card)
                            time.sleep(0.6)
                        except Exception:
                            pass

                        recent_logs = driver.get_log('performance')
                        candidates = extract_fooditem_image_urls(recent_logs)
                        if not candidates:
                            dom_after = extract_fooditem_image_urls_from_dom(driver)
                            candidates = [url for url in dom_after if url not in baseline_dom]

                        if candidates:
                            item_entry["image_url"] = candidates[-1]
                            break
                    except Exception:
                        continue

    if not printed:
        print(f"No menu items found for {target_day_label}. Saving refreshed output with empty-state content.")

    date_suffix = target_date.isoformat()
    json_filename = f"menu_output_{date_suffix}.json"
    csv_filename = f"menu_output_{date_suffix}.csv"
    widget_filename = f"menu_widget_{date_suffix}.html"

    with open("menu_output.json", "w", encoding="utf-8") as json_file:
        json.dump(menu_data, json_file, indent=2, ensure_ascii=False)

    with open(json_filename, "w", encoding="utf-8") as dated_json_file:
        json.dump(menu_data, dated_json_file, indent=2, ensure_ascii=False)

    with open("menu_output.csv", "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["day", "item", "image_url"])
        for day_entry in menu_data:
            day = day_entry["day"]
            for item in day_entry["items"]:
                writer.writerow([day, item["name"], item["image_url"]])

    with open(csv_filename, "w", newline="", encoding="utf-8") as dated_csv_file:
        writer = csv.writer(dated_csv_file)
        writer.writerow(["day", "item", "image_url"])
        for day_entry in menu_data:
            day = day_entry["day"]
            for item in day_entry["items"]:
                writer.writerow([day, item["name"], item["image_url"]])

    widget_html = build_widget_html(menu_data, date_suffix, fallback_day_label=target_day_label)
    with open("menu_widget.html", "w", encoding="utf-8") as widget_file:
        widget_file.write(widget_html)

    with open(widget_filename, "w", encoding="utf-8") as dated_widget_file:
        dated_widget_file.write(widget_html)

    print("Saved JSON: menu_output.json")
    print(f"Saved JSON: {json_filename}")
    print("Saved CSV: menu_output.csv")
    print(f"Saved CSV: {csv_filename}")
    print("Saved HTML: menu_widget.html")
    print(f"Saved HTML: {widget_filename}")
finally:
    driver.quit()