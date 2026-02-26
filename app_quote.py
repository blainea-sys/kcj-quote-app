
import io, os, json, datetime, tempfile
import streamlit as st
from pricing import load_settings, compute_quote, list_mm_options, get_default_center_price_per_ct
from render_quote import render_pdf, render_png

APP_TITLE = "KCJ Quote App"

def _get_password() -> str:
    # Streamlit Cloud secrets first, then env var
    try:
        if "APP_PASSWORD" in st.secrets:
            return str(st.secrets["APP_PASSWORD"])
    except Exception:
        pass
    return os.environ.get("APP_PASSWORD", "")

def _gate():
    pw = _get_password().strip()
    if not pw:
        return  # no password set
    st.sidebar.subheader("Access")
    entered = st.sidebar.text_input("Password", type="password")
    if entered != pw:
        st.error("Password required.")
        st.stop()

def _today_str():
    return datetime.date.today().strftime("%Y-%m-%d")

def _money(x: float) -> str:
    return f"${x:,.0f}"

st.set_page_config(page_title=APP_TITLE, layout="wide")
_gate()

st.title("Kizer Cummings Jewelers — Quote Builder")

# ---- Settings ----
with st.expander("Settings (edit the file in GitHub for Streamlit Cloud)", expanded=False):
    st.caption("Pricing logic comes from pricing.py. Update settings.json to change defaults (metals, fees, trim table, labor rates, tax, deposit).")

settings = load_settings("settings.json")

# ---- Sidebar: logo + export options ----
st.sidebar.header("Branding / Output")

logo_file = st.sidebar.file_uploader("Upload logo (PNG/JPG)", type=["png","jpg","jpeg"])
customer_view = st.sidebar.toggle("Customer-view PDF (hide internal notes)", value=True)

# ---- Password hint if set ----
pw_set = bool(_get_password().strip())
if pw_set:
    st.sidebar.caption("Password gate: ON")

# ---- Customer + job info ----
colA, colB, colC = st.columns([1.2, 1.2, 1])
with colA:
    customer_name = st.text_input("Customer name", value="")
    job_name = st.text_input("Job / Project name", value="")
with colB:
    quote_date = st.text_input("Quote date (YYYY-MM-DD)", value=_today_str())
    valid_days = int(settings.get("output", {}).get("valid_days", 30))
    st.caption(f"Default validity: {valid_days} days (edit settings.json to change).")
with colC:
    notes = st.text_area("Notes (shown on quote)", value="", height=110)

st.divider()

# ---- Multi-metal pricing ----
st.subheader("Metal")
metals = list(settings["metals"].keys())
selected_metals = st.multiselect("Show pricing for these metals", options=metals, default=[metals[0]] if metals else [])
if not selected_metals:
    st.warning("Select at least one metal.")
    st.stop()

mcol1, mcol2, mcol3 = st.columns([1,1,1])
with mcol1:
    metal_weight_value = st.number_input("Metal weight", min_value=0.0, step=0.1, value=0.0)
with mcol2:
    metal_weight_unit = st.selectbox("Weight unit", options=["DWT","Grams"], index=0)
with mcol3:
    add_platinum_casting = st.checkbox("Add platinum casting fee (if Platinum)", value=False)

st.divider()

# ---- CAD fee ----
st.subheader("Design")
cad_fee = st.number_input("CAD / design fee", min_value=0.0, step=25.0, value=0.0)

# ---- Center stone ----
st.subheader("Center stone")
center_type = st.selectbox(
    "Center stone type",
    options=[
        "None",
        "Lab diamond (price/ct by range)",
        "Natural diamond (cost x markup)",
        "Colored / calibrated (cost x markup)",
        "Custom line item",
    ],
    index=0,
)

center = {"type": center_type}

