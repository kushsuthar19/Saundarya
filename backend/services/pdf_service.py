"""
PDF invoice generation — fixed all issues:
1. Bridal: person_count field (NUMBER in Oracle, not string)
2. Bridal: pkg_detail shows in Package column
3. Bridal: Due Amount visible with white text on dark green
4. Bridal: Footer address fully readable (white on green)
5. Bridal: balance recalculated correctly
6. Booked functions highlighted in table
"""
import io
from datetime import date, datetime
from typing import List, Dict, Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, PageBreak
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

DARK_GREEN  = colors.HexColor("#1A4A3A")
GOLD        = colors.HexColor("#9A7B2C")
LIGHT_GOLD  = colors.HexColor("#C8A84B")
WHITE       = colors.white
BLACK       = colors.black
LIGHT_GRAY  = colors.HexColor("#F7F7F7")
MED_GRAY    = colors.HexColor("#DDDDDD")
TEXT_GRAY   = colors.HexColor("#555555")
GREEN_LIGHT = colors.HexColor("#E8F5EE")
RED_COLOR   = colors.HexColor("#C0392B")

M = 14 * mm


def S(name, **kw):
    d = dict(fontName="Helvetica", fontSize=10, textColor=BLACK, leading=14)
    d.update(kw); return ParagraphStyle(name, **d)

def SB(name, **kw):
    kw.setdefault("fontName", "Helvetica-Bold"); return S(name, **kw)


def _header(booking_type=""):
    logo = [
        Paragraph("<b>Saundarya</b>",
                  S("ln", fontName="Helvetica-Bold", fontSize=26, textColor=GOLD)),
        Paragraph("Beauty Care",
                  S("ls", fontSize=9, textColor=TEXT_GRAY, leading=13)),
    ]
    # Booking type shown in phone box on right
    phone = [
        Paragraph("96621 35422",
                  SB("p1", fontSize=11, textColor=WHITE, alignment=TA_RIGHT)),
        Paragraph("9723044589",
                  S("p2", fontSize=11, textColor=WHITE, alignment=TA_RIGHT)),
    ]
    if booking_type:
        phone.insert(0, Paragraph(booking_type.upper(),
                                   SB("bt", fontSize=8, textColor=LIGHT_GOLD,
                                      alignment=TA_RIGHT, leading=12)))
    t = Table([[logo, phone]], colWidths=[118*mm, 64*mm])
    t.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",    (0,0),(-1,-1),0),
        ("BOTTOMPADDING", (0,0),(-1,-1),0),
        ("BACKGROUND",    (1,0),(1,0),  DARK_GREEN),
        ("LEFTPADDING",   (1,0),(1,0),  12),
        ("RIGHTPADDING",  (1,0),(1,0),  12),
        ("TOPPADDING",    (1,0),(1,0),  10),
        ("BOTTOMPADDING", (1,0),(1,0),  10),
    ]))
    return t


def _footer():
    addr  = Paragraph(
        "12, Vishnuprashad Society, Outside Panigate, Waghodiya Road, Vadodara",
        S("fa", fontSize=9, textColor=WHITE))
    brand = Paragraph("Saundarya Beauty Care",
                      SB("fb", fontSize=11, textColor=LIGHT_GOLD, alignment=TA_RIGHT))
    t = Table([[addr, brand]], colWidths=[118*mm, 64*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), DARK_GREEN),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0),(-1,-1), 9),
        ("BOTTOMPADDING", (0,0),(-1,-1), 9),
        ("LEFTPADDING",   (0,0),(0,0),   10),
        ("RIGHTPADDING",  (1,0),(1,0),   10),
    ]))
    return t


