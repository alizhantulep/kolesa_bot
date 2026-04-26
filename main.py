import asyncio
import os
import re
from playwright.async_api import async_playwright
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- НАСТРОЙКИ (Берутся из Secrets GitHub) ---
API_TOKEN = os.getenv('API_TOKEN')
# Превращаем CHAT_ID в число, так как в секретах он лежит строкой
raw_chat_id = os.getenv('CHAT_ID')
CHAT_ID = int(raw_chat_id) if raw_chat_id else None

URL = "https://kolesa.kz/cars/toyota/land-cruiser/year-from-2021/?_sys-hasphoto=2"
HISTORY_FILE = "seen_ads.txt"
MIN_YEAR = 2021

async def check_kolesa():
    # Проверка наличия секретов
    if not API_TOKEN or not CHAT_ID:
        print("❌ Ошибка: API_TOKEN или CHAT_ID не найдены в Secrets!")
        return

    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    # Загрузка истории
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            seen_ads = set(line.strip() for line in f)
    else:
        seen_ads = set()

    print(f"🚀 Запуск проверки. В базе: {len(seen_ads)}")
    
    async with async_playwright() as p:
        # Запуск браузера
        browser = await p.chromium.launch(headless=True)
        # Эмуляция реального браузера на macOS
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        try:
            print(f"🔗 Перехожу на: {URL}")
            # Ожидаем networkidle, чтобы данные успели подгрузиться
            await page.goto(URL, wait_until="networkidle", timeout=60000)
            
            # Ждем появления карточек (увеличили таймаут на случай медленной загрузки)
            await page.wait_for_selector(".a-card", timeout=20000)
            
            ads = await page.query_selector_all(".a-card")
            
            # ГЛАВНАЯ ПРОВЕРКА: Если здесь будет 0, значит сайт нас блокирует
            print(f"📊 Всего карточек на странице: {len(ads)}")
            
            new_ads_count = 0
            for ad in ads:
                ad_id = await ad.get_attribute("data-id")
                if not ad_id:
                    continue

                if ad_id in seen_ads:
                    continue
                
                title_el = await ad.query_selector(".a-card__title")
                title_text = await title_el.inner_text() if title_el else "Без названия"
                
                # Проверка года через регулярное выражение
                year_match = re.search(r'(\d{4})', title_text)
                if year_match:
                    ad_year = int(year_match.group(1))
                    if ad_year < MIN_YEAR:
                        print(f"   ⚠️ Пропуск {ad_id}: год {ad_year} слишком старый")
                        continue
                else:
                    print(f"   ⚠️ Пропуск {ad_id}: год не найден в названии '{title_text}'")
                    continue

                # Если дошли сюда — значит машина новая и подходит!
                print(f"✨ НАШЕЛ: {title_text.strip()} (ID: {ad_id})")
                
                price_el = await ad.query_selector(".a-card__price")
                price = await price_el.inner_text() if price_el else "Цена не указана"
                link = f"https://kolesa.kz/a/show/{ad_id}"
                
                msg = f"<b>🆕 Новое объявление!</b>\n\n🚗 {title_text.strip()}\n💰 <b>{price.strip()}</b>\n🔗 <a href='{link}'>Открыть</a>"
                
                # Пробуем отправить сообщение
                try:
                    await bot.send_message(CHAT_ID, msg)
                    with open(HISTORY_FILE, "a") as f:
                        f.write(f"{ad_id}\n")
                    seen_ads.add(ad_id)
                    new_ads_count += 1
                except Exception as e:
                    print(f"   ❌ Не удалось отправить в Telegram (ID {ad_id}): {e}")

            print(f"✅ Проверка окончена. Отправлено новых: {new_ads_count}")

        except Exception as e:
            print(f"⚠️ Ошибка во время выполнения: {e}")
        finally:
            await browser.close()
            await bot.session.close()

if __name__ == "__main__":
    asyncio.run(check_kolesa())