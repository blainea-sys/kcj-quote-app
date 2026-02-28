import os
import math
from typing import Optional, Dict, Any, List, Tuple

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader

from PIL import Image, ImageDraw, ImageFont

def _money0(x: float) -> str:
    return f"${x:,.0f}"

def _money2(x: float) -> str:
    # Always show cents (used for tax / totals / deposits)
    return f"${x:,.2f}"

def _wrap_text(text: str, max_chars: int) -> List[str]:
    words = (text or "").replace("\n", " ").split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def _draw_logo_and_store_info_pdf(c, settings: Dict[str, Any], W, y, margin, logo_path: Optional[str]) -> float:
    store = settings.get("store", {}) or {}
    store_name = store.get("name", "") or ""
    store_phone = store.get("phone", "") or ""
    store_email = store.get("email", "") or ""
    store_address = store.get("address", "") or ""

    logo_draw_h = 0.0
    if logo_path and os.path.exists(logo_path):
        try:
            img = ImageReader(logo_path)
            # Keep the logo smaller so most quotes can fit on a single page.
            max_w, max_h = 6.0 * inch, 0.75 * inch
            iw, ih = img.getSize()
            scale = min(max_w / iw, max_h / ih)
            draw_w, draw_h = iw * scale, ih * scale
            x = (W - draw_w) / 2
            c.drawImage(img, x, y - draw_h, width=draw_w, height=draw_h, mask="auto")
            logo_draw_h = draw_h
        except Exception:
            logo_draw_h = 0.0

    # Tighter spacing under logo to preserve vertical space.
    info_y = y - (logo_draw_h + 0.12 * inch)
    ## Store name intentionally omitted (logo already contains it)

    contact_line = "  ".join([s for s in [store_phone, store_email] if s])
    if contact_line:
        c.setFont("Helvetica", 9)
        c.drawCentredString(W / 2, info_y, contact_line)
        info_y -= 0.16 * inch
    if store_address:
        c.setFont("Helvetica", 9)
        c.drawCentredString(W / 2, info_y, store_address)
        info_y -= 0.16 * inch

    return info_y - 0.06 * inch

def _draw_images_grid_pdf(c, image_paths: List[str], W, y, margin) -> float:
    # Customer output: one-page grid. We'll draw up to N images (settings-controlled upstream).
    paths = [p for p in image_paths if p and os.path.exists(p)]
    if not paths:
        return y

    # Grid sizing
    max_cols = 3
    cell = 1.9 * inch
    gap = 0.18 * inch
    cols = min(max_cols, len(paths))
    rows = int(math.ceil(len(paths) / cols))

    grid_w = cols * cell + (cols - 1) * gap
    start_x = (W - grid_w) / 2

    # Ensure grid doesn't run off page: if too many rows, truncate safely
    max_rows = 2  # keeps it reasonable on a single page with totals
    if rows > max_rows:
        paths = paths[: cols * max_rows]
        rows = max_rows

    y0 = y
    for idx, p in enumerate(paths):
        r = idx // cols
        ccol = idx % cols
        x = start_x + ccol * (cell + gap)
        top = y0 - r * (cell + gap)
        # box
        c.rect(x, top - cell, cell, cell, stroke=1, fill=0)
        try:
            img = ImageReader(p)
            c.drawImage(img, x, top - cell, width=cell, height=cell, preserveAspectRatio=True, anchor="c")
        except Exception:
            pass

    return y0 - rows * cell - (rows - 1) * gap - 0.25 * inch