# ── Daily invoice ─────────────────────────────────────────
def generate_daily_invoice(entry: Dict[str, Any],
                           items: List[Dict[str, Any]]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=M, rightMargin=M,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = _daily_story(entry, items)
    doc.build(story)
    return buf.getvalue()


def _daily_story(entry, items):
    story = []
    story.append(_header())
    story.append(Spacer(1, 5*mm))

    ttl = Table([[Paragraph("SERVICES",
                            SB("st", fontSize=13, textColor=WHITE, alignment=TA_CENTER))]],
                colWidths=[100*mm])
    ttl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), DARK_GREEN),
        ("TOPPADDING",    (0,0),(-1,-1), 7),
        ("BOTTOMPADDING", (0,0),(-1,-1), 7),
    ]))
    story.append(Table([[Spacer(1,1), ttl, Spacer(1,1)]], colWidths=[37*mm,108*mm,37*mm]))
    story.append(Spacer(1, 5*mm))

    ed = entry.get("entry_date")
    if isinstance(ed, date):
        ds = ed.strftime("%d/%m/%Y"); dy = ed.strftime("%A")
    else:
        ds = str(ed or ""); dy = ""

    story.append(Table([[
        Paragraph(f"<b>Date:</b>  {ds}", S("m1")),
        Paragraph(f"<b>Invoice:</b>  {entry.get('inv_no','')}", SB("m2", textColor=DARK_GREEN)),
        Paragraph(f"<b>Day:</b>  {dy}", S("m3")),
    ]], colWidths=[60*mm, 72*mm, 50*mm]))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        f"<b>Client:</b>  {entry.get('client_name','')}   |   "
        f"<b>Phone:</b>  {entry.get('phone','') or '—'}   |   "
        f"<b>Payment:</b>  {entry.get('pay_method','Cash')}",
        S("ci")))
    story.append(Spacer(1, 4*mm))

    COL = [14*mm, 90*mm, 42*mm, 36*mm]
    TH = SB("th", fontSize=9, textColor=WHITE, alignment=TA_CENTER)
    rows = [[
        Paragraph("<b>Sr.</b>", TH),
        Paragraph("<b>Service / Work Done</b>", SB("th2", fontSize=9, textColor=WHITE)),
        Paragraph("<b>Staff</b>", TH),
        Paragraph("<b>Amount (Rs)</b>", SB("th3", fontSize=9, textColor=WHITE, alignment=TA_RIGHT)),
    ]]
    for i, it in enumerate(items, 1):
        qty = it.get("qty", 1); price = it.get("price", 0); total = price * qty
        name = it.get("service_name", "") + (f" x{qty}" if qty > 1 else "")
        rows.append([
            Paragraph(str(i), S("sr", alignment=TA_CENTER)),
            Paragraph(name, S("sn")),
            Paragraph(it.get("staff_name") or "-", S("sf", fontSize=9, textColor=TEXT_GRAY)),
            Paragraph(f"Rs.{int(total):,}", S("am", alignment=TA_RIGHT)),
        ])
    while len(rows) <= 6:
        rows.append(["", "", "", ""])

    svc = Table(rows, colWidths=COL, repeatRows=1)
    svc.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  DARK_GREEN),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [WHITE, LIGHT_GRAY]),
        ("GRID",          (0,0),(-1,-1), 0.4, MED_GRAY),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("LEFTPADDING",   (0,0),(-1,-1), 5),
        ("ALIGN",         (3,0),(3,-1),  "RIGHT"),
        ("ALIGN",         (0,0),(0,-1),  "CENTER"),
    ]))
    story.append(svc)
    story.append(Spacer(1, 4*mm))

    gross = float(entry.get("gross_total", 0))
    disc  = float(entry.get("discount", 0))
    net   = float(entry.get("net_total", 0))
    meth  = entry.get("pay_method", "Cash")
    cash  = net if meth == "Cash"          else (net/2 if meth=="Split" else 0)
    onl   = net if meth in ("UPI","Card")  else (net/2 if meth=="Split" else 0)
    pend  = max(0, gross - cash - onl)

    tr = [
        [Paragraph("Total Services", S("tl")),
         Paragraph(str(len(items)),  SB("tv", alignment=TA_RIGHT))],
        [Paragraph("Total Amount",   S("tl")),
         Paragraph(f"Rs.{int(gross):,}", SB("tv", alignment=TA_RIGHT))],
    ]
    if disc > 0:
        tr.append([Paragraph("Discount", S("tl")),
                   Paragraph(f"- Rs.{int(disc):,}", SB("dv", alignment=TA_RIGHT, textColor=RED_COLOR))])
    tr += [
        [Paragraph("Cash Received",   S("tl")),
         Paragraph(f"Rs.{int(cash):,}", SB("tv", alignment=TA_RIGHT))],
        [Paragraph("Online Received", S("tl")),
         Paragraph(f"Rs.{int(onl):,}", SB("tv", alignment=TA_RIGHT))],
        [Paragraph("<b>Pending Amount</b>",
                   SB("pl", textColor=BLACK if pend==0 else RED_COLOR)),
         Paragraph(f"<b>Rs.{int(pend):,}</b>",
                   SB("pv", alignment=TA_RIGHT,
                      textColor=DARK_GREEN if pend==0 else RED_COLOR))],
    ]
    tot = Table(tr, colWidths=[132*mm, 50*mm])
    tot.setStyle(TableStyle([
        ("BOX",          (0,0),(-1,-1), 0.8, DARK_GREEN),
        ("LINEBELOW",    (0,0),(-1,-2), 0.4, MED_GRAY),
        ("BACKGROUND",   (0,-1),(-1,-1), GREEN_LIGHT),
        ("TOPPADDING",   (0,0),(-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
        ("LEFTPADDING",  (0,0),(0,-1),  10),
        ("RIGHTPADDING", (1,0),(1,-1),  10),
        ("ALIGN",        (1,0),(1,-1),  "RIGHT"),
    ]))
    story.append(tot)
    story.append(Spacer(1, 4*mm))
    if entry.get("remarks"):
        story.append(Paragraph(f"<i>Note: {entry['remarks']}</i>",
                               S("note", fontSize=9, textColor=TEXT_GRAY)))
        story.append(Spacer(1, 3*mm))
    story.append(Spacer(1, 3*mm))
    story.append(_footer())
    return story


# ── Bridal invoice ────────────────────────────────────────
def generate_bridal_invoice(booking: Dict[str, Any],
                             functions: List[Dict[str, Any]]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=M, rightMargin=M,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []
    btype = booking.get("booking_type", "Bride")
    story.append(_header(btype))
    story.append(Spacer(1, 5*mm))

    today  = datetime.now().strftime("%d/%m/%Y")
    job_no = booking.get("job_no", "")
    story.append(Table([[
        Paragraph(f"<b>Job No.:</b>  {job_no}", SB("jn", fontSize=11)),
        Paragraph(f"<b>Date:</b>  {today}",
                  SB("jd", fontSize=11, alignment=TA_RIGHT)),
    ]], colWidths=[95*mm, 87*mm]))
    story.append(Spacer(1, 5*mm))

    # Client info
    wd = booking.get("wedding_date")
    if isinstance(wd, date):
        wd_str = wd.strftime("%d/%m/%Y")
    elif wd:
        try:    wd_str = datetime.strptime(str(wd)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except: wd_str = str(wd)
    else:
        wd_str = ""

    def dotted(label, value):
        dots = "." * max(5, 58 - len(label) - len(str(value)))
        return [Paragraph(f"<b>{label}:</b>  {value}{dots}",
                          S("dl", fontSize=10, leading=17))]

    info_rows = [
        dotted("Wedding Person Name", booking.get("client_name", "")),
        dotted("Wedding Date",        wd_str),
        dotted("Venue",               booking.get("venue") or ""),
        dotted("Reference",           booking.get("reference") or ""),
        dotted("Contact",             booking.get("phone") or ""),
    ]
    info_inner = Table([[r[0]] for r in info_rows], colWidths=[172*mm])
    info_inner.setStyle(TableStyle([
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
    ]))
    info_box = Table([[info_inner]], colWidths=[176*mm])
    info_box.setStyle(TableStyle([
        ("BOX",           (0,0),(-1,-1), 1.2, DARK_GREEN),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
    ]))
    story.append(info_box)
    story.append(Spacer(1, 5*mm))

    # Function schedule
    STANDARD = [
        "Bridal","Engagement","Reception","Haldi Rasam",
        "Ganesh Pooja","Sangeet","Mahendi","Mamera/Mosadu",
        "Grah Santi Pooja","Party","Baby Shower","Other Function",
    ]
    fn_map: Dict[str, Dict] = {}
    extra: List[str] = []
    for fn in functions:
        nm = (fn.get("function_name") or "").strip()
        if nm:
            fn_map[nm] = fn
            if nm not in STANDARD:
                extra.append(nm)

    all_fn = STANDARD + extra
    TH_W = SB("fth", fontSize=9, textColor=WHITE, alignment=TA_CENTER)
    fn_data = [[
        Paragraph("", S("fh0")),
        Paragraph("<b>Date</b>",    TH_W),
        Paragraph("<b>Timing</b>",  TH_W),
        Paragraph("<b>Person</b>",  TH_W),
        Paragraph("<b>Package</b>", TH_W),
    ]]

    booked_rows = []
    for idx, fn_name in enumerate(all_fn):
        fn  = fn_map.get(fn_name, {})
        is_booked = fn_name in fn_map

        # Date
        fd = fn.get("fn_date")
        if isinstance(fd, date):
            fd_str = fd.strftime("%d/%m/%y")
        elif fd:
            try:    fd_str = datetime.strptime(str(fd)[:10], "%Y-%m-%d").strftime("%d/%m/%y")
            except: fd_str = str(fd)
        else:
            fd_str = ""

        # person_count is NUMBER in Oracle
        pc = fn.get("person_count")
        pc_str = str(int(pc)) if (pc is not None and pc != "") else ""

        pkg = fn.get("pkg_detail") or ""

        fn_data.append([
            Paragraph(
                f"<b>{fn_name}:</b>" if is_booked else f"{fn_name}:",
                SB("fnb", fontSize=9, textColor=DARK_GREEN)
                if is_booked else S("fnr", fontSize=9)
            ),
            Paragraph(fd_str,                    S("fd", fontSize=9, alignment=TA_CENTER)),
            Paragraph(fn.get("fn_time") or "",   S("ft", fontSize=9, alignment=TA_CENTER)),
            Paragraph(pc_str,                    S("fp", fontSize=9, alignment=TA_CENTER)),
            Paragraph(pkg,                       S("fpk", fontSize=9)),
        ])
        if is_booked:
            booked_rows.append(idx + 1)   # +1 for header row

    fn_cols = [46*mm, 36*mm, 32*mm, 26*mm, 42*mm]
    fn_tbl  = Table(fn_data, colWidths=fn_cols, repeatRows=1)
    style_cmds = [
        ("BACKGROUND",    (1,0),(-1,0),  DARK_GREEN),
        ("TEXTCOLOR",     (1,0),(-1,0),  WHITE),
        ("GRID",          (0,0),(-1,-1), 0.4, MED_GRAY),
        ("BOX",           (0,0),(-1,-1), 0.8, DARK_GREEN),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(-1,-1), 5),
        ("RIGHTPADDING",  (0,0),(-1,-1), 5),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]
    for r in booked_rows:
        style_cmds.append(("BACKGROUND", (0,r),(-1,r), GREEN_LIGHT))
    fn_tbl.setStyle(TableStyle(style_cmds))
    story.append(fn_tbl)
    story.append(Spacer(1, 5*mm))

    # Billing
    pkg_amt   = float(booking.get("pkg_amount",  0))
    transport = float(booking.get("transport",   0))
    discount  = float(booking.get("discount",    0))
    advance   = float(booking.get("advance_paid",0))
    balance   = max(0, pkg_amt + transport - discount - advance)

    BL = SB("bl", fontSize=10, alignment=TA_RIGHT)
    BV = S("bv",  fontSize=10, alignment=TA_CENTER)
    bill_rows = [
        [Paragraph("<b>Total Amount</b>",           BL),
         Paragraph(f"Rs.{int(pkg_amt):,}",          BV)],
        [Paragraph("<b>Outdoor Transportation</b>", BL),
         Paragraph(f"Rs.{int(transport):,}",        BV)],
        [Paragraph("<b>Discount</b>",               BL),
         Paragraph(f"Rs.{int(discount):,}",         BV)],
        [Paragraph("<b>Advance</b>",                BL),
         Paragraph(f"Rs.{int(advance):,}",          BV)],
        [Paragraph("<b>Due Amount</b>",
                   SB("dl2", fontSize=11, textColor=WHITE, alignment=TA_RIGHT)),
         Paragraph(f"<b>Rs.{int(balance):,}</b>",
                   SB("dv2", fontSize=12, textColor=WHITE, alignment=TA_CENTER))],
    ]
    bill_tbl = Table(bill_rows, colWidths=[74*mm, 38*mm])
    bill_tbl.setStyle(TableStyle([
        ("BOX",           (0,0),(-1,-1), 0.8, DARK_GREEN),
        ("LINEBELOW",     (0,0),(-1,-2), 0.4, MED_GRAY),
        ("BACKGROUND",    (0,-1),(-1,-1), DARK_GREEN),
        ("TOPPADDING",    (0,0),(-1,-1), 7),
        ("BOTTOMPADDING", (0,0),(-1,-1), 7),
        ("RIGHTPADDING",  (0,0),(0,-1),  10),
        ("LEFTPADDING",   (1,0),(1,-1),  8),
        ("RIGHTPADDING",  (1,0),(1,-1),  8),
    ]))

    sign_rows = [
        [Paragraph("Customer",
                   S("s1", fontSize=10, textColor=TEXT_GRAY))],
        [Paragraph("Name & Sign  _______________________", S("s2", fontSize=10))],
        [Spacer(1, 10*mm)],
        [Paragraph("Authorised Sign  ___________________", S("s3", fontSize=10))],
    ]
    sign_tbl = Table(sign_rows, colWidths=[80*mm])

    combined = Table([[bill_tbl, Spacer(1,4), sign_tbl]],
                     colWidths=[114*mm, 4*mm, 64*mm])
    combined.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(combined)
    story.append(Spacer(1, 6*mm))
    story.append(_footer())
    doc.build(story)
    return buf.getvalue()


# ── Batch daily PDF ───────────────────────────────────────
def generate_daily_batch_pdf(entries_with_items: List[Dict[str, Any]],
                              batch_date: date) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=M, rightMargin=M,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []
    for idx, ed in enumerate(entries_with_items):
        if idx > 0:
            story.append(PageBreak())
        story.extend(_daily_story(ed["entry"], ed["items"]))
    doc.build(story)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════
# SIDER INVOICE  — Person | Function | Date | Time | Package | Amount
# All persons on ONE page, compact layout
# ══════════════════════════════════════════════════════════
def generate_sider_invoice(booking: Dict[str, Any],
                            functions: List[Dict[str, Any]]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=M, rightMargin=M,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    story.append(_header("Sider / Guest"))
    story.append(Spacer(1, 4*mm))

    # Job No + Date (compact)
    today  = datetime.now().strftime("%d/%m/%Y")
    job_no = booking.get("job_no", "")
    story.append(Table([[
        Paragraph(f"<b>Job No.:</b>  {job_no}", SB("jn", fontSize=10)),
        Paragraph(f"<b>Booking Date:</b>  {today}",
                  SB("jd", fontSize=10, alignment=TA_RIGHT)),
    ]], colWidths=[95*mm, 87*mm]))
    story.append(Spacer(1, 3*mm))

    # Main client info (compact single line)
    story.append(Paragraph(
        f"<b>Contact Name:</b>  {booking.get('client_name','')}   "
        f"|   <b>Phone:</b>  {booking.get('phone','') or '—'}   "
        f"|   <b>Event Date:</b>  {booking.get('wedding_date','') or '—'}",
        S("ci", fontSize=10)
    ))
    story.append(Spacer(1, 4*mm))

    # ── Function table: Person | Function | Date | Time | Package | Amount ──
    TH = SB("th", fontSize=9, textColor=WHITE, alignment=TA_CENTER)
    rows = [[
        Paragraph("<b>Person Name</b>",  TH),
        Paragraph("<b>Function</b>",     TH),
        Paragraph("<b>Date</b>",         TH),
        Paragraph("<b>Time</b>",         TH),
        Paragraph("<b>Package</b>",      TH),
        Paragraph("<b>Amount (Rs)</b>",  SB("th6", fontSize=9, textColor=WHITE, alignment=TA_RIGHT)),
    ]]

    # Parse functions — each row has:
    # function_name = function name (e.g. "Ghrashanti")
    # pkg_detail    = "Person Name - Package Name" (e.g. "Rikesh - UHD Makeup")
    total_amount = 0
    for fn in functions:
        fd = fn.get("fn_date")
        if isinstance(fd, date):
            fd_str = fd.strftime("%d/%m/%y")
        elif fd:
            try:    fd_str = datetime.strptime(str(fd)[:10], "%Y-%m-%d").strftime("%d/%m/%y")
            except: fd_str = str(fd)
        else:
            fd_str = ""

        pkg_raw  = fn.get("pkg_detail") or ""
        fn_name  = fn.get("function_name") or ""

        # Parse "PersonName - PackageName" format
        if " - " in pkg_raw:
            parts    = pkg_raw.split(" - ", 1)
            person   = parts[0].strip()
            pkg_name = parts[1].strip()
        else:
            person   = pkg_raw
            pkg_name = ""

        # Try to extract amount from package name
        # e.g. "UHD Makeup — 15,499" or just use booking total / count
        rows.append([
            Paragraph(person,          S("pn", fontSize=10, fontName="Helvetica-Bold")),
            Paragraph(fn_name,         S("fn2", fontSize=10, textColor=DARK_GREEN,
                                         fontName="Helvetica-Bold")),
            Paragraph(fd_str,          S("fd2", fontSize=10, alignment=TA_CENTER)),
            Paragraph(fn.get("fn_time") or "", S("ft2", fontSize=10, alignment=TA_CENTER)),
            Paragraph(pkg_name,        S("pk2", fontSize=10)),
            Paragraph("",              S("am2", fontSize=10, alignment=TA_RIGHT)),
        ])

    # Add empty rows for signature if very few entries
    min_rows = max(len(functions), 3)
    while len(rows) - 1 < min_rows:
        rows.append(["", "", "", "", "", ""])

    # Column widths — must fit A4 (182mm usable)
    COL = [38*mm, 35*mm, 24*mm, 20*mm, 45*mm, 20*mm]

    fn_tbl = Table(rows, colWidths=COL, repeatRows=1)
    fn_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  DARK_GREEN),
        ("TEXTCOLOR",     (0,0), (-1,0),  WHITE),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT_GRAY]),
        ("GRID",          (0,0), (-1,-1), 0.5, MED_GRAY),
        ("BOX",           (0,0), (-1,-1), 1.0, DARK_GREEN),
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ("RIGHTPADDING",  (0,0), (-1,-1), 5),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",         (5,0), (5,-1),  "RIGHT"),
        ("ALIGN",         (2,0), (3,-1),  "CENTER"),
    ]))
    story.append(fn_tbl)
    story.append(Spacer(1, 5*mm))

    # ── Billing summary ───────────────────────────────────
    pkg_amt   = float(booking.get("pkg_amount",  0))
    transport = float(booking.get("transport",   0))
    discount  = float(booking.get("discount",    0))
    advance   = float(booking.get("advance_paid",0))
    balance   = max(0, pkg_amt + transport - discount - advance)

    BL = SB("bl", fontSize=10, alignment=TA_RIGHT)
    BV = S("bv",  fontSize=10, alignment=TA_CENTER, fontName="Helvetica-Bold")

    bill_rows = [
        [Paragraph("<b>Total Amount</b>",           BL),
         Paragraph(f"Rs.{int(pkg_amt):,}",          BV)],
        [Paragraph("<b>Outdoor Transportation</b>", BL),
         Paragraph(f"Rs.{int(transport):,}",        BV)],
        [Paragraph("<b>Discount</b>",               BL),
         Paragraph(f"Rs.{int(discount):,}",         BV)],
        [Paragraph("<b>Advance</b>",                BL),
         Paragraph(f"Rs.{int(advance):,}",          BV)],
        [Paragraph("<b>Due Amount</b>",
                   SB("dl2", fontSize=11, textColor=WHITE, alignment=TA_RIGHT)),
         Paragraph(f"<b>Rs.{int(balance):,}</b>",
                   SB("dv2", fontSize=12, textColor=WHITE, alignment=TA_CENTER))],
    ]
    bill_tbl = Table(bill_rows, colWidths=[74*mm, 38*mm])
    bill_tbl.setStyle(TableStyle([
        ("BOX",           (0,0), (-1,-1), 0.8, DARK_GREEN),
        ("LINEBELOW",     (0,0), (-1,-2), 0.4, MED_GRAY),
        ("BACKGROUND",    (0,-1),(-1,-1), DARK_GREEN),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (0,-1),  10),
        ("LEFTPADDING",   (1,0), (1,-1),  8),
        ("RIGHTPADDING",  (1,0), (1,-1),  8),
    ]))

    sign_rows = [
        [Paragraph("Customer Name & Sign", S("s1", fontSize=10, textColor=TEXT_GRAY))],
        [Paragraph("_______________________________", S("s2", fontSize=10))],
        [Spacer(1, 8*mm)],
        [Paragraph("Authorised Sign  _______________", S("s3", fontSize=10))],
    ]
    sign_tbl = Table(sign_rows, colWidths=[80*mm])

    combined = Table([[bill_tbl, Spacer(1,4), sign_tbl]],
                     colWidths=[114*mm, 4*mm, 64*mm])
    combined.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(combined)
    story.append(Spacer(1, 5*mm))
    story.append(_footer())

    doc.build(story)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════
