# Jewelry Quote App 2.0 (Clean Quote Calculator)

This is a Streamlit app for creating professional customer quotes with **multiple metal options**, **image attachments**, **version history**, and **JSON-first storage**.

## What it does

- Customer name, job description, item type (ring/earrings/necklace/pendant/bracelet/other), notes
- Ring-only fields (finger size, width, center shape)
- CAD/design fee
- Stones:
  - Center stone description + price (can mark customer-supplied, for internal reference)
  - Trim stones: multiple lines, each is `qty × price each`
- Labor:
  - Center setting labor (total)
  - Trim setting labor: `qty × rate per stone`
- Extra charges: appraisal, engraving, shipping, rhodium
- Taxability toggles per category (defaults: labor taxable, shipping not taxable)
- Metal pricing:
  - Retail rates are stored as **$/DWT** in `settings.json`
  - You enter a **base weight (14K Yellow)** in DWT or grams
  - Platinum uses a **simplified density ratio** (multiplier) to adjust weight
  - Optional platinum extra fee
- Outputs:
  - Customer PDF
  - Internal PDF
  - Customer PNG (email image)
- Quotes are stored as JSON and versioned:
  - `quotes/YYYY-####/quote_v1.json`, `quote_v2.json`, etc.
  - images are copied into `quotes/YYYY-####/images/`

## Run locally

### 1) Install
```bash
python -m pip install -r requirements.txt
```

### 2) Start the app
```bash
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).

## Settings

Open the **Settings** tab to set:
- store name/contact info
- tax rate
- deposit rate (applied to pre-tax subtotal)
- rounding rule (applied to pre-tax subtotal)
- metal retail rates ($/DWT)
- platinum density ratio + extra fee
- logo upload (`assets/logo.png`)

## Deploy to Streamlit Community Cloud

1. Create a GitHub repo and upload these files:
   - `app.py`, `pricing.py`, `render_quote.py`, `settings.json`, `requirements.txt`
2. In Streamlit Cloud, create a new app:
   - Main file: `app.py`
3. Streamlit will install dependencies from `requirements.txt`

> Note: On Streamlit Cloud, files are stored in the app container. Quotes will be saved inside the container filesystem.
If you need shared multi-user storage later, we can add a database or S3, but this build is intentionally a clean calculator first.
