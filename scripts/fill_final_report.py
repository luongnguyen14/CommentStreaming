#!/usr/bin/env python3
"""fill_final_report.py — Điền Final Report (tiếng Anh) từ template của cô.

Quy ước (CLAUDE.md §11):
  - KHÔNG sửa file trong templates/. Copy sang deliverables/ rồi mới điền.
  - Giữ layout/font/màu của template; chỉ thay chữ và thêm nội dung vào các
    content-control (w:sdt) mà template để trống.
  - Xoá w:spacing (letter-spacing) trong run do mình tạo và ép màu đen, bỏ
    themeColor/themeShade — lỗi LibreOffice làm mất dấu cách với template này.
  - Sau khi điền, kiểm tra trang trắng bằng LibreOffice + pdfinfo/pdftotext.

Chạy:
    /usr/bin/python3 scripts/fill_final_report.py
"""

from __future__ import annotations

import copy
import shutil
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "SIC_Big Data_Capstone Project_Final Report.docx"
OUT = ROOT / "deliverables" / "Final_Report.docx"
FIG = ROOT / "outputs" / "figures"

BLUE = "193DB0"
BLACK = "000000"
GREY = "595959"
LIGHT = "F2F5FA"
BORDER = "BFBFBF"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_sdt(doc: Document, sdt_id: int):
    """Tìm w:sdt theo w:id (id có thể âm)."""
    for sdt in doc.element.body.iter(qn("w:sdt")):
        pr = sdt.find(qn("w:sdtPr"))
        if pr is None:
            continue
        id_el = pr.find(qn("w:id"))
        if id_el is not None and id_el.get(qn("w:val")) == str(sdt_id):
            return sdt
    raise KeyError(f"Không tìm thấy w:sdt id={sdt_id}")


def _clean_rpr(rpr):
    """Xoá letter-spacing, highlight và thuộc tính theme của màu chữ."""
    if rpr is None:
        return
    for tag in ("w:spacing", "w:highlight"):
        for el in rpr.findall(qn(tag)):
            rpr.remove(el)
    color = rpr.find(qn("w:color"))
    if color is not None:
        for attr in ("themeColor", "themeShade", "themeTint"):
            if color.get(qn(f"w:{attr}")) is not None:
                del color.attrib[qn(f"w:{attr}")]


def set_run(run, *, size=10, bold=False, italic=False, font="SamsungOne-400",
            color=BLACK):
    run.font.name = font
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("ascii", "hAnsi", "cs", "eastAsia"):
        rfonts.set(qn(f"w:{attr}"), font)
    _clean_rpr(rpr)
    # Ngôn ngữ để Word kiểm tra chính tả đúng (en-US; tài liệu tiếng Anh)
    lang = rpr.find(qn("w:lang"))
    if lang is None:
        lang = OxmlElement("w:lang")
        rpr.append(lang)
    lang.set(qn("w:val"), "en-US")
    lang.set(qn("w:eastAsia"), "en-US")


def _shade(element, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    element.append(shd)


def new_para(doc: Document, parts, *, size=10, bold=False, italic=False,
             align="left", space_before=0, space_after=4, indent=0.75,
             hanging=None, keep_next=False, color=BLACK,
             font="SamsungOne-400", line=1.15, shading=None):
    """Tạo paragraph rồi trả về phần tử w:p (chưa gắn vào vị trí đích)."""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line
    pf.keep_together = True
    pf.keep_with_next = keep_next
    if indent is not None:
        pf.left_indent = Cm(indent)
    if hanging is not None:
        pf.first_line_indent = Cm(-hanging)
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "justify":
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    elif align == "right":
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    else:
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    if shading:
        _shade(p._p.get_or_add_pPr(), shading)

    if isinstance(parts, str):
        parts = [(parts, {})]
    for text, opts in parts:
        r = p.add_run(text)
        set_run(r, size=opts.get("size", size), bold=opts.get("bold", bold),
                italic=opts.get("italic", italic),
                font=opts.get("font", font), color=opts.get("color", color))
    return p._p


def bullet(doc: Document, text, *, size=10, marker="•", indent=1.05,
           space_after=2, line=1.15):
    return new_para(doc, [(f"{marker}  ", {"bold": False}), (text, {})],
                    size=size, indent=indent, hanging=0.45,
                    space_after=space_after, line=line)


def code_block(doc: Document, text):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(4)
    pf.space_after = Pt(6)
    pf.line_spacing = 1.0
    pf.left_indent = Cm(0.35)
    pf.right_indent = Cm(0.35)
    pf.keep_together = True
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    ppr = p._p.get_or_add_pPr()
    _shade(ppr, "F2F2F2")
    borders = OxmlElement("w:pBdr")
    for edge in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{edge}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "4")
        b.set(qn("w:space"), "4")
        b.set(qn("w:color"), "D9D9D9")
        borders.append(b)
    ppr.append(borders)
    lines = text.split("\n")
    for i, line in enumerate(lines):
        r = p.add_run(line)
        set_run(r, size=8, font="Courier New", color="1F1F1F")
        if i < len(lines) - 1:
            r.add_break()
    return p._p


def _set_table_borders(table):
    tbl_pr = table._tbl.tblPr
    old = tbl_pr.find(qn("w:tblBorders"))
    if old is not None:
        tbl_pr.remove(old)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), BORDER)
        borders.append(el)
    tbl_pr.append(borders)


def _set_cell_margins(table, top=40, bottom=40, left=70, right=70):
    tbl_pr = table._tbl.tblPr
    old = tbl_pr.find(qn("w:tblCellMar"))
    if old is not None:
        tbl_pr.remove(old)
    mar = OxmlElement("w:tblCellMar")
    for edge, val in (("top", top), ("left", left), ("bottom", bottom),
                      ("right", right)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tbl_pr.append(mar)


def table_block(doc: Document, rows, widths, *, font_size=8.5, header=True,
                caption=None, first_col_bold=False, keep_together=None):
    """Trả về [caption?, w:tbl, spacer]."""
    if keep_together is None:
        keep_together = len(rows) <= 10
    out = []
    if caption:
        out.append(new_para(doc, [("Table ", {"bold": True}),
                                  (caption, {"italic": True})],
                            size=9, indent=0, space_before=6, space_after=2,
                            keep_next=True))
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    _set_table_borders(table)
    _set_cell_margins(table)
    # tblW cố định
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is not None:
        tbl_w.set(qn("w:w"), str(int(sum(widths) * 1440)))
        tbl_w.set(qn("w:type"), "dxa")
    for j, w in enumerate(widths):
        table.columns[j].width = Inches(w)
    for i, row in enumerate(rows):
        tr = table.rows[i]._tr
        tr_pr = tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))
        if i == 0 and header:
            tr_pr.append(OxmlElement("w:tblHeader"))
        for j, value in enumerate(row):
            cell = table.cell(i, j)
            cell.width = Inches(widths[j])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            tc_pr = cell._tc.get_or_add_tcPr()
            if i == 0 and header:
                _shade(tc_pr, BLUE)
            elif i % 2 == 0:
                _shade(tc_pr, LIGHT)
            p = cell.paragraphs[0]
            pf = p.paragraph_format
            pf.space_before = Pt(1)
            pf.space_after = Pt(1)
            pf.line_spacing = 1.0
            if keep_together and i < len(rows) - 1:
                pf.keep_with_next = True
            run = p.add_run(str(value))
            set_run(run,
                    size=font_size,
                    bold=(i == 0 and header) or (first_col_bold and j == 0),
                    color="FFFFFF" if (i == 0 and header) else BLACK)
    out.append(table._tbl)
    out.append(new_para(doc, "", size=4, indent=0, space_after=2))
    return out


