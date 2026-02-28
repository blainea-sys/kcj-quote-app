import os
import json
import uuid
import datetime
import tempfile
from pathlib import Path

import streamlit as st

from pricing import load_settings, compute_quote_for_metal
from render_quote import render_pdf, render_png


APP_DIR = Path(__file__).resolve().parent
DEFAULT_SETTINGS_PATH = APP_DIR / "settings.json"


st.set_page_config(page_title="Jewelry Quote 2.0", page_icon="💎", layout="wide")


def money0(x: float) -> str:
    return f"${x:,.0f}"


def money2(x: float) -> str:
    return f"${x:,.2f}"


def today_iso() -> str:
    return datetime.date.today().isoformat()


def make_quote_id() -> str:
    """Stateless hosting: make a readable unique id without storing counters."""
    now = datetime.datetime.now()
    return now.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6].upper()


def _safe_filename(s: str) -> str:
    s = (s or "").strip().replace(" ", "_")
    return "".join(ch for ch in s if ch.isalnum() or ch in ("_", "-")) or "item"


# ---------------- Settings (session-scoped) ----------------
if "settings" not in st.session_state:
    st.session_state["settings"] = load_settings(str(DEFAULT_SETTINGS_PATH))

settings = st.session_state["settings"]


st.title("💎 Jewelry Quote 2.0 — Streamlit-hostable (no storage)")
st.caption(
    "This version does **not** save quotes, images, or outputs on the server. "
    "It generates PDFs/PNGs for download during your session."
)

tabs = st.tabs(["Build quote", "Settings"])


