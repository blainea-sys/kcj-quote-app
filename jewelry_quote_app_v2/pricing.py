import json
import math
from typing import Dict, Any, List, Optional, Tuple

GRAMS_TO_DWT = 0.643  # historical jeweler conversion used in your earlier tool

def load_settings(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_settings(path: str, settings: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

def _round_nearest_5(x: float) -> float:
    return float(round(x / 5.0) * 5.0)

def round_money(x: float, rule: str) -> float:
    """
    Rounding rule applied to *pre-tax subtotal* for your workflow.
    - none: no rounding
    - nearest_dollar: nearest whole dollar
    - nearest_5: nearest $5
    """
    rule = (rule or "none").strip().lower()
    if rule == "nearest_dollar":
        return float(round(x))
    if rule == "nearest_5":
        return _round_nearest_5(x)
    return float(x)

def money_str(x: float) -> str:
    return f"${x:,.0f}"

def weight_to_dwt(weight_value: float, unit: str) -> float:
    unit = (unit or "DWT").strip()
    if unit.lower().startswith("gram"):
        return float(weight_value) * GRAMS_TO_DWT
    return float(weight_value)

def compute_quote_for_metal(
    *,
    settings: Dict[str, Any],
    quote_core: Dict[str, Any],
    metal_key: str,
) -> Dict[str, Any]:
    """
    Computes a single-metal option quote. The metal weight entered is assumed to be
    the base 14K Yellow weight; platinum weight is adjusted using a simplified ratio.
    """
    line_items: List[Dict[str, Any]] = []

    tax_rate = float(settings.get("tax_rate", 0.0))
    deposit_rate = float(settings.get("deposit_rate", 0.5))
    rounding_rule = str(settings.get("rounding", "none"))

    # --- CAD / Design ---
    cad_fee = float(quote_core.get("cad_fee", 0.0) or 0.0)
    if cad_fee > 0:
        line_items.append({
            "label": "CAD / design fee",
            "amount": cad_fee,
            "taxable": bool(quote_core.get("tax_cad", True)),
            "kind": "cad",
        })

    # --- Metal ---
    metal_weight_value = float(quote_core.get("metal_weight_value", 0.0) or 0.0)
    metal_weight_unit = str(quote_core.get("metal_weight_unit", "DWT"))
    base_dwt = weight_to_dwt(metal_weight_value, metal_weight_unit)

    metal_amt = 0.0
    if base_dwt > 0:
        rate_table = settings.get("metals_retail_per_dwt", {}) or {}
        rate = float(rate_table.get(metal_key, 0.0) or 0.0)

        dwt = base_dwt
        if metal_key.upper().startswith("PLAT"):
            ratio = float(settings.get("platinum_density_ratio", 1.0) or 1.0)
            dwt = base_dwt * ratio

        metal_amt = dwt * rate

        # Platinum extra fee (optional toggle per quote)
        if metal_key.upper().startswith("PLAT") and bool(quote_core.get("add_platinum_extra_fee", True)):
            metal_amt += float(settings.get("platinum_extra_fee", 0.0) or 0.0)

        line_items.append({
            "label": f"Metal ({metal_key})",
            "amount": metal_amt,
            "taxable": bool(quote_core.get("tax_metal", True)),
            "kind": "metal",
            "meta": {
                "input_weight_value": metal_weight_value,
                "input_weight_unit": metal_weight_unit,
                "computed_dwt": dwt,
                "rate_per_dwt": rate,
            }
        })

    # --- Stones ---
    # Center stone
    center_desc = (quote_core.get("center_stone_desc") or "").strip()
    center_price = float(quote_core.get("center_stone_price", 0.0) or 0.0)
    if center_desc or center_price > 0:
        line_items.append({
            "label": f"Center stone: {center_desc}".strip() if center_desc else "Center stone",
            "amount": center_price,
            "taxable": bool(quote_core.get("tax_center_stone", True)),
            "kind": "center_stone",
            "meta": {"customer_supplied": bool(quote_core.get("center_stone_customer_supplied", False))}
        })

    # Trim stones (multi-line)
    trim_lines = quote_core.get("trim_stones", []) or []
    trim_total = 0.0
    trim_details: List[Dict[str, Any]] = []
    for row in trim_lines:
        desc = (row.get("desc") or "").strip()
        qty = int(row.get("qty", 0) or 0)
        each = float(row.get("price_each", 0.0) or 0.0)
        if qty <= 0 or each <= 0:
            continue
        amt = qty * each
        trim_total += amt
        trim_details.append({"desc": desc, "qty": qty, "price_each": each, "amount": amt})
    if trim_total > 0:
        line_items.append({
            "label": "Trim stones",
            "amount": trim_total,
            "taxable": bool(quote_core.get("tax_trim_stones", True)),
            "kind": "trim_stones",
            "details": trim_details
        })

    # --- Setting labor ---
    center_setting_labor = float(quote_core.get("center_setting_labor", 0.0) or 0.0)
    if center_setting_labor > 0:
        line_items.append({
            "label": "Setting labor (center)",
            "amount": center_setting_labor,
            "taxable": bool(quote_core.get("tax_labor", True)),
            "kind": "labor_center_setting",
        })

    # Trim setting labor (multi-line)
    trim_setting_lines = quote_core.get("trim_setting_lines")
    details: List[Dict[str, Any]] = []
    trim_setting_total = 0.0

    # Back-compat: older quotes used single qty + rate fields
    legacy_qty = int(quote_core.get("trim_setting_qty", 0) or 0)
    legacy_rate = float(quote_core.get("trim_setting_rate", 0.0) or 0.0)
    if (not trim_setting_lines) and legacy_qty > 0 and legacy_rate > 0:
        trim_setting_lines = [{"desc": "", "qty": legacy_qty, "rate": legacy_rate}]

    for row in (trim_setting_lines or []):
        desc = (row.get("desc") or "").strip()
        qty = int(row.get("qty", 0) or 0)
        rate = float(row.get("rate", 0.0) or 0.0)
        if qty <= 0 or rate <= 0:
            continue
        amt = qty * rate
        trim_setting_total += amt
        details.append({"desc": desc, "qty": qty, "rate": rate, "amount": amt})

    if trim_setting_total > 0:
        line_items.append({
            "label": "Setting labor (trim)",
            "amount": trim_setting_total,
            "taxable": bool(quote_core.get("tax_labor", True)),
            "kind": "labor_trim_setting",
            "details": details,
        })

    # --- Additional charges ---
    # appraisal, engraving, shipping, rhodium (manual fields)
    def _add_charge(key: str, label: str, default_taxable: bool):
        val = float(quote_core.get(key, 0.0) or 0.0)
        if val > 0:
            line_items.append({
                "label": label,
                "amount": val,
                "taxable": bool(quote_core.get(f"tax_{key}", default_taxable)),
                "kind": key,
            })

    _add_charge("appraisal", "Appraisal (outside components)", True)
    _add_charge("engraving", "Engraving", True)
    _add_charge("shipping", "Shipping", False)  # per your rule
    _add_charge("rhodium", "Rhodium plating", True)

    # --- Subtotals ---
    subtotal_pre_tax = float(sum(li["amount"] for li in line_items))

    taxable_subtotal_pre_tax = float(sum(li["amount"] for li in line_items if bool(li.get("taxable", False))))
    tax = taxable_subtotal_pre_tax * tax_rate

    total_with_tax_unrounded = subtotal_pre_tax + tax

    # Your workflow: round the *pre-tax subtotal* (not the tax, not the total)
    rounded_subtotal_pre_tax = round_money(subtotal_pre_tax, rounding_rule)

    deposit = subtotal_pre_tax * deposit_rate  # deposit is % of pre-tax subtotal

    return {
        "metal_key": metal_key,
        "line_items": line_items,
        "subtotal_pre_tax": subtotal_pre_tax,
        "rounded_subtotal_pre_tax": rounded_subtotal_pre_tax,
        "taxable_subtotal_pre_tax": taxable_subtotal_pre_tax,
        "tax_rate": tax_rate,
        "tax": tax,
        "total_with_tax": total_with_tax_unrounded,
        "deposit_rate": deposit_rate,
        "deposit": deposit,
        "rounding_rule": rounding_rule,
    }

def compute_quote_multi(
    *,
    settings: Dict[str, Any],
    quote_core: Dict[str, Any],
    metal_keys: List[str],
) -> Dict[str, Any]:
    options = []
    for mk in metal_keys:
        options.append(compute_quote_for_metal(settings=settings, quote_core=quote_core, metal_key=mk))
    return {
        "options": options
    }
