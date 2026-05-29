import json
import os
import requests
import random
import re

from datetime import datetime
from json.decoder import JSONDecodeError
from dotenv import load_dotenv
from time import sleep
from urllib.parse import urljoin, urlsplit, urlunsplit
from bs4 import BeautifulSoup

load_dotenv()
TG_API = os.getenv('TG_API')
CHAT_ID = os.getenv('CHAT_ID')

if not TG_API or not CHAT_ID:
    raise RuntimeError("TG_API/CHAT_ID missing in environment")

print(f"[{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}] Scraper started", flush=True)

LISTINGS_FILE = 'listings.json'
CONFIG_FILE = 'config.json'
PRICE_RE = re.compile(r"(?:₪|ש\"ח)\s*[\d,]+|[\d,]+\s*(?:₪|ש\"ח)")

if os.path.isfile(LISTINGS_FILE):
    try:
        with open(LISTINGS_FILE, 'r', encoding='utf-8') as f:
            scraped_data = json.load(f)
            scraped_urls = {item['url'] for item in scraped_data}
    except JSONDecodeError:
        scraped_data = []
        scraped_urls = set()
else:
    scraped_data = []
    scraped_urls = set()

new_listings = []

if os.path.isfile(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except JSONDecodeError:
        raise RuntimeError(f"{CONFIG_FILE} is not valid JSON")
else:
    raise FileNotFoundError(f"{CONFIG_FILE} is missing")

areas = config.get("areas", [])


UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
]

DEFAULT_HEADERS = {
    "User-Agent": f"{random.choice(UA_POOL)}",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Referer": "https://www.yad2.co.il/realestate/rent",
    "DNT": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "no-cache",
}


def clean_text(value):
    if not value:
        return ""

    for c in ['\u200e', '\u200f', '\u202a', '\u202b', '\u202c']:
        value = value.replace(c, '')
    return " ".join(value.split())