# ---------------- Build Quote ----------------
with tabs[0]:
    left, right = st.columns([1.1, 0.9], gap="large")

    with left:
        st.subheader("Customer & job")
        customer_name = st.text_input("Customer name", value="")
        job_desc = st.text_input("Job description", value="")
        item_type = st.selectbox(
            "Item type",
            options=["Ring", "Earrings", "Necklace", "Pendant", "Bracelet", "Other"],
            index=0,
        )
        quote_date = st.date_input("Quote date", value=datetime.date.fromisoformat(today_iso()))
        notes = st.text_area("Notes (internal)", value="", height=90)

        ring = {"finger_size": "", "ring_width": "", "center_shape": ""}
        if item_type == "Ring":
            st.subheader("Ring details")
            c1, c2, c3 = st.columns(3)
            ring["finger_size"] = c1.text_input("Finger size", value="")
            ring["ring_width"] = c2.text_input("Ring width (mm)", value="")
            ring["center_shape"] = c3.selectbox(
                "Center stone shape",
                options=[
                    "",
                    "Round",
                    "Oval",
                    "Cushion",
                    "Emerald",
                    "Princess",
                    "Pear",
                    "Marquise",
                    "Radiant",
                    "Asscher",
                    "Heart",
                    "Other",
                ],
                index=0,
            )

        st.divider()
        st.subheader("CAD / Design")
        cad_fee = st.number_input("CAD / design fee", min_value=0.0, value=0.0, step=25.0)

        st.divider()
        st.subheader("Metals")
        metals = list((settings.get("metals_retail_per_dwt", {}) or {}).keys())
        metals_selected = st.multiselect(
            "Select metal options to price",
            options=metals,
            default=["14K Yellow"] if "14K Yellow" in metals else [],
        )

        c1, c2 = st.columns(2)
        unit = c1.radio("Weight unit", options=["DWT", "Grams"], horizontal=True, index=0)
        weight = c2.number_input("Metal weight (base: 14K Yellow)", min_value=0.0, value=0.0, step=0.1)

        add_plat_fee = st.checkbox(
            "Add platinum extra fee (if platinum selected)",
            value=True,
        )

        st.divider()
        st.subheader("Stones")
        center_desc = st.text_input("Center stone description", value="")
        center_price = st.number_input("Center stone price", min_value=0.0, value=0.0, step=50.0)
        center_customer_supplied = st.checkbox("Customer-supplied center stone", value=False)

        st.subheader("Trim stones (multiple lines)")
        n_trim = st.number_input("How many trim lines?", min_value=0, max_value=10, value=1, step=1)
        trim_stones = []
        for i in range(int(n_trim)):
            with st.expander(f"Trim line {i+1}", expanded=(i == 0)):
                c1, c2, c3 = st.columns([1.4, 0.8, 0.9])
                desc = c1.text_input("Description", value="", key=f"trim_desc_{i}")
                qty = c2.number_input("Qty", min_value=0, value=0, step=1, key=f"trim_qty_{i}")
                each = c3.number_input("Price each", min_value=0.0, value=0.0, step=10.0, key=f"trim_each_{i}")
                trim_stones.append({"desc": desc, "qty": int(qty), "price_each": float(each)})

        st.divider()
        st.subheader("Setting labor")
        center_setting_labor = st.number_input("Center setting labor (total)", min_value=0.0, value=0.0, step=25.0)

        st.subheader("Trim setting labor (multiple lines)")
        n_trim_set = st.number_input("How many trim setting lines?", min_value=0, max_value=10, value=1, step=1)
        trim_setting_lines = []
        for i in range(int(n_trim_set)):
            with st.expander(f"Trim setting line {i+1}", expanded=(i == 0)):
                c1, c2, c3 = st.columns([1.4, 0.8, 0.9])
                desc = c1.text_input("Description", value="", key=f"trimset_desc_{i}")
                qty = c2.number_input("Qty", min_value=0, value=0, step=1, key=f"trimset_qty_{i}")
                rate = c3.number_input("Rate per stone", min_value=0.0, value=0.0, step=5.0, key=f"trimset_rate_{i}")
                trim_setting_lines.append({"desc": desc, "qty": int(qty), "rate": float(rate)})

        st.divider()
        st.subheader("Additional charges")
        c1, c2, c3, c4 = st.columns(4)
        appraisal = c1.number_input("Appraisal", min_value=0.0, value=0.0, step=25.0)
        engraving = c2.number_input("Engraving", min_value=0.0, value=0.0, step=10.0)
        shipping = c3.number_input("Shipping", min_value=0.0, value=0.0, step=10.0)
        rhodium = c4.number_input("Rhodium plating", min_value=0.0, value=0.0, step=10.0)

        st.divider()
        st.subheader("Tax & rounding")
        c1, c2, c3 = st.columns(3)
        rounding_rule = c1.selectbox(
            "Rounding rule (applies to pre-tax subtotal)",
            options=["none", "nearest_dollar", "nearest_5"],
            index=["none", "nearest_dollar", "nearest_5"].index(str(settings.get("rounding", "none"))),
        )
        tax_rate = c2.number_input(
            "Tax rate",
            min_value=0.0,
            max_value=1.0,
            value=float(settings.get("tax_rate", 0.0)),
            step=0.0005,
            format="%.4f",
        )
        deposit_rate = c3.number_input(
            "Deposit rate (pre-tax subtotal)",
            min_value=0.0,
            max_value=1.0,
            value=float(settings.get("deposit_rate", 0.5)),
            step=0.05,
            format="%.2f",
        )

        # Locked defaults
        tax_labor_default = True
        tax_shipping_default = False

        with st.expander("Taxability toggles (advanced)", expanded=False):
            t1, t2, t3 = st.columns(3)
            tax_cad = t1.checkbox("CAD taxable", value=True)
            tax_metal = t2.checkbox("Metal taxable", value=True)
            tax_center_stone = t3.checkbox("Center stone taxable", value=True)

            t4, t5, t6 = st.columns(3)
            tax_trim_stones = t4.checkbox("Trim stones taxable", value=True)
            tax_labor = t5.checkbox("Labor taxable", value=tax_labor_default)
            tax_appraisal = t6.checkbox("Appraisal taxable", value=True)

            t7, t8, t9 = st.columns(3)
            tax_engraving = t7.checkbox("Engraving taxable", value=True)
            tax_shipping = t8.checkbox("Shipping taxable", value=tax_shipping_default)
            tax_rhodium = t9.checkbox("Rhodium taxable", value=True)

        st.divider()
        st.subheader("Images")
        st.caption("Upload sketches / reference photos. Customer output shows up to a 1-page grid.")
        images = st.file_uploader("Upload images", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)

        st.divider()
        output_mode = st.radio(
            "Generate outputs",
            options=["Customer + Internal PDFs", "Customer PDF only"],
            horizontal=True,
            index=0,
        )
        generate = st.button("Generate quote files", type="primary", use_container_width=True)

        quote_core = {
            "customer_name": customer_name.strip(),
            "job_desc": job_desc.strip(),
            "item_type": item_type,
            "quote_date": str(quote_date),
            "notes": notes.strip(),
            "ring": ring if item_type == "Ring" else {},
            "cad_fee": float(cad_fee),
            "metals_selected": metals_selected,
            "metal_weight_value": float(weight),
            "metal_weight_unit": unit,
            "add_platinum_extra_fee": bool(add_plat_fee),
            "center_stone_desc": center_desc.strip(),
            "center_stone_price": float(center_price),
            "center_stone_customer_supplied": bool(center_customer_supplied),
            "trim_stones": trim_stones,
            "center_setting_labor": float(center_setting_labor),
            "trim_setting_lines": trim_setting_lines,
            "appraisal": float(appraisal),
            "engraving": float(engraving),
            "shipping": float(shipping),
            "rhodium": float(rhodium),
            # tax toggles
            "tax_cad": bool(tax_cad),
            "tax_metal": bool(tax_metal),
            "tax_center_stone": bool(tax_center_stone),
            "tax_trim_stones": bool(tax_trim_stones),
            "tax_labor": bool(tax_labor),
            "tax_appraisal": bool(tax_appraisal),
            "tax_engraving": bool(tax_engraving),
            "tax_shipping": bool(tax_shipping),
            "tax_rhodium": bool(tax_rhodium),
            "rounding_rule": str(rounding_rule),
        }

        # Update runtime settings for calculations (session only)
        settings["tax_rate"] = float(tax_rate)
        settings["deposit_rate"] = float(deposit_rate)
        settings["rounding"] = str(rounding_rule)

        if generate:
            if not metals_selected:
                st.error("Select at least one metal option.")
            else:
                quote_id = make_quote_id()
                with tempfile.TemporaryDirectory() as td:
                    tdir = Path(td)

                    # Save uploaded images to temp files for rendering
                    saved_images = []
                    for up in (images or []):
                        ext = Path(up.name).suffix.lower()
                        if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
                            ext = ".png"
                        fp = tdir / f"img_{uuid.uuid4().hex}{ext}"
                        fp.write_bytes(up.getbuffer())
                        saved_images.append(str(fp))

                    # Optional session logo (temp)
                    logo_tmp = None
                    if st.session_state.get("session_logo_bytes"):
                        logo_tmp = tdir / "logo.png"
                        logo_tmp.write_bytes(st.session_state["session_logo_bytes"])

                    options = []
                    for mk in metals_selected:
                        opt = compute_quote_for_metal(settings=settings, quote_core=quote_core, metal_key=mk)
                        metal_amt = 0.0
                        for li in opt["line_items"]:
                            if li.get("kind") == "metal":
                                metal_amt = float(li.get("amount", 0.0) or 0.0)
                                break
                        opt["metal_amount"] = metal_amt
                        options.append(opt)

                    shared = []
                    if options:
                        for li in options[0]["line_items"]:
                            if li.get("kind") != "metal":
                                shared.append(li)

                    valid_days = int((settings.get("output", {}) or {}).get("quote_valid_days", 14) or 14)
                    try:
                        qd = datetime.date.fromisoformat(str(quote_date))
                        valid_until = (qd + datetime.timedelta(days=valid_days)).isoformat()
                    except Exception:
                        valid_until = ""

                    quote_doc = {
                        "header": {
                            "quote_id": quote_id,
                            "version": "v1",
                            "quote_date": str(quote_date),
                            "valid_until": valid_until,
                            "customer_name": customer_name.strip(),
                            "job_desc": job_desc.strip(),
                            "item_type": item_type,
                            "notes": notes.strip(),
                            "ring": ring if item_type == "Ring" else {},
                        },
                        "images": saved_images,
                        "shared_line_items": shared,
                        "metal_options": [
                            {
                                "metal_key": o["metal_key"],
                                "metal_amount": o.get("metal_amount", 0.0),
                                "subtotal_pre_tax": o["subtotal_pre_tax"],
                                "rounded_subtotal_pre_tax": o["rounded_subtotal_pre_tax"],
                                "tax": o["tax"],
                                "total_with_tax": o["total_with_tax"],
                                "deposit": o["deposit"],
                            }
                            for o in options
                        ],
                        "rounding_rule": str(rounding_rule),
                        "footer": "Prices subject to change due to metal market and stone availability.",
                    }

                    safe_customer = _safe_filename(customer_name or "customer")
                    safe_job = _safe_filename(job_desc or "job")
                    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

                    pdf_customer_path = tdir / f"Quote_{quote_id}_{safe_customer}_{safe_job}_{stamp}_CUSTOMER.pdf"
                    pdf_internal_path = tdir / f"Quote_{quote_id}_{safe_customer}_{safe_job}_{stamp}_INTERNAL.pdf"
                    png_customer_path = tdir / f"Quote_{quote_id}_{safe_customer}_{safe_job}_{stamp}_CUSTOMER.png"

                    render_pdf(
                        quote_doc=quote_doc,
                        settings=settings,
                        out_path=str(pdf_customer_path),
                        logo_path=str(logo_tmp) if logo_tmp else None,
                        customer_view=True,
                    )
                    if output_mode == "Customer + Internal PDFs":
                        render_pdf(
                            quote_doc=quote_doc,
                            settings=settings,
                            out_path=str(pdf_internal_path),
                            logo_path=str(logo_tmp) if logo_tmp else None,
                            customer_view=False,
                        )
                    render_png(
                        quote_doc=quote_doc,
                        settings=settings,
                        out_path=str(png_customer_path),
                        logo_path=str(logo_tmp) if logo_tmp else None,
                        customer_view=True,
                    )

                    st.success("Quote generated (not saved). Download below:")
                    st.download_button(
                        "Download Customer PDF",
                        data=pdf_customer_path.read_bytes(),
                        file_name=pdf_customer_path.name,
                        mime="application/pdf",
                        use_container_width=True,
                    )
                    if output_mode == "Customer + Internal PDFs":
                        st.download_button(
                            "Download Internal PDF",
                            data=pdf_internal_path.read_bytes(),
                            file_name=pdf_internal_path.name,
                            mime="application/pdf",
                            use_container_width=True,
                        )
                    st.download_button(
                        "Download Customer PNG",
                        data=png_customer_path.read_bytes(),
                        file_name=png_customer_path.name,
                        mime="image/png",
                        use_container_width=True,
                    )

                    # Optional: download JSON for your records
                    payload = {
                        "quote_core": quote_core,
                        "quote_doc": quote_doc,
                        "computed": options,
                    }
                    st.download_button(
                        "Download Quote JSON (optional)",
                        data=json.dumps(payload, indent=2).encode("utf-8"),
                        file_name=f"Quote_{quote_id}_{safe_customer}_{safe_job}.json",
                        mime="application/json",
                        use_container_width=True,
                    )

    with right:
        st.subheader("Preview")
        if metals_selected:
            preview_opts = []
            for mk in metals_selected:
                opt = compute_quote_for_metal(settings=settings, quote_core=quote_core, metal_key=mk)
                metal_amt = 0.0
                for li in opt["line_items"]:
                    if li.get("kind") == "metal":
                        metal_amt = float(li.get("amount", 0.0) or 0.0)
                        break
                preview_opts.append((mk, metal_amt, opt["subtotal_pre_tax"], opt["rounded_subtotal_pre_tax"], opt["tax"], opt["total_with_tax"], opt["deposit"]))

            for mk, metal_amt, sub, rsub, tax, total, dep in preview_opts:
                with st.container(border=True):
                    st.write(f"**{mk}**")
                    st.write(f"Metal: {money0(metal_amt)}")
                    st.write(f"Subtotal (pre-tax): {money0(sub)}")
                    if str(rounding_rule).lower() != "none":
                        st.write(f"Rounded subtotal (pre-tax): {money0(rsub)}")
                    st.write(f"Tax: {money2(tax)}")
                    st.write(f"Total (with tax): {money2(total)}")
                    st.write(f"Deposit ({deposit_rate*100:.0f}% pre-tax): {money2(dep)}")
        else:
            st.info("Select at least one metal option to preview totals.")


