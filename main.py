import asyncio
import os
import re
from playwright.async_api import async_playwright
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- НАСТРОЙКИ ---
API_TOKEN = os.getenv('API_TOKEN')
raw_id = os.getenv('CHAT_ID', '')
clean_id = "".join(c for c in raw_id if c.isdigit() or c == '-')
CHAT_ID = int(clean_id) if clean_id else None

URL = "https://kolesa.kz/cars/toyota/land-cruiser/year-from-2021/?_sys-hasphoto=2"
HISTORY_FILE = "seen_ads.txt"
MIN_YEAR = 2021

async def check_kolesa():
    if not API_TOKEN or not CHAT_ID:
        print(f"❌ Ошибка: API_TOKEN или CHAT_ID не настроены!")
        return

    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    seen_ads = set()
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            seen_ads = set(line.strip() for line in f if line.strip())

    print(f"🚀 Проверка началась. В базе: {len(seen_ads)}")
    
    async with async_playwright() as p:
        # Запускаем браузер
        browser = await p.chromium.launch(headless=True)
        
        # Добавляем больше параметров маскировки
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        try:
            print(f"🔗 Переход: {URL}")
            
            # 1. Используем 'domcontentloaded' (быстрее) вместо 'networkidle'
            # 2. Добавляем повторную попытку при таймауте
            try:
                await page.goto(URL, wait_until="domcontentloaded", timeout=40000)
            except Exception:
                print("⚠️ Таймаут. Пробую второй раз с увеличенным временем...")
                await asyncio.sleep(5)
                await page.goto(URL, wait_until="load", timeout=60000)

            # Ждем появления именно объявлений
            print("⏳ Ожидание появления карточек...")
            await page.wait_for_selector(".a-card", timeout=15000)
            
            # Прокрутка вниз для активации ленивой загрузки
            await page.mouse.wheel(0, 1000)
            await asyncio.sleep(2)

            ads = await page.query_selector_all(".a-card")
            print(f"📊 Найдено объявлений: {len(ads)}")

            new_ads_count = 0
            for ad in ads:
                ad_id = await ad.get_attribute("data-id")
                if not ad_id or ad_id in seen_ads:
                    continue
                
                card_text = await ad.inner_text()
                year_match = re.search(r'(\d{4})', card_text)
                ad_year = int(year_match.group(1)) if year_match else 0
                
                if ad_year < MIN_YEAR:
                    continue

                title_el = await ad.query_selector(".a-card__link")
                title_text = await title_el.inner_text() if title_el else "Land Cruiser"
                
                price_el = await ad.query_selector(".a-card__price")
                price_text = await price_el.inner_text() if price_el else "---"
                
                href = await title_el.get_attribute("href") if title_el else f"/a/show/{ad_id}"
                full_link = f"https://kolesa.kz{href}"

                print(f"✨ НАШЕЛ: {title_text.strip()} (ID: {ad_id})")
                
                msg = (f"<b>🆕 Новое объявление!</b>\n\n"
                       f"🚗 {title_text.strip()}, {ad_year}г.\n"
                       f"💰 <b>{price_text.strip().replace(' ', ' ')}</b>\n"
                       f"🔗 <a href='{full_link}'>Открыть</a>")
                
                try:
                    await bot.send_message(CHAT_ID, msg)
                    with open(HISTORY_FILE, "a") as f:
                        f.write(f"{ad_id}\n")
                    seen_ads.add(ad_id)
                    new_ads_count += 1
                except Exception as e:
                    print(f"❌ Ошибка TG: {e}")

            print(f"✅ Готово. Новых: {new_ads_count}")

        except Exception as e:
            print(f"⚠️ Ошибка выполнения: {e}")
        finally:
            await browser.close()
            await bot.session.close()

if __name__ == "__main__":
    asyncio.run(check_kolesa())