def render_pdf(
    *,
    quote_doc: Dict[str, Any],
    settings: Dict[str, Any],
    out_path: str,
    logo_path: Optional[str] = None,
    customer_view: bool = True,
) -> None:
    """
    quote_doc contains:
      - header fields (customer/job/item/date/quote_id/version/valid_until)
      - images list (paths)
      - shared line items (non-metal)
      - metal options (each with totals + metal line item amount)
    """
    c = canvas.Canvas(out_path, pagesize=letter)
    W, H = letter
    margin = 0.65 * inch
    y = H - margin

    # Header
    y = _draw_logo_and_store_info_pdf(c, settings, W, y, margin, logo_path)

    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(W / 2, y, "Custom Jewelry Quote")
    y -= 0.45 * inch

    # Customer block
    c.setFont("Helvetica", 11)
    h = quote_doc.get("header", {}) or {}
    c.drawString(margin, y, f"Customer: {h.get('customer_name') or '—'}")
    right = f"Quote #: {h.get('quote_id','—')}  {h.get('version','')}".strip()
    c.drawRightString(W - margin, y, right + f"   Date: {h.get('quote_date','')}")
    y -= 0.28 * inch

    valid_until = h.get("valid_until", "")
    if valid_until:
        c.setFont("Helvetica", 10)
        c.drawString(margin, y, f"Valid until: {valid_until}")
        y -= 0.22 * inch
        c.setFont("Helvetica", 11)

    if h.get("job_desc"):
        c.drawString(margin, y, f"Job: {h.get('job_desc')}")
        y -= 0.24 * inch

    if h.get("item_type"):
        c.drawString(margin, y, f"Item type: {h.get('item_type')}")
        y -= 0.22 * inch

    ring = h.get("ring", {}) or {}
    if h.get("item_type") == "Ring" and any(ring.get(k) for k in ["finger_size", "ring_width", "center_shape"]):
        c.setFont("Helvetica", 10)
        parts = []
        if ring.get("finger_size"): parts.append(f"Size: {ring['finger_size']}")
        if ring.get("ring_width"): parts.append(f"Width: {ring['ring_width']}")
        if ring.get("center_shape"): parts.append(f"Center shape: {ring['center_shape']}")
        c.drawString(margin, y, "   ".join(parts))
        y -= 0.22 * inch
        c.setFont("Helvetica", 11)

    if (not customer_view) and h.get("notes"):
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(margin, y, "Notes (internal):")
        y -= 0.16 * inch
        c.setFont("Helvetica", 10)
        for line in _wrap_text(str(h["notes"]), 95):
            c.drawString(margin, y, line)
            y -= 0.15 * inch
        y -= 0.10 * inch
        c.setFont("Helvetica", 11)

    # Images (customer view, 1 page grid)
    if customer_view:
        img_paths = quote_doc.get("images", []) or []
        y = _draw_images_grid_pdf(c, img_paths, W, y, margin)

    # Shared line items (non-metal)
    shared = quote_doc.get("shared_line_items", []) or []

    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Line items (excluding metal)")
    y -= 0.22 * inch
    c.setLineWidth(1)
    c.line(margin, y, W - margin, y)
    y -= 0.18 * inch

    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, y, "Description")
    c.drawRightString(W - margin, y, "Amount")
    y -= 0.18 * inch
    c.setLineWidth(0.5)
    c.line(margin, y, W - margin, y)
    y -= 0.20 * inch

    def _new_page():
        nonlocal y
        c.showPage()
        y = H - margin
        y = _draw_logo_and_store_info_pdf(c, settings, W, y, margin, logo_path)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(W / 2, y, "Custom Jewelry Quote (continued)")
        y -= 0.40 * inch
        c.setFont("Helvetica", 10)
        c.drawString(margin, y, f"Customer: {h.get('customer_name') or '—'}")
        right = f"Quote #: {h.get('quote_id','—')}  {h.get('version','')}".strip()
        c.drawRightString(W - margin, y, right + f"   Date: {h.get('quote_date','')}")
        y -= 0.26 * inch

    c.setFont("Helvetica", 10)
    for li in shared:
        if y < margin + 1.6 * inch:
            _new_page()

        label = li.get("label", "")
        amt = float(li.get("amount", 0.0) or 0.0)
        c.drawString(margin, y, label)
        c.drawRightString(W - margin, y, _money0(amt))
        y -= 0.20 * inch

        details = li.get("details")
        if details:
            c.setFont("Helvetica", 9)
            for d in details:
                if y < margin + 1.4 * inch:
                    _new_page()
                desc = (d.get("desc") or "").strip()
                qty = int(d.get("qty", 0) or 0)
                each = float(d.get("price_each", d.get("rate", 0.0)) or 0.0)
                amount = float(d.get("amount", qty * each) or 0.0)
                line = f"• {qty} × {_money0(each)}"
                if desc:
                    line = f"• {desc} — " + line
                c.drawString(margin + 0.2 * inch, y, line)
                c.drawRightString(W - margin, y, _money0(amount))
                y -= 0.18 * inch
            c.setFont("Helvetica", 10)

    y -= 0.10 * inch

    # Metal options block
    options = quote_doc.get("metal_options", []) or []

    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Metal options")
    y -= 0.22 * inch
    c.setLineWidth(1)
    c.line(margin, y, W - margin, y)
    y -= 0.18 * inch

    # Table header
    c.setFont("Helvetica-Bold", 10)
    cols = ["Metal", "Metal price", "Subtotal (pre-tax)", "Tax", "Total", "Deposit (50% pre-tax)"]
    # column x positions (right aligned for money)
    x_metal = margin
    x_metal_price = margin + 2.1 * inch
    x_sub = margin + 3.6 * inch
    x_tax = margin + 4.6 * inch
    x_total = margin + 5.7 * inch
    x_dep = W - margin

    def _draw_metal_header():
        nonlocal y
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x_metal, y, cols[0])
        c.drawRightString(x_metal_price, y, cols[1])
        c.drawRightString(x_sub, y, cols[2])
        c.drawRightString(x_tax, y, cols[3])
        c.drawRightString(x_total, y, cols[4])
        c.drawRightString(x_dep, y, cols[5])
        y -= 0.16 * inch
        c.setLineWidth(0.5)
        c.line(margin, y, W - margin, y)
        y -= 0.18 * inch
        c.setFont("Helvetica", 9.5)

    _draw_metal_header()

    for opt in options:
        if y < margin + 1.25 * inch:
            _new_page()
            c.setFont("Helvetica-Bold", 11)
            c.drawString(margin, y, "Metal options (continued)")
            y -= 0.22 * inch
            c.setLineWidth(1)
            c.line(margin, y, W - margin, y)
            y -= 0.18 * inch
            _draw_metal_header()
        mk = opt.get("metal_key", "")
        metal_price = float(opt.get("metal_amount", 0.0) or 0.0)
        sub = float(opt.get("subtotal_pre_tax", 0.0) or 0.0)
        tax = float(opt.get("tax", 0.0) or 0.0)
        total = float(opt.get("total_with_tax", 0.0) or 0.0)
        dep = float(opt.get("deposit", 0.0) or 0.0)

        c.drawString(x_metal, y, mk)
        c.drawRightString(x_metal_price, y, _money0(metal_price))
        c.drawRightString(x_sub, y, _money0(sub))
        c.drawRightString(x_tax, y, _money2(tax))
        c.drawRightString(x_total, y, _money2(total))
        c.drawRightString(x_dep, y, _money2(dep))
        y -= 0.18 * inch

    # (Removed explanatory rounding note per user request.)

    # Footer
    c.setFont("Helvetica-Oblique", 9)
    footer = quote_doc.get("footer", "") or "Prices subject to change due to metal market and stone availability."
    c.drawString(margin, 0.50 * inch, footer[:140])

    c.save()

