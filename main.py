import requests
import os
import time
import json
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup


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

def fetch_olx_listings():
    results = []

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    for url in URLS_TO_SCRAPE:
        print(f"🌍 Scraping: {url}")
        try:
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")

            listings = soup.select("div[data-cy='l-card']")

            for card in listings:
                try:
                    title_elem = card.select_one("h6")
                    title = title_elem.text.strip() if title_elem else "N/A"

                    price_elem = card.select_one("p[data-testid='ad-price']")
                    price = price_elem.text.strip() if price_elem else "N/A"

                    price_per_m2 = "N/A"
                    for tag in card.find_all(["p", "span"]):
                        if "zł/m²" in tag.text:
                            price_per_m2 = tag.text.strip()
                            break

                    loc_date_elem = card.select_one("p[data-testid='location-date']")
                    location, date_posted = "N/A", "N/A"
                    if loc_date_elem and " - " in loc_date_elem.text:
                        parts = loc_date_elem.text.split(" - ")
                        location = parts[0].strip()
                        date_posted = parts[1].strip()

                    a_tag = card.find("a", href=True)
                    link = "https://www.olx.pl" + a_tag["href"] if a_tag else "#"

                    sort_date = parse_date_posted(date_posted)

                    results.append({
                        "title": title,
                        "price": price,
                        "price_per_m2": price_per_m2,
                        "location": location,
                        "date_posted": date_posted,
                        "link": link,
                        "sort_date": sort_date
                    })
                except Exception as e:
                    print("⚠️ Error parsing listing:", e)

        except Exception as e:
            print(f"❌ Request failed: {e}")

    results.sort(key=lambda x: x["sort_date"], reverse=True)
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    return [item for item in results if item["sort_date"].date() in {today, yesterday}]


# ▶️ Run Once
if __name__ == "__main__":
    print("🚀 Running OLX Telegram notifier...")

    listings = fetch_olx_listings()
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
