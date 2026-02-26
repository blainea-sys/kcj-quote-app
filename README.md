# KCJ Quote App (Streamlit Cloud ready)

## Deploy (Streamlit Community Cloud)
- Upload these files to a new GitHub repo
- In Streamlit Cloud, set **Main file path** to `app_quote.py`

## Password protection (optional but included)
This app supports a simple password gate.

### Streamlit Cloud (recommended)
In your Streamlit app settings, add a **Secret**:

- Key: `APP_PASSWORD`
- Value: (your password)

### Local run
Set an env var before launching:
- Windows (PowerShell): `$env:APP_PASSWORD="yourpassword"`
- Windows (CMD): `set APP_PASSWORD=yourpassword`

## Run locally
```bash
pip install -r requirements.txt
streamlit run app_quote.py
```

## Notes
- PDFs/PNGs are generated in-memory and offered as downloads (no Windows paths).
- `settings.json` is a template: update metals, trim pricing, labor rates, and fee defaults for your shop.