def image_block(doc: Document, path: Path, caption: str, width=5.9):
    doc.add_picture(str(path), width=Inches(width))
    p = doc.paragraphs[-1]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(6)
    pf.space_after = Pt(2)
    pf.keep_with_next = True
    pf.keep_together = True
    # ảnh phải vừa trang
    out = [p._p]
    out.append(new_para(doc, [(caption, {"italic": True})],
                        size=9, align="center", indent=0,
                        space_after=8, keep_next=True))
    return out


def build_block(doc: Document, block):
    kind = block[0]
    if kind == "p":
        _, text, *rest = block
        opts = rest[0] if rest else {}
        return [new_para(doc, text, **opts)]
    if kind == "rich":
        _, parts, *rest = block
        opts = rest[0] if rest else {}
        return [new_para(doc, parts, **opts)]
    if kind == "bullet":
        _, text, *rest = block
        opts = rest[0] if rest else {}
        return [bullet(doc, text, **opts)]
    if kind == "bullets":
        _, items, *rest = block
        opts = rest[0] if rest else {}
        return [bullet(doc, item, **opts) for item in items]
    if kind == "code":
        return [code_block(doc, block[1])]
    if kind == "table":
        _, rows, widths, opts = block
        return table_block(doc, rows, widths, **opts)
    if kind == "image":
        _, path, caption, *rest = block
        width = rest[0] if rest else 5.9
        return image_block(doc, path, caption, width)
    raise ValueError(f"Unknown block kind: {kind}")


def replace_sdt(doc: Document, sdt_id: int, blocks, *, keep_pagebreak=False):
    """Thay toàn bộ content-control bằng nội dung mới (bỏ wrapper w:sdt)."""
    sdt = find_sdt(doc, sdt_id)
    parent = sdt.getparent()
    idx = parent.index(sdt)
    pagebreaks = []
    if keep_pagebreak:
        for p in sdt.iter(qn("w:p")):
            if any(br.get(qn("w:type")) == "page" for br in p.iter(qn("w:br"))):
                pagebreaks.append(copy.deepcopy(p))
    parent.remove(sdt)
    elems = []
    for block in blocks:
        elems.extend(build_block(doc, block))
    for el in elems:
        if el.getparent() is not None:
            el.getparent().remove(el)
        parent.insert(idx, el)
        idx += 1
    for pb in pagebreaks:
        parent.insert(idx, pb)
        idx += 1


def set_sdt_text(doc: Document, sdt_id: int, text: str, *, size=None,
                 bold=None, color=BLACK, font=None):
    """Thay chữ trong sdt, giữ paragraph alignment và font gốc."""
    sdt = find_sdt(doc, sdt_id)
    p = next(sdt.iter(qn("w:p")))
    runs = list(p.iter(qn("w:r")))
    if not runs:
        r = OxmlElement("w:r")
        rpr = copy.deepcopy(p.find(qn("w:pPr")).find(qn("w:rPr")))
        if rpr is not None:
            r.append(rpr)
        p.append(r)
        runs = [r]
    first = runs[0]
    for extra in runs[1:]:
        extra.getparent().remove(extra)
    t = first.find(qn("w:t"))
    if t is None:
        t = OxmlElement("w:t")
        first.append(t)
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    rpr = first.find(qn("w:rPr"))
    if rpr is None:
        rpr = OxmlElement("w:rPr")
        first.insert(0, rpr)
    if font is not None:
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.insert(0, rfonts)
        for attr in ("ascii", "hAnsi", "cs", "eastAsia"):
            rfonts.set(qn(f"w:{attr}"), font)
    if size is not None:
        for tag in ("w:sz", "w:szCs"):
            el = rpr.find(qn(tag))
            if el is None:
                el = OxmlElement(tag)
                rpr.append(el)
            el.set(qn("w:val"), str(size))
    if bold is not None:
        for el in rpr.findall(qn("w:b")):
            rpr.remove(el)
        if bold:
            rpr.append(OxmlElement("w:b"))
    _clean_rpr(rpr)
    color_el = rpr.find(qn("w:color"))
    if color_el is None:
        color_el = OxmlElement("w:color")
        rpr.append(color_el)
    color_el.set(qn("w:val"), color)


def page_break_before_sdt(doc: Document, sdt_id: int):
    """Bắt đầu mục mới trên trang mới (dùng pageBreakBefore của heading)."""
    sdt = find_sdt(doc, sdt_id)
    p = next(sdt.iter(qn("w:p")))
    ppr = p.find(qn("w:pPr"))
    if ppr is None:
        ppr = OxmlElement("w:pPr")
        p.insert(0, ppr)
    if ppr.find(qn("w:pageBreakBefore")) is None:
        pb = OxmlElement("w:pageBreakBefore")
        rpr = ppr.find(qn("w:rPr"))
        if rpr is not None:
            rpr.addprevious(pb)
        else:
            ppr.append(pb)


def remove_all_highlights(doc: Document):
    """Bỏ các highlight vàng còn sót từ template (ô vàng ở mục lục)."""
    for hl in list(doc.element.body.iter(qn("w:highlight"))):
        hl.getparent().remove(hl)


def remove_letter_spacing(doc: Document):
    """Bỏ letter-spacing trong rPr (template đặt -12; LibreOffice làm mất dấu cách)."""
    for sp in list(doc.element.body.iter(qn("w:spacing"))):
        if sp.getparent().tag == qn("w:rPr"):
            sp.getparent().remove(sp)


def keep_instructor_table_rows(doc: Document):
    """Không cho bảng mục 6 tách dòng giữa hai trang."""
    for t in doc.tables:
        if len(t.rows) == 7 and len(t.columns) == 3:
            for row in t.rows:
                tr_pr = row._tr.get_or_add_trPr()
                if tr_pr.find(qn("w:cantSplit")) is None:
                    tr_pr.append(OxmlElement("w:cantSplit"))
            return True
    return False


def add_heading_keepnext(doc: Document, headings):
    """Giữ heading với nội dung ngay sau nó."""
    for p in doc.element.body.iter(qn("w:p")):
        text = "".join(p.itertext()).strip()
        if not text or len(text) > 100:
            continue
        if any(h in text for h in headings):
            ppr = p.find(qn("w:pPr"))
            if ppr is None:
                ppr = OxmlElement("w:pPr")
                p.insert(0, ppr)
            if ppr.find(qn("w:keepNext")) is None:
                ppr.append(OxmlElement("w:keepNext"))
            if ppr.find(qn("w:keepLines")) is None:
                ppr.append(OxmlElement("w:keepLines"))


# ---------------------------------------------------------------------------
# Cover
# ---------------------------------------------------------------------------

def fill_cover(doc: Document):
    title = ("SentimentGuard: Real-Time Sentiment Classification of Live Chat "
             "Comments for Early Detection of Harmful Comment Spikes")
    # SDT ngoài -1968567240 bọc 3 paragraph + 1 bảng tiêu đề. Chỉ giữ bảng,
    # đặt tiêu đề vào SDT bên trong hộp (-1656834780) để đúng thiết kế template.
    outer = find_sdt(doc, -1968567240)
    content = outer.find(qn("w:sdtContent"))
    for child in list(content):
        if child.tag == qn("w:p"):
            content.remove(child)
    set_sdt_text(doc, -1656834780, title, size=36, bold=False,
                 font="SamsungOne-400")

    set_sdt_text(doc, 1654180491, "19/10/26", size=36,
                 font="SamsungOne-400")
    set_sdt_text(doc, -337541970, "Team 6", size=48, bold=False,
                 font="SamsungOne-400")
    members = [
        (-481466300, "Vàng A Ký (Team Leader)"),
        (1397703220, "Nguyễn Đình Bằng"),
        (657040006, "Vàng Thị Dẳm"),
        (1655188738, "Dương Thị Hạnh"),
        (-409935491, "Ngô Lương Nguyên"),
    ]
    for sid, name in members:
        set_sdt_text(doc, sid, name, size=24, font="SamsungOne-400")


# ---------------------------------------------------------------------------
# Section content
# ---------------------------------------------------------------------------

