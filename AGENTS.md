# Repository Guidelines

## Project Structure & Module Organization

This repository contains a scheduled Python scraper for Yad2 rental listings.

- `scraper.py` is the main executable. It loads configuration, scrapes listing pages, updates state, and sends new listings to Telegram.
- `config.json` defines target search areas. Each area needs a `zone` label and a Yad2 `url`.
- `listings.json` is persisted scraper state and stores listings that were already seen.
- `requirements.txt` pins Python dependencies.
- `.github/workflows/scrape.yml` runs the scraper on a schedule and commits updated `listings.json`.

Keep new logic close to `scraper.py` unless the script grows enough to justify splitting helpers into modules.

## Build, Test, and Development Commands

Use Python 3.11, matching the GitHub Actions workflow.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scraper.py
```

`python scraper.py` requires `TG_API` and `CHAT_ID` in the environment or a local `.env` file. The script writes `listings.json`, so inspect that diff before committing.

## Coding Style & Naming Conventions

Use standard Python style with 4-space indentation, clear snake_case names, and constants in uppercase, as in `LISTINGS_FILE` and `CONFIG_FILE`. Prefer explicit error messages for missing configuration or malformed JSON. Keep JSON files formatted with 2-space indentation and preserve UTF-8 output with `ensure_ascii=False` when writing Hebrew or other non-ASCII text.

## Testing Guidelines

There is no formal test suite yet. Before submitting changes, run `python scraper.py` with valid Telegram credentials or test against a disposable chat. For parser changes, verify that new listings include `zone`, `url`, `img`, `address`, `price`, and `details`, and that duplicate URLs are not re-added to `listings.json`.

If tests are added, place them under `tests/`, use `pytest`, and name files `test_*.py`. Mock network calls to Yad2 and Telegram rather than depending on live services.

## Commit & Pull Request Guidelines

Current history uses automation-style commits such as `chore: update listings Mon Aug 18 17:49:11 UTC 2025`. For manual changes, use concise conventional prefixes, for example `fix: handle missing listing image` or `chore: update dependencies`.

Pull requests should describe the behavior change, list any config or secret changes, and include before/after notes for scraper output when relevant. Include screenshots or Telegram message examples only when notification formatting changes.

## Security & Configuration Tips

Do not commit `.env` files or Telegram credentials. Store `TG_API` and `CHAT_ID` as GitHub Actions secrets for scheduled runs. Treat `listings.json` as state: avoid deleting it unless intentionally re-notifying all known listings.