if center_type == "Lab diamond (price/ct by range)":
    ct = st.number_input("Carat weight (ct)", min_value=0.0, step=0.05, value=0.0)
    default_ppct = get_default_center_price_per_ct(settings, ct) or 0.0
    price_per_ct = st.number_input("Retail price per ct", min_value=0.0, step=50.0, value=float(default_ppct))
    center.update({"ct": ct, "price_per_ct": price_per_ct})
elif center_type in ("Natural diamond (cost x markup)", "Colored / calibrated (cost x markup)"):
    cost = st.number_input("Your cost", min_value=0.0, step=50.0, value=0.0)
    key = "default_natural_markup" if "Natural" in center_type else "default_colored_markup"
    default_markup = float(settings.get("center_stone", {}).get(key, 2.7))
    markup = st.number_input("Markup multiplier (ex: 2.7)", min_value=0.0, step=0.1, value=float(default_markup))
    center.update({"cost": cost, "markup": markup})
elif center_type == "Custom line item":
    label = st.text_input("Line item label", value="Center stone")
    price = st.number_input("Retail price", min_value=0.0, step=50.0, value=0.0)
    taxable = st.checkbox("Taxable", value=True)
    center.update({"label": label, "price": price, "taxable": taxable})

st.divider()

# ---- Trim stones ----
st.subheader("Trim stones")
trim_enabled = st.checkbox("Include trim stones", value=False)
trim_items = []
mm_options = list_mm_options(settings)

if trim_enabled:
    st.caption("Add as many trim lines as you need. Retail $/ct can be overridden per line.")
    if "trim_rows" not in st.session_state:
        st.session_state.trim_rows = 1

    btnc1, btnc2 = st.columns([1,5])
    with btnc1:
        if st.button("➕ Add trim line"):
            st.session_state.trim_rows += 1
    with btnc2:
        if st.session_state.trim_rows > 1 and st.button("➖ Remove last line"):
            st.session_state.trim_rows -= 1

    for i in range(st.session_state.trim_rows):
        c1,c2,c3 = st.columns([1,1,1.2])
        with c1:
            mm = st.selectbox(f"MM (line {i+1})", options=mm_options, key=f"mm_{i}")
        with c2:
            qty = st.number_input(f"Qty (line {i+1})", min_value=0, step=1, key=f"qty_{i}")
        with c3:
            override = st.number_input(f"Override retail $/ct (0 = use table) (line {i+1})", min_value=0.0, step=50.0, key=f"ov_{i}")
        trim_items.append({"mm": mm, "qty": qty, "retail_per_ct_override": override if override > 0 else None})

trim = {"enabled": trim_enabled, "items": trim_items}

st.divider()

# ---- Labor / setting ----
st.subheader("Setting labor")
lr = settings["labor_rates"]

def _style_options():
    # union of all styles plus None
    s = set()
    for bucket in ("round_center","fancy_center","round_trim","fancy_trim"):
        s |= set((lr.get(bucket) or {}).keys())
    return ["None"] + sorted(s)

style_opts = _style_options()

l1,l2,l3,l4 = st.columns(4)
with l1:
    center_setting_style = st.selectbox("Center setting style", options=style_opts, index=0)
with l2:
    center_setting_qty = st.number_input("Center setting qty", min_value=0, step=1, value=1)
with l3:
    trim_setting_style = st.selectbox("Trim setting style", options=style_opts, index=0)
with l4:
    trim_setting_qty = st.number_input("Trim setting qty", min_value=0, step=1, value=0)

labor = {
    "center_setting_style": center_setting_style,
    "center_setting_qty": center_setting_qty,
    "trim_setting_style": trim_setting_style,
    "trim_setting_qty": trim_setting_qty,
}

st.divider()

# ---- Misc fees ----
st.subheader("Finishing & misc")
mc1, mc2, mc3, mc4 = st.columns(4)
with mc1:
    rhodium = st.checkbox("Rhodium", value=False)
with mc2:
    polishing = st.checkbox("Polishing / finishing", value=False)
with mc3:
    engraving = st.checkbox("Engraving", value=False)