def section_1_1():
    return [
        ("p", "Video platforms and livestreaming services receive a continuous flow of "
              "viewer comments. Most messages are harmless, but a sudden rise in hostile or "
              "strongly negative comments can damage community trust, drive viewers away, and "
              "overwhelm moderators who still read comments manually. The difficulty is not "
              "only volume. Harmful messages arrive in bursts, so a warning that appears hours "
              "later is no longer useful. A practical moderation system must ingest comments "
              "continuously, classify them quickly, and show aggregated signals to a human "
              "moderator without collecting unnecessary personal data.", {"align": "justify"}),
        ("p", "SentimentGuard is the Team 6 capstone prototype built for this problem. It "
              "connects Apache Kafka, Spark Structured Streaming, a Spark ML text-classification "
              "pipeline, and a Streamlit dashboard in one reproducible workflow. The system was "
              "designed as a Technology-for-Good project: it supports safer online communities, "
              "gives moderators an early warning, and exposes only aggregate statistics. Because "
              "a real livestream feed was not available under the course constraints, public IMDb "
              "reviews are replayed through Kafka. The replay stream is a simulation, not real "
              "livestream data. Every volume, latency, and alert result in this report must be "
              "read in that context.", {"align": "justify"}),
    ]


def section_1_2():
    return [
        ("p", "The motivation is simple: a moderator cannot read thousands of comments per "
              "minute, but a machine can rank and summarise them. The project therefore aims to "
              "answer one engineering question: can a small, reproducible Big Data stack detect "
              "a negative sentiment spike early enough to support a human decision? The specific "
              "objectives were:", {"align": "justify"}),
        ("bullets", [
            "Build a reproducible data-preparation pipeline that cleans text, removes duplicate "
            "and near-duplicate comments, and creates fixed train/validation/test splits.",
            "Train and evaluate a three-class sentiment classifier with Spark ML, using macro-F1 "
            "and per-class precision, recall, and F1 instead of accuracy alone.",
            "Implement a Kafka-to-Spark Structured Streaming pipeline with an explicit schema, "
            "event-time processing, a watermark, per-query checkpoints, and a dead-letter queue (DLQ).",
            "Produce Spark SQL analyses and English-labelled figures that describe class imbalance, "
            "comment length, vocabulary, emoji use, throughput, alert behaviour, and latency.",
            "Provide a Streamlit dashboard and a standalone model-trial program that can be "
            "demonstrated without a full cluster.",
            "Verify that the streaming path produces the same predictions as offline scoring, and "
            "document every limitation honestly.",
        ]),
        ("p", "Scope. The project is a prototype, not a production moderation system. It does not "
              "collect real livestream comments, does not identify individual users, and does not "
              "claim exactly-once delivery; these boundaries are stated again in Section 4.",
              {"align": "justify", "space_before": 4}),
    ]


def section_1_3():
    rows = [
        ["Member", "Role", "Main contributions"],
        ["Vàng A Ký", "Team Leader",
         "Project planning and topic framing; Action Plan and WBS coordination; presentation "
         "preparation; final report integration and submission check."],
        ["Nguyễn Đình Bằng", "Data ingestion",
         "Kafka 4.3.1 (KRaft) setup and three-topic design; replay producer; bad-event generator; "
         "ingestion throughput measurement."],
        ["Vàng Thị Dẳm", "Streaming and text processing",
         "Shared Spark SQL text-cleaning module; Structured Streaming job with explicit schema, "
         "event time, watermark, checkpoints, and DLQ; usage scenario and operating guide."],
        ["Dương Thị Hạnh", "Data and model",
         "Data source and CC0 licence verification; quality assessment, rating mapping, "
         "deduplication, fixed split; training, tuning, and evaluation of five models."],
        ["Ngô Lương Nguyên", "Analytics and dashboard",
         "Thirteen Spark SQL queries; fifteen figures and insight notes; Streamlit dashboard; "
         "standalone model-trial program; report figures."],
        ["All members", "Presentation and demo",
         "Proposal, prototype, and final presentations; report review; live demonstration."],
    ]
    return [
        ("p", "The team has five members. The table below lists the main responsibility of each "
              "member; the WBS and Git history contain the detailed task breakdown.",
              {"align": "justify"}),
        ("table", rows, [1.35, 1.25, 3.6],
         {"font_size": 8.5, "caption": "1. Members and role assignments.",
          "keep_together": False}),
    ]


def section_1_4():
    rows = [
        ["Milestone", "Planned (WBS)", "Actual", "Deliverable"],
        ["Team setup and topic framing", "15-16/09/2026", "02/10/2026", "docs/topic_decision.md"],
        ["Action Plan", "16-17/09/2026", "02/10/2026", "deliverables/Action_Plan.docx"],
        ["Preliminary presentation (Day 5)", "19/09/2026", "14/10/2026", "deliverables/Proposal_Slides.pptx"],
        ["Data preparation", "20-22/09/2026", "14-15/10/2026", "data/processed/*.parquet"],
        ["Kafka ingestion", "22-24/09/2026", "14/10/2026", "kafka/, src/producer/"],
        ["Streaming transformation", "24-26/09/2026", "15/10/2026", "src/streaming/stream_job.py"],
        ["Model training and evaluation", "25-28/09/2026", "15/10/2026", "outputs/models/sentiment_pipeline"],
        ["Prototype presentation (Day 11)", "25/09/2026", "15/10/2026", "outputs/streaming_summary.md"],
        ["EDA, figures, and dashboard", "28/09-01/10/2026", "15/10/2026", "src/eda/, src/app/"],
        ["Final report (Day 18)", "02/10/2026", "19/10/2026", "deliverables/Final_Report.docx"],
        ["Final presentation and demo (Day 20)", "04/10/2026", "19/10/2026", "Prototype demo and this report"],
    ]
    return [
        ("p", "The WBS defined a 20-day plan from Day 1 (15/09/2026) to Day 20 (04/10/2026). The "
              "implementation sessions recorded in this repository began on 02/10/2026 and were "
              "completed on 19/10/2026, after the nominal milestones. Table 2 reports the planned "
              "dates and the actual completion dates. It does not claim that the original deadlines "
              "were met.", {"align": "justify"}),
        ("table", rows, [1.9, 1.05, 0.95, 2.3],
         {"font_size": 8.2, "caption": "2. Planned and actual schedule."}),
    ]


def section_2_1():
    return [
        ("p", "The simulated scenario is a moderation desk for a video platform. Each stream_id "
              "represents one live room; in the replay, the stream_id is a movie or series title. "
              "Viewer comments arrive on the Kafka topic comments_raw as JSON messages with five "
              "fields: comment_id, stream_id, user_hash, text, and event_ts. Labels are never sent "
              "to Kafka.", {"align": "justify"}),
        ("p", "A moderator watches the dashboard. The system scores each comment as negative, "
              "neutral, or positive, and updates a one-minute tumbling window and a ten-second "
              "sliding window. An alert is raised when the negative share is above 30% and the "
              "window contains at least five comments. The moderator can then inspect the room, "
              "decide whether to slow the chat, pin a message, or escalate. Figure 1 shows the "
              "full architecture.", {"align": "justify"}),
        ("image", FIG / "00_pipeline_architecture.png",
         "Figure 1. End-to-end architecture: Kafka ingestion, shared cleaning, Spark ML scoring, "
         "windowed aggregation, DLQ, Parquet sinks, and the dashboard.", 6.0),
        ("p", "The end-to-end flow has five steps:", {"space_before": 2}),
        ("bullets", [
            "The replay producer publishes five-field JSON messages to comments_raw.",
            "The streaming job parses the explicit schema, applies the shared cleaning function, "
            "and scores valid comments with the saved PipelineModel.",
            "Valid comments go to scored_detail and to the comments_scored topic; invalid comments "
            "go to the DLQ with a reason.",
            "Two window queries aggregate by stream_id and event time: one-minute tumbling and "
            "ten-second sliding windows.",
            "The Streamlit dashboard reads the Parquet sinks and applies the alert rule; it does "
            "not need Spark or Kafka at read time.",
        ]),
        ("p", "The official verification run replayed 1,000 labelled test reviews, 14 valid "
              "heartbeat/probe records, and 10 deliberately malformed records. Of the 1,024 "
              "records sent, 1,014 were scored and 10 were routed to the DLQ. The 10 errors cover "
              "invalid JSON, missing fields, an unparsable timestamp, empty text, text shorter than "
              "20 characters, and text longer than 5,000 characters.",
              {"align": "justify", "space_before": 2}),
    ]