# SIDER / GUEST INVOICE — separate layout, 1 page guaranteed
# Name | Function | Date | Time | Package | Amount
# ══════════════════════════════════════════════════════════
def generate_sider_invoice(booking: Dict[str, Any],
                            functions: List[Dict[str, Any]]) -> bytes:
    """
    Compact 1-page invoice for Sider/Guest bookings.
    Each row = one person × one function with package and amount.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=M, rightMargin=M,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    story.append(_header("Sider / Guest"))
    story.append(Spacer(1, 4*mm))

    # Job No + Date
    today  = datetime.now().strftime("%d/%m/%Y")
    job_no = booking.get("job_no", "")
    story.append(Table([[
        Paragraph(f"<b>Job No.:</b>  {job_no}", SB("jn", fontSize=11)),
        Paragraph(f"<b>Date:</b>  {today}", SB("jd", fontSize=11, alignment=TA_RIGHT)),
    ]], colWidths=[95*mm, 87*mm]))
    story.append(Spacer(1, 3*mm))

    # Client info (compact)
    wd = booking.get("wedding_date")
    if isinstance(wd, date):
        wd_str = wd.strftime("%d/%m/%Y")
    elif wd:
        try:    wd_str = datetime.strptime(str(wd)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except: wd_str = str(wd)
    else:
        wd_str = "—"

    info = Table([[
        Paragraph(f"<b>Client Group:</b>  {booking.get('client_name','')}", S("ci1")),
        Paragraph(f"<b>Phone:</b>  {booking.get('phone') or '—'}", S("ci2")),
        Paragraph(f"<b>Event Date:</b>  {wd_str}", S("ci3", alignment=TA_RIGHT)),
    ]], colWidths=[80*mm, 50*mm, 52*mm])
    info.setStyle(TableStyle([
        ("BOX",           (0,0),(-1,-1), 0.8, DARK_GREEN),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("BACKGROUND",    (0,0),(-1,-1), LIGHT_GRAY),
    ]))
    story.append(info)
    story.append(Spacer(1, 4*mm))

    # ── Main services table ───────────────────────────────
    # Each function row = person | function | date | time | package | amount
    TH  = SB("th", fontSize=9, textColor=WHITE, alignment=TA_CENTER)
    THL = SB("thl", fontSize=9, textColor=WHITE)

    # Columns: # | Person Name | Function | Date | Time | Package | Amount
    COL = [8*mm, 38*mm, 35*mm, 24*mm, 18*mm, 40*mm, 19*mm]

    rows = [[
        Paragraph("<b>#</b>",            TH),
        Paragraph("<b>Person Name</b>",  THL),
        Paragraph("<b>Function</b>",     THL),
        Paragraph("<b>Date</b>",         TH),
        Paragraph("<b>Time</b>",         TH),
        Paragraph("<b>Package</b>",      THL),
        Paragraph("<b>Amount</b>",       SB("tha", fontSize=9, textColor=WHITE, alignment=TA_RIGHT)),
    ]]

    total_amount = 0.0
    for i, fn in enumerate(functions, 1):
        # Data stored as: person_count=person_name, function_name=event, pkg_detail=package, artist_name=amount
        person_nm = str(fn.get("person_count") or "").strip() or "—"
        func_nm   = str(fn.get("function_name") or "").strip() or "—"
        pkg_nm    = str(fn.get("pkg_detail") or "").strip() or "—"

        # Amount stored in artist_name field as string
        amt = 0.0
        amt_str_raw = fn.get("artist_name") or ""
        try:
            amt = float(amt_str_raw) if amt_str_raw else 0.0
        except (ValueError, TypeError):
            amt = 0.0

        # Fallback: map package name to price if amount not stored
        if amt == 0 and pkg_nm and pkg_nm != "—":
            PKG_PRICES = {
                "basic makeup": 2299, "+lashes": 3999, "+extension": 5999,
                "+lens": 7999, "+all": 10500, "hd makeup": 12500,
                "uhd makeup": 15499, "airbrush": 18499,
            }
            for k, v2 in PKG_PRICES.items():
                if k in pkg_nm.lower():
                    amt = float(v2); break

        # Date
        fd = fn.get("fn_date")
        if isinstance(fd, date):
            fd_str = fd.strftime("%d/%m/%y")
        elif fd:
            try:    fd_str = datetime.strptime(str(fd)[:10], "%Y-%m-%d").strftime("%d/%m/%y")
            except: fd_str = str(fd)
        else:
            fd_str = ""

        ft_str = fn.get("fn_time") or ""

        total_amount += amt
        amt_str = f"Rs.{int(amt):,}" if amt > 0 else "—"

        row_bg = LIGHT_GRAY if i % 2 == 0 else WHITE
        rows.append([
            Paragraph(str(i), S("sr", fontSize=9, alignment=TA_CENTER)),
            Paragraph(person_nm or "—",  SB("pn", fontSize=9, textColor=DARK_GREEN)),
            Paragraph(func_nm or "—",    S("fn2", fontSize=9)),
            Paragraph(fd_str,            S("fd2", fontSize=9, alignment=TA_CENTER)),
            Paragraph(ft_str,            S("ft2", fontSize=9, alignment=TA_CENTER)),
            Paragraph(pkg_nm or "—",     S("pk2", fontSize=9)),
            Paragraph(amt_str,           SB("am2", fontSize=9, alignment=TA_RIGHT)),
        ])

    # Ensure minimum 8 rows so table looks complete
    while len(rows) < 9:
        rows.append(["", "", "", "", "", "", ""])

    svc = Table(rows, colWidths=COL, repeatRows=1)
    svc.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  DARK_GREEN),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT_GRAY]),
        ("GRID",          (0,0), (-1,-1), 0.4, MED_GRAY),
        ("BOX",           (0,0), (-1,-1), 0.8, DARK_GREEN),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",         (0,0), (0,-1),  "CENTER"),
        ("ALIGN",         (3,0), (3,-1),  "CENTER"),
        ("ALIGN",         (4,0), (4,-1),  "CENTER"),
        ("ALIGN",         (6,0), (6,-1),  "RIGHT"),
    ]))
    story.append(svc)
    story.append(Spacer(1, 4*mm))

    # ── Billing summary ───────────────────────────────────
    pkg_amt   = float(booking.get("pkg_amount",  0)) or total_amount
    transport = float(booking.get("transport",   0))
    discount  = float(booking.get("discount",    0))
    advance   = float(booking.get("advance_paid",0))
    balance   = max(0, pkg_amt + transport - discount - advance)

    BL = SB("bl", fontSize=10, alignment=TA_RIGHT)
    BV = S("bv",  fontSize=10, alignment=TA_CENTER)

    bill_rows = [
        [Paragraph("<b>Total Amount</b>",           BL),
         Paragraph(f"Rs.{int(pkg_amt):,}",          BV)],
        [Paragraph("<b>Outdoor Transportation</b>", BL),
         Paragraph(f"Rs.{int(transport):,}",        BV)],
        [Paragraph("<b>Discount</b>",               BL),
         Paragraph(f"Rs.{int(discount):,}",         BV)],
        [Paragraph("<b>Advance</b>",                BL),
         Paragraph(f"Rs.{int(advance):,}",          BV)],
        [Paragraph("<b>Due Amount</b>",
                   SB("dl2", fontSize=11, textColor=WHITE, alignment=TA_RIGHT)),
         Paragraph(f"<b>Rs.{int(balance):,}</b>",
                   SB("dv2", fontSize=12, textColor=WHITE, alignment=TA_CENTER))],
    ]
    bill_tbl = Table(bill_rows, colWidths=[74*mm, 36*mm])
    bill_tbl.setStyle(TableStyle([
        ("BOX",           (0,0), (-1,-1), 0.8, DARK_GREEN),
        ("LINEBELOW",     (0,0), (-1,-2), 0.4, MED_GRAY),
        ("BACKGROUND",    (0,-1),(-1,-1), DARK_GREEN),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (0,-1),  8),
        ("LEFTPADDING",   (1,0), (1,-1),  6),
        ("RIGHTPADDING",  (1,0), (1,-1),  6),
    ]))

    sign_rows = [
        [Paragraph("Customer Name & Sign", S("s1", fontSize=9, textColor=TEXT_GRAY))],
        [Paragraph("_________________________", S("s2", fontSize=10))],
        [Spacer(1, 8*mm)],
        [Paragraph("Authorised Sign _______________", S("s3", fontSize=10))],
    ]
    sign_tbl = Table(sign_rows, colWidths=[80*mm])

    combined = Table([[bill_tbl, Spacer(1,4), sign_tbl]],
                     colWidths=[112*mm, 4*mm, 66*mm])
    combined.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
    story.append(combined)
    story.append(Spacer(1, 4*mm))
    story.append(_footer())

    doc.build(story)
    return buf.getvalue()