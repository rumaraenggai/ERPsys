# modules/pdf_payslip.py
# Requires: pip install reportlab
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import io

BRAND_BLUE  = colors.HexColor("#185FA5")
BRAND_LIGHT = colors.HexColor("#E6F1FB")
BRAND_GRAY  = colors.HexColor("#7A7974")
ROW_ALT     = colors.HexColor("#F9F8F5")
RED         = colors.HexColor("#A32D2D")
GREEN       = colors.HexColor("#1D9E75")

def generate_payslip(emp, slip, year, month, month_name, company_name="Your Company Pvt. Ltd."):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm, bottomMargin=12*mm
    )
    styles = getSampleStyleSheet()

    def style(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    S = {
        "company":  style("co",   fontSize=14, textColor=BRAND_BLUE,  fontName="Helvetica-Bold"),
        "slip_hdr": style("sh",   fontSize=10, textColor=colors.white, fontName="Helvetica-Bold", alignment=TA_CENTER),
        "label":    style("lbl",  fontSize=8,  textColor=BRAND_GRAY),
        "value":    style("val",  fontSize=9,  fontName="Helvetica-Bold"),
        "rvalue":   style("rval", fontSize=9,  fontName="Helvetica-Bold", alignment=TA_RIGHT),
        "small":    style("sm",   fontSize=7,  textColor=BRAND_GRAY),
        "footer":   style("ft",   fontSize=7,  textColor=BRAND_GRAY,  alignment=TA_CENTER),
    }

    MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    period = f"{month_name} {year}"

    story = []

    # ── Header ──────────────────────────────────────────────────────────────
    header_data = [[
        Paragraph(company_name, S["company"]),
        Paragraph(f"SALARY SLIP — {period}", S["slip_hdr"]),
    ]]
    header_tbl = Table(header_data, colWidths=[95*mm, 85*mm])
    header_tbl.setStyle(TableStyle([
        ("BACKGROUND",  (1,0),(1,0), BRAND_BLUE),
        ("VALIGN",      (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",  (0,0),(-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
        ("LEFTPADDING", (0,0),(-1,-1), 4),
        ("RIGHTPADDING",(0,0),(-1,-1), 4),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 4*mm))

    # ── Employee Details ────────────────────────────────────────────────────
    def cell(label, value):
        return [Paragraph(label, S["label"]), Paragraph(str(value), S["value"])]

    details = [
        cell("Employee Name",  emp["name"]) + cell("Department",   emp["dept"]),
        cell("Designation",    emp["role"]) + cell("Joining Date",  emp["join_date"]),
        cell("PAN",            emp["pan"])  + cell("Working Days",  str(slip.get("worked_days","—"))),
    ]
    det_tbl = Table(details, colWidths=[28*mm, 62*mm, 28*mm, 62*mm])
    det_tbl.setStyle(TableStyle([
        ("BOX",         (0,0),(-1,-1), 0.5, BRAND_GRAY),
        ("INNERGRID",   (0,0),(-1,-1), 0.25, colors.HexColor("#D5D3CB")),
        ("BACKGROUND",  (0,0),(0,-1), ROW_ALT),
        ("BACKGROUND",  (2,0),(2,-1), ROW_ALT),
        ("TOPPADDING",  (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("LEFTPADDING", (0,0),(-1,-1), 4),
    ]))
    story.append(det_tbl)
    story.append(Spacer(1, 4*mm))

    # ── Earnings & Deductions ───────────────────────────────────────────────
    def money(n):
        return f"₹ {n:,.0f}"

    earn_rows = [
        [Paragraph("EARNINGS", S["slip_hdr"]), "", Paragraph("DEDUCTIONS", S["slip_hdr"]), ""],
        ["Basic Salary",         money(slip["basic"]),   "Provident Fund",      money(slip["pf"])   if emp["pf"]  else "N/A"],
        ["House Rent Allowance", money(slip["hra"]),     "ESI",                 money(slip["esi"])  if emp["esi"] else "N/A"],
        ["Special Allowance",    money(slip["special"]), "Professional Tax",    money(slip["pt"])],
        ["",                     "",                     "TDS (Est.)",          money(slip["tds"])],
    ]

    col_w = [50*mm, 30*mm, 50*mm, 30*mm]
    ed_tbl = Table(earn_rows, colWidths=col_w)
    ed_tbl.setStyle(TableStyle([
        # Header row
        ("BACKGROUND",    (0,0),(1,0), BRAND_BLUE),
        ("BACKGROUND",    (2,0),(3,0), colors.HexColor("#0C447C")),
        ("TEXTCOLOR",     (0,0),(-1,0), colors.white),
        ("SPAN",          (0,0),(0,0)),
        ("SPAN",          (2,0),(3,0)),
        ("ALIGN",         (0,0),(-1,0), "CENTER"),
        # Data rows
        ("ALIGN",         (1,1),(1,-1), "RIGHT"),
        ("ALIGN",         (3,1),(3,-1), "RIGHT"),
        ("FONTNAME",      (1,1),(1,-1), "Helvetica"),
        ("FONTNAME",      (3,1),(3,-1), "Helvetica"),
        ("FONTSIZE",      (0,0),(-1,-1), 8.5),
        ("BOX",           (0,0),(-1,-1), 0.5, BRAND_GRAY),
        ("INNERGRID",     (0,0),(-1,-1), 0.25, colors.HexColor("#D5D3CB")),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, ROW_ALT]),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
        ("RIGHTPADDING",  (0,0),(-1,-1), 4),
    ]))
    story.append(ed_tbl)
    story.append(Spacer(1, 3*mm))

    # ── Totals bar ──────────────────────────────────────────────────────────
    totals = [[
        Paragraph("Gross Salary", S["label"]),
        Paragraph(money(slip["gross"]), S["rvalue"]),
        Paragraph("Total Deductions", S["label"]),
        Paragraph(money(slip["total_ded"]), ParagraphStyle("rd", parent=S["rvalue"], textColor=RED)),
        Paragraph("NET PAY", ParagraphStyle("np", parent=S["label"], textColor=BRAND_BLUE, fontName="Helvetica-Bold")),
        Paragraph(money(slip["net"]), ParagraphStyle("nv", parent=S["rvalue"], textColor=BRAND_BLUE, fontSize=11)),
    ]]
    tot_tbl = Table(totals, colWidths=[35*mm, 25*mm, 38*mm, 25*mm, 25*mm, 32*mm])
    tot_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), BRAND_LIGHT),
        ("BOX",           (0,0),(-1,-1), 0.5, BRAND_BLUE),
        ("LINEAFTER",     (1,0),(4,0), 0.5, BRAND_BLUE),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("LEFTPADDING",   (0,0),(-1,-1), 5),
        ("RIGHTPADDING",  (0,0),(-1,-1), 5),
    ]))
    story.append(tot_tbl)
    story.append(Spacer(1, 6*mm))

    # ── Statutory note ──────────────────────────────────────────────────────
    story.append(Paragraph(
        "PF calculated at 12% of basic (capped at ₹15,000). ESI at 0.75% (applicable ≤ ₹21,000 gross). "
        "TDS is an estimate; consult your CA for exact liability. PT as per Maharashtra schedule.",
        S["small"]
    ))
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BRAND_GRAY))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "This is a computer-generated payslip and does not require a signature. "
        f"Generated for {period}.",
        S["footer"]
    ))

    doc.build(story)
    buf.seek(0)
    return buf