def section_2_2():
    field_rows = [
        ["Source field", "Project field", "Use"],
        ["review_id", "comment_id", "Join key across Parquet, Kafka, and evaluation labels."],
        ["movie", "stream_id", "Simulated room; also the grouping key for the split."],
        ["reviewer", "user_hash", "Salted SHA-256; the original value is not stored."],
        ["review_detail", "text", "Comment text used by the model."],
        ["rating", "label, rating", "Proxy label (1-4 / 5-6 / 7-10); rating kept for traceability."],
        ["review_date", "review_date", "Reference only; not used as event time."],
        ["review_summary, spoiler_tag, helpful", "(dropped)", "Not needed for the simulation; not stored."],
    ]
    return [
        ("p", "The training data is a 201,074-review shard of the IMDb Review Dataset - ebD, "
              "published on Kaggle by Enam Biswas under the CC0 public-domain licence. The source "
              "file part-01.json contains 1,010,293 reviews, and the Kaggle page lists 5,571,499 "
              "reviews in the complete dataset. The project used a deterministic 19.9% sample "
              "because the virtual machine has limited RAM and disk; this is a subset, not the "
              "complete corpus. The exact subset is preserved in data/processed; because "
              "config.yaml now permits a larger subsample, rerunning prepare.py from the raw file "
              "would build a different subset unless the saved JSONL/manifest is kept.",
              {"align": "justify"}),
        ("p", "The source has no sentiment label. The team defined a three-class proxy label from "
              "the rating: 1-4 negative, 5-6 neutral, and 7-10 positive. This mapping is a team "
              "convention, not an official IMDb label. It is the main source of label noise, "
              "especially for the neutral class.", {"align": "justify"}),
        ("table", field_rows, [2.1, 1.3, 2.8],
         {"font_size": 8.3, "caption": "3. Source fields and their use in the project."}),
        ("p", "Privacy. The reviewer field is hashed with a salt read from the COMMENT_HASH_SALT "
              "environment variable. Only the first 16 hexadecimal characters of the hash are "
              "stored. The dashboard shows aggregates, not individual users. The original reviewer "
              "name or ID never appears in the processed Parquet files.",
              {"align": "justify"}),
    ]


def section_2_3():
    topic_rows = [
        ["Topic", "Partitions", "Purpose"],
        ["comments_raw", "3", "Raw five-field JSON from the replay producer."],
        ["comments_scored", "3", "Scored JSON from the streaming job."],
        ["comments_dlq", "1", "Invalid records with a machine-readable reason."],
    ]
    return [
        ("p", "Kafka 4.3.1 runs in KRaft mode, without ZooKeeper. Kafka 4.x requires Java 17, "
              "while Spark 3.5.9 in this environment uses Java 8; the two runtimes are installed "
              "separately. Table 4 lists the three topics.", {"align": "justify"}),
        ("table", topic_rows, [1.35, 0.85, 4.0],
         {"font_size": 8.5, "caption": "4. Kafka topics used by the pipeline."}),
        ("p", "The replay producer reads the fixed test split and publishes one JSON message per "
              "comment. It preserves a deterministic order with seed 42, supports a target rate and "
              "burst mode, and can deliberately delay a fraction of records. In the official run the "
              "target rate was 50 messages/s and the burst ceiling was 400 messages/s. The producer "
              "waits for broker acknowledgements and records delivery failures.",
              {"align": "justify"}),
        ("p", "Ingestion was measured on the single virtual machine. 969 of the 1,014 scored "
              "comments arrived within 27 seconds, and the highest one-second rate was 384 "
              "messages/s, which is 96% of the 400 messages/s design ceiling. This is a replay-load "
              "result, not a capacity claim for a production cluster.",
              {"align": "justify"}),
    ]


def section_2_4():
    cleaning_rows = [
        ["Step", "Rows in", "Removed", "Rows out", "Reason"],
        ["01 Load raw", "201,074", "0", "201,074", "JSONL shard"],
        ["02 Empty text", "201,074", "0", "201,074", "No empty text after cleaning"],
        ["03 Missing label", "201,074", "10,394", "190,680", "Rating missing or outside 1-10"],
        ["04 Too short", "190,680", "10", "190,670", "Fewer than 20 characters"],
        ["05 Too long", "190,670", "1,686", "188,984", "More than 5,000 characters"],
        ["06 Duplicate ID", "188,984", "2,999", "185,985", "Keep the longest text"],
        ["07 Exact duplicate", "185,985", "636", "185,349", "Identical cleaned text"],
        ["08 Near duplicate", "185,349", "63", "185,286", "Same token set after normalisation"],
        ["09 Remaining", "185,286", "0", "185,286", "Used for the fixed split"],
    ]
    query_rows = [
        ["Query", "Output", "Purpose"],
        ["detail", "Parquet scored_detail", "One row per scored comment, partitioned by event date/hour."],
        ["kafka", "comments_scored topic", "Scored JSON for downstream consumers."],
        ["window", "window_1min Parquet", "One-minute tumbling aggregates per stream_id."],
        ["sliding", "window_sliding_10s Parquet", "Ten-second windows with a five-second slide."],
        ["dlq_kafka", "comments_dlq topic", "Invalid records with a reason."],
        ["dlq_parquet", "dlq Parquet", "Durable copy of the dead-letter queue."],
    ]
    return [
        ("p", "Data preparation is a separate batch step (src/training/prepare.py) so that "
              "training and streaming share the same cleaning logic. The raw JSON array is converted "
              "to JSONL for parallel reading, sampled deterministically, cleaned with Spark SQL "
              "functions, deduplicated in three passes, and split by movie into 70/15/15 "
              "train/validation/test sets with seed 42. Table 5 records every removal.",
              {"align": "justify"}),
        ("table", cleaning_rows, [1.25, 0.8, 0.7, 0.8, 2.65],
         {"font_size": 8.2, "caption": "5. Data-preparation log (outputs/tables/cleaning_log.csv)."}),
        ("p", "The cleaning function is written once in src/common/text_cleaning.py and is used by "
              "both training and streaming. It lowercases, removes HTML, replaces URLs with <url> "
              "and mentions with <user>, normalises punctuation, expands abbreviations, reduces "
              "repeated characters, separates emoji into tokens, and collapses whitespace. All steps "
              "are Spark SQL expressions; no Python UDF is used. The function is idempotent, so "
              "cleaning an already-cleaned comment does not change it.", {"align": "justify"}),
        ("p", "The split is grouped by movie, not by row, to prevent the same title from appearing "
              "in two sets. The three sets have the same class distribution within 0.02 percentage "
              "points. The test set was scored once, on 15/10/2026 at 00:05:02, and the event is "
              "recorded in outputs/tables/test_eval_log.csv. TF-IDF is fitted inside the Spark ML "
              "Pipeline, so the vectorizer sees only training data.", {"align": "justify"}),
        ("p", "Streaming transformation. The streaming job (src/streaming/stream_job.py) starts six "
              "independent queries. Each query has its own checkpoint directory. The job declares "
              "the JSON schema explicitly, converts event_ts to an event-time timestamp, applies the "
              "shared cleaning function, and routes every record to exactly one branch: valid or "
              "DLQ. Table 6 lists the queries.", {"align": "justify"}),
        ("table", query_rows, [1.05, 1.65, 3.5],
         {"font_size": 8.3, "caption": "6. The six streaming queries."}),
        ("p", "The watermark is two minutes on event_time. Window queries use append mode and wait "
              "for the watermark before emitting a window. A record that arrives after the watermark "
              "is dropped by design; a record that is malformed or fails validation goes to the DLQ, "
              "not to the windows. This distinction matters: late data and bad data are different "
              "problems.", {"align": "justify"}),
        ("p", "Verification. The run sent 1,024 records and accounted for all of them: 1,014 in "
              "scored_detail and 10 in the DLQ. The comments_scored topic grew by exactly 1,014 "
              "messages and comments_dlq by exactly 10. Re-scoring the same 1,000 test comment_ids "
              "offline with the saved PipelineModel produced 1,000 identical predictions (100%). "
              "The streaming macro-F1 on that 1,000-comment sample was 0.6311, compared with 0.6233 "
              "on the full 27,792-row test set. The difference comes from the sample composition, "
              "not from the streaming code path.", {"align": "justify"}),
        ("p", "Delivery guarantee. The observed run had no duplicate and no loss: 1,014 + 10 = "
              "1,024. The mechanism is at-least-once, because offsets are committed after a "
              "micro-batch is written; a crash between write and commit can replay the batch. "
              "Exactly-once has not been verified by a crash/restart experiment, and this report "
              "does not claim it.", {"align": "justify"}),
    ]


