# Repository Guidelines

## Project Structure & Module Organization

This repository contains a scheduled Python scraper for Yad2 car listings, with support for other Yad2 searches. The current configuration includes a BYD car search and a coffee-machine search.

- `scraper.py` is the main executable. It loads configuration, parses listing cards, fetches mileage from new vehicle listing detail pages, updates state, and sends new listings to Telegram.
- `config.json` defines searches in the `areas` array. Each entry needs a `zone` label and a Yad2 `url`. Preserve these key names; `zone` labels a search rather than necessarily a geographic area. Car searches use `/vehicles/cars` URLs with manufacturer, model, year, price, and mileage filters.
- `listings.json` is persisted scraper state and stores listings that were already seen.
- `requirements.txt` pins Python dependencies.
- `.github/workflows/scrape.yml` schedules checks every 15 minutes, runs scheduled scraping from 08:00 to 00:00 Israel time, and commits updated `listings.json`. Manual workflow runs bypass the time window.
- `scripts/run_scraper.ps1` runs local checks in the same Israel time window and logs to `logs/scraper.log`.
- `scripts/register_windows_task.ps1` registers checks every 15 minutes. Its current task name is `Yad2 Coffee Machines Scraper`, but it runs all configured searches.

Keep new logic close to `scraper.py` unless the script grows enough to justify splitting helpers into modules.

## Build, Test, and Development Commands

Use Python 3.11, matching the GitHub Actions workflow.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scraper.py
```

Run commands from the repository root. `python scraper.py` requires `TG_API` and `CHAT_ID` in the environment or a local `.env` file. A live run writes `listings.json` and sends Telegram notifications, so inspect the state diff before committing.

## Coding Style & Naming Conventions

Use standard Python style with 4-space indentation, clear snake_case names, and constants in uppercase, as in `LISTINGS_FILE` and `CONFIG_FILE`. Prefer explicit error messages for missing configuration or malformed JSON. Keep JSON files formatted with 2-space indentation and preserve UTF-8 output with `ensure_ascii=False` when writing Hebrew or other non-ASCII text.

## Testing Guidelines

There is no formal test suite yet. For scraper behavior changes, validate with mocked network calls or run `python scraper.py` against a disposable Telegram chat. Documentation-only changes do not require a live scrape.

For parser changes, verify that new listings include `zone`, `url`, `img`, `title`, `location`, `address`, `price`, and `details`. For cars, check model/trim extraction, year and ownership-hand details, seller information when present, and the additional `km` field fetched from the detail page. Mileage is text and must remain an empty string when unavailable or retrieval fails. `location` may hold the seller; `address` is retained for compatibility and falls back to the title.

Check both `/item/` card links and `/vehicles/item/` links, and preserve conversion to the vehicle detail URL for mileage retrieval. Verify that query strings and fragments are removed from saved URLs and that duplicate URLs are not re-added to `listings.json`, including across overlapping searches. Cover missing images, text-only Telegram fallback, and the existing non-vehicle search when changing shared parser logic.

If tests are added, place them under `tests/`, use `pytest`, and name files `test_*.py`. Mock network calls to Yad2 and Telegram rather than depending on live services.

## Commit & Pull Request Guidelines

Current history uses automation-style commits such as `chore: update listings Mon Aug 18 17:49:11 UTC 2025`. For manual changes, use concise conventional prefixes, for example `fix: handle missing listing image` or `chore: update dependencies`.

Pull requests should describe the behavior change, list any config or secret changes, and include before/after notes for scraper output when relevant. Include screenshots or Telegram message examples only when notification formatting changes.

## Security & Configuration Tips

Do not commit `.env` files or Telegram credentials. Store `TG_API` and `CHAT_ID` as GitHub Actions secrets for scheduled runs. Treat `listings.json` as state: preserve it when changing car filters or adding searches, and avoid deleting or resetting it unless intentionally re-notifying all matching listings. State is saved before Telegram delivery, so failed notifications are not automatically retried on subsequent runs.
