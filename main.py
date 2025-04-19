import asyncio
import re
import time
import json
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
import requests

print("BOT_TOKEN:", BOT_TOKEN)
print("CHAT_ID:", CHAT_ID)

# === Load Secrets from Environment Variables (Railway or local)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    print("❌ Missing BOT_TOKEN or CHAT_ID in environment.")
    exit(1)

# === OLX Search URLs ===
URLS_TO_SCRAPE = [
    "https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/warszawa/?search%5Bfilter_float_price%3Ato%5D=450000&search%5Bfilter_float_price_per_m%3Ato%5D=13000&search[order]=created_at:desc",
    "https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/poznan/?search%5Bfilter_float_price%3Ato%5D=400000&search%5Bfilter_float_price_per_m%3Ato%5D=10000&search[order]=created_at:desc",
    "https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/krakow/?search%5Bfilter_float_price%3Ato%5D=400000&search%5Bfilter_float_price_per_m%3Ato%5D=12000&search[order]=created_at:desc",
    "https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/wroclaw/?search%5Bfilter_float_price%3Ato%5D=400000&search%5Bfilter_float_price_per_m%3Ato%5D=11000&search[order]=created_at:desc"
]

# === Sent Links File ===
SENT_LINKS_FILE = "sent_links.json"

def load_sent_links():
    if os.path.exists(SENT_LINKS_FILE):
        with open(SENT_LINKS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_sent_links(links_set):
    with open(SENT_LINKS_FILE, "w") as f:
        json.dump(list(links_set), f)

def send_to_telegram(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    response = requests.post(url, data=payload)
    print("📬 Telegram response:", response.status_code, response.json())
    return response.ok

def parse_date_posted(text):
    text = text.lower()
    now = datetime.now()
    if "dzisiaj" in text:
        return now
    elif "wczoraj" in text:
        return now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    else:
        try:
            months = {
                "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4,
                "maja": 5, "czerwca": 6, "lipca": 7, "sierpnia": 8,
                "września": 9, "października": 10, "listopada": 11, "grudnia": 12
            }
            parts = text.split()
            if len(parts) >= 2:
                day = int(parts[0])
                month = months.get(parts[1], 1)
                return datetime(now.year, month, day)
        except:
            pass
    return datetime.min

async def fetch_olx_listings():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for url in URLS_TO_SCRAPE:
            print(f"🌍 Scraping: {url}")
            await page.goto(url)
            await page.wait_for_selector("div[data-cy='l-card']")
            listings = await page.query_selector_all("div[data-cy='l-card']")

            for listing in listings:
                title = "N/A"
                title_elem = await listing.query_selector("h6")
                if not title_elem:
                    title_elem = await listing.query_selector("img[alt]")
                    if title_elem:
                        title = await title_elem.get_attribute("alt")
                else:
                    try:
                        title = await title_elem.inner_text()
                    except:
                        pass

                price = "N/A"
                price_elem = await listing.query_selector("p[data-testid='ad-price']")
                if price_elem:
                    try:
                        price = await price_elem.inner_text()
                    except:
                        pass

                price_per_m2 = "N/A"
                for tag in await listing.query_selector_all("p, span"):
                    try:
                        txt = await tag.inner_text()
                        if "zł/m²" in txt:
                            price_per_m2 = txt.strip()
                            break
                    except:
                        continue

                location = "N/A"
                date_posted = "N/A"
                loc_date_elem = await listing.query_selector("p[data-testid='location-date']")
                if loc_date_elem:
                    try:
                        loc_date_text = await loc_date_elem.inner_text()
                        if " - " in loc_date_text:
                            parts = loc_date_text.split(" - ")
                            location = parts[0].strip()
                            date_posted = parts[1].strip()
                    except:
                        pass

                link = "#"
                link_elem = await listing.query_selector("a[href]")
                if link_elem:
                    raw_link = await link_elem.get_attribute("href")
                    link = f"https://www.olx.pl{raw_link}" if raw_link.startswith("/") else raw_link

                sort_date = parse_date_posted(date_posted)

                results.append({
                    "title": title.strip(),
                    "price": price.strip(),
                    "price_per_m2": price_per_m2,
                    "location": location,
                    "date_posted": date_posted,
                    "link": link,
                    "sort_date": sort_date
                })

        await browser.close()

        results.sort(key=lambda x: x["sort_date"], reverse=True)
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        return [item for item in results if item["sort_date"].date() in {today, yesterday}]


# ▶️ Run Once (Perfect for Railway or Manual Test)
if __name__ == "__main__":
    print("🚀 Running OLX Telegram notifier...")

    listings = asyncio.run(fetch_olx_listings())
    print(f"\n✅ Total listings found: {len(listings)}")

    sent_links = load_sent_links()
    new_listings = [l for l in listings if l["link"] not in sent_links]

    if new_listings:
        for listing in new_listings:
            print(f"🏠 {listing['title']}")
            print(f"💰 {listing['price']}")
            print(f"📐 {listing['price_per_m2']}")
            print(f"📍 {listing['location']} — 🗓 {listing['date_posted']}")
            print(f"🔗 {listing['link']}")
            print("-" * 40)

            message = f"""
<b>{listing['title']}</b>
💰 <b>{listing['price']}</b>
📐 {listing['price_per_m2']}
📍 {listing['location']} — 🗓 {listing['date_posted']}
🔗 <a href="{listing['link']}">Zobacz ogłoszenie</a>
"""
            send_to_telegram(BOT_TOKEN, CHAT_ID, message.strip())
            sent_links.add(listing["link"])
        save_sent_links(sent_links)
    else:
        print("⚠️ No new listings found.")
        send_to_telegram(BOT_TOKEN, CHAT_ID, "👀 Nothing new found for now.")