def section_2_5():
    query_rows = [
        ["Query", "Question", "Output"],
        ["q00 overview", "One-row sanity check of the analysis dataset", "Console table"],
        ["q01 class distribution", "Class balance in train/validation/test", "Figure 6"],
        ["q02 length quantiles", "Comment length by class", "Figure 7"],
        ["q03 length histogram", "Length distribution by class", "Figure 7"],
        ["q04 top words", "Most distinctive words per class", "Figure 8"],
        ["q05 emoji", "Emoji use per 1,000 comments by class", "Figure 9"],
        ["q06 sentiment per minute", "One-minute sentiment timeline", "Figure 10 (top)"],
        ["q07 sentiment per 10s", "Ten-second sliding timeline", "Figure 10 (bottom)"],
        ["q08 throughput", "Messages per second and burst flags", "Figure 11"],
        ["q09 negative share alert", "Negative share and alert rule", "Figure 12"],
        ["q10 latency quantiles", "p50/p95/p99 end-to-end latency", "Figure 13"],
        ["q11 latency histogram", "Latency distribution buckets", "Figure 13"],
        ["q12 token vocabulary", "Vocabulary growth from punctuation tokens", "Table only"],
    ]
    return [
        ("p", "Thirteen Spark SQL queries in src/eda/sql/ produce the tables behind the figures. "
              "They cover dataset size, class distribution, length quantiles and histograms, "
              "distinctive words, emoji, sentiment over time, throughput, alerting, latency, and "
              "vocabulary size. Table 7 lists them.", {"align": "justify"}),
        ("table", query_rows, [1.55, 2.75, 1.9],
         {"font_size": 8.1, "caption": "7. Spark SQL queries used for the analysis."}),
        ("p", "The main findings are:", {"space_before": 2}),
        ("bullets", [
            "The data is imbalanced: positive 61.1%, negative 25.1%, neutral 13.9%. A majority-class "
            "baseline already reaches 61.1% accuracy, so accuracy alone is misleading; macro-F1 is "
            "the primary metric.",
            "Neutral comments are the longest (median 131 tokens) and the hardest class (test F1 "
            "0.378). Positive comments have a median of 83 tokens.",
            "The replay burst reached 384 messages/s, 96% of the 400 messages/s design ceiling. "
            "969 of 1,014 comments arrived in 27 seconds.",
            "The alert rule fired once, at 18:08:30 UTC, with a 38.5% negative share and 13 "
            "comments. Removing the minimum of five comments would add 13 false alarms.",
            "End-to-end latency has two peaks: 81% of comments were scored in 1.0-4.0 s (p50 "
            "2,413 ms), but p95 was 9,663 ms and p99 was 27,091 ms. Queueing inside the micro-batch "
            "dominates; Kafka transfer is effectively local (p50 0 ms).",
            "Tokenisation is coarse: 11.2% of tokens carry punctuation, and the vocabulary grows "
            "from 318,980 to 524,107 tokens (+64%). This is a known limitation.",
            "Emoji are weak features: positive comments use 46 emoji per 1,000 comments, neutral "
            "18; the top emoji in the negative class is the face with tears of joy, which is often "
            "sarcastic.",
        ]),
        ("p", "All streaming findings describe the replay run. They illustrate the mechanics of the "
              "pipeline; they are not claims about real viewer behaviour.",
              {"align": "justify", "space_before": 2}),
    ]


def section_3_1():
    return [
        ("p", "The ingestion code is split into three small scripts so that each step can be run "
              "and checked independently.", {"align": "justify"}),
        ("bullets", [
            "kafka/start_kafka.sh, stop_kafka.sh, create_topics.sh: start the KRaft broker, create "
            "the three topics, and stop the broker.",
            "src/producer/replay_producer.py: read the fixed test split, build the five-field JSON "
            "message, and publish to comments_raw with rate, burst, and late-record controls.",
            "scripts/send_bad_events.py: send ten known malformed records plus valid heartbeat and "
            "late-probe records for DLQ and watermark verification.",
        ]),
        ("p", "A producer message has exactly five fields and never contains the label:",
              {"space_before": 4}),
        ("code", "msg = {\n"
                 "    \"comment_id\": comment_id,\n"
                 "    \"stream_id\": stream_id,\n"
                 "    \"user_hash\": salted_hash(reviewer, salt=salt),\n"
                 "    \"text\": review_text,\n"
                 "    \"event_ts\": iso_utc(time.time()),\n"
                 "}\n"
                 "producer.send(\"comments_raw\", key=comment_id,\n"
                 "              value=json.dumps(msg).encode(\"utf-8\"))"),
        ("p", "Topics are created with explicit partition counts:", {"space_before": 2}),
        ("code", "kafka-topics.sh --bootstrap-server localhost:9092 \\\n"
                 "  --create --if-not-exists --topic comments_raw \\\n"
                 "  --partitions 3 --replication-factor 1"),
        ("p", "The full command used in the verification run was: replay_producer.py --only-test "
              "--max 1000 --rate 50, followed by send_bad_events.py --heartbeat 12 "
              "--heartbeat-interval 25 --late-probe. The producer reported 1,000 delivered messages "
              "and 0 send failures.", {"align": "justify"}),
    ]


