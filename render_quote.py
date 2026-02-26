
import os, datetime
from typing import Optional, Dict, Any, List
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader

from PIL import Image, ImageDraw, ImageFont

def _money(x: float) -> str:
    return f"${x:,.0f}"

def render_pdf(quote: Dict[str, Any], settings: Dict[str, Any], out_path: str, logo_path: Optional[str]=None, customer_view: bool=True) -> None:
    c = canvas.Canvas(out_path, pagesize=letter)
    W, H = letter

    # Slightly tighter margins for better printer compatibility on most office printers.
    margin = 0.65 * inch
    y = H - margin

    # Header with logo (centered)
    store = settings.get("store", {}) or {}
    store_name = store.get("name", "") or ""
    store_phone = store.get("phone", "") or ""
    store_email = store.get("email", "") or ""
    store_address = store.get("address", "") or ""
    top_y = y

    logo_draw_h = 0.0
    if logo_path and os.path.exists(logo_path):
        try:
            img = ImageReader(logo_path)
            # Fit logo into 1.2" height max, 6.0" width max
            max_w, max_h = 6.0*inch, 1.2*inch
            iw, ih = img.getSize()
            scale = min(max_w/iw, max_h/ih)
            draw_w, draw_h = iw*scale, ih*scale
            logo_x = (W - draw_w) / 2
            c.drawImage(img, logo_x, y - draw_h, width=draw_w, height=draw_h, mask='auto')
            logo_draw_h = draw_h
        except Exception:
            pass

    # Optional store info under logo
    info_y = y - (logo_draw_h + 0.18*inch)
    if store_name:
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(W/2, info_y, store_name)
        info_y -= 0.18*inch

    contact_line = "  ".join([s for s in [store_phone, store_email] if s])
    if contact_line:
        c.setFont("Helvetica", 9)
        c.drawCentredString(W/2, info_y, contact_line)
        info_y -= 0.16*inch
    if store_address:
        c.setFont("Helvetica", 9)
        c.drawCentredString(W/2, info_y, store_address)
        info_y -= 0.16*inch

    # Move cursor below logo/info block
    y = info_y - 0.10*inch

    # Photo under logo (centered)
    photo_path = quote.get("photo_path", "")
    if photo_path and os.path.exists(photo_path):
        try:
            img2 = ImageReader(photo_path)
            photo_size = 2.25 * inch
            photo_x = (W - photo_size) / 2
            photo_y = y - photo_size
            c.rect(photo_x, photo_y, photo_size, photo_size, stroke=1, fill=0)
            c.drawImage(img2, photo_x, photo_y, width=photo_size, height=photo_size, preserveAspectRatio=True, anchor="c")
            y = photo_y - 0.35*inch
        except Exception:
            pass

    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(W/2, y, "Custom Jewelry Quote")
    y -= 0.45*inch


    # Customer block
    c.setFont("Helvetica", 11)
    quote_no = quote.get("quote_number", "") or "—"
    c.drawString(margin, y, f"Customer: {quote.get('customer_name','') or '—'}")
    c.drawRightString(W - margin, y, f"Quote #: {quote_no}   Date: {quote.get('quote_date','')}")
    y -= 0.28*inch

    valid_until = quote.get("valid_until", "")
    if valid_until:
        c.setFont("Helvetica", 10)
        c.drawString(margin, y, f"Valid until: {valid_until}")
        y -= 0.26*inch
        c.setFont("Helvetica", 11)

    if quote.get("job_name"):
        c.drawString(margin, y, f"Job: {quote.get('job_name')}")
        y -= 0.28*inch

    if (not customer_view) and quote.get("notes"):
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(margin, y, "Notes (internal):")
        y -= 0.18*inch
        c.setFont("Helvetica", 10)
        for line in _wrap_text(str(quote["notes"]), 95):
            c.drawString(margin, y, line)
            y -= 0.16*inch
        y -= 0.10*inch


    # Line items table
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Line items")
    y -= 0.22*inch
    c.setLineWidth(1)
    c.line(margin, y, W - margin, y)
    y -= 0.18*inch

    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, y, "Description")
    c.drawRightString(W - margin, y, "Amount")
    y -= 0.18*inch
    c.setLineWidth(0.5)
    c.line(margin, y, W - margin, y)
    y -= 0.20*inch

    c.setFont("Helvetica", 10)
    for li in quote["line_items"]:
        if y < margin + 2.0*inch:
            c.showPage()
            y = H - margin
        c.drawString(margin, y, li["label"])
        c.drawRightString(W - margin, y, _money(li["amount"]))
        y -= 0.20*inch

        # optional trim details
        details = li.get("details")
        if details:
            c.setFont("Helvetica", 9)
            for (mm, qty, total_ct, retail_per_ct, price) in details:
                if y < margin + 1.6*inch:
                    c.showPage()
                    y = H - margin
                c.drawString(margin + 0.2*inch, y, f"• {mm:g}mm x {qty}  ({total_ct:.3f}ct)") if customer_view else c.drawString(margin + 0.2*inch, y, f"• {mm:g}mm x {qty}  ({total_ct:.3f}ct @ ${retail_per_ct:,.0f}/ct)")
                c.drawRightString(W - margin, y, _money(price))
                y -= 0.18*inch
            c.setFont("Helvetica", 10)

    y -= 0.05*inch
    c.setLineWidth(0.8)
    c.line(margin, y, W - margin, y)
    y -= 0.30*inch

    # Totals
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(W - margin, y, f"Subtotal: {_money(quote['subtotal'])}")
    y -= 0.24*inch
    c.setFont("Helvetica", 11)
    c.drawRightString(W - margin, y, f"Sales tax ({quote['tax_rate']*100:.2f}%): {_money(quote['tax'])}")
    y -= 0.24*inch
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(W - margin, y, f"Total  {_money(quote['total'])}")
    y -= 0.35*inch

    c.setFont("Helvetica", 11)
    c.drawRightString(W - margin, y, f"Deposit due today ({quote['deposit_rate']*100:.0f}%): {_money(quote['deposit'])}")

    # Footer (keep within printable area)
    c.setFont("Helvetica-Oblique", 9)
    valid_days = int(quote.get('valid_days', 14) or 14)
    valid_until = quote.get('valid_until', '')
    footer = f"Quote valid for {valid_days} days" + (f" (valid until {valid_until})" if valid_until else "")
    footer += ". Prices subject to change due to metal market and stone availability. Total rounded to nearest $5."
    c.drawString(margin, 0.50*inch, footer)

    c.save()

