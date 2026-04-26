import asyncio
import os
import re
from playwright.async_api import async_playwright
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

API_TOKEN = os.getenv('API_TOKEN')
CHAT_ID = int(os.getenv('CHAT_ID'))
URL = "https://kolesa.kz/cars/toyota/land-cruiser/year-from-2021/?_sys-hasphoto=2"
HISTORY_FILE = "seen_ads.txt"
MIN_YEAR = 2021

async def check_kolesa():
    if not API_TOKEN or not CHAT_ID:
        print("❌ Ошибка: API_TOKEN или CHAT_ID не найдены в переменных окружения!")
        return

    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            seen_ads = set(line.strip() for line in f)
    else:
        seen_ads = set()

    print(f"🚀 Запуск проверки. В базе: {len(seen_ads)}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector(".a-card", timeout=15000)
            ads = await page.query_selector_all(".a-card")
            
            new_ads_count = 0
            for ad in ads:
                ad_id = await ad.get_attribute("data-id")
                if ad_id and ad_id not in seen_ads:
                    title_el = await ad.query_selector(".a-card__title")
                    title_text = await title_el.inner_text() if title_el else ""
                    
                    year_match = re.search(r'(\d{4})', title_text)
                    if year_match:
                        ad_year = int(year_match.group(1))
                        if ad_year < MIN_YEAR: continue
                    else: continue

                    price_el = await ad.query_selector(".a-card__price")
                    price = await price_el.inner_text() if price_el else "Цена не указана"
                    link = f"https://kolesa.kz/a/show/{ad_id}"
                    
                    msg = f"<b>🆕 Новое объявление!</b>\n\n🚗 {title_text.strip()}\n💰 <b>{price.strip()}</b>\n🔗 <a href='{link}'>Открыть</a>"
                    
                    await bot.send_message(CHAT_ID, msg)
                    with open(HISTORY_FILE, "a") as f:
                        f.write(f"{ad_id}\n")
                    seen_ads.add(ad_id)
                    new_ads_count += 1
            
            print(f"✅ Проверка окончена. Найдено новых: {new_ads_count}")

        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
        finally:
            await browser.close()
            await bot.session.close()

if __name__ == "__main__":
    asyncio.run(check_kolesa())