def section_3_2():
    pipeline_rows = [
        ["Stage", "Configuration", "Purpose"],
        ["RegexTokenizer", "Whitespace pattern; text already lowercased", "Split cleaned text into tokens."],
        ["StopWordsRemover", "162 English stop words; negations kept", "Remove low-information words without losing 'not good'."],
        ["NGram", "n=1 (n=2 tested for NB and LR)", "Unigrams won in both tested models."],
        ["CountVectorizer", "vocabSize 20,000; minDF 3", "Term-frequency vector."],
        ["IDF", "Default", "Down-weight common terms."],
        ["Normalizer", "L2", "Stabilise linear models."],
        ["Classifier", "LR / NB / SVC / RF", "Compare five models; LR selected."],
    ]
    model_rows = [
        ["Model", "Accuracy", "Weighted F1", "Macro-F1", "Train time (s)", "Features"],
        ["MajorityBaseline", "0.6107", "0.4631", "0.2528", "0", "0"],
        ["NaiveBayes", "0.6743", "0.7013", "0.6192", "107.9", "20,000"],
        ["LogisticRegression", "0.7063", "0.7241", "0.6291", "245.0", "20,000"],
        ["LinearSVC (OvR)", "0.7000", "0.7172", "0.6218", "116.3", "20,000"],
        ["RandomForest", "0.5878", "0.6131", "0.5343", "282.4", "5,000"],
    ]
    class_rows = [
        ["Class", "Precision", "Recall", "F1", "Support", "Share"],
        ["negative", "0.6807", "0.6642", "0.6723", "6,965", "25.06%"],
        ["neutral", "0.3036", "0.5019", "0.3783", "3,853", "13.86%"],
        ["positive", "0.8851", "0.7626", "0.8193", "16,974", "61.08%"],
    ]
    return [
        ("p", "The training script builds one Spark ML Pipeline for every candidate model. The "
              "pipeline is fitted only on the training split; validation is used to compare models, "
              "and the test split is touched once at the end.", {"align": "justify"}),
        ("table", pipeline_rows, [1.35, 2.15, 2.7],
         {"font_size": 8.3, "caption": "8. Spark ML Pipeline stages."}),
        ("p", "Class imbalance is handled with weights w_c = N / (k * n_c), computed on the training "
              "split only. The weights were negative 1.330, neutral 2.404, and positive 0.546. "
              "Hyperparameters were selected with TrainValidationSplit (80/20 inside train) using "
              "weighted F1; the validation and test sets were never used for tuning.",
              {"align": "justify"}),
        ("p", "Table 9 compares four classifiers and a majority baseline on validation. Logistic "
              "Regression had the best macro-F1 (0.6291), trained in 245 seconds, and provides "
              "per-class probabilities, which the dashboard and the model-trial program use.",
              {"align": "justify"}),
        ("table", model_rows, [1.45, 0.8, 0.95, 0.85, 1.05, 0.85],
         {"font_size": 8.2, "caption": "9. Model comparison on the validation split (27,793 rows)."}),
        ("p", "The selected model was evaluated once on the test set: accuracy 0.7018, weighted F1 "
              "0.7213, macro-F1 0.6233. Table 10 gives per-class metrics, and Figure 2 shows the "
              "confusion matrix. The neutral class is the weak point: only 50.2% of neutral comments "
              "were recalled, and errors split almost evenly between negative and positive. Positive "
              "comments were classified well (F1 0.8193), while 16.6% of positive comments were "
              "predicted as neutral.", {"align": "justify"}),
        ("table", class_rows, [1.2, 1.0, 0.9, 0.8, 0.9, 0.9],
         {"font_size": 8.4, "caption": "10. Final test metrics by class (27,792 rows)."}),
        ("image", FIG / "01_confusion_matrix.png",
         "Figure 2. Confusion matrix on the test set (rows: true class; columns: predicted class).", 5.2),
        ("p", "The neutral row is split almost evenly across all three predictions. This is the "
              "expected consequence of a proxy label built from ratings 5-6: those reviews contain "
              "both mild praise and mild criticism.", {"align": "justify"}),
        ("image", FIG / "02_per_class_prf1.png",
         "Figure 3. Precision, recall, and F1 by class on the test set.", 5.6),
        ("p", "Positive has high precision (0.885) but lower recall (0.763); negative is balanced "
              "at about 0.67; neutral is below 0.4 on every measure.", {"align": "justify"}),
        ("image", FIG / "05_error_reasons.png",
         "Figure 4. Manual error categories among misclassified test comments.", 5.8),
        ("p", "The largest error categories are noisy neutral labels, suspected sarcasm, and "
              "negation or contrast constructions such as 'not good' and 'but'. These are language "
              "problems, not streaming problems.", {"align": "justify"}),
        ("image", FIG / "04_top_features.png",
         "Figure 5. Top weighted TF-IDF features for each class (Logistic Regression).", 5.8),
        ("p", "The top neutral features include explicit rating strings such as '6/10'. The model "
              "is partly reading the number in the review, a shortcut that will not exist in most "
              "real livestream comments.", {"align": "justify"}),
        ("p", "Leak checks. No cleaned text appears in more than one split (0 overlaps in "
              "train/validation, train/test, and validation/test). The test evaluation log contains "
              "exactly one entry. A residual risk remains: the split is grouped by movie, but the "
              "same reviewer can review several movies. A post-hoc measurement found 11,427 of "
              "111,087 user hashes (10.3%) in more than one split, covering 75,939 of 185,286 rows "
              "(41.0%). The effect on the test metrics was not quantified; it is reported as a "
              "limitation rather than treated as evidence of a clean split.",
              {"align": "justify"}),
    ]


def section_3_3():
    schema_rows = [
        ["Column", "Type", "Meaning"],
        ["comment_id", "string", "review_id of the source review; key for labels and Kafka."],
        ["stream_id", "string", "Movie title used as the simulated room."],
        ["user_hash", "string(16)", "First 16 hex characters of salted SHA-256(reviewer)."],
        ["label", "string", "negative / neutral / positive (proxy from rating)."],
        ["rating", "string", "Original rating 1-10; kept for traceability, not a feature."],
        ["text", "string", "Cleaned text used by the model."],
        ["review_date", "string", "Original review date; reference only."],
        ["n_chars", "int", "Character count of cleaned text."],
        ["n_tokens", "int", "Whitespace token count."],
    ]
    split_rows = [
        ["Split", "Negative", "Neutral", "Positive", "Total", "Share of all rows"],
        ["Train", "32,504", "17,983", "79,214", "129,701", "70.0%"],
        ["Validation", "6,965", "3,854", "16,974", "27,793", "15.0%"],
        ["Test", "6,965", "3,853", "16,974", "27,792", "15.0%"],
        ["All", "46,434", "25,690", "113,162", "185,286", "100.0%"],
    ]
    sample_rows = [
        ["comment_id", "stream_id", "user_hash", "label", "rating", "split", "text (truncated)"],
        ["rw6358464", "The Call (2020)", "e87642b1", "positive", "7", "test",
         "good acting, plot was great & overall pretty good movie! imagine the movie frequency, just darker.. recommended"],
        ["rw5571862", "Onward (I) (2020)", "3fc79249", "positive", "8", "train",
         "onward is a pretty good animation movie which deserves your time. it's funny, emotional and have some pretty good animated effects."],
        ["rw5739267", "The Hollow (2018-2020)", "fc0564f8", "neutral", "6", "train",
         "at first it seemed not well thought. but as episodes keeps going, they get entertaining. it has no main plot, but it keeps you watching."],
        ["rw2994146", "Love It or List It (2008- )", "ab2492c5", "negative", "1", "train",
         "this could be a great show. i have tried to get through it because i love the idea of seeing the finished product and what they choose. however, the soul crushing stupidity of the fake drama stops me."],
    ]
    return [
        ("p", "The processed data is stored as three Parquet datasets with the same schema. Table 11 "
              "describes the columns; Table 12 gives the row counts and class shares.",
              {"align": "justify"}),
        ("table", schema_rows, [1.15, 0.95, 4.1],
         {"font_size": 8.2, "caption": "11. Schema of train.parquet, val.parquet, and test.parquet."}),
        ("table", split_rows, [1.0, 0.95, 0.85, 0.9, 0.9, 1.35],
         {"font_size": 8.3, "caption": "12. Split sizes and class distribution."}),
        ("p", "Table 13 shows four real rows from outputs/tables/clean_sample.csv. The user_hash is "
              "a salted hash; the text is shown as cleaned by the shared function. Long comments are "
              "truncated for display only.", {"align": "justify"}),
        ("table", sample_rows, [0.75, 1.05, 0.65, 0.55, 0.4, 0.4, 2.35],
         {"font_size": 7.4, "caption": "13. Sample rows from the transformed dataset."}),
        ("p", "The evaluation labels are stored separately in data/processed/eval_labels.parquet "
              "for the test split only. The producer never reads labels for the messages it sends; "
              "the verification script joins them by comment_id after the run. This separation is "
              "what makes the streaming evaluation honest.", {"align": "justify"}),
    ]


