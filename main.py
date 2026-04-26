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

# Умная очистка ID: оставляем только цифры и знак минуса
clean_id = "".join(c for c in raw_id if c.isdigit() or c == '-')
CHAT_ID = int(clean_id) if clean_id else None

URL = "https://kolesa.kz/cars/toyota/land-cruiser/year-from-2021/?_sys-hasphoto=2"
HISTORY_FILE = "seen_ads.txt"
MIN_YEAR = 2021  # Поставь 2010, если хочешь протестировать прямо сейчас

async def check_kolesa():
    if not API_TOKEN or not CHAT_ID:
        print(f"❌ Ошибка: API_TOKEN или CHAT_ID не настроены правильно! (ID: {raw_id})")
        return

    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    # Загружаем историю
    seen_ads = set()
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            seen_ads = set(line.strip() for line in f if line.strip())

    print(f"🚀 Запуск проверки. В базе объявлений: {len(seen_ads)}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            print(f"🔗 Перехожу на: {URL}")
            await page.goto(URL, wait_until="networkidle", timeout=60000)
            
            # Ждем появления карточек
            await page.wait_for_selector(".a-card", timeout=10000)
            ads = await page.query_selector_all(".a-card")
            print(f"📊 Найдено карточек на странице: {len(ads)}")

            new_ads_count = 0
            for ad in ads:
                ad_id = await ad.get_attribute("data-id")
                if not ad_id or ad_id in seen_ads:
                    continue
                
                # Получаем весь текст карточки для надежного поиска года
                card_text = await ad.inner_text()
                
                # Ищем год (первое четырехзначное число)
                year_match = re.search(r'(\d{4})', card_text)
                ad_year = int(year_match.group(1)) if year_match else 0
                
                if ad_year < MIN_YEAR:
                    continue

                # Извлекаем заголовок и цену
                title_el = await ad.query_selector(".a-card__link")
                title_text = await title_el.inner_text() if title_el else "Toyota Land Cruiser"
                
                price_el = await ad.query_selector(".a-card__price")
                price_text = await price_el.inner_text() if price_el else "Цена не указана"
                
                # Формируем ссылку
                href = await title_el.get_attribute("href") if title_el else f"/a/show/{ad_id}"
                full_link = f"https://kolesa.kz{href}"

                print(f"✨ НАШЕЛ: {title_text.strip()} {ad_year}г. (ID: {ad_id})")
                
                msg = (f"<b>🆕 Новое объявление!</b>\n\n"
                       f"🚗 {title_text.strip()}, {ad_year}г.\n"
                       f"💰 <b>{price_text.strip().replace(' ', ' ')}</b>\n"
                       f"🔗 <a href='{full_link}'>Открыть на Kolesa.kz</a>")
                
                try:
                    await bot.send_message(CHAT_ID, msg)
                    # Сразу записываем в историю
                    with open(HISTORY_FILE, "a") as f:
                        f.write(f"{ad_id}\n")
                    seen_ads.add(ad_id)
                    new_ads_count += 1
                    await asyncio.sleep(1)  # Пауза, чтобы TG не забанил
                except Exception as e:
                    print(f"❌ Ошибка отправки в Telegram: {e}")

            print(f"✅ Готово. Найдено новых: {new_ads_count}")

        except Exception as e:
            print(f"⚠️ Произошла ошибка во время работы: {e}")
        finally:
            await browser.close()
            await bot.session.close()

if __name__ == "__main__":
    asyncio.run(check_kolesa())