def render_png(
    *,
    quote_doc: Dict[str, Any],
    settings: Dict[str, Any],
    out_path: str,
    logo_path: Optional[str] = None,
    customer_view: bool = True,
) -> None:
    # 8.5x11 at 150 DPI => 1275x1650
    W, H = 1275, 1650
    margin = 90
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    # Fonts
    try:
        title_font = ImageFont.truetype("DejaVuSans.ttf", 44)
        h_font = ImageFont.truetype("DejaVuSans.ttf", 28)
        body_font = ImageFont.truetype("DejaVuSans.ttf", 22)
        small_font = ImageFont.truetype("DejaVuSans.ttf", 18)
        tiny_font = ImageFont.truetype("DejaVuSans.ttf", 16)
    except Exception:
        title_font = h_font = body_font = small_font = tiny_font = ImageFont.load_default()

    y = margin

    # Logo
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            max_w, max_h = 800, 150
            lw, lh = logo.size
            scale = min(max_w / lw, max_h / lh, 1.0)
            logo = logo.resize((int(lw * scale), int(lh * scale)))
            lx = (W - logo.size[0]) // 2
            img.paste(logo, (lx, y), logo)
            y += logo.size[1] + 10
        except Exception:
            pass

    # Store name intentionally omitted (logo should carry branding)

    # Title
    draw.text((W // 2, y), "Custom Jewelry Quote", font=title_font, anchor="ma", fill="black")
    y += 70

    h = quote_doc.get("header", {}) or {}
    draw.text((margin, y), f"Customer: {h.get('customer_name') or '—'}", font=body_font, fill="black")
    right = f"Quote #: {h.get('quote_id','—')} {h.get('version','')}".strip()
    draw.text((W - margin, y), f"{right}   Date: {h.get('quote_date','')}", font=body_font, anchor="ra", fill="black")
    y += 38

    if h.get("job_desc"):
        draw.text((margin, y), f"Job: {h.get('job_desc')}", font=small_font, fill="black")
        y += 28

    if customer_view:
        paths = [p for p in (quote_doc.get("images", []) or []) if p and os.path.exists(p)]
        if paths:
            # 1 page grid, up to 6 images
            max_imgs = int((settings.get("output", {}) or {}).get("max_images_on_customer_page", 6) or 6)
            paths = paths[:max_imgs]
            cols = 3
            cell = 260
            gap = 18
            rows = int(math.ceil(len(paths) / cols))
            rows = min(rows, 2)
            grid_w = cols * cell + (cols - 1) * gap
            start_x = (W - grid_w) // 2
            y0 = y + 6

            for idx, p in enumerate(paths):
                r = idx // cols
                ccol = idx % cols
                if r >= rows:
                    break
                x = start_x + ccol * (cell + gap)
                top = y0 + r * (cell + gap)
                draw.rectangle((x, top, x + cell, top + cell), outline="black", width=2)
                try:
                    ph = Image.open(p).convert("RGBA")
                    ph.thumbnail((cell, cell))
                    box = Image.new("RGBA", (cell, cell), (255, 255, 255, 0))
                    px = (cell - ph.size[0]) // 2
                    py = (cell - ph.size[1]) // 2
                    box.paste(ph, (px, py), ph)
                    img.paste(box, (x, top), box)
                except Exception:
                    pass

            y = y0 + rows * cell + (rows - 1) * gap + 30

    # Shared line items (condensed)
    draw.text((margin, y), "Line items (excluding metal)", font=h_font, fill="black")
    y += 36
    draw.line((margin, y, W - margin, y), width=3, fill="black")
    y += 16

    shared = quote_doc.get("shared_line_items", []) or []
    for li in shared[:8]:
        label = li.get("label", "")
        amt = float(li.get("amount", 0.0) or 0.0)
        draw.text((margin, y), label, font=small_font, fill="black")
        draw.text((W - margin, y), _money0(amt), font=small_font, anchor="ra", fill="black")
        y += 24

    if len(shared) > 8:
        draw.text((margin, y), "… (more items in PDF)", font=tiny_font, fill="black")
        y += 20

    y += 10

    # Metal options (condensed)
    draw.text((margin, y), "Metal options", font=h_font, fill="black")
    y += 36
    draw.line((margin, y, W - margin, y), width=3, fill="black")
    y += 16

    options = quote_doc.get("metal_options", []) or []
    for opt in options[:5]:
        mk = opt.get("metal_key", "")
        metal_price = float(opt.get("metal_amount", 0.0) or 0.0)
        total = float(opt.get("total_with_tax", 0.0) or 0.0)
        dep = float(opt.get("deposit", 0.0) or 0.0)
        draw.text((margin, y), f"{mk}", font=small_font, fill="black")
        draw.text((W - margin, y), f"Total: {_money2(total)}   Deposit: {_money2(dep)}", font=small_font, anchor="ra", fill="black")
        y += 26
        draw.text((margin + 20, y), f"Metal: {_money0(metal_price)}", font=tiny_font, fill="black")
        y += 22

    img.save(out_path, "PNG")
