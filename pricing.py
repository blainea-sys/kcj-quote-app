
import json, os, math
from typing import Dict, Any, List, Optional

def load_settings(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_settings(path: str, settings: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

def list_mm_options(settings: Dict[str, Any]) -> List[float]:
    return sorted({float(r["mm"]) for r in settings["trim_table"]})

def _trim_row_for_mm(settings: Dict[str, Any], mm: float) -> Optional[Dict[str, Any]]:
    for r in settings["trim_table"]:
        if float(r["mm"]) == float(mm):
            return r
    return None

def get_default_center_price_per_ct(settings: Dict[str, Any], ct: float) -> Optional[float]:
    for rr in settings["center_stone"]["lab_diamond_price_per_ct_ranges"]:
        if ct >= float(rr["min_ct"]) and ct <= float(rr["max_ct"]):
            return float(rr["price_per_ct"])
    return None

def _round_money(settings: Dict[str, Any], x: float) -> float:
    rule = settings.get("rounding", "nearest_dollar")
    if rule == "nearest_dollar":
        return float(round(x))
    return float(x)

def _round_to_5(x: float) -> float:
    """Round to the nearest $5."""
    return float(round(x / 5.0) * 5.0)

def compute_quote(
    *,
    settings: Dict[str, Any],
    customer_name: str,
    job_name: str,
    quote_date: str,
    notes: str,
    cad_fee: float,
    metal_type: str,
    metal_weight_value: float,
    metal_weight_unit: str,
    add_platinum_casting: bool,
    center: Dict[str, Any],
    trim: Dict[str, Any],
    labor: Dict[str, Any],
    misc: Dict[str, Any],
) -> Dict[str, Any]:

    line_items: List[Dict[str, Any]] = []

    # CAD
    if cad_fee > 0:
        line_items.append({"label": "CAD / design fee", "amount": _round_money(settings, cad_fee), "taxable": True})

    # Metal
    metal_amount = 0.0
    if metal_weight_value and metal_weight_value > 0:
        dwt = metal_weight_value
        if metal_weight_unit == "Grams":
            # From sheet note: grams -> DWT factor 0.643
            dwt = metal_weight_value * 0.643
        cost_per_dwt = float(settings["metals"][metal_type])
        metal_amount = cost_per_dwt * dwt
        if add_platinum_casting and metal_type.upper().startswith("PLAT"):
            metal_amount += float(settings["fees"].get("platinum_casting_fee", 0.0))
        line_items.append({"label": f"Metal ({metal_type})", "amount": _round_money(settings, metal_amount), "taxable": True})

    # Center stone
    center_amount = 0.0
    ctype = center.get("type", "None")
    if ctype == "Lab diamond (price/ct by range)":
        ct = float(center.get("ct", 0.0))
        price_per_ct = float(center.get("price_per_ct", 0.0))
        center_amount = ct * price_per_ct
        if center_amount > 0:
            line_items.append({"label": f"Center stone (lab) {ct:.2f}ct @ ${price_per_ct:,.0f}/ct", "amount": _round_money(settings, center_amount)})
    elif ctype == "Natural diamond (cost x markup)":
        cost = float(center.get("cost", 0.0))
        markup = float(center.get("markup", 0.0))
        center_amount = cost * markup
        if center_amount > 0:
            line_items.append({"label": f"Center stone (natural) cost ${cost:,.0f} x {markup:.2f}", "amount": _round_money(settings, center_amount)})
    elif ctype == "Colored / calibrated (cost x markup)":
        cost = float(center.get("cost", 0.0))
        markup = float(center.get("markup", 0.0))
        center_amount = cost * markup
        if center_amount > 0:
            line_items.append({"label": f"Center stone (colored) cost ${cost:,.0f} x {markup:.2f}", "amount": _round_money(settings, center_amount)})
    elif ctype == "Custom line item":
        label = str(center.get("label", "Center stone"))
        price = float(center.get("price", 0.0))
        if price > 0:
            line_items.append({"label": label, "amount": _round_money(settings, price), "taxable": bool(center.get("taxable", True))})

    # Trim stones
    trim_total = 0.0
    trim_details = []
    if trim.get("enabled") and trim.get("items"):
        for item in trim["items"]:
            mm = float(item["mm"])
            qty = int(item.get("qty", 0))
            if qty <= 0:
                continue
            row = _trim_row_for_mm(settings, mm)
            if not row:
                continue
            ct_each = float(row["ct_each"])
            retail_per_ct = float(item["retail_per_ct_override"] or row["retail_per_ct"])
            total_ct = ct_each * qty
            price = total_ct * retail_per_ct
            trim_total += price
            trim_details.append((mm, qty, total_ct, retail_per_ct, price))
        if trim_total > 0:
            label = "Trim stones"
            line_items.append({"label": label, "amount": _round_money(settings, trim_total), "details": trim_details, "taxable": True})

    # Setting labor
    labor_total = 0.0
    lr = settings["labor_rates"]

    def _rate_for_style(style: str) -> float:
        if style in lr["round_center"]:
            return float(lr["round_center"][style])
        if style in lr["fancy_center"]:
            return float(lr["fancy_center"][style])
        if style in lr["round_trim"]:
            return float(lr["round_trim"][style])
        if style in lr["fancy_trim"]:
            return float(lr["fancy_trim"][style])
        return 0.0

    center_style = labor.get("center_setting_style", "None")
    if center_style and center_style != "None":
        qty = int(labor.get("center_setting_qty", 0))
        rate = _rate_for_style(center_style)
        amt = rate * qty
        if amt > 0:
            labor_total += amt
            line_items.append({"label": f"Set center stone ({center_style})", "amount": _round_money(settings, amt), "taxable": True})

    trim_style = labor.get("trim_setting_style", "None")
    if trim_style and trim_style != "None":
        qty = int(labor.get("trim_setting_qty", 0))
        rate = _rate_for_style(trim_style)
        amt = rate * qty
        if amt > 0:
            labor_total += amt
            line_items.append({"label": f"Set trim stones ({trim_style})", "amount": _round_money(settings, amt), "taxable": True})

    # Finishing & misc
    fees = settings["fees"]
    if misc.get("rhodium"):
        line_items.append({"label": "Rhodium", "amount": _round_money(settings, float(fees.get("rhodium_fee", 0.0))), "taxable": True})
    if misc.get("polishing"):
        line_items.append({"label": "Polishing / finishing", "amount": _round_money(settings, float(fees.get("polishing_fee", 0.0))), "taxable": True})
    if misc.get("engraving"):
        line_items.append({"label": "Engraving", "amount": _round_money(settings, float(fees.get("engraving_fee", 0.0))), "taxable": True})
    if misc.get("shipping"):
        line_items.append({"label": "Shipping", "amount": _round_money(settings, float(fees.get("shipping_fee", 0.0))), "taxable": True})

    # Custom misc line item (manual)
    misc_amount = float(misc.get("amount", 0.0) or 0.0)
    misc_desc = (misc.get("description") or "").strip()
    if misc_amount > 0:
        label = "Misc."
        if misc_desc:
            label = f"Misc.: {misc_desc}"
        line_items.append({"label": label, "amount": _round_money(settings, misc_amount), "taxable": bool(misc.get("taxable", True))})



    subtotal = sum(li["amount"] for li in line_items)
    # Keep tax math unrounded-to-5; only round the final total to the nearest $5.
    tax = _round_money(settings, subtotal * float(settings.get("tax_rate", 0.0)))
    raw_total = float(subtotal + tax)
    total = _round_to_5(raw_total)
    deposit = _round_to_5(total * float(settings.get("deposit_rate", 0.5)))

    # Quote expiration
    valid_days = int(settings.get("output", {}).get("quote_valid_days", 14))
    try:
        import datetime as _dt
        qd = _dt.date.fromisoformat(str(quote_date))
        valid_until = (qd + _dt.timedelta(days=valid_days)).isoformat()
    except Exception:
        valid_until = ""

    return {
        "customer_name": customer_name,
        "job_name": job_name,
        "quote_date": quote_date,
        "notes": notes,
        "line_items": line_items,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "deposit": deposit,
        "tax_rate": float(settings.get("tax_rate", 0.0)),
        "deposit_rate": float(settings.get("deposit_rate", 0.5)),
        "valid_days": valid_days,
        "valid_until": valid_until,
        "raw_total": raw_total,
    }
