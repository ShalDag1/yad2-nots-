# Yad2 Rental Scraper

This repository runs a Python scraper for Yad2 rental searches and sends newly found listings to Telegram. It is designed for periodic checks through GitHub Actions, with `listings.json` used as local state to avoid duplicate notifications.

## Configure Search Zones

Search targets are defined in `config.json`. To search different neighborhoods or cities, replace the existing entries in the `areas` array:

```json
{
  "areas": [
    {
      "zone": "Example Zone",
      "url": "https://www.yad2.co.il/realestate/rent?...your-search-query..."
    }
  ]
}
```

Use a clear `zone` name because it appears in Telegram messages. The `url` should be copied from Yad2 after applying the desired filters, such as city, neighborhood, price, rooms, and property type.

## Reset Existing Results

`listings.json` stores listings that were already seen. When switching to new zones, reset it to:

```json
[]
```

This repository has already been reset, so the next run will treat all listings from the configured zones as new.

## Local Setup

Use Python 3.11, matching the GitHub Actions workflow.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a local `.env` file or export environment variables:

```env
TG_API=your_telegram_bot_token
CHAT_ID=your_chat_id
```

Run the scraper:

```powershell
python scraper.py
```

## GitHub Actions

The workflow in `.github/workflows/scrape.yml` runs on a schedule and can also be started manually with `workflow_dispatch`. In GitHub, configure these repository secrets before running it:

- `TG_API`
- `CHAT_ID`

After each run, the workflow commits changes to `listings.json` when new listings are recorded.