with mc4:
    shipping = st.checkbox("Shipping", value=False)

misc_desc = st.text_input("Custom misc description (optional)", value="")
misc_amount = st.number_input("Custom misc amount", min_value=0.0, step=10.0, value=0.0)
misc_taxable = st.checkbox("Custom misc taxable", value=True)

misc = {
    "rhodium": rhodium,
    "polishing": polishing,
    "engraving": engraving,
    "shipping": shipping,
    "description": misc_desc,
    "amount": misc_amount,
    "taxable": misc_taxable,
}

st.divider()

# ---- Compute + display ----
st.subheader("Totals")

quotes = {}
for metal_type in selected_metals:
    q = compute_quote(
        settings=settings,
        customer_name=customer_name,
        job_name=job_name,
        quote_date=quote_date,
        notes=notes,
        cad_fee=float(cad_fee),
        metal_type=metal_type,
        metal_weight_value=float(metal_weight_value),
        metal_weight_unit=metal_weight_unit,
        add_platinum_casting=bool(add_platinum_casting),
        center=center,
        trim=trim,
        labor=labor,
        misc=misc,
    )
    quotes[metal_type] = q

# Side-by-side summary
summary_rows = []
for mt, q in quotes.items():
    summary_rows.append({
        "Metal": mt,
        "Subtotal": q["subtotal"],
        "Tax": q["tax"],
        "Total": q["total"],
        "Deposit": q["deposit"],
        "Balance Due": max(0.0, q["total"] - q["deposit"]),
    })

st.dataframe(summary_rows, use_container_width=True, hide_index=True)

# Pick which metal to export
export_metal = st.selectbox("Export metal", options=list(quotes.keys()), index=0)
qexp = quotes[export_metal]

# Line item detail
with st.expander("Line items (selected export metal)", expanded=True):
    for li in qexp["line_items"]:
        left, right = st.columns([4,1])
        with left:
            st.write(li["label"])
            if "details" in li and li["details"]:
                st.caption(str(li["details"]))
        with right:
            st.write(_money(li["amount"]))

# Deposit breakdown
st.markdown(
    f"""
**Subtotal:** {_money(qexp["subtotal"])}  
**Tax:** {_money(qexp["tax"])}  (rate: {qexp["tax_rate"]*100:.2f}%)  
**Total:** {_money(qexp["total"])}  
**Deposit ({qexp["deposit_rate"]*100:.0f}%):** {_money(qexp["deposit"])}  
**Balance due at pickup:** {_money(max(0.0, qexp["total"]-qexp["deposit"]))}
"""
)

# ---- PDF/PNG generation ----
st.subheader("Downloads")

def _write_logo_temp(uploaded):
    if not uploaded:
        return None
    suffix = "." + uploaded.name.split(".")[-1].lower()
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(uploaded.getbuffer())
    return path

logo_path = _write_logo_temp(logo_file)

# PDF
pdf_buf = None
png_buf = None

c1, c2 = st.columns(2)
with c1:
    if st.button("Build PDF"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            out_path = tf.name
        render_pdf(qexp, settings, out_path, logo_path=logo_path, customer_view=customer_view)
        with open(out_path, "rb") as f:
            pdf_buf = f.read()
        st.download_button(
            "Download PDF",
            data=pdf_buf,
            file_name=f"Quote_{customer_name or 'Customer'}_{export_metal}.pdf".replace(" ", "_"),
            mime="application/pdf"
        )
with c2:
    if st.button("Build PNG"):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            out_path = tf.name
        render_png(qexp, settings, out_path, logo_path=logo_path, customer_view=customer_view)
        with open(out_path, "rb") as f:
            png_buf = f.read()
        st.download_button(
            "Download PNG",
            data=png_buf,
            file_name=f"Quote_{customer_name or 'Customer'}_{export_metal}.png".replace(" ", "_"),
            mime="image/png"
        )