def normalize_listing_url(href):
    if not href:
        return ""

    absolute_url = urljoin("https://www.yad2.co.il", href)
    parts = urlsplit(absolute_url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def get_text_or_empty(element):
    if not element:
        return ""
    return clean_text(element.get_text(" ", strip=True))


def find_price_text(card):
    price_el = (
        card.select_one(".feed-item-price_price__ygoeF")
        or card.select_one('[data-testid="price"]')
        or card.select_one('[class*="price"]')
    )
    price = get_text_or_empty(price_el)
    if price:
        return price

    match = PRICE_RE.search(card.get_text(" ", strip=True))
    return clean_text(match.group(0)) if match else ""


def card_text_parts(card):
    ignored = {"המודעה נשמרה", "מודעה נשמרה"}
    parts = []

    for raw_part in card.stripped_strings:
        part = clean_text(raw_part)
        if not part or part in ignored or part in parts:
            continue
        parts.append(part)

    return parts


def fallback_details_from_card(card, price, title, location):
    ignored = {"המודעה נשמרה"}
    parts = []

    for part in card_text_parts(card):
        if (
            part in ignored
            or part == price
            or part == title
            or part == location
            or PRICE_RE.search(part)
        ):
            continue
        if part not in parts:
            parts.append(part)

    return " | ".join(parts[:3])


def find_listing_cards(soup):
    cards = []
    selectors = [
        'li[data-testid="platinum-item"]',
        'li[data-testid="item-basic"]',
        'li[data-testid="agency-item"]',
    ]

    for selector in selectors:
        cards.extend(soup.select(selector))

    seen = {id(card) for card in cards}
    for link in soup.select('a[href*="/realestate/item/"], a[href*="/market/item/"]'):
        card = link.find_parent("li") or link.find_parent("article") or link.parent
        if card and id(card) not in seen:
            cards.append(card)
            seen.add(id(card))

    return cards


def extract_listing(item, zone):
    a = (
        item.select_one('a.item-layout_itemLink__CZZ7w')
        or item.select_one('a[href*="/realestate/item/"]')
        or item.select_one('a[href*="/market/item/"]')
    )
    if not a:
        return None

    listing_url = normalize_listing_url(a.get("href"))
    if "/item/" not in listing_url:
        return None

    img = item.select_one('img[data-testid="image"]') or item.select_one("img")
    img_url = (img.get("src") or img.get("data-src") or img.get("data-original") or "") if img else ""

    location_el = (
        item.select_one("h2 span.item-data-content_heading__tphH4")
        or item.select_one('[data-testid="location"]')
        or item.select_one('[class*="location"]')
        or item.select_one('[class*="city"]')
    )
    title_el = (
        item.select_one('[data-testid="title"]')
        or item.select_one('[class*="title"]')
        or item.select_one("h2")
        or item.select_one("h3")
    )
    info_lines = item.select("h2 span.item-data-content_itemInfoLine__AeoPP")

    price = find_price_text(item)
    location = get_text_or_empty(location_el)
    title = get_text_or_empty(title_el)
    parts = card_text_parts(item)
    non_price_parts = [part for part in parts if not PRICE_RE.search(part)]

    if not title and img:
        title = clean_text(img.get("alt", ""))

    if not title and not location and len(non_price_parts) >= 2:
        location = non_price_parts[0]
        title = non_price_parts[1]
    elif not title:
        title = next((part for part in non_price_parts if part != location), "")
    elif not location:
        location = next((part for part in non_price_parts if part != title), "")

    details = clean_text(info_lines[1].get_text(" ", strip=True) if len(info_lines) > 1 else "")

    if not details:
        details = fallback_details_from_card(item, price, title, location)

    return {
        "zone": zone,
        "url": listing_url,
        "img": img_url,
        "title": title,
        "location": location,
        "address": location or title,
        "price": price,
        "details": details
    }


for area in areas:
    search_url, zone = area["url"], area["zone"]
    try:
        print(f"Scraping {zone}", flush=True)
        sleep(random.uniform(3, 7))

        headers = DEFAULT_HEADERS.copy()
        headers["User-Agent"] = random.choice(UA_POOL)
        headers["Referer"] = "https://www.yad2.co.il/market" if "/market/" in search_url else "https://www.yad2.co.il/realestate/rent"

        response = requests.get(search_url, headers=headers)
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')
        if soup.title and 'shieldsquare' in soup.title.text.lower():
            print(f"Bot detected for {zone}, terminating...", flush=True)
            break

        items = find_listing_cards(soup)

        for item in items:
            try:
                listing = extract_listing(item, zone)
                if not listing or listing["url"] in scraped_urls:
                    continue

                new_listings.append(listing)
                scraped_data.append(listing)
                scraped_urls.add(listing["url"])

            except Exception as e:
                print(f"Error extracting listing: {e}", flush=True)

    except Exception as e:
        print(f"Error scraping {zone}: {e}", flush=True)


with open(LISTINGS_FILE, 'w', encoding='utf-8') as f:
    json.dump(scraped_data, f, indent=2, ensure_ascii=False)

print(f"Scraping complete. {len(new_listings)} new listings found.", flush=True)

if new_listings:
    for listing in new_listings:
        title = listing.get("title") or listing.get("address", "")
        location = listing.get("location") or listing.get("address", "")
        msg = f"""
📢 <b>New Listing in {listing['zone']}</b> 📢
<b>Title:</b> {title}
<b>Location:</b> {location}
<b>Price:</b> {listing['price']}
<b>Details:</b> {listing['details']}
<a href="{listing['url']}">View Listing</a>
"""
        img = listing['img']

        try:
            if img and img.endswith(".svg"):
                raise ValueError("Placeholder image detected")

            photo_data = requests.get(img, timeout=5).content

            response = requests.post(
                f"https://api.telegram.org/bot{TG_API}/sendPhoto",
                data={
                    "chat_id": CHAT_ID,
                    "caption": msg,
                    "parse_mode": "HTML"
                },
                files={
                    "photo": photo_data
                }
            )

            if not response.ok:
                raise Exception(f"Telegram photo post failed: {response.status_code}")

        except Exception as e:  # fall back text only
            print(f"Falling back to text for: {listing['address']} ({e})", flush=True)
            requests.post(
                f"https://api.telegram.org/bot{TG_API}/sendMessage",
                data={
                    "chat_id": CHAT_ID,
                    "text": msg,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False
                }
            )

        sleep(1.5)

    print("New listings sent to Telegram, program terminated.", flush=True)