# ---------------- Settings (non-persistent) ----------------
with tabs[1]:
    st.subheader("Settings (session-only)")
    st.caption(
        "Changes here apply only for your current session on Streamlit hosting. "
        "To make permanent changes, edit settings.json in your GitHub repo (or download and replace it)."
    )

    st.write("### Store info")
    s1, s2 = st.columns(2)
    store = settings.get("store", {}) or {}
    store["name"] = s1.text_input("Store name (optional)", value=str(store.get("name", "")), key="set_store_name")
    store["phone"] = s2.text_input("Phone", value=str(store.get("phone", "")), key="set_store_phone")
    s3, s4 = st.columns(2)
    store["email"] = s3.text_input("Email", value=str(store.get("email", "")), key="set_store_email")
    store["address"] = s4.text_input("Address", value=str(store.get("address", "")), key="set_store_address")
    settings["store"] = store

    st.write("### Tax / deposit / rounding defaults")
    c1, c2, c3 = st.columns(3)
    settings["tax_rate"] = c1.number_input(
    "Tax rate",
    min_value=0.0,
    max_value=1.0,
    value=float(settings.get("tax_rate", 0.0)),
    step=0.0005,
    format="%.4f",
    key="set_tax_rate",
)
settings["deposit_rate"] = c2.number_input(
    "Deposit rate (pre-tax)",
    min_value=0.0,
    max_value=1.0,
    value=float(settings.get("deposit_rate", 0.5)),
    step=0.05,
    format="%.2f",
    key="set_deposit_rate",
)
settings["rounding"] = c3.selectbox(
    "Rounding rule (pre-tax subtotal)",
    options=["none", "nearest_dollar", "nearest_5"],
    index=["none", "nearest_dollar", "nearest_5"].index(str(settings.get("rounding", "none"))),
    key="set_rounding_rule",
)

    st.write("### Metal retail rates ($/DWT)")
    rates = settings.get("metals_retail_per_dwt", {}) or {}
    for k in list(rates.keys()):
        rates[k] = st.number_input(f"{k} retail $/DWT", min_value=0.0, value=float(rates[k]), step=5.0, key=f"set_rate_{k}")
    settings["metals_retail_per_dwt"] = rates

    st.write("### Platinum density + extra fee")
    c1, c2 = st.columns(2)
    settings["platinum_density_ratio"] = c1.number_input(
        "Platinum density ratio (multiplier vs 14K weight)",
        min_value=0.5,
        max_value=2.5,
        value=float(settings.get("platinum_density_ratio", 1.38)),
        step=0.01,
        key="set_platinum_density_ratio",
    )
    settings["platinum_extra_fee"] = c2.number_input("Platinum extra fee", min_value=0.0, value=float(settings.get("platinum_extra_fee", 0.0)), step=25.0, key="set_platinum_extra_fee")

    st.write("### Output")
    out = settings.get("output", {}) or {}
    c1, c2 = st.columns(2)
    out["quote_valid_days"] = c1.number_input("Quote valid days", min_value=1, max_value=60, value=int(out.get("quote_valid_days", 14)), step=1, key="set_quote_valid_days")
    out["max_images_on_customer_page"] = c2.number_input("Max images on customer page", min_value=1, max_value=12, value=int(out.get("max_images_on_customer_page", 6)), step=1, key="set_max_images_on_customer_page")
    settings["output"] = out

    st.write("### Logo (session-only)")
    st.caption("Upload a PNG logo for this session. For permanent hosting, commit assets/logo.png to GitHub.")
    up = st.file_uploader("Upload logo", type=["png"], key="logo_uploader")
    if up is not None:
        st.session_state["session_logo_bytes"] = up.getbuffer()
        st.success("Logo loaded for this session.")
        st.image(up, use_container_width=True)

    st.divider()
    st.download_button(
        "Download settings.json (use this to update GitHub)",
        data=json.dumps(settings, indent=2).encode("utf-8"),
        file_name="settings.json",
        mime="application/json",
        use_container_width=True,
    )