def _wrap_text(text: str, max_chars: int) -> List[str]:
    words = text.replace("\n", " ").split()
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

def render_png(quote: Dict[str, Any], settings: Dict[str, Any], out_path: str, logo_path: Optional[str]=None, customer_view: bool=True) -> None:
    # 8.5x11 at 150 DPI => 1275x1650
    W, H = 1275, 1650
    margin = 90
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    # Fonts (fallback-safe)
    font_dir = os.path.join(os.path.dirname(__file__), "assets")
    try:
        title_font = ImageFont.truetype("DejaVuSans.ttf", 44)
        h_font = ImageFont.truetype("DejaVuSans.ttf", 28)
        body_font = ImageFont.truetype("DejaVuSans.ttf", 22)
        small_font = ImageFont.truetype("DejaVuSans.ttf", 18)
    except Exception:
        title_font = h_font = body_font = small_font = ImageFont.load_default()

    y = margin

    # Logo (centered)
    store = settings.get("store", {}) or {}
    store_name = store.get("name", "") or ""
    store_phone = store.get("phone", "") or ""
    store_email = store.get("email", "") or ""
    store_address = store.get("address", "") or ""

    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            max_w, max_h = 800, 150
            lw, lh = logo.size
            scale = min(max_w/lw, max_h/lh, 1.0)
            logo = logo.resize((int(lw*scale), int(lh*scale)))
            lx = (W - logo.size[0]) // 2
            img.paste(logo, (lx, y), logo)
            y += logo.size[1] + 10
        except Exception:
            pass

    if store_name:
        draw.text((W//2, y), store_name, font=body_font, anchor="ma", fill="black")
        y += 36

    contact_line = "  ".join([s for s in [store_phone, store_email] if s])
    if contact_line:
        draw.text((W//2, y), contact_line, font=small_font, anchor="ma", fill="black")
        y += 26
    if store_address:
        draw.text((W//2, y), store_address, font=small_font, anchor="ma", fill="black")
        y += 26

    # Photo under logo (centered)
    photo_path = quote.get("photo_path", "")
    if photo_path and os.path.exists(photo_path):
        try:
            photo = Image.open(photo_path).convert("RGBA")
            size = 340
            photo.thumbnail((size, size))
            # paste centered into a square box
            box = Image.new("RGBA", (size, size), (255,255,255,0))
            px = (size - photo.size[0]) // 2
            py = (size - photo.size[1]) // 2
            box.paste(photo, (px, py), photo)
            bx = (W - size) // 2
            img.paste(box, (bx, y), box)
            # border
            draw.rectangle((bx, y, bx+size, y+size), outline="black", width=2)
            y += size + 22
        except Exception:
            pass

    draw.text((W//2, y), "Custom Jewelry Quote", font=title_font, anchor="ma", fill="black")
    y += 70


    quote_no = quote.get("quote_number","") or "—"
    draw.text((margin, y), f"Customer: {quote.get('customer_name','') or '—'}", font=body_font, fill="black")
    draw.text((W - margin, y), f"Quote #: {quote_no}   Date: {quote.get('quote_date','')}", font=body_font, anchor="ra", fill="black")
    y += 40

    valid_until = quote.get("valid_until", "")
    if valid_until:
        draw.text((margin, y), f"Valid until: {valid_until}", font=small_font, fill="black")
        y += 30

    if quote.get("job_name"):
        draw.text((margin, y), f"Job: {quote.get('job_name')}", font=body_font, fill="black")
        y += 40

    if (not customer_view) and quote.get("notes"):
        draw.text((margin, y), "Notes:", font=small_font, fill="black")
        y += 28
        for line in _wrap_text(str(quote["notes"]), 92):
            draw.text((margin, y), line, font=small_font, fill="black")
            y += 22
        y += 10

    # Table header
    draw.text((margin, y), "Line items", font=h_font, fill="black")
    y += 40
    draw.line((margin, y, W - margin, y), width=3, fill="black")
    y += 18
    draw.text((margin, y), "Description", font=body_font, fill="black")
    draw.text((W - margin, y), "Amount", font=body_font, anchor="ra", fill="black")
    y += 32
    draw.line((margin, y, W - margin, y), width=2, fill="black")
    y += 18

    for li in quote["line_items"]:
        draw.text((margin, y), li["label"], font=body_font, fill="black")
        draw.text((W - margin, y), _money(li["amount"]), font=body_font, anchor="ra", fill="black")
        y += 34
        details = li.get("details")
        if details:
            for (mm, qty, total_ct, retail_per_ct, price) in details:
                draw.text((margin + 20, y), f"• {mm:g}mm x {qty} ({total_ct:.3f}ct)" if customer_view else f"• {mm:g}mm x {qty} ({total_ct:.3f}ct @ ${retail_per_ct:,.0f}/ct)", font=small_font, fill="black")
                draw.text((W - margin, y), _money(price), font=small_font, anchor="ra", fill="black")
                y += 26
            y += 6

    y += 8
    draw.line((margin, y, W - margin, y), width=3, fill="black")
    y += 30

    draw.text((W - margin, y), f"Subtotal: {_money(quote['subtotal'])}", font=body_font, anchor="ra", fill="black")
    y += 34
    draw.text((W - margin, y), f"Sales tax ({quote['tax_rate']*100:.2f}%): {_money(quote['tax'])}", font=body_font, anchor="ra", fill="black")
    y += 34
    draw.text((W - margin, y), f"Total (rounded to nearest $5): {_money(quote['total'])}", font=title_font, anchor="ra", fill="black")
    y += 54
    draw.text((W - margin, y), f"Deposit due today ({quote['deposit_rate']*100:.0f}%): {_money(quote['deposit'])}", font=body_font, anchor="ra", fill="black")
    y += 50


    valid_days = int(quote.get('valid_days', 14) or 14)
    valid_until = quote.get('valid_until', '')
    footer = f"Quote valid for {valid_days} days" + (f" (valid until {valid_until})" if valid_until else "")
    footer += ". Prices subject to change due to metal market and stone availability. Total rounded to nearest $5."
    # Bottom footer inside print-safe area
    draw.text((margin, H - margin + 10), footer, font=small_font, fill="black")

    img.save(out_path, "PNG")
