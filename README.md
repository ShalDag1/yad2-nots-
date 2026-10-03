# Yad2 Car Search Scraper

This repository runs a Python scraper for Yad2 car searches and sends newly found listings to Telegram, including price and mileage when available. It supports multiple searches; `config.json` currently includes a BYD car search and a coffee-machine search. Periodic checks run through GitHub Actions or Windows Task Scheduler, with `listings.json` used as local state to avoid duplicate notifications.

## Configure Car Searches

Search targets are defined in `config.json`. Add or edit entries in the `areas` array to change the cars you monitor. The existing `areas` and `zone` keys are retained for compatibility; `zone` is a search label, not necessarily a geographic area:

```json
{
  "areas": [
    {
      "zone": "byd",
      "url": "https://www.yad2.co.il/vehicles/cars?manufacturer=141&model=13050&year=2024-2024&price=-1-150000&km=-1-50000"
    }
  ]
}
```

Use a clear `zone` name because it appears in Telegram messages. Copy the `url` from Yad2 after applying the desired manufacturer, model, year, price, and mileage filters. The configured car search selects manufacturer ID `141`, model ID `13050`, year `2024`, a maximum price of ₪150,000, and maximum mileage of 50,000 km.

## Listing Data and Notifications

Each saved listing includes `zone`, `url`, `img`, `title`, `location`, `address`, `price`, and `details`. For car cards, `title` combines the model and trim, `location` contains the seller when available, and `details` contains the year, ownership hand, and seller information when available. `address` is a compatibility field populated from `location` or `title`.

For vehicle searches, the scraper also fetches each new listing's detail page to populate `km`. Mileage is stored as text and may be empty if unavailable or the detail request fails. Listing URLs are saved without query strings or fragments to avoid duplicates from tracking parameters.

Telegram messages include the search label, title, location/seller, price, KM, details, and listing link. The scraper sends a photo when available and falls back to a text message if the image is missing or sending the photo fails.

## Preserve Existing Results

`listings.json` stores listings that were already seen. Keep it when changing searches so previously seen URLs are not notified again. Resetting it to `[]` intentionally makes all currently matching listings eligible for notification again. The scraper saves state before sending notifications, so a failed notification does not automatically retry on the next run.

## Local Setup

Use Python 3.11, matching the GitHub Actions workflow.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a local `.env` file in the repository root with your Telegram values, or set them as environment variables:

```env
TG_API=your_telegram_bot_token
CHAT_ID=your_chat_id
```

Run the scraper:

```powershell
python scraper.py
```

Run from the repository root so the scraper finds `config.json` and `listings.json`. A live run writes state and sends notifications; inspect the `listings.json` diff before committing. Do not commit `.env` or Telegram credentials.

## GitHub Actions

The workflow in `.github/workflows/scrape.yml` is scheduled every 15 minutes. Scheduled scraper runs are restricted to 08:00–00:00 Israel time (`Asia/Jerusalem`). Manual runs with `workflow_dispatch` bypass this time window. In GitHub, configure these repository secrets before running it:

- `TG_API`
- `CHAT_ID`

After each run, the workflow commits changes to `listings.json` when new listings are recorded.

## Windows Task Scheduler

To register local checks every 15 minutes:

```powershell
.\scripts\register_windows_task.ps1
```

The task currently uses the name `Yad2 Coffee Machines Scraper`, but runs every search in `config.json`, including cars. `scripts/run_scraper.ps1` uses the local virtual environment when available, skips runs outside 08:00–00:00 Israel time, and writes logs to `logs/scraper.log`.