def section_3_4():
    return [
        ("p", "This section presents the figures produced from the Spark SQL tables. Each caption "
              "states what is plotted; the paragraph below each figure gives the measured insight. "
              "The underlying CSV files are in outputs/tables/.", {"align": "justify"}),
        ("image", FIG / "06_class_distribution.png",
         "Figure 6. Class distribution in the training data (129,701 rows).", 5.4),
        ("p", "Positive comments dominate (61.1%), negative is 25.1%, and neutral is only 13.9%. "
              "The distribution is almost identical in train, validation, and test, so a majority "
              "baseline reaches 61.1% accuracy; macro-F1 is the fair metric.", {"align": "justify"}),
        ("image", FIG / "07_length_by_class.png",
         "Figure 7. Comment length by sentiment class (tokens).", 6.0),
        ("p", "Neutral comments are the longest (median 131 tokens, p95 501); positive comments "
              "have a median of 83 tokens. All classes have a long right tail, so comment length "
              "varies by more than an order of magnitude.", {"align": "justify"}),
        ("image", FIG / "08_top_words_by_class.png",
         "Figure 8. Top 20 distinctive words per class.", 6.0),
        ("p", "The strongest words are 'bad' for negative, '6/10' for neutral, and 'great' for "
              "positive. Two of the 20 neutral markers are explicit rating strings such as '6/10'; "
              "the model is partly learning the number in the review, not only sentiment.",
              {"align": "justify"}),
        ("image", FIG / "09_emoji_by_class.png",
         "Figure 9. Emoji use per 1,000 comments by class.", 6.0),
        ("p", "Positive comments use 46 emoji per 1,000 comments, versus 18 for neutral. The "
              "absolute rate is low (2.1% of positive comments contain an emoji). The top emoji in "
              "the negative class is the face with tears of joy, so emoji cannot be used as a simple "
              "positive rule.", {"align": "justify"}),
        ("image", FIG / "10_sentiment_timeline.png",
         "Figure 10. Sentiment over time: one-minute windows (top) and ten-second sliding windows "
         "(bottom).", 6.0),
        ("p", "The replay burst is compressed into 27 seconds, so the one-minute view has only four "
              "points. The ten-second view shows the negative share moving between 14.3% and 38.5%; "
              "this is why the dashboard uses the sliding window.", {"align": "justify"}),
        ("image", FIG / "11_throughput_burst.png",
         "Figure 11. Messages per second and burst threshold in the replay run.", 5.9),
        ("p", "Only 2 of 43 active seconds exceed the 175 messages/s burst threshold: 384 and 316 "
              "messages/s. The peak is 96% of the 400 messages/s design ceiling, which is the "
              "highest load actually tested.", {"align": "justify"}),
        ("image", FIG / "12_negative_share_alert.png",
         "Figure 12. Negative-share monitor and alert rule.", 5.8),
        ("p", "The rule (negative share > 30% and at least 5 comments) fired once: 38.5% with 13 "
              "comments at 18:08:30 UTC. Without the minimum of five comments, the same data would "
              "produce 13 false alarms from windows with 1-3 comments.", {"align": "justify"}),
        ("image", FIG / "13_latency_distribution.png",
         "Figure 13. End-to-end latency distribution (log scale).", 6.0),
        ("p", "81% of comments were scored in 1.0-4.0 s, with a median of 2,413 ms. The p95 is "
              "9,663 ms and the p99 is 27,091 ms; the long tail comes from queueing inside the "
              "micro-batch, not from Kafka. Two deliberately late records appear at about 603 s.",
              {"align": "justify"}),
    ]


def section_4_1():
    acc_rows = [
        ["Accomplishment", "Evidence"],
        ["Reproducible data pipeline: 201,074 raw reviews to 185,286 clean rows",
         "outputs/tables/cleaning_log.csv"],
        ["Fixed grouped split with no duplicate text across sets",
         "outputs/tables/class_distribution.csv; outputs/tables/leak_check.json"],
        ["Four classifiers plus a majority baseline, and a saved Spark ML Pipeline",
         "outputs/tables/model_results.csv; outputs/models/sentiment_pipeline"],
        ["Final test evaluation: accuracy 0.7018, macro-F1 0.6233",
         "outputs/tables/test_eval_log.csv; outputs/tables/per_class_metrics.csv"],
        ["Kafka replay ingestion: 1,024 records sent, 1,014 scored, 10 DLQ",
         "outputs/streaming_summary.md"],
        ["Streaming/offline agreement: 1,000/1,000 identical predictions",
         "outputs/stream/verify1/verification.json"],
        ["Thirteen SQL analyses and fifteen figures", "src/eda/sql/; outputs/figures/"],
        ["Streamlit dashboard with a tested alert rule",
         "src/app/app.py; tests/test_dashboard.py"],
        ["Standalone model-trial program",
         "src/app/model_trial.py; outputs/model_trial_report.md"],
        ["77 automated tests passed", "tests/"],
    ]
    limit_rows = [
        ["Limitation", "Consequence"],
        ["Replay, not real livestream", "Volume, latency, and alert results are a simulation."],
        ["Labels inferred from rating", "Neutral is noisy; the model learns rating language."],
        ["English movie reviews, not live chat", "Domain mismatch; Vietnamese and teencode were not tested."],
        ["Rating strings in text ('7/10')", "Metrics are optimistic for comments without ratings."],
        ["Neutral F1 0.378", "One class is not reliably usable without human review."],
        ["p95 latency 9.7 s", "Not suitable for sub-second moderation."],
        ["Single VM, local[2], 1,024 records", "No scale or multi-broker evidence."],
        ["At-least-once only", "Exactly-once not verified; a crash can duplicate a batch."],
        ["11,427 users across splits", "Residual leakage risk; the effect was not quantified."],
    ]
    return [
        ("p", "The project delivered a complete, reproducible prototype rather than a slide-only "
              "design. Table 14 lists the main accomplishments and the file that evidences each one.",
              {"align": "justify"}),
        ("table", acc_rows, [3.55, 2.65],
         {"font_size": 8.2, "caption": "14. Main accomplishments and evidence."}),
        ("p", "Benefits. For a community team, the system provides an early-warning signal instead "
              "of a manual backlog. It ranks rooms by negative share, requires a minimum sample "
              "before alerting, and shows the number of comments behind every number. For engineers, "
              "the repository is a reusable template: shared cleaning code, explicit schemas, "
              "per-query checkpoints, a DLQ, and a written verification protocol. For the team, the "
              "project demonstrates the full Big Data workflow from ingestion to a user-facing "
              "dashboard.", {"align": "justify"}),
        ("p", "Technology for Good. The project is designed to protect online communities. It does "
              "not identify or score individual users publicly, stores only salted hashes, and "
              "displays aggregate statistics. The intended use is moderator support, not "
              "surveillance.", {"align": "justify"}),
        ("p", "Limitations. Table 15 lists the limitations that a reader must keep in mind. None of "
              "them is hidden in the results.", {"align": "justify"}),
        ("table", limit_rows, [2.2, 4.0],
         {"font_size": 8.3, "caption": "15. Limitations of the current prototype."}),
    ]


