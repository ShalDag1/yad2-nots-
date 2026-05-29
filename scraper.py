import json
import os
import requests
import random
import re
import sys

from datetime import datetime
from json.decoder import JSONDecodeError
from dotenv import load_dotenv
from time import sleep
from urllib.parse import urljoin, urlsplit, urlunsplit
from bs4 import BeautifulSoup

load_dotenv()
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TG_API = os.getenv('TG_API')
CHAT_ID = os.getenv('CHAT_ID')

if not TG_API or not CHAT_ID:
    raise RuntimeError("TG_API/CHAT_ID missing in environment")

print(f"[{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}] Scraper started", flush=True)

LISTINGS_FILE = 'listings.json'
CONFIG_FILE = 'config.json'
PRICE_RE = re.compile(r"(?:₪|ש\"ח)\s*[\d,]+|[\d,]+\s*(?:₪|ש\"ח)")
VEHICLE_YEAR_RE = re.compile(r"\b20\d{2}\b")
ITEM_LINK_SELECTOR = (
    'a[href*="/realestate/item/"], '
    'a[href*="/market/item/"], '
    'a[href*="/vehicles/item/"], '
    'a[href^="/item/"], '
    'a[href^="item/"]'
)
VEHICLE_BADGES = {"גם בטרייד אין", "ירד ב"}

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


def vehicle_detail_url(listing_url):
    return listing_url.replace("https://www.yad2.co.il/item/", "https://www.yad2.co.il/vehicles/item/")


def is_listing_link(tag):
    href = tag.get("href", "") if tag else ""
    return (
        "/realestate/item/" in href
        or "/market/item/" in href
        or "/vehicles/item/" in href
        or href.startswith("/item/")
        or href.startswith("item/")
    )


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


def extract_vehicle_text(parts, price):
    non_price_parts = [part for part in parts if not PRICE_RE.search(part)]
    useful_parts = [part for part in non_price_parts if part not in VEHICLE_BADGES]

    has_seller = not (len(useful_parts) > 2 and VEHICLE_YEAR_RE.search(useful_parts[2]))
    offset = 1 if has_seller else 0

    seller = useful_parts[0] if has_seller and useful_parts else ""
    model = useful_parts[offset] if len(useful_parts) > offset else ""
    trim = useful_parts[offset + 1] if len(useful_parts) > offset + 1 else ""
    year_hand = useful_parts[offset + 2] if len(useful_parts) > offset + 2 else ""

    title = clean_text(f"{model} {trim}") or seller
    details = " | ".join(part for part in [year_hand, seller] if part)
    if not details:
        details = fallback_details_from_card_from_parts(parts, price, title, seller)

    return title, seller, details


def fallback_details_from_card_from_parts(parts, price, title, location):
    details = []
    for part in parts:
        if (
            part in {price, title, location}
            or part in VEHICLE_BADGES
            or PRICE_RE.search(part)
        ):
            continue
        if part not in details:
            details.append(part)
    return " | ".join(details[:3])


def extract_vehicle_km(listing_url, headers):
    detail_headers = headers.copy()
    detail_headers["Referer"] = "https://www.yad2.co.il/vehicles/cars"

    response = requests.get(vehicle_detail_url(listing_url), headers=detail_headers, timeout=20)
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    parts = card_text_parts(soup)
    for index, part in enumerate(parts):
        if "קילומטראז" in part and index + 1 < len(parts):
            value = parts[index + 1]
            if re.fullmatch(r"[\d,]+", value):
                return value

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    match = re.search(r"([\d,]+)\s*ק״מ", title)
    return match.group(1) if match else ""


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
    for link in soup.select(ITEM_LINK_SELECTOR):
        card = link if is_listing_link(link) and link.get("href", "").lstrip("/").startswith("item/") else link.find_parent("li") or link.find_parent("article") or link.parent
        if card and id(card) not in seen:
            cards.append(card)
            seen.add(id(card))

    return cards


def extract_listing(item, zone):
    a = item if item.name == "a" and is_listing_link(item) else (
        item.select_one('a.item-layout_itemLink__CZZ7w')
        or item.select_one(ITEM_LINK_SELECTOR)
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

    is_vehicle_listing = a.get("href", "").lstrip("/").startswith("item/")

    if is_vehicle_listing:
        title, location, details = extract_vehicle_text(parts, price)
    elif not title and img:
        title = clean_text(img.get("alt", ""))

    if not is_vehicle_listing and not title and not location and len(non_price_parts) >= 2:
        location = non_price_parts[0]
        title = non_price_parts[1]
    elif not is_vehicle_listing and not title:
        title = next((part for part in non_price_parts if part != location), "")
    elif not is_vehicle_listing and not location:
        location = next((part for part in non_price_parts if part != title), "")

    if not is_vehicle_listing:
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
        if "/market/" in search_url:
            headers["Referer"] = "https://www.yad2.co.il/market"
        elif "/vehicles/" in search_url:
            headers["Referer"] = "https://www.yad2.co.il/vehicles/cars"
        else:
            headers["Referer"] = "https://www.yad2.co.il/realestate/rent"

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
                if "/vehicles/" in search_url:
                    try:
                        listing["km"] = extract_vehicle_km(listing["url"], headers)
                    except Exception as e:
                        listing["km"] = ""
                        print(f"Error extracting vehicle km for {listing['url']}: {e}", flush=True)

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
<b>KM:</b> {listing.get('km', '')}
<b>Details:</b> {listing['details']}
<a href="{listing['url']}">View Listing</a>
"""
        img = listing['img']

        try:
            if not img or img.endswith(".svg"):
                raise ValueError("No usable image")

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
            print(f"Falling back to text for: {listing['url']} ({e})", flush=True)
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
