import asyncio
import os
import re
from playwright.async_api import async_playwright
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- НАСТРОЙКИ ---
API_TOKEN = os.getenv('API_TOKEN')
raw_id = os.getenv('CHAT_ID')
CHAT_ID = int(raw_id) if raw_id else None

URL = "https://kolesa.kz/cars/toyota/land-cruiser/year-from-2021/?_sys-hasphoto=2"
HISTORY_FILE = "seen_ads.txt"
MIN_YEAR = 2021

async def check_kolesa():
    if not API_TOKEN or not CHAT_ID:
        print("❌ Ошибка: API_TOKEN или CHAT_ID не найдены!")
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
        # Маскируемся под обычного пользователя на Windows
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        try:
            print(f"🔗 Перехожу на: {URL}")
            # Пытаемся загрузиться и ждем немного дольше
            await page.goto(URL, wait_until="load", timeout=60000)
            await asyncio.sleep(5) # Даем JS подгрузить карточки

            # Проверяем, есть ли карточки вообще
            ads = await page.query_selector_all(".a-card")
            print(f"📊 Всего карточек .a-card найдено: {len(ads)}")

            if len(ads) == 0:
                print("⚠️ Сайт выдал пустую страницу. Пробую проверить альтернативный селектор...")
                # На всякий случай проверяем другой селектор, если дизайн сменился
                ads = await page.query_selector_all("[data-id]")
                print(f"📊 Попытка №2 (data-id): {len(ads)}")

            new_ads_count = 0
            for ad in ads:
                ad_id = await ad.get_attribute("data-id")
                if not ad_id or ad_id in seen_ads:
                    continue
                
                title_el = await ad.query_selector(".a-card__title, .title")
                title_text = await title_el.inner_text() if title_el else "Без названия"
                
                # Ищем год
                year_match = re.search(r'(\d{4})', title_text)
                if year_match:
                    ad_year = int(year_match.group(1))
                    if ad_year < MIN_YEAR:
                        continue
                else:
                    continue

                print(f"✨ НАШЕЛ: {title_text.strip()} (ID: {ad_id})")
                
                price_el = await ad.query_selector(".a-card__price, .price")
                price = await price_el.inner_text() if price_el else "Цена не указана"
                link = f"https://kolesa.kz/a/show/{ad_id}"
                
                msg = f"<b>🆕 Новое объявление!</b>\n\n🚗 {title_text.strip()}\n💰 <b>{price.strip()}</b>\n🔗 <a href='{link}'>Открыть</a>"
                
                try:
                    await bot.send_message(CHAT_ID, msg)
                    with open(HISTORY_FILE, "a") as f:
                        f.write(f"{ad_id}\n")
                    seen_ads.add(ad_id)
                    new_ads_count += 1
                except Exception as e:
                    print(f"❌ Ошибка TG: {e}")

            print(f"✅ Готово. Найдено новых: {new_ads_count}")

        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
        finally:
            await browser.close()
            await bot.session.close()

if __name__ == "__main__":
    asyncio.run(check_kolesa())