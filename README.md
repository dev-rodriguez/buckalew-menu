# Buckalew Menu Widget

This project scrapes the Buckalew Elementary MealViewer lunch menu and generates:

- machine-readable output (`JSON` and `CSV`)
- a polished widget page (`HTML`) for DAKboard custom URL widgets

## What it generates

Each run of `menu.py` creates:

- `menu_output.json` (latest)
- `menu_output_YYYY-MM-DD.json` (dated snapshot)
- `menu_output.csv` (latest)
- `menu_output_YYYY-MM-DD.csv` (dated snapshot)
- `menu_widget.html` (latest widget)
- `menu_widget_YYYY-MM-DD.html` (dated widget snapshot)

## Requirements

- Python 3.10+
- Google Chrome installed
- ChromeDriver available to Selenium (Selenium Manager handles this automatically in most setups)

Install dependencies:

```bash
pip install -r requirements.txt
```

## Quick start

### 1) Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Run scraper + widget generator

```bash
python menu.py
```

## DAKboard usage

Use `menu_widget.html` as your widget source.

Typical workflow:

1. Host `menu_widget.html` somewhere accessible by DAKboard (public URL or local dashboard-accessible endpoint).
2. In DAKboard, add a **Custom** widget.
3. Set the URL to your hosted `menu_widget.html`.
4. Re-run `menu.py` on a schedule (daily) so the widget stays fresh.

## Notes about images

- Image URLs come from MealViewer hover/detail requests.
- Some menu items may not provide an image from the source system; these appear as `No image` in HTML.

## Files in this repo

- `menu.py` — scraper + export + widget generation
- `requirements.txt` — Python dependencies
- `.gitignore` — ignores venv, caches, and generated output files

## Troubleshooting

- If scraping returns no items, re-run once (MealViewer can be dynamic and timing-sensitive).
- If ChromeDriver issues appear, update Chrome and run again.
- Ensure your environment is active before running:

```bash
source venv/bin/activate
```
