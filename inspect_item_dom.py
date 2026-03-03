from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import json
from urllib.parse import unquote

options = webdriver.ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--window-size=1920,1080')
options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
driver = webdriver.Chrome(options=options)

try:
    driver.get('https://schools.mealviewer.com/school/BuckalewElementary')
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.calendar-grid-day')))

    try:
        accept = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.tsandcs-modal-buttons-accept')))
        driver.execute_script('arguments[0].click();', accept)
    except Exception:
        pass

    menu_block = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'menu-block')))
    Select(menu_block).select_by_visible_text('Lunch')
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.item-name')))

    card = driver.find_element(By.XPATH, "//div[contains(@class,'calendar-grid-item')][.//span[contains(@class,'weekday') and normalize-space()='Tuesday'] and .//span[contains(@class,'day') and normalize-space()='3']]")
    buttons = card.find_elements(By.CSS_SELECTOR, 'button.foodItem')
    print('buttons:', len(buttons))
    target = None
    for b in buttons:
        if 'Pizza Boli' in (b.text or ''):
            target = b
            break
    if target is None and buttons:
        target = buttons[0]

    if target:
        print('button text:', target.text)
        print('button outer html:\n', target.get_attribute('outerHTML')[:4000])

        imgs = target.find_elements(By.CSS_SELECTOR, 'img')
        print('nested imgs:', len(imgs))
        for i in imgs[:5]:
            print('img src', i.get_attribute('src'))
            print('img data-src', i.get_attribute('data-src'))

        info_btn = target.find_element(By.CSS_SELECTOR, 'button.notification-section')
        driver.get_log('performance')
        driver.execute_script('arguments[0].click();', info_btn)
        WebDriverWait(driver, 12).until(
            lambda d: d.find_element(By.CSS_SELECTOR, '#food-item-modal').value_of_css_property('display') != 'none'
        )
        modal = driver.find_element(By.CSS_SELECTOR, '#food-item-modal')
        print('modal display:', modal.value_of_css_property('display'))
        print('modal html:\n', modal.get_attribute('outerHTML')[:5000])
        modal_imgs = modal.find_elements(By.CSS_SELECTOR, 'img')
        print('modal imgs:', len(modal_imgs))
        for i in modal_imgs[:10]:
            print('modal img src', i.get_attribute('src'))
            print('modal img data-src', i.get_attribute('data-src'))

        food_pic = modal.find_elements(By.CSS_SELECTOR, '.foodItemPicture')
        if food_pic:
            print('foodItemPicture style:', food_pic[0].get_attribute('style'))

        logs = driver.get_log('performance')
        urls = []
        for entry in logs:
            try:
                payload = json.loads(entry.get('message', ''))
                msg = payload.get('message', {})
                if msg.get('method') != 'Network.requestWillBeSent':
                    continue
                u = msg.get('params', {}).get('request', {}).get('url', '')
                if '/fooditemimages/' in u:
                    uu = unquote(u)
                    if uu not in urls:
                        urls.append(uu)
            except Exception:
                pass
        print('captured image urls:', urls[-10:])

finally:
    driver.quit()