def section_4_2():
    items = [
        "Collect real comments with platform permission and an appropriate licence. Start with "
        "200-300 Vietnamese comments labelled by two annotators; measure inter-annotator agreement "
        "before training.",
        "Replace the rating proxy with human labels for neutral and sarcasm. Add active learning so "
        "moderators can correct uncertain cases, and keep a held-out set that is never used for tuning.",
        "Improve the text pipeline: Vietnamese word segmentation, punctuation-aware tokenisation, "
        "emoji and teencode handling, and negation/sarcasm features. Measure the cost of any Python "
        "UDF before adopting it.",
        "Evaluate transformer models such as PhoBERT or a multilingual BERT on GPU. Compare macro-F1, "
        "latency, and cost with the current TF-IDF + Logistic Regression baseline; do not adopt a "
        "heavier model without a measured gain.",
        "Harden the streaming layer: a multi-broker Kafka cluster, more partitions, a 1-2 s trigger, "
        "backpressure, schema registry, and a crash/restart test that verifies exactly-once or "
        "documents the duplicate bound.",
        "Build a real moderator workflow: authentication, alert routing, acknowledgement, feedback "
        "buttons, and a drift monitor that compares live class shares with the training distribution.",
        "Strengthen privacy: retention limits, access control, aggregation thresholds, and a review "
        "of platform terms before any real collection.",
        "Package the system with Docker Compose and CI, and add a reproducible benchmark at 10,000 "
        "messages/s on more than one machine.",
    ]
    refs = [
        "E. Biswas, IMDb Review Dataset - ebD, Kaggle, CC0. "
        "https://www.kaggle.com/datasets/ebiswas/imdb-review-dataset "
        "(DOI 10.34740/KAGGLE/DSV/1836923).",
        "Apache Software Foundation, Apache Spark 3.5.9 Documentation. "
        "https://spark.apache.org/docs/3.5.9/",
        "Apache Software Foundation, Apache Kafka 4.3 Documentation. "
        "https://kafka.apache.org/documentation/",
        "Apache Spark MLlib, Feature Extractors and Classification. "
        "https://spark.apache.org/docs/3.5.9/ml-features.html",
        "Streamlit, Streamlit Documentation. https://docs.streamlit.io/",
    ]
    blocks = [
        ("p", "The next version should address the limitations in the order below.",
              {"align": "justify"}),
        ("bullets", items, {"size": 9.3, "space_after": 1, "line": 1.05}),
        ("p", "References. The project used the following public sources and documentation:",
              {"align": "justify", "space_before": 4, "space_after": 2}),
    ]
    for i, ref in enumerate(refs, 1):
        blocks.append(("p", f"[{i}]  {ref}",
                       {"size": 8.6, "indent": 0.75, "space_after": 2,
                        "line": 1.05}))
    return blocks


def section_5_intro():
    return [
        ("p", "The comments below summarise each member's documented contributions. Each member "
              "should confirm or revise their own row before submission.", {"align": "justify"}),
    ]


# ---------------------------------------------------------------------------
# Section 5 tables
# ---------------------------------------------------------------------------

def fill_member_table(doc: Document):
    table = None
    for t in doc.tables:
        if len(t.rows) == 6 and len(t.columns) == 2:
            table = t
            break
    if table is None:
        raise RuntimeError("Không tìm thấy bảng thành viên 6x2")
    table.columns[0].width = Inches(1.6)
    table.columns[1].width = Inches(4.6)
    data = [
        ("Vàng A Ký (Team Leader)",
         "Coordinated the plan, WBS, and Action Plan; framed the topic and the Technology-for-Good "
         "scope; integrated the final report and presentations. Remaining: final rehearsal and "
         "submission check."),
        ("Nguyễn Đình Bằng",
         "Set up Kafka 4.3.1 in KRaft mode and the three topics; built the replay producer and "
         "bad-event generator; measured ingestion throughput up to 384 messages/s. Remaining: "
         "multi-broker test."),
        ("Vàng Thị Dẳm",
         "Wrote the shared Spark SQL text-cleaning module and the Structured Streaming job with "
         "explicit schema, event time, watermark, checkpoints, and DLQ; documented the scenario and "
         "operating guide. Remaining: crash/restart fault-tolerance test."),
        ("Dương Thị Hạnh",
         "Verified the data source and CC0 licence; performed cleaning, deduplication, and the fixed "
         "split; trained and evaluated five models. Remaining: human-labelled validation of the "
         "neutral class."),
        ("Ngô Lương Nguyên",
         "Built thirteen Spark SQL queries, fifteen figures, and insight notes; implemented the "
         "Streamlit dashboard and the model-trial program; prepared report figures. Remaining: "
         "dashboard screenshot and deployment guide."),
    ]
    # Dòng 0 là header NAME / REVIEW and COMMENT (nằm trong w:sdt); giữ nguyên.
    for i, (name, comment) in enumerate(data, start=1):
        c0, c1 = table.cell(i, 0), table.cell(i, 1)
        c0.width = Inches(1.6)
        c1.width = Inches(4.6)
        for cell, text, bold in ((c0, name, True), (c1, comment, False)):
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.0
            r = p.add_run(text)
            set_run(r, size=9, bold=bold)


def fill_team_photo_placeholder(doc: Document):
    """Thay placeholder ảnh nhóm bằng ghi chú trung thực (không có ảnh trong repo)."""
    try:
        replace_sdt(doc, -1395664091, [
            ("p", "Team photo: insert the official group photo before submission. "
                  "No team photo was available in the project repository when this "
                  "report was generated.",
             {"size": 9, "italic": True, "align": "center", "indent": 0,
              "color": GREY, "space_before": 6, "space_after": 6}),
        ])
        return True
    except KeyError:
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    shutil.copyfile(TEMPLATE, OUT)
    doc = Document(OUT)

    fill_cover(doc)

    replace_sdt(doc, 785466908, section_1_1())          # 1.1
    replace_sdt(doc, -329831763, section_1_2())         # 1.2
    replace_sdt(doc, 1143392081, section_1_3())         # 1.3
    replace_sdt(doc, -573279965, section_1_4())         # 1.4
    replace_sdt(doc, 1978491041, section_2_1())         # 2.1
    replace_sdt(doc, 1762327235, section_2_2())         # 2.2
    replace_sdt(doc, 1807432170, section_2_3())         # 2.3
    replace_sdt(doc, -1679187678, section_2_4())        # 2.4
    replace_sdt(doc, 1304897882, section_2_5())         # 2.5
    page_break_before_sdt(doc, -2124760548)              # 3. Results bắt đầu trang mới
    replace_sdt(doc, 2044553165, section_3_1())         # 3.1
    replace_sdt(doc, 786541343, section_3_2())          # 3.2
    replace_sdt(doc, -252906542, section_3_3())         # 3.3
    replace_sdt(doc, -983541672, section_3_4())         # 3.4
    replace_sdt(doc, 1777513428, section_4_1())         # 4.1
    page_break_before_sdt(doc, -991407545)               # 4.2 bắt đầu trang mới
    replace_sdt(doc, -1143574651, section_4_2(), keep_pagebreak=True)  # 4.2

    # Section 5: lời dẫn + bảng thành viên; giữ bảng ảnh làm placeholder trung thực
    replace_sdt(doc, 393170479, section_5_intro())
    fill_team_photo_placeholder(doc)
    fill_member_table(doc)
    page_break_before_sdt(doc, 211155832)
    keep_instructor_table_rows(doc)

    remove_all_highlights(doc)
    remove_letter_spacing(doc)
    add_heading_keepnext(doc, [
        "1. Introduction", "1.1. Background Information",
        "1.2. Motivation and Objective", "1.3. Members and Role Assignments",
        "1.4. Schedule and Milestones", "2. Project Execution",
        "2.1. Simulated Scenario Description", "2.2. Datasets Selection and Description",
        "2.3. Data Ingestion Pipeline", "2.4. Data Transformation Processing",
        "2.5. Data Query and Insight", "3. Results",
        "3.1. Data Ingestion Scripts and Code", "3.2. Data Transformation Scripts and Code",
        "3.3. Description and Sample of Transformed Datasets",
        "3.4. Data Visualization of Query Results", "4. Projected Impact",
        "4.1. Accomplishments and Benefits", "4.2. Future Improvements",
        "5. Team Member Review and Comment", "6. Instructor Review and Comment",
    ])

    doc.save(OUT)
    print(f"Đã ghi {OUT.relative_to(ROOT)}")
    print(f"  paragraphs: {len(doc.paragraphs):,} | tables: {len(doc.tables)}")


if __name__ == "__main__":
    main()
