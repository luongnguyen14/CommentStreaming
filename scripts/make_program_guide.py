#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_program_guide.py — Sinh tài liệu Word "Giải thích chương trình" cho dự án
SentimentGuard / CommentStreaming.

Tài liệu giải thích:
  - mọi chương trình (shell + Python) đã viết: mục đích, cách chạy, tham số,
    các bước hoạt động, đầu vào/đầu ra, cách đọc kết quả;
  - các câu lệnh shell quan trọng theo từng dòng;
  - các câu lệnh Python/Spark cốt lõi và ý nghĩa;
  - config.yaml, 13 truy vấn SQL, kiểm thử, xử lý sự cố, bảng tra lệnh.

Chạy BẰNG python-docx của hệ thống (python-docx KHÔNG có trong .venv):
    /usr/bin/python3 scripts/make_program_guide.py
    /usr/bin/python3 scripts/make_program_guide.py --out docs/giai_thich_chuong_trinh.docx

Sau khi sinh, kiểm tra bố cục theo CLAUDE.md §11:
    soffice --headless --convert-to pdf --outdir /tmp/pdfcheck docs/giai_thich_chuong_trinh.docx
    pdfinfo /tmp/pdfcheck/giai_thich_chuong_trinh.pdf | grep Pages

Nguyên tắc: mọi số liệu nêu trong tài liệu này lấy từ file kết quả thật trong
outputs/ hoặc từ README của chính dự án; không có số liệu bịa.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / "docs" / "giai_thich_chuong_trinh.docx"

NAVY = RGBColor(0x1F, 0x38, 0x64)
BLUE = RGBColor(0x2E, 0x54, 0x96)
DARK = RGBColor(0x22, 0x22, 0x22)
GRAY = RGBColor(0x59, 0x59, 0x59)
CODE_BG = "F3F4F6"
INFO_BG = "EAF1FB"
WARN_BG = "FFF4E5"
OK_BG = "EAF7EE"
ERR_BG = "FDECEC"

CH = [
    "Bản đồ chương trình và cách đọc tài liệu",
    "Môi trường và cấu hình",
    "Kafka — hàng đợi sự kiện",
    "Chuẩn bị dữ liệu — prepare.py",
    "Huấn luyện mô hình — train.py",
    "Xử lý luồng — stream_job.py và verify_stream.py",
    "Phát và kiểm tra dữ liệu — producer, consumer, bad events",
    "Dashboard Streamlit — app.py",
    "App terminal — terminal_app.py",
    "Thử nghiệm mô hình — model_trial.py và check_model.py",
    "Phân tích dữ liệu — queries.py và plots.py",
    "Điều phối demo — run_demo.sh, run_stream.sh, stop_stream.sh",
    "Thư viện dùng chung — utils, text_cleaning, metrics, plotting",
    "Kiểm thử tự động",
    "Script tạo tài liệu nộp",
    "Bảng tra toàn bộ lệnh",
    "Xử lý sự cố thường gặp",
    "Thuật ngữ",
]
APX = [
    "A — Bảng tra file → chức năng → đầu ra",
    "B — Lộ trình đọc code trong 30 phút",
]

doc = Document()
_total_chapters = len(CH)
# Ánh xạ "C1".."C18"/"A"/"B" → số trang, do main() điền sau lượt dựng đầu tiên.
PAGE_MAP: dict[str, int] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _set_run_font(run, name: str, size: float | None = None, bold: bool | None = None,
                  color: RGBColor | None = None, italic: bool | None = None) -> None:
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    run.font.color.rgb = color if color is not None else DARK


def _shade(element, fill: str) -> None:
    ppr = element.get_or_add_pPr() if hasattr(element, "get_or_add_pPr") else element
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    ppr.append(shd)


def _cell_shade(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def _cell_margins(table, top=40, bottom=40, left=70, right=70) -> None:
    tbl_pr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for name, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        node = OxmlElement(f"w:{name}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        mar.append(node)
    tbl_pr.append(mar)


def _repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    tr_pr.append(el)


def _add_field(paragraph, instr: str) -> None:
    run = paragraph.add_run()
    fld1 = OxmlElement("w:fldChar")
    fld1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = instr
    fld2 = OxmlElement("w:fldChar")
    fld2.set(qn("w:fldCharType"), "separate")
    t = OxmlElement("w:t")
    t.text = "1"
    fld3 = OxmlElement("w:fldChar")
    fld3.set(qn("w:fldCharType"), "end")
    run._r.append(fld1)
    run._r.append(it)
    run._r.append(fld2)
    run._r.append(t)
    run._r.append(fld3)


def _style_document() -> None:
    sec = doc.sections[0]
    sec.page_height = Cm(29.7)
    sec.page_width = Cm(21.0)
    sec.top_margin = Cm(2.0)
    sec.bottom_margin = Cm(2.0)
    sec.left_margin = Cm(2.3)
    sec.right_margin = Cm(2.0)
    sec.header_distance = Cm(1.0)
    sec.footer_distance = Cm(1.0)
    sec.different_first_page_header_footer = True

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    normal.paragraph_format.line_spacing = 1.15
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.space_before = Pt(0)

    for name, size, color, before, after in (
        ("Heading 1", 17, NAVY, 6, 10),
        ("Heading 2", 13.5, BLUE, 12, 5),
        ("Heading 3", 11.5, RGBColor(0x33, 0x33, 0x33), 9, 3),
    ):
        st = doc.styles[name]
        st.font.name = "Calibri"
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = color
        st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(after)
        st.paragraph_format.keep_with_next = True
    # Mỗi chương bắt đầu trên trang mới, không cần chèn page break thủ công.
    doc.styles["Heading 1"].paragraph_format.page_break_before = True

    # Header
    hp = sec.header.paragraphs[0]
    hp.text = ""
    r = hp.add_run("SentimentGuard — Hướng dẫn đọc và hiểu chương trình")
    _set_run_font(r, "Calibri", 8.5, color=GRAY)
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # Footer: trang X / Y
    fp = sec.footer.paragraphs[0]
    fp.text = ""
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = fp.add_run("Nhóm 6 · SIC Big Data · Trang ")
    _set_run_font(r1, "Calibri", 8.5, color=GRAY)
    _add_field(fp, "PAGE")
    r2 = fp.add_run(" / ")
    _set_run_font(r2, "Calibri", 8.5, color=GRAY)
    _add_field(fp, "NUMPAGES")


def h1(text: str) -> None:
    p = doc.add_paragraph(style="Heading 1")
    r = p.add_run(text)
    _set_run_font(r, "Calibri", 17, True, NAVY)


def h2(text: str) -> None:
    p = doc.add_paragraph(style="Heading 2")
    r = p.add_run(text)
    _set_run_font(r, "Calibri", 13.5, True, BLUE)


def h3(text: str) -> None:
    p = doc.add_paragraph(style="Heading 3")
    r = p.add_run(text)
    _set_run_font(r, "Calibri", 11.5, True, RGBColor(0x33, 0x33, 0x33))


def p(text: str, bold: bool = False, italic: bool = False, size: float = 10.5,
      color: RGBColor | None = None, space_after: float = 4,
      align=WD_ALIGN_PARAGRAPH.JUSTIFY) -> None:
    par = doc.add_paragraph()
    par.alignment = align
    par.paragraph_format.space_after = Pt(space_after)
    r = par.add_run(text)
    _set_run_font(r, "Calibri", size, bold, color or DARK)
    r.italic = italic


def bullets(items: list[str]) -> None:
    # Tự vẽ dấu đầu dòng thay vì style "List Bullet": style này dùng font Symbol,
    # LibreOffice trên máy không có font đó nên hiện thành ô vuông rỗng.
    for it in items:
        par = doc.add_paragraph()
        par.paragraph_format.space_after = Pt(2)
        par.paragraph_format.left_indent = Cm(0.65)
        par.paragraph_format.first_line_indent = Cm(-0.4)
        r = par.add_run("•  ")
        _set_run_font(r, "Calibri", 10.5, True, BLUE)
        r2 = par.add_run(it)
        _set_run_font(r2, "Calibri", 10.5)


def steps(items: list[str]) -> None:
    for i, it in enumerate(items, 1):
        par = doc.add_paragraph()
        par.paragraph_format.left_indent = Cm(0.75)
        par.paragraph_format.first_line_indent = Cm(-0.75)
        par.paragraph_format.space_after = Pt(3)
        r = par.add_run(f"{i}.  ")
        _set_run_font(r, "Calibri", 10.5, True, BLUE)
        r2 = par.add_run(it)
        _set_run_font(r2, "Calibri", 10.5)


def code(text: str, caption: str | None = None) -> None:
    if caption:
        cp = doc.add_paragraph()
        cp.paragraph_format.space_before = Pt(4)
        cp.paragraph_format.space_after = Pt(0)
        cp.paragraph_format.keep_with_next = True
        r = cp.add_run(caption)
        _set_run_font(r, "Calibri", 9, italic=True, color=GRAY)
    par = doc.add_paragraph()
    par.paragraph_format.left_indent = Cm(0.3)
    par.paragraph_format.right_indent = Cm(0.1)
    par.paragraph_format.space_before = Pt(2)
    par.paragraph_format.space_after = Pt(6)
    par.paragraph_format.line_spacing = 1.0
    ppr = par._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), CODE_BG)
    ppr.append(shd)
    bdr = OxmlElement("w:pBdr")
    for side in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{side}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "4")
        b.set(qn("w:space"), "3")
        b.set(qn("w:color"), "D0D7DE")
        bdr.append(b)
    ppr.append(bdr)
    lines = text.rstrip("\n").split("\n")
    for i, line in enumerate(lines):
        r = par.add_run(line if line else " ")
        _set_run_font(r, "Consolas", 8.4, color=RGBColor(0x1B, 0x1F, 0x23))
        if i < len(lines) - 1:
            r.add_break()


def note(text: str, kind: str = "info", title: str | None = None) -> None:
    fill = {"info": INFO_BG, "warn": WARN_BG, "ok": OK_BG, "err": ERR_BG}.get(kind, INFO_BG)
    label = title or {"info": "GHI CHÚ", "warn": "LƯU Ý", "ok": "ĐÃ ĐO", "err": "CẢNH BÁO"}.get(kind, "GHI CHÚ")
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    _cell_margins(t, 70, 70, 120, 120)
    cell = t.cell(0, 0)
    _cell_shade(cell, fill)
    par = cell.paragraphs[0]
    par.paragraph_format.space_after = Pt(0)
    r = par.add_run(label + ": ")
    _set_run_font(r, "Calibri", 9.5, True, NAVY)
    r2 = par.add_run(text)
    _set_run_font(r2, "Calibri", 9.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def table(headers: list[str], rows: list[list], widths: list[float] | None = None,
          font_size: float = 8.8, header_fill: str = "DCE6F1", spacer: bool = True) -> None:
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    _cell_margins(t)
    hdr = t.rows[0]
    _repeat_header(hdr)
    for i, htxt in enumerate(headers):
        cell = hdr.cells[i]
        _cell_shade(cell, header_fill)
        par = cell.paragraphs[0]
        par.paragraph_format.space_after = Pt(0)
        r = par.add_run(str(htxt))
        _set_run_font(r, "Calibri", font_size, True, NAVY)
        if widths:
            cell.width = Cm(widths[i])
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            if widths:
                cells[i].width = Cm(widths[i])
            par = cells[i].paragraphs[0]
            par.paragraph_format.space_after = Pt(0)
            par.paragraph_format.line_spacing = 1.0
            txt = "" if val is None else str(val)
            r = par.add_run(txt)
            _set_run_font(r, "Calibri", font_size)
    # Độ rộng phải ghi vào tblGrid, không chỉ vào từng ô: LibreOffice tính lại
    # bố cục từ tblGrid nên nếu bỏ qua bước này mọi cột sẽ rộng bằng nhau.
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
        for col, w in zip(t._tbl.tblGrid.findall(qn("w:gridCol")), widths):
            col.set(qn("w:w"), str(int(Cm(w).twips)))
        tbl_pr = t._tbl.tblPr
        tbl_w = tbl_pr.find(qn("w:tblW"))
        if tbl_w is None:
            tbl_w = OxmlElement("w:tblW")
            style_el = tbl_pr.find(qn("w:tblStyle"))
            if style_el is not None:
                style_el.addnext(tbl_w)
            else:
                tbl_pr.insert(0, tbl_w)
        tbl_w.set(qn("w:w"), str(int(Cm(sum(widths)).twips)))
        tbl_w.set(qn("w:type"), "dxa")
    if spacer:
        doc.add_paragraph().paragraph_format.space_after = Pt(2)


def kv(rows: list[tuple[str, str]]) -> None:
    table(["Mục", "Giá trị"], [[a, b] for a, b in rows], widths=[4.6, 11.8])


def chapter(n: int) -> None:
    h1(f"Chương {n} — {CH[n - 1]}")


# ---------------------------------------------------------------------------
# Cover + mục lục
# ---------------------------------------------------------------------------
def cover() -> None:
    for _ in range(4):
        doc.add_paragraph()
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = par.add_run("HƯỚNG DẪN ĐỌC VÀ HIỂU CHƯƠNG TRÌNH")
    _set_run_font(r, "Calibri", 26, True, NAVY)

    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = par.add_run("SentimentGuard — CommentStreaming")
    _set_run_font(r, "Calibri", 17, True, BLUE)

    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = par.add_run("Hệ thống phân loại cảm xúc bình luận trực tuyến theo thời gian thực")
    _set_run_font(r, "Calibri", 12, False, GRAY)
    doc.add_paragraph()
    doc.add_paragraph()

    table(
        ["Mục", "Nội dung"],
        [
            ["Nhóm thực hiện", "Nhóm 6 — Samsung Innovation Campus, Big Data Course"],
            ["Thành viên", "Vàng A Ký (Nhóm trưởng); Nguyễn Đình Bằng; Vàng Thị Dẳm; "
                           "Dương Thị Hạnh; Ngô Lương Nguyên"],
            ["Đề tài", "Mô hình phân loại cảm xúc dựa trên bình luận trực tuyến"],
            ["Loại tài liệu", "Tài liệu nội bộ — giải thích mã nguồn và cách vận hành"],
            ["Phiên bản", "1.0"],
            ["Ngày", "20/10/2026"],
            ["Phạm vi", "Toàn bộ chương trình trong repo: 11 shell script, 26 file Python, "
                        "13 truy vấn SQL, config.yaml và 5 bộ kiểm thử (tổng 31 file .py)"],
        ],
        widths=[4.0, 12.4],
        font_size=9.5,
    )

    note(
        "Dữ liệu streaming trong dự án là REPLAY từ review IMDb công khai (CC0), "
        "KHÔNG phải bình luận livestream thật. Hệ thống chỉ khẳng định ngữ nghĩa "
        "at-least-once; exactly-once CHƯA được kiểm chứng bằng thực nghiệm. "
        "Tập test chỉ được dùng một lần ở bước đánh giá cuối.",
        "warn",
        "TRUNG THỰC",
    )

    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = par.add_run("Tài liệu được sinh tự động từ mã nguồn trong repo.\n"
                    "Mọi đường dẫn tính từ PROJECT_ROOT = /home/hadoop/capstone")
    _set_run_font(r, "Calibri", 9, italic=True, color=GRAY)
    doc.add_page_break()


def _toc_line(label: str, title: str, page: int | None) -> None:
    par = doc.add_paragraph()
    par.paragraph_format.space_after = Pt(3)
    par.paragraph_format.left_indent = Cm(0.3)
    par.paragraph_format.right_indent = Cm(0.3)
    par.paragraph_format.tab_stops.add_tab_stop(
        Cm(16.4), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
    r = par.add_run(label)
    _set_run_font(r, "Calibri", 10.5, True, BLUE)
    r2 = par.add_run(title)
    _set_run_font(r2, "Calibri", 10.5)
    r3 = par.add_run("\t" + (str(page) if page else ""))
    _set_run_font(r3, "Calibri", 10.5, color=GRAY)


def toc() -> None:
    par = doc.add_paragraph()
    r = par.add_run("MỤC LỤC")
    _set_run_font(r, "Calibri", 20, True, NAVY)
    p("Số trang ở lề phải, tính theo bản in A4. Mỗi chương bắt đầu trên một trang mới.",
      italic=True, color=GRAY)
    for i, title in enumerate(CH, 1):
        _toc_line(f"Chương {i}.  ", title, PAGE_MAP.get(f"C{i}"))
    doc.add_paragraph()
    for j, title in enumerate(APX):
        _toc_line(f"Phụ lục {title.split(' — ')[0]}.  ",
                  title.split(" — ", 1)[1], PAGE_MAP.get("AB"[j]))
    doc.add_paragraph()
    note(
        "Tài liệu ưu tiên giải thích 'câu lệnh này làm gì và vì sao'. Với mỗi chương trình, "
        "cấu trúc thống nhất gồm: mục đích → cách chạy → tham số → các bước hoạt động → "
        "câu lệnh cốt lõi → đầu ra → cách đọc kết quả. Muốn tra nhanh một lệnh, xem Chương 16.",
        "info",
    )


# ---------------------------------------------------------------------------
# Chương 1 — Bản đồ chương trình
# ---------------------------------------------------------------------------
def ch1() -> None:
    chapter(1)
    h2("1.1. Tài liệu này trả lời câu hỏi gì")
    p("Tài liệu giải thích toàn bộ mã nguồn của dự án theo cách một người mới có thể "
      "đọc hiểu và tự chạy lại: mỗi chương trình nhận dữ liệu gì, biến đổi ra sao, "
      "ghi kết quả ở đâu, các tham số có ý nghĩa gì, và những câu lệnh quan trọng "
      "trong code thực sự làm gì. Tài liệu không thay thế báo cáo kỹ thuật hay báo "
      "cáo nộp; nó là bản đồ để đọc code và vận hành hệ thống.")
    p("Có ba cách dùng tài liệu: (1) đọc tuần tự Chương 1 → 3 để nắm bối cảnh, "
      "(2) nhảy tới chương của chương trình đang cần, (3) tra bảng lệnh ở Chương 16 "
      "hoặc bảng xử lý sự cố ở Chương 17.")

    h2("1.2. Ba câu hỏi phải trả lời khi đọc bất kỳ chương trình nào")
    steps([
        "Đầu vào là gì? — file, topic Kafka, tham số dòng lệnh hay biến môi trường.",
        "Nó biến đổi cái gì? — lọc, làm sạch, huấn luyện, gộp cửa sổ, hay chỉ đọc để hiển thị.",
        "Đầu ra ở đâu? — thư mục trong outputs/, topic Kafka, model đã lưu, hay màn hình.",
    ])
    p("Ba câu này lặp lại ở đầu mỗi chương và là cách nhanh nhất để không bị lạc "
      "khi đọc một file dài vài trăm dòng.")

    h2("1.3. Sáu tầng của hệ thống")
    table(
        ["Tầng", "Thư mục / file", "Nhiệm vụ", "Chương"],
        [
            ["1. Dữ liệu", "data/raw → data/processed", "Review IMDb thô → parquet sạch, "
             "chia train/val/test, nhãn đánh giá tách riêng", "4"],
            ["2. Huấn luyện", "src/training/", "TF-IDF + bộ phân loại trong một Pipeline; "
             "chọn mô hình trên validation; đánh giá test một lần", "5"],
            ["3. Phát dữ liệu", "src/producer/", "Đọc review, đóng gói message 5 trường, "
             "băm user, gửi Kafka; mô phỏng burst và dữ liệu đến muộn", "7"],
            ["4. Xử lý luồng", "src/streaming/", "6 query Structured Streaming: parse, DLQ, "
             "làm sạch, chấm điểm, ghi 3 đích, gộp cửa sổ", "6"],
            ["5. Phân tích & hiển thị", "src/eda/, src/app/", "SQL + biểu đồ; dashboard 3 tab; "
             "app terminal 8 giai đoạn; công cụ thử mô hình", "8–11"],
            ["6. Kiểm chứng & tài liệu", "verify_stream.py, tests/, scripts/fill_*.py",
             "Đối chiếu số lượng, macro-F1 trên luồng, kiểm thử, sinh tài liệu nộp", "12–15"],
        ],
        widths=[3.0, 4.2, 7.4, 1.8],
    )

    h2("1.4. Luồng dữ liệu end-to-end")
    code(
        "data/raw/part-01.json  (1.010.293 review IMDb, CC0, ~1,0 GB)\n"
        "        │  prepare.py: JSONL → làm sạch → loại trùng → chia tập\n"
        "        ▼\n"
        "data/processed/{train,val,test}.parquet   +   eval_labels.parquet (chỉ test)\n"
        "        │  train.py: Pipeline (Tokenizer → StopWords → NGram → TF-IDF → Normalizer → Classifier)\n"
        "        ▼\n"
        "outputs/models/sentiment_pipeline   (+ metadata JSON)\n"
        "        │\n"
        "        │  replay_producer.py  (message 5 trường, KHÔNG có nhãn)\n"
        "        ▼\n"
        "Kafka topic comments_raw  (3 partition)\n"
        "        │  stream_job.py: from_json(schema tường minh) → DLQ? → clean_text() → model.transform()\n"
        "        ├──────────────► outputs/stream/<run>/scored_detail   (Parquet, theo ngày/giờ)\n"
        "        ├──────────────► Kafka comments_scored               (JSON đã chấm)\n"
        "        ├──────────────► outputs/stream/<run>/window_1min     (event time, 1 phút)\n"
        "        ├──────────────► outputs/stream/<run>/window_sliding_10s (10 giây, trượt 5 giây)\n"
        "        └──────────────► DLQ: Kafka comments_dlq + outputs/stream/<run>/dlq (kèm reason)\n"
        "        │\n"
        "        ├── verify_stream.py  → đối soát + macro-F1 trên luồng + độ trễ\n"
        "        ├── queries.py/plots.py → bảng eda_*.csv + hình 06–15 + insights.md\n"
        "        └── app.py / terminal_app.py → dashboard và walkthrough"
    )

    h2("1.5. Muốn làm gì thì chạy chương trình nào")
    table(
        ["Mục tiêu", "Lệnh / chương trình", "Chương"],
        [
            ["Kiểm tra môi trường", "bash scripts/check_env.sh --smoke", "2"],
            ["Tạo lại dữ liệu huấn luyện", "spark-submit src/training/prepare.py", "4"],
            ["Huấn luyện lại mô hình", "spark-submit src/training/train.py", "5"],
            ["Chạy toàn bộ demo (Kafka → dashboard)", "bash scripts/run_demo.sh --duration 600", "12"],
            ["Chỉ chạy job streaming", "bash scripts/run_stream.sh <tên>", "6, 12"],
            ["Phát dữ liệu replay", "$VENV_PY src/producer/replay_producer.py", "7"],
            ["Kiểm chứng một lần chạy", "spark-submit src/streaming/verify_stream.py", "6"],
            ["Xem dashboard", "$VENV_PY -m streamlit run src/app/app.py", "8"],
            ["Xem quy trình trong terminal", "bash scripts/run_terminal_app.sh", "9"],
            ["Chấm từng comment ngay khi đến", "bash scripts/run_comment_stream.sh", "9"],
            ["Thử mô hình với câu tự nhập", "bash scripts/run_model_trial.sh", "10"],
            ["Chạy lại EDA và vẽ hình", "$VENV_PY src/eda/queries.py && $VENV_PY src/eda/plots.py", "11"],
            ["Chạy kiểm thử", ".venv/bin/python -m pytest tests/ -q", "14"],
        ],
        widths=[6.0, 8.6, 1.8],
    )

    h2("1.6. Ba cách chạy hệ thống")
    h3("Cách 1 — Toàn bộ hệ thống bằng một lệnh")
    p("Dùng khi demo trước hội đồng. run_demo.sh khởi động Kafka, tạo topic, chạy job "
      "streaming, chờ job in READY, chạy producer replay ở nền, rồi mở dashboard. "
      "Khi dừng, script dừng theo thứ tự ngược lại để không còn tiến trình nào ghi vào sink.")
    code("cd /home/hadoop/capstone\n"
         "source scripts/env.sh\n"
         "bash scripts/run_demo.sh --duration 600\n"
         "# mở http://localhost:8501\n"
         "bash scripts/run_demo.sh --stop")
    h3("Cách 2 — Chỉ xem dashboard với dữ liệu đã có")
    p("Dashboard chỉ đọc Parquet, không cần Kafka và không cần Spark ở tab Live Monitor.")
    code("source scripts/env.sh\n"
         "$VENV_PY -m streamlit run src/app/app.py --server.address 0.0.0.0 --server.port 8501")
    h3("Cách 3 — Xem quy trình trong terminal, không cần Kafka")
    p("App terminal dùng đúng code của hệ thống nhưng chạy offline trên mẫu đã lưu. "
      "Đây là cách phù hợp để giải thích từng bước mà không phụ thuộc broker.")
    code("bash scripts/run_terminal_app.sh                # 8 giai đoạn, Enter sau mỗi bước\n"
         "bash scripts/run_terminal_app.sh --fast --limit 20\n"
         "bash scripts/run_comment_stream.sh              # từng comment, kết quả ngay")

    h2("1.7. Quy trình sáu bước để đọc một file code")
    steps([
        "Đọc docstring đầu file (trong ba dấu ngoặc kép) — thường nêu mục đích, luồng dữ liệu "
        "và các lệnh chạy mẫu.",
        "Tìm hàm main() và phần argparse — đó là danh sách đầy đủ các tham số và giá trị mặc định.",
        "Trong main(), đọc theo thứ tự: nạp config → nạp dữ liệu → biến đổi → ghi kết quả.",
        "Với mỗi hàm được gọi, nhảy tới định nghĩa và chỉ đọc phần docstring + vài dòng đầu.",
        "Đối chiếu đầu ra: tên file/thư mục trong code với file thật trong outputs/.",
        "Đọc log khi chạy: mỗi bước quan trọng đều in số dòng vào/ra, thời gian và đường dẫn.",
    ])
    note("Mọi script Python của dự án đều có cấu trúc chung: PROJECT_ROOT được suy từ vị trí file, "
         "config đọc bằng load_config(), đường dẫn cục bộ đi qua local_uri() để tránh HDFS, "
         "và seed lấy từ config (mặc định 42). Nắm bốn quy ước này là đọc được mọi file.",
         "info", "MẸO ĐỌC NHANH")

    h2("1.8. Năm điều phải nhớ trước khi đọc tiếp")
    bullets([
        "Dữ liệu streaming là replay IMDb, không phải livestream thật. Mọi câu trong báo cáo "
        "phải nói rõ phần nào là mô phỏng.",
        "Nhãn cảm xúc được suy từ rating IMDb (1–4 negative, 5–6 neutral, 7–10 positive), "
        "không phải nhãn gán tay; lớp neutral rất nhiễu.",
        "Nhãn không bao giờ đi vào Kafka. Nhãn test nằm riêng ở data/processed/eval_labels.parquet "
        "và chỉ được ghép theo comment_id khi đánh giá.",
        "TF-IDF nằm trong Pipeline và chỉ fit trên train. Tập test chỉ dùng một lần ở cuối.",
        "Chỉ khẳng định at-least-once. Exactly-once chưa được kiểm chứng; không được viết "
        "trong báo cáo như một kết quả đã đo.",
    ])


# ---------------------------------------------------------------------------
# Chương 2 — Môi trường và cấu hình
# ---------------------------------------------------------------------------
def ch2() -> None:
    chapter(2)
    h2("2.1. scripts/env.sh — một chỗ duy nhất khai báo môi trường")
    p("Mọi script đều source file này trước khi chạy. Lý do: chạy được cả khi không nạp "
      ".bashrc (cron, script gọi script), và tránh mỗi nơi dùng một phiên bản Java/Python khác nhau.")
    p("Cách dùng:", bold=True)
    code("source scripts/env.sh\necho $SPARK_HOME $VENV_PY $JAVA_HOME")
    table(
        ["Dòng lệnh", "Ý nghĩa"],
        [
            ["export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-arm64",
             "Spark 3.5.9 chạy Java 8. Đây là Java dùng cho spark-submit."],
            ["export HADOOP_HOME=/usr/local/hadoop", "Cài Hadoop của máy, dùng cho HDFS và event log."],
            ["export HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop", "Spark đọc cấu hình HDFS từ đây."],
            ["export SPARK_HOME=/home/hadoop/spark-3.5.9", "Bản Spark duy nhất của dự án."],
            ["export SPARK_KAFKA_PKG=org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.9",
             "Gói connector Kafka. Phải khớp Spark 3.5.9 và Scala 2.12; gói đã có trong ~/.ivy2/jars."],
            ["export PYSPARK_PYTHON=/usr/bin/python3.11",
             "Python cho executor. PySpark 3.5.9 lỗi với Python 3.14 (cloudpickle RecursionError)."],
            ["export PYSPARK_DRIVER_PYTHON=/usr/bin/python3.11", "Python cho driver."],
            ["mkdir -p /home/hadoop/spark-tmp", "Tạo thư mục tạm trên ổ đĩa thật."],
            ["export SPARK_LOCAL_DIRS=/home/hadoop/spark-tmp", "Nơi Spark ghi shuffle/spill."],
            ["export TMPDIR=/home/hadoop/spark-tmp", "Nơi các tiến trình con ghi file tạm."],
            [". \"$HOME/.capstone-secrets.sh\"", "Nạp bí mật cục bộ (COMMENT_HASH_SALT) nếu có; file không nằm trong repo."],
            ["export KAFKA_HOME=/home/hadoop/kafka", "Cài Kafka 4.3.1."],
            ["export KAFKA_JAVA_HOME=/home/hadoop/jdk-17", "Kafka 4.x bắt buộc Java 17 (KIP-1013)."],
            ["export KAFKA_DATA_DIR=/home/hadoop/kafka-data", "Thư mục log dữ liệu của broker."],
            ["export KAFKA_BOOTSTRAP=localhost:9092", "Địa chỉ broker dùng xuyên suốt."],
            ["PROJECT_ROOT=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")/..\" && pwd)\"",
             "Suy gốc dự án từ vị trí file env.sh, không hard-code đường dẫn."],
            ["export VENV_PY=\"$PROJECT_ROOT/.venv/bin/python\"",
             "Python của venv cho producer, EDA, dashboard, app terminal."],
            ["case \":$PATH:\" in ... esac", "Thêm Spark/Hadoop vào PATH nhưng không thêm trùng."],
        ],
        widths=[7.4, 9.0],
    )
    note("Có hai môi trường Python: PYSPARK_PYTHON=3.11 cho Spark, và VENV_PY cho các thư viện "
         "thường (kafka-python, streamlit, pandas). Không trộn hai môi trường này.",
         "warn")

    h2("2.2. scripts/check_env.sh — kiểm tra trước khi chạy")
    p("Script kiểm tra nhanh (~5 giây) các thành phần bắt buộc và trả mã thoát 0 nếu mọi thứ OK, "
      "1 nếu có mục FAIL. Với --smoke, script tạo một SparkSession thật và chạy spark.range(5).count().")
    code("bash scripts/check_env.sh\nbash scripts/check_env.sh --smoke")
    table(
        ["Mục kiểm tra", "Cách kiểm tra", "Khi FAIL thì làm gì"],
        [
            ["Java", "java -version", "Kiểm tra JAVA_HOME trong scripts/env.sh."],
            ["HDFS NameNode", "jps | grep NameNode", "/usr/local/hadoop/sbin/start-dfs.sh"],
            ["/spark-logs", "hdfs dfs -ls -d /spark-logs", "hdfs dfs -mkdir -p /spark-logs"],
            ["spark-submit", "-x $SPARK_HOME/bin/spark-submit", "Kiểm tra SPARK_HOME."],
            ["pandas cho Python 3.11", "python3.11 -c 'import pandas'", "Cài pandas cho 3.11."],
            ["streamlit", "python3 -c 'import streamlit'", "Cài streamlit cho Python mặc định."],
            ["Smoke Spark", "spark-submit một script tạm in SPARK_OK", "Xem log Spark để biết lỗi."],
        ],
        widths=[4.0, 7.4, 5.0],
    )
    p("Lưu ý: HDFS chỉ dùng cho event log của Spark. Nếu HDFS tắt, run_stream.sh tự chạy với "
      "spark.eventLog.enabled=false; sink và checkpoint vẫn ghi bình thường trên ổ đĩa cục bộ.")

    h2("2.3. config.yaml — tham số dùng chung")
    p("CLAUDE.md §3 yêu cầu không hard-code tham số trong script. config.yaml là nguồn duy nhất "
      "cho seed, đường dẫn, ngưỡng làm sạch, lưới siêu tham số, cấu hình Kafka/streaming, "
      "ngưỡng cảnh báo và cấu hình dashboard. Dưới đây là các mục theo thứ tự trong file.")
    h3("seed và paths")
    table(
        ["Khóa", "Giá trị hiện tại", "Dùng ở đâu"],
        [
            ["seed", "42", "prepare, train, producer, app terminal — mọi bước có yếu tố ngẫu nhiên."],
            ["paths.raw_comments", "data/raw/part-01.json", "prepare.py"],
            ["paths.raw_jsonl", "data/processed/imdb_jsonl", "prepare.py (JSONL trung gian)"],
            ["paths.train / val / test", "data/processed/{train,val,test}.parquet", "prepare, train, EDA"],
            ["paths.eval_labels", "data/processed/eval_labels.parquet", "verify_stream, producer --only-test"],
            ["paths.outputs_tables / figures / logs", "outputs/tables, outputs/figures, logs", "mọi script"],
        ],
        widths=[5.4, 6.2, 4.8],
    )
    h3("labels, cleaning, dedup, split, prepare")
    table(
        ["Khóa", "Giá trị", "Ý nghĩa"],
        [
            ["labels.mapping", "1–4 negative; 5–6 neutral; 7–10 positive", "Ánh xạ thiết kế từ rating IMDb; dữ liệu gốc không có nhãn cảm xúc."],
            ["labels.index", "negative=0, neutral=1, positive=2", "Chỉ số lớp cho Spark ML và metadata model."],
            ["cleaning.min_chars / max_chars", "20 / 5000", "Ngưỡng loại văn bản quá ngắn/quá dài, dùng chung train và streaming."],
            ["cleaning.abbreviations", "21 cặp teencode", "Thay theo ranh giới từ, trước khi chuẩn hóa."],
            ["dedup.near_dup", "true", "Loại cả gần trùng theo bộ từ sau chuẩn hóa."],
            ["split.method", "group_movie_balanced", "Chia theo nhóm phim để tránh rò rỉ; có thể đổi sang stratified."],
            ["split.ratios", "0.70 / 0.15 / 0.15", "Tỷ lệ train/validation/test."],
            ["prepare.truncate_raw_detail", "20000", "Cắt review_detail khi chuyển JSONL."],
            ["prepare.subsample_pct", "64", "Giữ 64% nguồn theo crc32(review_id); tất định và lồng nhau."],
            ["prepare.sample_rows_out", "1000", "Số dòng mẫu ghi ra clean_sample.csv."],
            ["prepare.emoji_top_n", "30", "Số emoji phổ biến ghi ra emoji_frequency.csv."],
        ],
        widths=[4.6, 5.4, 6.4],
    )
    h3("training")
    table(
        ["Khóa", "Giá trị", "Ý nghĩa"],
        [
            ["vectorizer.vocab_size / min_df", "20000 / 3", "Số từ/ngram giữ lại; bỏ từ xuất hiện dưới 3 tài liệu."],
            ["normalize_l2", "true", "Chuẩn hóa L2 vector TF-IDF."],
            ["keep_negations", "true", "Giữ not/no/never/n't — bỏ đi sẽ mất tín hiệu phủ định."],
            ["class_weights", "balanced", "w_c = N/(k·n_c), tính trên train."],
            ["tvs.train_ratio / metric", "0.8 / f1", "TrainValidationSplit bên trong train; Spark 3.5 không có evaluator macro-F1."],
            ["grids.nb / lr / svc / rf", "xem file", "Lưới siêu tham số từng mô hình."],
            ["top_features_n / error_n", "20 / 30", "Số từ hàng đầu mỗi lớp; số lỗi đem phân tích."],
            ["model_out", "outputs/models/sentiment_pipeline", "Nơi lưu PipelineModel."],
            ["leakage_threshold_macro_f1", "0.95", "Vượt ngưỡng thì không lưu model, ghi leakage_alert.txt, thoát mã 2."],
        ],
        widths=[5.0, 5.2, 6.2],
    )
    h3("kafka, streaming, replay")
    table(
        ["Khóa", "Giá trị", "Ý nghĩa"],
        [
            ["kafka.bootstrap_servers", "localhost:9092", "Broker."],
            ["kafka.topic_raw / scored / dlq", "comments_raw / comments_scored / comments_dlq", "Ba topic của dự án."],
            ["kafka.producer.acks / linger_ms", "all / 20", "Chờ broker xác nhận; gom lô nhỏ để tăng thông lượng."],
            ["streaming.starting_offsets", "latest", "Chỉ xử lý bản ghi đến sau khi query khởi động; phải chờ READY mới phát."],
            ["streaming.max_offsets_per_trigger", "5000", "Trần bản ghi mỗi micro-batch."],
            ["streaming.trigger_seconds", "10", "Chu kỳ micro-batch."],
            ["streaming.watermark", "2 minutes", "Mốc muộn tối đa; bằng 4× mức trễ giả lập tối đa 30 giây."],
            ["streaming.window_duration", "1 minute", "Cửa sổ nhảy."],
            ["streaming.sliding_window_duration / slide", "10 seconds / 5 seconds", "Cửa sổ trượt thật sự."],
            ["streaming.privacy.keep_text", "false", "Mặc định không lưu văn bản trong bảng chi tiết."],
            ["streaming.dlq.to_kafka / to_parquet", "true / true", "Ghi DLQ ra cả hai đích."],
            ["replay.rate / burst_prob / burst_factor / burst_len_s", "50 / 0.02 / 8 / 2.0", "Tốc độ và mô phỏng bùng nổ."],
            ["replay.late_ratio / late_max_s", "0.05 / 30", "5% bản ghi bị đẩy trễ tới 30 giây để thử watermark."],
        ],
        widths=[5.4, 5.0, 6.0],
    )
    h3("eda, dashboard, model_trial")
    table(
        ["Khóa", "Giá trị", "Ý nghĩa"],
        [
            ["eda.streaming_run", "verify1", "Lần chạy streaming dùng cho EDA."],
            ["eda.top_words_n / min_count", "20 / 20", "Từ đặc trưng mỗi lớp; bỏ từ hiếm trong lớp."],
            ["eda.emoji_per_class_n / length bins", "12 / 25, 400", "Tham số hình 09 và 07."],
            ["eda.alert.negative_share_threshold / min_comments", "0.30 / 5", "Cảnh báo khi tỷ lệ âm > 30% và có ít nhất 5 bình luận."],
            ["eda.burst.sigma", "2.0", "Bùng nổ = giây có số bình luận > mean + 2σ."],
            ["dashboard.streaming_run", "demo", "Lần chạy dashboard đọc mặc định."],
            ["dashboard.refresh_seconds / recent_minutes / latest_comments_n", "5 / 30 / 10", "Nhịp làm mới, cửa sổ thời gian, số bình luận mới nhất."],
            ["dashboard.current_window_s", "30", "Cửa sổ hiện tại để tính tỷ lệ và xét cảnh báo."],
            ["dashboard.mask_words / mask_patterns", "5 từ + email/SĐT", "Che dữ liệu hiển thị."],
            ["model_trial.split / max_sample_rows / max_batch_rows", "test / 5000 / 10000", "Cấu hình công cụ thử mô hình."],
        ],
        widths=[5.8, 5.0, 5.6],
    )
    note("Khi đổi config, phải chạy lại đúng bước phụ thuộc. Ví dụ đổi cleaning.min_chars ảnh hưởng "
         "cả prepare lẫn streaming; đổi labels.mapping phải chạy lại prepare và train.",
         "warn")

    h2("2.4. Bí mật: muối băm người dùng")
    p("user_hash = SHA-256(salt + user_id), lấy 16 ký tự hex. Muối đọc từ biến môi trường "
      "COMMENT_HASH_SALT, không nằm trong repo. Tạo một lần:")
    code("python3 -c \"import secrets;print('export COMMENT_HASH_SALT='+secrets.token_hex(16))\" \\\n"
         "  >> ~/.capstone-secrets.sh && chmod 600 ~/.capstone-secrets.sh\n"
         "source scripts/env.sh   # nạp lại")
    p("Nếu thiếu muối, prepare.py và các script cần băm sẽ dừng với mã 2 thay vì dùng giá trị mặc định. "
      "Không bao giờ ghi muối vào config.yaml hay code.")

    h2("2.5. Bốn quy ước Python lặp lại ở mọi file")
    table(
        ["Quy ước", "Cách viết", "Vì sao"],
        [
            ["Suy gốc dự án", "PROJECT_ROOT = Path(__file__).resolve().parents[N]",
             "Chạy được từ bất kỳ thư mục nào."],
            ["Đường dẫn cục bộ", "local_uri(path) → 'file://' + path",
             "Filesystem mặc định của Spark trên máy này là HDFS; thiếu file:// sẽ tìm sai."],
            ["Đọc config", "cfg = load_config(args.config)",
             "Một nguồn tham số duy nhất, hỗ trợ đường dẫn tương đối."],
            ["Seed", "seed = args.seed or cfg['seed']", "Tái lập kết quả; mặc định 42."],
        ],
        widths=[4.0, 7.2, 5.2],
    )

    h2("2.6. Lệnh kiểm tra môi trường tối thiểu")
    code("cd /home/hadoop/capstone\n"
         "source scripts/env.sh\n"
         "bash scripts/check_env.sh --smoke\n"
         "java -version 2>&1 | head -1          # phải là 1.8\n"
         "python3.11 -c 'import pyspark; print(pyspark.__version__)'   # 3.5.9\n"
         "$VENV_PY -c 'import kafka, streamlit, pandas; print(\"ok\")'")


# ---------------------------------------------------------------------------
# Chương 3 — Kafka
# ---------------------------------------------------------------------------
def ch3() -> None:
    chapter(3)
    h2("3.1. Kafka làm gì trong dự án này")
    p("Kafka là hàng đợi sự kiện giữa producer (phát review) và Spark Structured Streaming "
      "(đọc và chấm điểm). Producer ghi message vào topic; Spark đọc theo offset. Nhờ vậy "
      "hai phía không cần biết nhau, và dữ liệu không mất nếu một phía chậm.")
    table(
        ["Khái niệm", "Trong dự án"],
        [
            ["Broker", "Một tiến trình Kafka chạy tại localhost:9092, chế độ KRaft (không cần Zookeeper)."],
            ["Topic", "comments_raw (đầu vào), comments_scored (kết quả), comments_dlq (bản ghi lỗi)."],
            ["Partition", "comments_raw và comments_scored có 3; comments_dlq có 1."],
            ["Offset", "Số thứ tự của message trong một partition. Spark commit offset theo từng micro-batch."],
            ["Key", "Producer dùng comment_id làm key để các bản ghi cùng bình luận vào cùng partition."],
            ["Replication factor", "1 — máy đơn, không có bản sao."],
        ],
        widths=[4.0, 12.4],
    )

    h2("3.2. kafka/start_kafka.sh — khởi động broker")
    code("bash kafka/start_kafka.sh")
    p("Script chạy nền (nohup), ghi log vào /home/hadoop/kafka/logs/broker.log, và chỉ thoát "
      "khi broker trả lời được trên localhost:9092 (hoặc báo lỗi sau 60 giây).")
    table(
        ["Dòng lệnh", "Ý nghĩa"],
        [
            ["set -u", "Dừng nếu dùng biến chưa khai báo — phát hiện lỗi cấu hình sớm."],
            ["source \"$(dirname \"$0\")/../scripts/env.sh\"", "Nạp đường dẫn và phiên bản."],
            ["export JAVA_HOME=\"$KAFKA_JAVA_HOME\"", "Dùng Java 17 cho Kafka, không dùng Java 8 của Spark."],
            ["LOG_DIR=...; mkdir -p ...", "Tạo thư mục log và dữ liệu nếu chưa có."],
            ["kafka-broker-api-versions.sh --bootstrap-server ...", "Kiểm tra broker đã sống chưa; nếu rồi thì thoát 0."],
            ["export KAFKA_HEAP_OPTS=\"-Xmx512M -Xms256M\"", "Heap nhỏ, phù hợp máy ảo ~7 GB dùng chung HDFS/Spark."],
            ["nohup kafka-server-start.sh config/server.properties &", "Chạy broker ở nền, không phụ thuộc terminal."],
            ["for i in $(seq 1 60); do ...", "Chờ tối đa 60 giây, mỗi giây thử kết nối lại."],
            ["exit 1", "Báo lỗi rõ nếu broker không lên, kèm đường dẫn log."],
        ],
        widths=[7.6, 8.8],
    )
    note("Kafka 4.x bắt buộc Java 17. Nếu vô tình dùng Java 8, broker thoát ngay với lỗi "
         "UnsupportedClassVersionError trong broker.log.", "warn")

    h2("3.3. kafka/create_topics.sh — tạo ba topic")
    code("bash kafka/create_topics.sh")
    table(
        ["Topic", "Partition", "Vai trò"],
        [
            ["comments_raw", "3", "Message thô từ producer: 5 trường, không có nhãn."],
            ["comments_scored", "3", "Kết quả chấm điểm từ query `kafka` của stream_job."],
            ["comments_dlq", "1", "Bản ghi lỗi kèm reason và thông tin truy vết."],
        ],
        widths=[4.2, 2.4, 9.8],
    )
    p("Script dùng --if-not-exists nên chạy lại nhiều lần không lỗi; sau khi tạo, nó in "
      "--list và --describe để xác nhận.")
    code("K=\"$KAFKA_HOME/bin/kafka-topics.sh --bootstrap-server $KAFKA_BOOTSTRAP\"\n"
         "$K --create --if-not-exists --topic comments_raw --partitions 3 --replication-factor 1\n"
         "$K --list\n$K --describe")
    p("Từng phần của câu lệnh: --bootstrap-server chỉ broker; --create tạo topic; "
      "--if-not-exists bỏ qua nếu đã có; --partitions đặt số partition; --replication-factor 1 "
      "vì chỉ có một broker.")

    h2("3.4. kafka/stop_kafka.sh — dừng sạch")
    code("bash kafka/stop_kafka.sh")
    p("Script kiểm tra broker có sống không; nếu có, gọi kafka-server-stop.sh (SIGTERM), "
      "chờ tối đa 30 giây, rồi xác nhận. Nếu vẫn sống, script in PID tiến trình java để người "
      "dùng tự quyết định — mặc định không dùng kill -9.")
    table(
        ["Dòng lệnh", "Ý nghĩa"],
        [
            ["kafka-broker-api-versions.sh ... || exit 0", "Không có broker thì không làm gì."],
            ["kafka-server-stop.sh", "Gửi tín hiệu dừng chuẩn, broker đóng log và thoát."],
            ["for i in $(seq 1 30); do ...", "Chờ tối đa 30 giây để cổng 9092 ngừng trả lời."],
            ["pgrep -af \"kafka.Kafka\"", "In tiến trình còn sống để người dùng kiểm tra."],
        ],
        widths=[7.4, 9.0],
    )

    h2("3.5. Kiểm tra Kafka bằng tay")
    code("source scripts/env.sh\n"
         "export JAVA_HOME=$KAFKA_JAVA_HOME\n"
         "$KAFKA_HOME/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list\n"
         "$KAFKA_HOME/bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe\n"
         "# đọc thử 5 message đầu của topic\n"
         "$KAFKA_HOME/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 \\\n"
         "  --topic comments_raw --from-beginning --max-messages 5\n"
         "# xem offset cuối của từng partition\n"
         "$KAFKA_HOME/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic comments_raw")

    h2("3.6. Lỗi Kafka thường gặp")
    table(
        ["Triệu chứng", "Nguyên nhân thường gặp", "Cách xử lý"],
        [
            ["Connection refused localhost:9092", "Broker chưa chạy hoặc vừa chết", "bash kafka/start_kafka.sh; xem broker.log"],
            ["UnsupportedClassVersionError", "Kafka chạy nhầm Java 8", "Kiểm tra KAFKA_JAVA_HOME; start_kafka.sh tự đặt Java 17"],
            ["Topic đã tồn tại", "Chạy create_topics nhiều lần", "Không lỗi nhờ --if-not-exists"],
            ["Producer gửi nhưng Spark không thấy", "Job đọc startingOffsets=latest và chưa READY", "Chờ READY rồi mới phát; xem Chương 6"],
            ["UnknownTopicOrPartition", "Chưa tạo topic", "bash kafka/create_topics.sh"],
        ],
        widths=[5.0, 5.8, 5.6],
    )


# ---------------------------------------------------------------------------
# Chương 4 — prepare.py
# ---------------------------------------------------------------------------
def ch4() -> None:
    chapter(4)
    h2("4.1. Vai trò trong hệ thống")
    p("prepare.py biến file JSON thô của IMDb thành dữ liệu huấn luyện sạch, có nhãn và "
      "đã chia tập. Đây là bước duy nhất được phép đọc data/raw. Nó tạo ra bốn sản phẩm: "
      "train/val/test parquet, nhãn đánh giá của test (eval_labels), các bảng thống kê "
      "làm sạch/phân bố lớp, và mẫu 1.000 dòng để app terminal dùng offline.")
    p("Điểm quan trọng: mọi bước biến đổi (làm sạch, loại trùng, chia tập) xảy ra TRƯỚC khi "
      "chia train/val/test, để không có bản ghi nào xuất hiện ở hai tập. TF-IDF không được "
      "học ở đây; nó nằm trong Pipeline của train.py.")

    h2("4.2. Cách chạy")
    code("# chạy thử 20.000 dòng (ghi đè data/processed — chỉ chạy khi chưa có bản đầy đủ)\n"
         "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\\n"
         "  --driver-memory 2g --master 'local[2]' src/training/prepare.py --sample 20000\n\n"
         "# bản đầy đủ (dùng prepare.subsample_pct trong config)\n"
         "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\\n"
         "  --driver-memory 2g --master 'local[2]' src/training/prepare.py")
    note("--sample vẫn ghi đè data/processed/*.parquet bằng bản N dòng. Chạy thử SAU khi đã "
         "chạy bản đầy đủ sẽ phá tập thật. Hãy chạy thử trước, hoặc dùng một bản sao dự án.",
         "warn")

    h2("4.3. Tham số")
    table(
        ["Tham số", "Mặc định", "Ý nghĩa"],
        [
            ["--config", "config.yaml", "Đường dẫn file cấu hình."],
            ["--sample N", "0 (dùng toàn bộ tập con)", "Giữ N dòng có crc32(comment_id) nhỏ nhất — tất định, trải đều file."],
            ["--method", "split.method trong config", "Ghi đè phương pháp chia: group_movie_balanced hoặc stratified."],
            ["--seed", "config.seed = 42", "Seed cho thuật toán chia tập."],
        ],
        widths=[3.4, 4.6, 8.4],
    )

    h2("4.4. Đầu vào và đầu ra")
    table(
        ["Loại", "Đường dẫn", "Nội dung"],
        [
            ["Vào", "data/raw/part-01.json", "Mảng JSON 1.010.293 review IMDb (CC0)."],
            ["Trung gian", "data/processed/imdb_jsonl/part-000.jsonl", "JSONL để Spark đọc song song; review_detail cắt ở 20.000 ký tự."],
            ["Ra", "data/processed/train.parquet", "70% số nhóm phim (theo tỷ lệ cấu hình)."],
            ["Ra", "data/processed/val.parquet", "15% — dùng để chọn mô hình."],
            ["Ra", "data/processed/test.parquet", "15% — chỉ dùng một lần ở cuối."],
            ["Ra", "data/processed/eval_labels.parquet", "comment_id, label, rating của test; producer/verify dùng."],
            ["Ra", "outputs/tables/cleaning_log.csv", "Số dòng vào/ra từng bước làm sạch."],
            ["Ra", "outputs/tables/class_distribution.csv", "Phân bố lớp theo từng tập và toàn bộ."],
            ["Ra", "outputs/tables/clean_sample.csv", "1.000 dòng mẫu kèm text và text_raw."],
            ["Ra", "outputs/tables/emoji_frequency.csv", "30 emoji phổ biến nhất."],
        ],
        widths=[3.0, 6.4, 7.0],
    )

    h2("4.5. Các bước hoạt động")
    steps([
        "Đọc muối COMMENT_HASH_SALT. Thiếu muối thì dừng với mã 2, không dùng giá trị mặc định.",
        "Chuyển JSON → JSONL: đọc từng phần tử của mảng JSON, cắt review_detail ở 20.000 ký tự, "
        "giữ lại pct% theo crc32(review_id). Ghi _manifest.json để lần sau bỏ qua nếu nguồn không đổi.",
        "Đọc JSONL bằng schema tường minh. Kiểm tra số dòng Spark đọc được khớp manifest — "
        "nếu lệch, cảnh báo vì có file lạ trong thư mục.",
        "Tạo các cột: comment_id, stream_id (tên phim), user_hash (băm có muối), text (đã làm sạch), "
        "n_chars, n_tokens, label (từ rating). Bỏ reviewer và review_detail gốc.",
        "Lọc: bỏ văn bản rỗng, thiếu nhãn, ngắn hơn 20 ký tự, dài hơn 5.000 ký tự. Ghi số lượng từng nhóm.",
        "Loại trùng mã: nguồn có review_id lặp; giữ bản có văn bản dài nhất, hòa thì lấy ngày cũ hơn.",
        "Loại trùng chính xác: cùng md5(text) sau làm sạch.",
        "Loại gần trùng: cùng dedup_key(text) — bộ từ đã chuẩn hóa, bỏ qua thứ tự và dấu câu.",
        "Chia tập: group_movie_balanced chia theo nhóm phim, cân bằng lớp bằng tham lam + hoán đổi cục bộ; "
        "stratified chia ngẫu nhiên phân tầng. Ghi kiểm tra: không phim nào ở hai tập.",
        "Ghi parquet, eval_labels, cleaning_log, class_distribution, clean_sample, emoji_frequency.",
    ])

    h2("4.6. Các câu lệnh cốt lõi")
    table(
        ["Câu lệnh / hàm", "Nó làm gì"],
        [
            ["keep_record(review_id, pct)", "crc32(review_id) % 1000 < pct×10. Tất định theo id, các mức lồng nhau "
             "(20% ⊂ 64% ⊂ 100%). Không phụ thuộc vị trí trong file."],
            ["iter_json_array(raw_path)", "Đọc mảng JSON khổng lồ theo từng phần tử, không nạp cả GB vào RAM."],
            ["label_expr(cfg)", "Chuỗi F.when(...).when(...).otherwise(None): rating 1–4 → negative, 5–6 → neutral, "
             "7–10 → positive. Dùng Spark SQL, không dùng UDF."],
            ["user_hash_expr(salt)", "sha2(concat(lit(salt), col('reviewer')), 256) rồi lấy 16 ký tự hex — "
             "khớp hàm salted_hash bên Python."],
            ["clean_text(col, abbreviations)", "Hàm dùng chung ở src/common/text_cleaning.py; xem Chương 13."],
            ["valid = df.filter(keep).persist()", "Giữ các dòng qua mọi kiểm tra; persist để dùng lại nhiều lần."],
            ["Window.partitionBy('comment_id').orderBy(length('text').desc(), 'review_date')",
             "Xếp hạng bản ghi trùng mã; row_number() == 1 là bản được giữ."],
            ["Window.partitionBy('key_exact').orderBy('comment_id')", "Loại trùng chính xác theo md5(text)."],
            ["Window.partitionBy('key_near').orderBy('comment_id')", "Loại gần trùng theo dedup_key(text)."],
            ["split_group_movie_balanced(...)", "Tham lam chọn tập đang thiếu nhiều nhất cho từng phim, sau đó "
             "hoán đổi cục bộ để cân tỷ lệ lớp; seed 42."],
            ["assert movie_leak == 0", "Nếu một phim nằm ở hai tập, dừng ngay — đó là rò rỉ dữ liệu."],
            [".write.mode('overwrite').parquet(local_uri(path))", "Ghi đè có kiểm soát; local_uri thêm file:// để "
             "Spark không tìm trên HDFS."],
        ],
        widths=[7.2, 9.2],
    )

    h2("4.7. Cách đọc kết quả")
    p("cleaning_log.csv có một dòng cho mỗi bước, với rows_in, rows_removed, rows_out và note. "
      "Muốn biết mất bao nhiêu dữ liệu và vì sao, đọc từ trên xuống: nạp raw → thiếu văn bản → "
      "thiếu nhãn → quá ngắn → quá dài → trùng mã → trùng chính xác → trùng gần → còn lại.")
    p("class_distribution.csv cho biết tỷ lệ negative/neutral/positive trong từng tập. Đây là "
      "căn cứ cho ngưỡng cảnh báo 30% ở Chương 11: tỷ lệ negative trên test là 0,2506, cộng biên "
      "5 điểm phần trăm.")
    p("clean_sample.csv là đầu vào của app terminal ở chế độ offline. Cột text là văn bản đã làm sạch; "
      "text_raw là văn bản gốc để đối chiếu bằng mắt.")

    h2("4.8. Những điểm dễ sai đã gặp thật")
    bullets([
        "review_id không duy nhất: nguồn có 1.010.293 bản ghi nhưng chỉ 994.692 id khác nhau; "
        "15.601 dòng lặp id. Phải loại trùng theo comment_id trước khi chia tập và trước khi nối nhãn.",
        "Tên manifest phải bắt đầu bằng dấu _ (_manifest.json), nếu không Spark đọc nó thành một bản ghi rỗng.",
        "--sample phải lấy mẫu tất định theo crc32, không dùng sample().limit() — cách sau dồn mẫu về đầu file.",
        "Mọi đường dẫn cục bộ phải có file:// vì HDFS là filesystem mặc định của Spark trên máy này.",
        "Chia tập phải chọn tập đang thiếu nhiều nhất (argmax), không phải argmin khoảng cách — bản đầu "
        "dồn hết dữ liệu vào val/test, train còn 0 dòng.",
    ])


# ---------------------------------------------------------------------------
# Chương 5 — train.py
# ---------------------------------------------------------------------------
def ch5() -> None:
    chapter(5)
    h2("5.1. Vai trò trong hệ thống")
    p("train.py huấn luyện bốn mô hình phân loại cảm xúc, chọn mô hình tốt nhất trên validation "
      "theo macro-F1, rồi đánh giá đúng một lần trên test. Kết quả cuối là một PipelineModel "
      "đã lưu, dùng lại nguyên vẹn trong streaming, dashboard và app terminal.")
    p("TF-IDF nằm trong Pipeline, nên khi fit Pipeline trên train thì vectorizer chỉ thấy train. "
      "Đây là yêu cầu bắt buộc của CLAUDE.md §6 và là lý do không được vector hóa trước rồi mới chia tập.")

    h2("5.2. Cách chạy")
    code("# chạy thử: --sample tự bật --no-test, không chạm tập test\n"
         "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\\n"
         "  --driver-memory 2g --master 'local[2]' src/training/train.py --sample 20000\n\n"
         "# bản đầy đủ: chọn trên val, đánh giá test một lần, lưu model\n"
         "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\\n"
         "  --driver-memory 4g --master 'local[2]' src/training/train.py\n\n"
         "# chỉ vẽ lại hình từ bảng đã lưu (không huấn luyện, không chạm test)\n"
         "$VENV_PY src/training/train.py --figures-only")
    note("Với prepare.subsample_pct=64 (khoảng 415k dòng train), dùng --driver-memory 4g. "
         "Ở 2g, cache từng không vừa và Spark phải đẩy block ra đĩa.", "warn")

    h2("5.3. Tham số")
    table(
        ["Tham số", "Mặc định", "Ý nghĩa"],
        [
            ["--config", "config.yaml", "File cấu hình."],
            ["--sample N", "None", "Chỉ dùng N dòng train (crc32). Tự bật --no-test."],
            ["--models", "nb,lr,svc,rf", "Danh sách mô hình cần chạy."],
            ["--no-test", "tắt", "Không đánh giá test; không lưu model."],
            ["--seed", "config.seed", "Seed cho RandomForest và chia TVS."],
            ["--figures-only", "tắt", "Chỉ vẽ lại hình từ outputs/tables/*.csv."],
        ],
        widths=[3.4, 3.8, 9.2],
    )

    h2("5.4. Pipeline bảy bước")
    table(
        ["Bước", "Lớp Spark ML", "Vào → ra", "Vì sao"],
        [
            ["1", "RegexTokenizer", "text → tokens", "Tách theo khoảng trắng; text đã lowercase từ clean_text."],
            ["2", "StopWordsRemover", "tokens → words", "Bỏ stopword tiếng Anh nhưng GIỮ not/no/never/n't "
             "(keep_negations) vì phủ định đổi nghĩa câu."],
            ["3", "NGram", "words → ngrams", "Tham số n=1 hoặc 2; thử cả 1-gram và 1–2 gram trong lưới."],
            ["4", "CountVectorizer", "ngrams → tf", "vocabSize 20.000, minDF 3 — học từ vựng CHỈ trên train."],
            ["5", "IDF", "tf → tfidf", "Giảm trọng số từ xuất hiện ở nhiều văn bản."],
            ["6", "Normalizer(p=2)", "tfidf → features", "Chuẩn hóa L2 giúp LR/SVC hội tụ nhanh."],
            ["7", "Classifier", "features → prediction", "NaiveBayes, LogisticRegression, LinearSVC (OneVsRest) "
             "hoặc RandomForest."],
        ],
        widths=[1.4, 4.0, 4.2, 6.8],
    )

    h2("5.5. Các bước hoạt động")
    steps([
        "Đọc config, xác định thứ tự lớp [negative, neutral, positive] theo labels.index.",
        "Nạp train/val/test parquet; thêm cột label_idx (0/1/2). Nếu --sample, lấy N dòng tất định và bỏ test.",
        "Tính trọng số lớp balanced trên train: w_c = N / (k × n_c). Ghi kiểm tra rò rỉ vào leak_check.json.",
        "Chạy baseline đa số (dự đoán lớp nhiều nhất) để có mốc so sánh.",
        "Với từng mô hình: dựng Pipeline, tạo lưới siêu tham số, chạy TrainValidationSplit 80/20 bên trong train "
        "theo weighted F1, rồi dự đoán trên validation.",
        "Tính confusion matrix và macro-F1 riêng từ confusion matrix; ghi bảng validation.",
        "Chọn mô hình có macro-F1 cao nhất trên validation — không dùng test để chọn.",
        "Đánh giá mô hình đã chọn đúng một lần trên test; ghi test_eval_log.csv. Nếu macro-F1 > 0,95 thì "
        "coi là nghi rò rỉ, ghi leakage_alert.txt và không lưu model.",
        "Ghi bảng kết quả, confusion matrix, top features, error analysis, hình 01–05, model và metadata.",
    ])

    h2("5.6. Các câu lệnh cốt lõi")
    table(
        ["Câu lệnh", "Ý nghĩa"],
        [
            ["Pipeline(stages=stages + [clf])", "Gói toàn bộ tiền xử lý + bộ phân loại thành một đối tượng; "
             "fit trên train và transform trên val/test/streaming."],
            ["TrainValidationSplit(estimator=..., evaluator=..., trainRatio=0.8)",
             "Chọn siêu tham số bên trong train; không nhìn val/test."],
            ["paramGridBuilder().addGrid(...).build()", "Sinh tích các tổ hợp từ grids trong config."],
            ["add_class_weights(df)", "Thêm cột weight để bộ phân loại cân bằng lớp."],
            ["prediction = argmax(rawPrediction)", "Với LinearSVC/OneVsRest, tự lấy lớp có điểm cao nhất thay vì "
             "tin ngưỡng 0.5 của Spark."],
            ["confusion_matrix(y_true, y_pred, 3)", "Đếm ma trận nhầm lẫn 3×3."],
            ["metrics_from_cm(cm, labels)", "Tính accuracy, macro/weighted F1, precision/recall/F1 từng lớp."],
            ["top_features_table(...)", "Lấy trọng số lớn nhất mỗi lớp từ mô hình tuyến tính (LR/SVC)."],
            ["error_analysis(...)", "Lấy 30 lỗi và gán nhóm nguyên nhân: phủ định, mỉa mai, đối lập, quá ngắn."],
            ["best_model.write().overwrite().save(local_uri(model_out))", "Lưu PipelineModel để streaming nạp lại."],
        ],
        widths=[7.4, 9.0],
    )

    h2("5.7. Đầu ra")
    table(
        ["File / thư mục", "Nội dung"],
        [
            ["outputs/models/sentiment_pipeline/", "PipelineModel đã fit (Tokenizer → ... → Classifier)."],
            ["outputs/models/sentiment_pipeline_metadata.json", "Tên model, tham số tốt nhất, kích thước tập, "
             "metrics val/test, danh sách stage, way to map lớp."],
            ["outputs/tables/model_results.csv", "Mọi mô hình trên validation + mô hình chọn trên test."],
            ["outputs/tables/per_class_metrics.csv", "Precision/Recall/F1 từng lớp trên val và test."],
            ["outputs/tables/confusion_matrix.csv", "Ma trận nhầm lẫn của mô hình được chọn."],
            ["outputs/tables/top_features.csv", "20 từ có trọng số lớn nhất mỗi lớp."],
            ["outputs/tables/error_analysis.csv", "30 lỗi kèm nhóm nguyên nhân."],
            ["outputs/tables/leak_check.json", "Tỷ lệ trùng văn bản/người dùng giữa các tập."],
            ["outputs/tables/test_eval_log.csv", "Nhật ký mỗi lần chạm test — kiểm soát quy tắc 'dùng một lần'."],
            ["outputs/figures/01–05", "Confusion matrix, P/R/F1 từng lớp, so sánh mô hình, top features, lý do lỗi."],
        ],
        widths=[7.0, 9.4],
    )

    h2("5.8. Kết quả thật trên test")
    table(
        ["Chỉ số", "Giá trị", "Nguồn"],
        [
            ["Accuracy", "0,7018", "outputs/tables/model_results.csv"],
            ["Macro-F1", "0,6233", "outputs/tables/model_results.csv"],
            ["Weighted-F1", "0,7213", "outputs/tables/model_results.csv"],
            ["F1 negative / neutral / positive", "0,672 / 0,378 / 0,819", "outputs/tables/per_class_metrics.csv"],
            ["Số dòng test", "27.792", "outputs/tables/model_results.csv"],
        ],
        widths=[5.4, 5.0, 6.0],
    )
    p("Lớp neutral yếu nhất (F1 0,378) vì rating 5–6 là vùng mơ hồ và nhãn được suy từ điểm số, "
      "không phải cảm xúc thật. Đây là hạn chế đã đo, phải nêu trong báo cáo — không được chỉ "
      "báo accuracy 0,70 mà bỏ qua.")

    h2("5.9. Cách đọc kết quả")
    bullets([
        "model_results.csv: mỗi dòng là một mô hình × split (val hoặc test), kèm best_params, n_features, "
        "train_seconds và predict_seconds_per_10k.",
        "per_class_metrics.csv: xem precision/recall/F1 từng lớp; lớp neutral thấp là dấu hiệu dữ liệu "
        "mất cân bằng và nhãn nhiễu, không phải lỗi code.",
        "confusion_matrix.csv: hàng là nhãn thật, cột là nhãn dự đoán; row_share chuẩn hóa theo hàng.",
        "test_eval_log.csv: nếu file có nhiều hơn một dòng cho cùng một mô hình, nghĩa là tập test đã bị "
        "dùng nhiều lần — phải giải thích trong báo cáo.",
        "sentiment_pipeline_metadata.json: nguồn chính để biết model nào đã lưu, fit trên bao nhiêu dòng, "
        "và ánh xạ lớp 0/1/2.",
    ])


# ---------------------------------------------------------------------------
# Chương 6 — streaming
# ---------------------------------------------------------------------------
def ch6() -> None:
    chapter(6)
    h2("6.1. Kiến trúc sáu query")
    p("stream_job.py chạy sáu streaming query độc lập trên cùng topic comments_raw. Mỗi query "
      "tự đọc nguồn, tự parse/làm sạch/chấm điểm, và có checkpoint riêng. Đổi lại, cùng một "
      "bản ghi được đọc sáu lần; vì vậy mọi phép đối soát phải tính theo TỪNG đích, không "
      "cộng dồn sáu query.")
    code(
        "                       ┌─ detail        → outputs/stream/<run>/scored_detail (Parquet)\n"
        "comments_raw ──────────┼─ kafka         → topic comments_scored (JSON)\n"
        " (Kafka, 3 partition)  ├─ window        → outputs/stream/<run>/window_1min\n"
        "                       ├─ sliding       → outputs/stream/<run>/window_sliding_10s\n"
        "                       ├─ dlq_kafka     → topic comments_dlq (JSON + reason)\n"
        "                       └─ dlq_parquet   → outputs/stream/<run>/dlq"
    )
    table(
        ["Query", "Đích", "Checkpoint"],
        [
            ["detail", "scored_detail (Parquet, partition theo event_date/event_hour)", "checkpoints/streaming/<run>/detail"],
            ["kafka", "topic comments_scored", ".../kafka"],
            ["window", "window_1min (cửa sổ 1 phút, nhảy)", ".../window"],
            ["sliding", "window_sliding_10s (10 giây, trượt 5 giây)", ".../sliding"],
            ["dlq_kafka", "topic comments_dlq", ".../dlq_kafka"],
            ["dlq_parquet", "dlq (Parquet kèm reason)", ".../dlq_parquet"],
        ],
        widths=[3.2, 9.0, 4.2],
    )

    h2("6.2. Luồng xử lý trong stream_job.py")
    steps([
        "read_stream: đọc Kafka với startingOffsets (mặc định latest), maxOffsetsPerTrigger 5000. "
        "Không dùng processing time thay event time.",
        "parse_stream: from_json với RAW_SCHEMA tường minh, chế độ PERMISSIVE, cột lỗi _corrupt. "
        "Ép event_ts sang timestamp theo định dạng ISO-8601 UTC.",
        "add_cleaning_and_reason: tạo text_clean, n_chars và dlq_reason theo thứ tự kiểm tra cố định.",
        "Tách hai nhánh: reason IS NULL đi tiếp; reason khác null vào DLQ (Kafka + Parquet).",
        "score_stream: model.transform() trên nhánh hợp lệ; đổi prediction 0/1/2 thành tên lớp.",
        "detail_frame: chọn cột an toàn (không có text nếu keep_text=false), thêm event_date/event_hour, "
        "các cột độ trễ.",
        "kafka_scored_frame: đóng gói JSON kết quả, key = comment_id.",
        "window_agg_frame: gộp theo cửa sổ event time, đếm n/neg/neu/pos, tỷ lệ âm; watermark 2 phút.",
        "start_query: mỗi query gắn queryName, trigger processingTime, checkpointLocation riêng.",
        "BatchLogListener: ghi một dòng mỗi micro-batch vào outputs/tables/stream_batches.csv.",
    ])

    h2("6.3. Schema message và các trường")
    table(
        ["Trường", "Kiểu", "Bắt buộc", "Ý nghĩa"],
        [
            ["comment_id", "string", "có", "Khóa duy nhất; producer lấy từ review_id."],
            ["stream_id", "string", "có", "Tên phim, dùng làm 'phòng live' thay thế."],
            ["user_hash", "string", "có", "SHA-256 có muối, 16 hex; không có id thật."],
            ["text", "string", "có", "Nội dung bình luận (review_detail)."],
            ["event_ts", "string ISO-8601 UTC", "có", "Thời điểm sự kiện, dùng cho event time và watermark."],
        ],
        widths=[3.0, 4.2, 2.0, 7.2],
    )
    note("Schema được khai báo tường minh trong RAW_SCHEMA. Không suy luận schema từ dữ liệu. "
         "Schema có sẵn cột _corrupt vì Spark 3.5.9 không tự thêm cột này khi thiếu khai báo.",
         "warn")

    h2("6.4. Thứ tự kiểm tra DLQ")
    table(
        ["Thứ tự", "reason", "Khi nào"],
        [
            ["1", "json_khong_hop_le", "from_json báo lỗi: JSON hỏng, JSON mảng, null."],
            ["2", "thieu_truong:<tên>", "Thiếu comment_id / stream_id / text / event_ts."],
            ["3", "event_ts_khong_doc_duoc", "Có event_ts nhưng không parse được theo định dạng."],
            ["4", "van_ban_rong_sau_lam_sach", "text rỗng hoặc toàn khoảng trắng sau clean_text."],
            ["5", "van_ban_qua_ngan_duoi_N_ky_tu", "Ngắn hơn cleaning.min_chars (20)."],
            ["6", "van_ban_qua_dai_tren_N_ky_tu", "Dài hơn cleaning.max_chars (5000)."],
        ],
        widths=[2.0, 6.6, 7.8],
    )
    p("Mỗi bản ghi DLQ mang thêm comment_id (nếu đọc được), json_raw, kafka_partition, kafka_offset, "
      "event_ts và dlq_ts để truy vết về đúng message. Không có nhánh nào âm thầm bỏ bản ghi: "
      "điều kiện hợp lệ là dlq_reason IS NULL.")

    h2("6.5. Event time, watermark và cửa sổ")
    p("event_time lấy từ event_ts do producer gán. Watermark 2 phút nghĩa là dữ liệu đến muộn hơn "
      "mốc nước 2 phút sẽ bị bỏ và đếm vào num_rows_dropped_by_watermark. Cửa sổ 1 phút và cửa sổ "
      "trượt 10 giây/5 giây đều dùng event time, không dùng giờ xử lý.")
    code("window = F.window(F.col('event_time'), '1 minute')\n"
         "agg = scored.groupBy(window).agg(count('*').alias('n_comments'), ...)\n"
         "agg.writeStream.outputMode('append').format('parquet')...")
    bullets([
        "Kết quả một cửa sổ chỉ được ghi khi watermark vượt qua window_end. Vì vậy sau khi ngừng phát "
        "dữ liệu, các cửa sổ cuối vẫn nằm trong state; muốn đẩy nốt phải phát thêm bản ghi mới.",
        "Watermark chỉ tiến khi có bản ghi mới — đây là lý do send_bad_events.py có --heartbeat.",
        "Muốn kiểm tra watermark có tác dụng, xem cột num_rows_dropped_by_watermark trong stream_batches.csv.",
    ])

    h2("6.6. Định nghĩa độ trễ")
    code("latency_ms       = unix_millis(current_timestamp()) - unix_millis(event_time)\n"
         "kafka_latency_ms = timestamp_của_Kafka          - unix_millis(event_time)\n"
         "queue_latency_ms = latency_ms - kafka_latency_ms")
    p("current_timestamp() là thời điểm micro-batch xử lý, nên đây là độ trễ theo batch, không phải "
      "theo từng bản ghi. Nó bao gồm thời gian chờ trigger, chờ watermark/state và chấm điểm. "
      "Khi replay, latency_ms rất dễ lớn vì event_ts do producer gán (5% bị đẩy trễ tới 30 giây); "
      "kafka_latency_ms tách phần do phía phát.")

    h2("6.7. Chạy stream_job.py")
    code("# cách khuyến nghị: kiểm tra trước, chạy nền, chờ READY\n"
         "bash scripts/run_stream.sh verify1 --sink-dir outputs/stream/verify1 \\\n"
         "     --checkpoint-root checkpoints/streaming/verify1 --trigger-seconds 5\n\n"
         "# cách trực tiếp\n"
         "$SPARK_HOME/bin/spark-submit --master 'local[2]' --driver-memory 2g \\\n"
         "  --packages \"$SPARK_KAFKA_PKG\" src/streaming/stream_job.py --run-name verify1")
    table(
        ["Tham số", "Mặc định", "Ý nghĩa"],
        [
            ["--run-name", "main", "Tên lần chạy; tách sink, checkpoint, log và dòng trong stream_batches.csv."],
            ["--sink-dir", "outputs/stream/<run>", "Thư mục ghi Parquet."],
            ["--checkpoint-root", "checkpoints/streaming/<run>", "Gốc checkpoint; mỗi query một thư mục con."],
            ["--model-path", "outputs/models/sentiment_pipeline", "PipelineModel đã lưu."],
            ["--trigger-seconds", "10", "Chu kỳ micro-batch."],
            ["--max-offsets", "5000", "Trần bản ghi mỗi micro-batch."],
            ["--starting-offsets", "latest", "latest / earliest / chuỗi JSON offset."],
            ["--watermark", "2 minutes", "Ngưỡng event-time chấp nhận đến muộn."],
            ["--queries", "all", "Chỉ chạy một phần, ví dụ detail,kafka,window."],
            ["--duration-seconds", "0", "Tự dừng sau N giây; 0 = chạy tới khi có tín hiệu."],
            ["--keep-text / --no-keep-text", "theo config (false)", "Có lưu text trong bảng chi tiết hay không."],
        ],
        widths=[4.2, 4.6, 7.6],
    )
    note("Với startingOffsets=latest, phải đợi job in READY rồi mới phát dữ liệu. Bản ghi gửi trước "
         "mốc gắn offset sẽ bị bỏ qua — đây chính là lý do run_stream.sh tồn tại.", "warn")

    h2("6.8. Log micro-batch")
    p("BatchLogListener ghi một dòng cho mỗi micro-batch của mỗi query vào stream_batches.csv với các cột: "
      "timestamp_utc, run_name, query_name, batch_id, num_input_rows, input_rows_per_second, "
      "processed_rows_per_second, trigger_execution_ms, add_batch_ms, num_rows_dropped_by_watermark, "
      "state_operators. Đây là nguồn số liệu thật cho phần kiểm chứng, không phải số viết tay.")

    h2("6.9. verify_stream.py — kiểm chứng sau khi chạy")
    p("verify_stream.py không chấm điểm lại dữ liệu; nó đối soát những gì đã xảy ra và tính chỉ số "
      "trên luồng bằng nhãn sidecar. Script làm năm việc:")
    steps([
        "Đối chiếu số bản ghi: scored_detail + DLQ = số message đã gửi (theo offset Kafka và log producer).",
        "Đếm message trên comments_scored và comments_dlq bằng chênh lệch offset trước/sau.",
        "Ghép eval_labels theo comment_id, tính accuracy, macro-F1 và P/R/F1 từng lớp TRÊN LUỒNG.",
        "Chạy lại chính PipelineModel offline trên đúng các comment_id đó, so sánh từng dự đoán để tách "
        "'lệch do mẫu' khỏi 'lệch do đường ống'.",
        "Đo phân vị độ trễ, kiểm tra cửa sổ/watermark, in 20 dòng mẫu và ghi kết quả.",
    ])
    code("# (0) ghi mốc offset TRƯỚC khi chạy job\n"
         "$VENV_PY src/streaming/verify_stream.py --record-baseline --run-name verify1\n"
         "# (1) chạy job, (2) phát dữ liệu, (3) dừng êm, rồi:\n"
         "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\\n"
         "  --master 'local[2]' --driver-memory 2g src/streaming/verify_stream.py \\\n"
         "  --run-name verify1 --sink-dir outputs/stream/verify1 \\\n"
         "  --sent-labels outputs/stream/verify1/sent_labels.parquet \\\n"
         "  --extra-valid 14 --bad-injected 10")
    table(
        ["Tham số", "Mặc định", "Ý nghĩa"],
        [
            ["--run-name", "verify1", "Lần chạy cần kiểm chứng."],
            ["--sink-dir", "outputs/stream/<run>", "Thư mục sink."],
            ["--sent-labels", "outputs/stream/<run>/sent_labels.parquet", "Nhãn sidecar producer ghi ra."],
            ["--extra-valid", "0", "Số bản ghi hợp lệ phát thêm (heartbeat)."],
            ["--bad-injected", "0", "Số ca lỗi cố ý đã gửi."],
            ["--samples", "20", "Số dòng mẫu in ra."],
            ["--record-baseline", "tắt", "Chỉ ghi mốc offset rồi thoát."],
        ],
        widths=[4.2, 5.6, 6.6],
    )
    table(
        ["Đầu ra", "Nội dung"],
        [
            ["outputs/tables/stream_verification.csv", "Bảng chỉ số đối soát theo nhóm."],
            ["outputs/tables/stream_per_class_metrics.csv", "P/R/F1 từng lớp trên luồng."],
            ["outputs/tables/stream_sample_rows.csv", "20 dòng mẫu."],
            ["outputs/tables/stream_dlq_rows.csv", "Các bản ghi DLQ kèm lý do."],
            ["outputs/stream/<run>/verification.json", "Tóm tắt toàn bộ kết quả kiểm chứng."],
        ],
        widths=[7.4, 9.0],
    )

    h2("6.10. Kết quả thật của lần chạy verify1")
    table(
        ["Hạng mục", "Kết quả đo"],
        [
            ["Số bản ghi", "1.014 hợp lệ + 10 DLQ = 1.024, khớp tuyệt đối với số đã gửi."],
            ["Topic comments_scored", "nhận đúng +1.014 message."],
            ["Topic comments_dlq", "nhận đúng +10 message."],
            ["Macro-F1 trên luồng", "0,6311 (offline trên cùng bộ: 0,6233)."],
            ["Chạy lại offline trên đúng 1.000 id", "1.000/1.000 dự đoán giống nhau."],
            ["Độ trễ latency_ms", "p50 2,4 giây; p95 9,7 giây (p99 27,1 giây) trên 1.014 bình luận."],
            ["Cửa sổ 1 phút", "710 dòng → 4 cửa sổ."],
            ["Cửa sổ trượt 10 giây", "1.466 dòng → 23 cửa sổ."],
            ["Cảnh báo 10 giây", "18:08:30–18:08:40 UTC, 5/13 = 38,5% âm."],
        ],
        widths=[5.8, 10.6],
    )
    p("Nguồn: outputs/streaming_summary.md, outputs/stream/verify1/verification.json và các bảng "
      "stream_*.csv. Không dùng số nào khác trong báo cáo nếu không truy vết được về các file này.")

    h2("6.11. Ngữ nghĩa giao hàng")
    p("Về thiết kế, hệ thống là at-least-once: offset Kafka chỉ được commit khi micro-batch đã ghi xong; "
      "nếu job chết giữa lúc ghi và lúc commit, batch đó chạy lại và kết quả có thể trùng. "
      "Đã kiểm chứng: chạy liên tục không sự cố thì 1.014 + 10 = 1.024 đúng từng bản ghi; dừng êm thì "
      "cả 6 query dừng sạch, batch đang chạy được làm nốt.")
    p("CHƯA kiểm chứng: exactly-once nói chung; hành vi khi crash giữa batch hoặc kill -9; khi broker chết "
      "hoặc đĩa đầy; khi ghi lỗi rồi retry. Không được khẳng định exactly-once trong báo cáo.")
    note("Chạy lại cùng --run-name sẽ tiếp tục từ offset đã commit theo cơ chế checkpoint. Cơ chế này "
         "CHƯA được thí nghiệm lại ở Task 8; muốn khẳng định phải chạy thử và đếm bản ghi trùng.",
         "warn")


# ---------------------------------------------------------------------------
# Chương 7 — producer / consumer / bad events
# ---------------------------------------------------------------------------
def ch7() -> None:
    chapter(7)
    h2("7.1. replay_producer.py — phát review vào Kafka")
    p("Producer đọc review từ JSONL hoặc file raw, đóng gói mỗi review thành message năm trường, "
      "băm user, gán event_ts và gửi vào topic comments_raw. Nó có thể phát theo tốc độ cố định, "
      "mô phỏng bùng nổ, đẩy trễ một phần bản ghi, lặp dữ liệu, và ghi nhãn sidecar khi cần kiểm chứng.")
    code("# phát 2.000 review, lặp, tốc độ 50/giây (dùng trong run_demo.sh)\n"
         "$VENV_PY src/producer/replay_producer.py --sample 2000 --loop\n\n"
         "# chỉ phát tập test và ghi nhãn để verify_stream ghép\n"
         "$VENV_PY src/producer/replay_producer.py --only-test --max 1000 --rate 50 \\\n"
         "  --labels-out outputs/stream/verify1/sent_labels.parquet")
    table(
        ["Tham số", "Mặc định", "Ý nghĩa"],
        [
            ["--source", "jsonl", "jsonl (data/processed/imdb_jsonl) hoặc raw (part-01.json)."],
            ["--topic", "kafka.topic_raw", "Topic đích."],
            ["--rate", "replay.rate = 50", "Số bình luận/giây; 0 = không giới hạn."],
            ["--max", "0", "Số message tối đa; 0 = không giới hạn."],
            ["--sample", "0", "Chỉ lấy N bản ghi đầu (tất định) rồi phát."],
            ["--loop", "tắt", "Lặp lại dữ liệu khi hết."],
            ["--burst", "theo config", "Ghi đè xác suất bùng nổ."],
            ["--late-ratio", "theo config", "Tỷ lệ bản ghi bị đẩy trễ event_ts."],
            ["--only-test", "tắt", "Chỉ phát các comment_id thuộc tập test."],
            ["--labels-out", "không", "Ghi nhãn sidecar (comment_id, label, rating) ra parquet."],
            ["--report", "không", "Ghi một dòng thống kê thông lượng vào CSV (append)."],
            ["--seed", "config.seed", "Seed cho chọn mẫu, burst và late."],
            ["--log-every", "500", "Cứ N message in tiến độ một lần."],
        ],
        widths=[3.4, 4.4, 8.6],
    )
    h3("Message gửi đi")
    code('{\n'
         '  "comment_id": "tt0111161_123",\n'
         '  "stream_id": "The Shawshank Redemption",\n'
         '  "user_hash": "a1b2c3d4e5f60718",\n'
         '  "text": "the movie was ...",\n'
         '  "event_ts": "2026-10-15T18:08:30.123+00:00"\n'
         '}')
    p("Không có rating, label hay bất kỳ trường nhãn nào trong message. Nhãn chỉ được ghi riêng "
      "qua --labels-out khi cần đánh giá, và được ghép lại theo comment_id.")
    h3("Các bước hoạt động")
    steps([
        "Đọc config, tạo KafkaProducer với acks=all, linger_ms=20, key_serializer/ value_serializer.",
        "Chọn nguồn: JSONL (mỗi dòng một review) hoặc raw (đọc mảng JSON). Nếu --only-test, nạp "
        "eval_labels và lọc theo comment_id.",
        "Với mỗi review: tạo comment_id từ review_id, stream_id từ movie, text từ review_detail, "
        "user_hash = salted_hash(reviewer), event_ts = bây giờ (UTC) trừ một độ trễ ngẫu nhiên nếu rơi vào late_ratio.",
        "Nếu đang trong đợt burst, tăng tốc độ gửi gấp burst_factor trong burst_len_s giây.",
        "Gửi message với key = comment_id; đếm thành công/lỗi; in tiến độ mỗi log_every message.",
        "Khi hết dữ liệu: nếu --loop thì quay lại đầu; nếu không thì đóng producer và in tổng kết.",
    ])
    note("Dữ liệu producer phát là replay IMDb, KHÔNG phải livestream thật. event_ts được gán lại "
         "theo thời điểm phát (có trừ độ trễ giả lập), không phải ngày đăng review gốc.", "warn")

    h2("7.2. test_consumer.py — kiểm tra message trên topic")
    p("Consumer đọc topic, kiểm tra mỗi message có đủ năm trường bắt buộc và KHÔNG chứa trường nhãn. "
      "Dùng --expect N để kiểm chứng số message nhận được; nếu lệch, script trả mã thoát khác 0.")
    code("$VENV_PY src/producer/test_consumer.py --topic comments_raw --expect 1000\n"
         "$VENV_PY src/producer/test_consumer.py --from-now --samples 5")
    table(
        ["Tham số", "Mặc định", "Ý nghĩa"],
        [
            ["--topic", "kafka.topic_raw", "Topic cần đọc."],
            ["--from-now", "tắt", "Chỉ đọc message mới (bỏ qua message cũ)."],
            ["--expect", "0", "Số message mong đợi; khác 0 thì kiểm tra và trả mã lỗi nếu lệch."],
            ["--samples", "3", "Số mẫu in ra."],
            ["--idle-timeout", "10.0", "Dừng sau bao nhiêu giây không có message."],
            ["--max-seconds", "0", "Giới hạn tổng thời gian chạy."],
        ],
        widths=[3.6, 4.0, 8.8],
    )

    h2("7.3. scripts/send_bad_events.py — gửi lỗi đã biết")
    p("Script gửi 11 ca lỗi cố ý để kiểm chứng nhánh DLQ: JSON hỏng, thiếu từng trường, event_ts sai, "
      "text rỗng, quá ngắn, quá dài. Nó còn có --heartbeat để đẩy watermark tiến và --late-probe để "
      "gửi một bản ghi hợp lệ lạc hậu 10 phút (phải bị watermark bỏ).")
    code("$VENV_PY scripts/send_bad_events.py --dry-run\n"
         "$VENV_PY scripts/send_bad_events.py --heartbeat 12 --heartbeat-interval 25 --late-probe")
    table(
        ["Tham số", "Mặc định", "Ý nghĩa"],
        [
            ["--topic", "kafka.topic_raw", "Topic đích."],
            ["--dry-run", "tắt", "Chỉ in message, không gửi."],
            ["--counts", "1", "Số lần gửi mỗi ca."],
            ["--skip-bad", "tắt", "Không gửi 11 ca lỗi; chỉ heartbeat/probe."],
            ["--heartbeat N", "0", "Gửi N bản ghi hợp lệ để watermark tiến."],
            ["--heartbeat-interval S", "25.0", "Khoảng cách giữa các heartbeat (giây)."],
            ["--late-probe", "tắt", "Gửi một bản ghi lạc hậu 10 phút."],
        ],
        widths=[4.0, 4.0, 8.4],
    )
    h3("Vì sao cần heartbeat")
    p("Watermark chỉ tiến khi có bản ghi mới. Sau khi producer ngừng phát, các cửa sổ cuối vẫn nằm "
      "trong state và chưa được ghi ra. Heartbeat là các bản ghi hợp lệ có event_ts mới, đẩy watermark "
      "vượt qua window_end để các cửa sổ cuối được ghi nốt. Đây là hành vi đúng của event time, "
      "không phải lỗi.")

    h2("7.4. Cách đọc log producer")
    bullets([
        "Dòng 'gửi ... message' xuất hiện mỗi log_every message; nếu dừng đột ngột, xem lỗi Kafka ngay sau đó.",
        "Tổng kết cuối có số gửi thành công, số lỗi và thời gian chạy; dùng để đối chiếu với verify_stream.",
        "Nếu gửi nhanh hơn Spark xử lý, backlog tăng và latency trong bảng chi tiết tăng — đây là hiện tượng "
        "hàng đợi, không phải lỗi mô hình.",
    ])


# ---------------------------------------------------------------------------
# Chương 8 — dashboard
# ---------------------------------------------------------------------------
def ch8() -> None:
    chapter(8)
    h2("8.1. Thiết kế")
    p("app.py là dashboard Streamlit ba tab. Tab Live Monitor chỉ đọc Parquet do job streaming ghi; "
      "nó KHÔNG dùng Spark, nên xem dashboard không làm chậm job và ngược lại. Spark chỉ được dựng "
      "ở tab Try It, và chỉ khi người dùng thực sự bấm Phân tích.")
    code("source scripts/env.sh\n"
         "$VENV_PY -m streamlit run src/app/app.py --server.address 0.0.0.0 --server.port 8501")
    p("Mở http://localhost:8501. Nếu chạy trong máy ảo VirtualBox, xem hướng dẫn port forwarding "
      "trong src/app/README.md.")

    h2("8.2. Ba tab")
    table(
        ["Tab", "Nội dung", "Nguồn dữ liệu"],
        [
            ["Live Monitor", "Biểu ngữ cảnh báo, 4 chỉ số (số bình luận cửa sổ hiện tại, tỷ lệ tiêu cực, "
             "độ trễ trung bình + p95, bình luận/phút), 3 biểu đồ, bảng 10 bình luận mới nhất đã che",
             "window_sliding_10s, window_1min, scored_detail"],
            ["Try It", "Nhãn dự đoán, xác suất từng lớp, từ đóng góp nhiều nhất, văn bản sau làm sạch",
             "PipelineModel + clean_text"],
            ["About", "Sơ đồ pipeline, nói rõ phần replay, bảng P/R/F1 từng lớp, 6 hạn chế, quy ước riêng tư",
             "per_class_metrics.csv, metadata JSON"],
        ],
        widths=[3.0, 8.6, 4.8],
    )

    h2("8.3. Luồng một lần làm mới")
    steps([
        "Sidebar chọn lần chạy trong outputs/stream/ (ví dụ demo hoặc verify1), nhịp làm mới, ngưỡng cảnh báo.",
        "read_table đọc ba bảng Parquet; nếu bảng cửa sổ chưa có, quay sang tính từ scored_detail.",
        "aggregate_windows gộp các cửa sổ trượt thành cửa sổ hiện tại; windows_from_detail tính cửa sổ "
        "trực tiếp từ bảng chi tiết khi cửa sổ chính còn rỗng.",
        "eval_alerts áp quy tắc: share_negative > ngưỡng VÀ n_comments >= 5.",
        "Vẽ biểu đồ bằng Plotly, hiển thị bảng bình luận đã che, ghi rõ mốc thời gian UTC và nguồn dữ liệu.",
        "st.fragment(run_every=...) tự làm mới tab Live Monitor mà không xóa ô nhập ở tab Try It.",
    ])

    h2("8.4. Các hàm thuần (dễ kiểm thử)")
    table(
        ["Hàm", "Việc"],
        [
            ["read_table(sink, name)", "Đọc Parquet với vài lần thử; trả DataFrame + lỗi nếu có."],
            ["list_runs(sink_root)", "Liệt kê các lần chạy có ít nhất một bảng."],
            ["aggregate_windows(w)", "Gộp cửa sổ trượt thành cửa sổ hiện tại, tính tỷ lệ."],
            ["windows_from_detail(detail, seconds)", "Tính cửa sổ từ bảng chi tiết khi bảng cửa sổ chậm."],
            ["minute_from_detail(detail)", "Gộp theo phút cho biểu đồ timeline."],
            ["eval_alerts(agg, threshold, min_comments)", "Trả về mặt nạ cảnh báo đúng quy tắc."],
            ["mask_text(text, words, patterns)", "Che từ nhạy cảm bằng ***, email/SĐT bằng [đã che]."],
            ["fmt_utc(ts)", "Định dạng thời gian UTC."],
            ["chart_current / chart_timeline / chart_volume", "Ba biểu đồ chính."],
            ["get_spark_model(model_path)", "Nạp Spark + PipelineModel một lần, cache theo tiến trình."],
            ["linear_parts(model)", "Lấy hệ số của mô hình tuyến tính để hiển thị từ đóng góp."],
            ["score_comment(text, cfg)", "Làm sạch rồi chấm một câu; trả nhãn, xác suất, từ đóng góp."],
        ],
        widths=[6.6, 9.8],
    )

    h2("8.5. Quy tắc cảnh báo")
    p("Cảnh báo khi share_negative > ngưỡng (mặc định 0,30) VÀ n_comments >= 5. Điều kiện thứ hai "
      "bắt buộc: cửa sổ một bình luận luôn cho 0% hoặc 100%. Đo trên verify1 cho thấy bỏ điều kiện "
      "này sinh 13 báo động giả. Ngưỡng 0,30 lấy từ tỷ lệ negative trên test 0,2506 cộng biên 5 điểm "
      "phần trăm; đây là căn cứ đã ghi trong config.yaml.")

    h2("8.6. Riêng tư và hiển thị")
    bullets([
        "user_hash không bao giờ hiển thị. Mã bình luận chỉ hiện khi tự bật ô 'Hiện mã bình luận'.",
        "Từ nhạy cảm thay bằng ***; email và số điện thoại thay bằng [đã che].",
        "Mặc định job streaming không lưu text; run_demo.sh bật --keep-text vì dữ liệu demo là IMDb công khai.",
        "Khi thu bình luận thật, không dùng --keep-text và phải kiểm tra điều khoản nền tảng.",
    ])

    h2("8.7. Ba điều không phải lỗi khi demo")
    table(
        ["Hiện tượng", "Nguyên nhân"],
        [
            ["Cửa sổ 1 phút rỗng trong vài phút đầu", "Watermark 2 phút: cửa sổ chỉ được ghi sau khi "
             "watermark vượt window_end. Dashboard tự tính từ scored_detail và ghi rõ lý do."],
            ["Khung bình luận mới nhất trống", "Job chạy không có --keep-text. Đây là mặc định riêng tư."],
            ["Thời gian trên biểu đồ không phải 'bây giờ'", "Đó là thời gian dữ liệu (UTC) của replay, "
             "không phải giờ hệ thống."],
        ],
        widths=[5.8, 10.6],
    )


# ---------------------------------------------------------------------------
# Chương 9 — terminal app
# ---------------------------------------------------------------------------
def ch9() -> None:
    chapter(9)
    h2("9.1. Thiết kế")
    p("terminal_app.py là bản walkthrough tám giai đoạn chạy thẳng trong terminal. Nó dùng đúng code "
      "của hệ thống, không viết lại logic: lấy mẫu review → đóng gói message → from_json + DLQ → "
      "clean_text → PipelineModel → cửa sổ event time → sink Parquet → tổng kết. Mỗi giai đoạn in "
      "dữ liệu thật của chính lần chạy đó và một breadcrumb để biết đang ở đâu.")
    p("Chế độ mặc định không cần Kafka. Nó chỉ cần model đã lưu và outputs/tables/clean_sample.csv. "
      "Chế độ --live mới cần broker đang chạy.")
    code("bash scripts/run_terminal_app.sh                     # 8 giai đoạn, Enter sau mỗi bước\n"
         "bash scripts/run_terminal_app.sh --auto              # tự chạy\n"
         "bash scripts/run_terminal_app.sh --fast --limit 20   # nhanh\n"
         "bash scripts/run_terminal_app.sh --stage 5           # chỉ chấm điểm\n"
         "bash scripts/run_terminal_app.sh --text \"not bad\"   # chấm một câu\n"
         "bash scripts/run_comment_stream.sh                   # từng comment, kết quả ngay")

    h2("9.2. Tám giai đoạn")
    table(
        ["Giai đoạn", "Tên", "Việc làm", "Đầu ra trên màn hình"],
        [
            ["1", "Thu thập", "Lấy mẫu tất định từ clean_sample.csv theo seed", "Nguồn, số dòng, bảng review thô"],
            ["2", "Đóng gói", "Tạo message 5 trường, băm user, tách nhãn sidecar", "JSON message + bảng nhãn"],
            ["3", "Parse/DLQ", "parse_stream + add_cleaning_and_reason", "Schema, trạng thái từng bản ghi, đối soát"],
            ["4", "Làm sạch", "clean_text trên từng bình luận", "Bảng thô → sạch, quy tắc đã đổi"],
            ["5", "Phân tích", "model.transform, lấy nhãn + xác suất + từ đóng góp", "Card từng bình luận, bảng đúng/sai"],
            ["6", "Cửa sổ", "Gộp cửa sổ 1 phút trên mẫu; đọc cửa sổ thật của verify1", "Bảng cửa sổ, cảnh báo, độ trễ"],
            ["7", "Ghi", "Đọc sink Parquet, kiểm tra Kafka, ghi kết quả", "Số dòng từng đích, trạng thái topic"],
            ["8", "Tổng kết", "Tóm tắt số đo, nhắc điều đã/chưa kiểm chứng", "Bảng tổng kết + lệnh chạy lại"],
        ],
        widths=[1.6, 2.6, 7.4, 4.8],
    )

    h2("9.3. Các chế độ chạy")
    table(
        ["Chế độ", "Cờ", "Mô tả"],
        [
            ["Walkthrough", "(mặc định)", "Chạy 8 giai đoạn, dừng chờ Enter sau mỗi giai đoạn."],
            ["Tự động", "--auto / --fast", "Không dừng chờ; --fast không chờ giữa các giai đoạn."],
            ["Một giai đoạn", "--stage 1..8", "Chỉ chạy giai đoạn được chọn."],
            ["Một câu", "--text \"...\"", "Chấm một câu và in kết quả."],
            ["Tương tác", "--interactive", "Nhập nhiều câu, chấm liên tiếp."],
            ["Theo dõi Kafka", "--live --duration N", "Đọc ba topic trong N giây."],
            ["Từng comment", "--one-by-one", "Mỗi comment đến thì parse → clean → model → in kết quả ngay."],
        ],
        widths=[3.4, 4.2, 8.8],
    )
    h3("Tham số đầy đủ")
    table(
        ["Tham số", "Mặc định", "Ý nghĩa"],
        [
            ["--config", "config.yaml", "File cấu hình."],
            ["--limit", "12", "Số bình luận lấy từ mẫu."],
            ["--cards", "5", "Số card chi tiết in ở giai đoạn 5."],
            ["--seed", "config.seed", "Seed lấy mẫu."],
            ["--auto / --fast / --delay", "tắt / tắt / 0.8", "Điều khiển nhịp dừng giữa các giai đoạn."],
            ["--stage", "không", "Chỉ chạy một giai đoạn 1–8."],
            ["--text / --interactive", "không", "Chấm một câu hoặc nhập tương tác."],
            ["--live / --duration", "tắt / 60", "Theo dõi Kafka trong N giây."],
            ["--no-color / --no-write / --keep-text", "tắt", "Tắt màu, không ghi outputs/terminal_demo, giữ văn bản trong file."],
            ["--no-kafka-check", "tắt", "Bỏ kiểm tra Kafka ở giai đoạn 7."],
            ["--one-by-one / --interval", "tắt / 1.0", "Chế độ từng comment và thời gian nghỉ giữa hai comment."],
            ["--no-bad", "tắt", "Bỏ bốn bản ghi lỗi cố ý trong chế độ từng comment."],
        ],
        widths=[4.4, 4.0, 8.0],
    )

    h2("9.4. Chế độ từng comment")
    p("Đây là chế độ trả lời câu hỏi 'khi một comment xuất hiện thì phân tích và trả kết quả ngay'. "
      "Mỗi vòng lặp thực hiện đúng một Spark action: parse + làm sạch + chấm điểm + lấy kết quả bằng "
      "một lần .first(). Các bản ghi lỗi dùng cùng một lần transform với văn bản rỗng, nên không cần "
      "chạy Spark lần thứ hai.")
    code("cleaned = (add_cleaning_and_reason(parse_stream(raw_df), cfg)\n"
         "           .withColumn('text_raw', F.col('text')))\n"
         "safe_text = (F.when(F.col('dlq_reason').isNull(), F.col('text_clean'))\n"
         "              .otherwise(F.lit('')))\n"
         "scored = model.transform(cleaned.withColumn('text', safe_text))\n"
         "sr = scored.select('comment_id', 'stream_id', 'text_raw', 'text_clean',\n"
         "                   'dlq_reason', 'prediction', 'probability',\n"
         "                   F.unix_millis('event_time').alias('event_ms')).first()")
    p("Vì sao phải một action: nếu tách thành hai job (một job kiểm tra DLQ, một job chấm điểm), mỗi "
      "comment mất 3–12 giây. Gộp lại còn khoảng 1–2,5 giây sau khi JIT ổn định.")
    p("Thứ tự in của mỗi comment: số thứ tự → RAW → CLEAN → nhãn dự đoán + xác suất → nhãn thật (nếu có) "
      "→ DLQ reason (nếu lỗi). Kết thúc mỗi comment là một dòng trạng thái để biết chương trình còn chạy.")

    h2("9.5. Đầu ra của app terminal")
    p("Trừ khi dùng --no-write, mỗi lần chạy ghi vào outputs/terminal_demo/run_YYYYmmdd_HHMMSS/:")
    table(
        ["File", "Nội dung"],
        [
            ["predictions.csv", "comment_id, nhãn dự đoán, xác suất, nhãn thật, đúng/sai; không có văn bản trừ khi --keep-text."],
            ["dlq.csv", "Các bản ghi lỗi kèm reason."],
            ["windows_sample.csv", "Cửa sổ 1 phút tính trên mẫu."],
            ["run_summary.md", "Tóm tắt số đo và điều đã/chưa kiểm chứng."],
        ],
        widths=[4.6, 11.8],
    )
    note("Độ trễ trong app là độ trễ mô phỏng offline, gồm khởi động Spark và nạp model — không phải "
         "latency streaming thật. Latency thật của verify1 đo ở giai đoạn 6 (p50 2,4 s, p95 9,7 s).",
         "warn")

    h2("9.6. Cách đọc màn hình")
    bullets([
        "Breadcrumb ở đầu mỗi giai đoạn: Thu thập → Đóng gói → Parse/DLQ → Làm sạch → Phân tích → Cửa sổ → Ghi → Tổng kết.",
        "Màu: xanh lá = hợp lệ/đúng, vàng = cảnh báo, đỏ = lỗi/DLQ, xám = thông tin phụ.",
        "Mỗi card giai đoạn 5 có RAW, CLEAN, DỰ ĐOÁN, THẬT, xác suất và độ trễ mô phỏng.",
        "Giai đoạn 6 in cả cửa sổ trên mẫu và cửa sổ thật của verify1; nếu dữ liệu thật thiếu, app ghi rõ "
        "thay vì bịa số.",
        "Giai đoạn 8 nhắc lại: replay, không phải livestream; exactly-once chưa kiểm chứng.",
    ])


# ---------------------------------------------------------------------------
# Chương 10 — model_trial.py và check_model.py
# ---------------------------------------------------------------------------
def ch10() -> None:
    chapter(10)
    h2("10.1. model_trial.py — chương trình thử nghiệm mô hình")
    p("Đây là công cụ prototype tách khỏi app hoàn chỉnh: chạy bằng một lệnh, không cần Kafka, "
      "không cần Streamlit, chỉ cần model đã lưu. Nó đi đúng đường của hệ thống thật: "
      "văn bản thô → clean_text() → PipelineModel → nhãn + xác suất. Dùng khi báo cáo/demo "
      "hoặc khi cần kiểm tra nhanh một câu.")
    code("bash scripts/run_model_trial.sh                     # nhập bình luận tương tác\n"
         "bash scripts/run_model_trial.sh --examples          # 4 câu ví dụ trong config.yaml\n"
         "bash scripts/run_model_trial.sh --text \"not bad\"    # chấm một câu\n"
         "bash scripts/run_model_trial.sh --test-sample 200   # đo trên 200 dòng tập test")

    h2("10.2. Các chế độ")
    table(
        ["Chế độ", "Cách gọi", "Việc làm"],
        [
            ["Tương tác", "(mặc định)", "Nhập từng câu; :q để thoát, :sample để dùng câu ví dụ."],
            ["Một câu", "--text \"...\"", "Chấm câu được truyền; có thể lặp --text nhiều lần."],
            ["Từ file", "--file path", "Mỗi dòng một bình luận; bỏ dòng trống và dòng bắt đầu bằng #."],
            ["Ví dụ", "--examples", "Chấm các câu trong dashboard.try_it_examples."],
            ["Đo trên tập test", "--test-sample N", "Lấy N dòng test, dự đoán, tính P/R/F1, ghi báo cáo."],
        ],
        widths=[3.6, 4.2, 8.6],
    )
    table(
        ["Tham số", "Mặc định", "Ý nghĩa"],
        [
            ["--text", "không", "Một câu cần chấm; lặp lại được."],
            ["--file", "không", "File mỗi dòng một câu."],
            ["--examples", "tắt", "Dùng 4 câu ví dụ trong config."],
            ["--test-sample N", "0", "Số dòng test cần đo; vượt max_sample_rows (5000) thì báo lỗi."],
            ["--split", "model_trial.split = test", "Chọn test hoặc val khi đo mẫu."],
            ["--report", "outputs/model_trial_report.md", "Đường dẫn báo cáo Markdown."],
            ["--keep-text", "tắt", "Lưu văn bản vào CSV/report; chỉ dùng với dữ liệu công khai."],
            ["--no-write", "tắt", "Không ghi file kết quả."],
        ],
        widths=[3.8, 5.4, 7.2],
    )

    h2("10.3. Luồng hoạt động")
    steps([
        "Đọc config, dựng Spark local, nạp PipelineModel và metadata (label_index).",
        "Chọn chế độ: text/file/examples/test-sample/tương tác.",
        "Với mỗi câu: kiểm tra độ dài bằng text_problem() — rỗng, ngắn hơn 20, dài hơn 5000 bị loại "
        "với lý do giống DLQ streaming.",
        "Làm sạch bằng cleaned_df() (gọi clean_text dùng chung), rồi score_dataframe(): model.transform, "
        "lấy xác suất từng lớp, dịch chỉ số sang tên lớp.",
        "In kết quả: nhãn, xác suất, văn bản sạch, top từ đóng góp nếu là mô hình tuyến tính.",
        "Nếu --test-sample: ghép nhãn thật, tính confusion matrix và P/R/F1, ghi predictions/summary/report.",
    ])

    h2("10.4. Đầu ra")
    table(
        ["Chế độ", "File", "Nội dung"],
        [
            ["--test-sample", "outputs/tables/model_trial_predictions.csv", "Từng dòng: id, nhãn thật, dự đoán, xác suất, đúng/sai."],
            ["--test-sample", "outputs/tables/model_trial_summary.csv", "Một dòng tổng kết: accuracy, macro-F1, weighted-F1, n."],
            ["--test-sample", "outputs/model_trial_report.md", "Báo cáo tiếng Anh, số liệu lấy từ chính lần chạy."],
            ["text/file/examples", "outputs/tables/model_trial_batch_predictions.csv", "Kết quả các câu nhập tay (tách khỏi bằng chứng test)."],
        ],
        widths=[4.0, 7.4, 5.0],
    )
    note("--test-sample dùng cho demo/đo nhanh, KHÔNG dùng để chọn mô hình và không thay thế kết quả "
         "test chính thức trong model_results.csv. Khi báo cáo phải nói rõ đây là lần đo lại trên mẫu.",
         "warn")

    h2("10.5. scripts/check_model.py")
    p("Script nhỏ nhất để xác nhận model đã lưu hoạt động đúng đường đi mà streaming sẽ dùng: "
      "nạp PipelineModel bằng PipelineModel.load, gọi clean_text, dự đoán 5 câu thử tiếng Anh, "
      "in lớp và xác suất. Không có tham số dòng lệnh.")
    code("PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\\n"
         "  --driver-memory 2g --master 'local[2]' scripts/check_model.py")
    p("Nếu script này chạy được nhưng streaming lỗi, vấn đề nằm ở Kafka/schema/checkpoint, "
      "không phải ở model.")


# ---------------------------------------------------------------------------
# Chương 11 — EDA
# ---------------------------------------------------------------------------
def ch11() -> None:
    chapter(11)
    h2("11.1. Thiết kế hai bước")
    p("EDA tách làm hai bước chạy độc lập. queries.py dùng Spark SQL chạy 13 truy vấn trên parquet "
      "và ghi CSV. plots.py đọc lại chính các CSV đó để vẽ hình và sinh insights.md — không cần Spark. "
      "Nhờ vậy sửa hình không phải chạy lại Spark, và mọi con số trên hình truy vết được về một file CSV thật.")
    code("source scripts/env.sh\n"
         "$VENV_PY src/eda/queries.py --dry-run --check          # kiểm tra SQL, không cần Spark\n"
         "$VENV_PY src/eda/queries.py --only class_distribution   # chạy thử một truy vấn\n"
         "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\\n"
         "  --driver-memory 4g --master 'local[2]' src/eda/queries.py\n"
         "$VENV_PY src/eda/plots.py\n"
         "$VENV_PY src/eda/plots.py --only 12")

    h2("11.2. Mười ba truy vấn SQL")
    table(
        ["File SQL", "Câu hỏi", "Bảng ra", "Hình"],
        [
            ["q00_overview.sql", "Tổng số dòng, số lớp, khoảng thời gian", "eda_overview.csv", "—"],
            ["q01_class_distribution.sql", "Phân bố lớp theo tập", "eda_class_distribution.csv", "06"],
            ["q02_length_quantiles.sql", "Phân vị độ dài văn bản", "eda_length_quantiles.csv", "07"],
            ["q03_length_histogram.sql", "Phân bố độ dài theo lớp", "eda_length_histogram.csv", "07"],
            ["q04_top_words_by_class.sql", "Từ đặc trưng mỗi lớp (log-odds có prior)", "eda_top_words_by_class.csv", "08"],
            ["q05_emoji_by_class.sql", "Emoji nhiều nhất mỗi lớp", "eda_emoji_by_class.csv", "09"],
            ["q06_sentiment_per_minute.sql", "Cảm xúc theo phút trên luồng", "eda_sentiment_per_minute.csv", "10, 15"],
            ["q07_sentiment_per_10s.sql", "Cảm xúc theo cửa sổ 10 giây", "eda_sentiment_per_10s.csv", "10, 15"],
            ["q08_throughput_per_second.sql", "Số bình luận mỗi giây, phát hiện bùng nổ", "eda_throughput_per_second.csv", "11"],
            ["q09_negative_share_alert.sql", "Tỷ lệ âm theo cửa sổ và cảnh báo", "eda_negative_share_alert.csv", "12"],
            ["q10_latency_quantiles.sql", "Phân vị độ trễ", "eda_latency_quantiles.csv", "13"],
            ["q11_latency_histogram.sql", "Phân bố độ trễ theo bậc", "eda_latency_histogram.csv", "13"],
            ["q12_token_vocab.sql", "Kích thước từ vựng / token", "eda_token_vocab.csv", "—"],
        ],
        widths=[4.4, 5.8, 5.2, 1.6],
    )

    h2("11.3. queries.py")
    p("Script đăng ký các temp view, đọc file SQL, thay chỗ giữ chỗ {{tên}} bằng giá trị trong config, "
      "chạy truy vấn và ghi CSV. Không nhúng ngưỡng vào SQL.")
    table(
        ["Tham số", "Mặc định", "Ý nghĩa"],
        [
            ["--config", "config.yaml", "Cấu hình."],
            ["--run-name", "eda.streaming_run", "Lần chạy streaming cần phân tích."],
            ["--sample N", "0", "Chạy trên N dòng; ghi ra *_sample.csv để không lẫn với số báo cáo."],
            ["--only TÊN", "tất cả", "Chỉ chạy một truy vấn; lặp lại được."],
            ["--dry-run", "tắt", "In SQL đã thay tham số, không chạy."],
            ["--check", "tắt", "Kiểm tra tham số và file SQL."],
        ],
        widths=[3.8, 4.4, 8.2],
    )
    table(
        ["Temp view", "Nguồn"],
        [
            ["train / val / test", "data/processed/*.parquet"],
            ["stream_detail", "outputs/stream/<run>/scored_detail"],
            ["window_1min / window_sliding_10s", "outputs/stream/<run>/window_*"],
            ["stopwords", "Danh sách stopword dùng chung với train.py (đưa qua view, không nhúng literal)."],
        ],
        widths=[5.4, 11.0],
    )
    note("Mọi truy vấn chạy với spark.sql.session.timeZone=UTC. Máy ở UTC+7, nếu không ghim múi giờ "
         "thì mốc cửa sổ và biểu đồ lệch 7 tiếng.", "warn")

    h2("11.4. plots.py và các hình 06–15")
    table(
        ["Hình", "Nội dung", "Nguồn"],
        [
            ["06_class_distribution.png", "Phân bố lớp theo tập", "eda_class_distribution.csv"],
            ["07_length_by_class.png", "Độ dài văn bản theo lớp", "eda_length_histogram + quantiles"],
            ["08_top_words_by_class.png", "Từ đặc trưng mỗi lớp", "eda_top_words_by_class.csv"],
            ["09_emoji_by_class.png", "Emoji theo lớp", "eda_emoji_by_class.csv"],
            ["10_sentiment_timeline.png", "Cảm xúc theo thời gian (phút + 10 giây)", "eda_sentiment_per_minute + per_10s"],
            ["11_throughput_burst.png", "Thông lượng mỗi giây và các đợt bùng nổ", "eda_throughput_per_second.csv"],
            ["12_negative_share_alert.png", "Tỷ lệ âm theo cửa sổ và ngưỡng cảnh báo", "eda_negative_share_alert.csv"],
            ["13_latency_distribution.png", "Phân bố và phân vị độ trễ", "eda_latency_histogram + quantiles"],
            ["14_model_quality.png", "Confusion matrix + P/R/F1 từng lớp", "confusion_matrix.csv, per_class_metrics.csv"],
            ["15_interactive_volume.png", "Tương quan thông lượng và tỷ lệ âm", "eda_sentiment_per_10s + per_minute"],
        ],
        widths=[5.4, 6.8, 4.2],
    )
    p("plots.py có --only N để vẽ lại một hình. Khi dùng --only, script KHÔNG ghi đè insights.md — "
      "tránh việc một hình lẻ làm mất phần insight đầy đủ.")
    p("plots.py sinh outputs/insights.md từ số đo thật. Không sửa tay file này; muốn đổi câu chữ "
      "thì sửa plots.py rồi chạy lại.")
    bullets([
        "Mỗi hình có tiêu đề, nhãn trục kèm đơn vị, chú thích nguồn số liệu dưới hình, PNG 200 dpi.",
        "Bảng màu dùng chung: negative cam đỏ, neutral xám, positive xanh ngọc.",
        "Hình 10 chèn NaN giữa các cửa sổ rời nhau để không nối đường qua chỗ trống.",
        "Nhãn emoji dùng tên Unicode tiếng Anh vì matplotlib không vẽ được glyph mặt cười.",
    ])


# ---------------------------------------------------------------------------
# Chương 12 — điều phối
# ---------------------------------------------------------------------------
def ch12() -> None:
    chapter(12)
    h2("12.1. run_demo.sh — một lệnh chạy cả hệ thống")
    p("Script khởi động theo đúng thứ tự bắt buộc và dừng theo thứ tự ngược lại. Thứ tự không phải "
      "cho đẹp: Kafka phải sống trước; job streaming phải READY trước khi producer gửi bản ghi đầu; "
      "dashboard lên sau cùng vì chỉ đọc Parquet.")
    code("bash scripts/run_demo.sh                    # Kafka → topic → job → producer → dashboard\n"
         "bash scripts/run_demo.sh --duration 600     # tự dừng sạch sau 10 phút\n"
         "bash scripts/run_demo.sh --sample 5000 --rate 30\n"
         "bash scripts/run_demo.sh --stop             # dừng sạch mọi thứ (kể cả Kafka)\n"
         "bash scripts/run_demo.sh --stop --keep-kafka")
    table(
        ["Tham số", "Mặc định", "Ý nghĩa"],
        [
            ["--run TÊN", "demo", "Tên lần chạy; cũng là outputs/stream/<tên> và checkpoints/streaming/<tên>."],
            ["--port N", "8501", "Cổng dashboard."],
            ["--rate N", "theo config (50)", "Bình luận/giây của producer."],
            ["--sample N", "2000", "Số bình luận lấy từ nguồn rồi phát lặp."],
            ["--duration N", "0", "Tự dừng sau N giây; 0 = chạy tới khi Ctrl+C/--stop."],
            ["--keep-kafka", "tắt", "Khi dừng thì giữ Kafka chạy."],
            ["--stop", "tắt", "Chỉ dừng những gì script đã khởi động rồi thoát."],
            ["-- <tham số>", "không", "Phần còn lại truyền thẳng cho stream_job.py."],
        ],
        widths=[3.6, 4.4, 8.4],
    )
    h3("Các bước của run_demo.sh")
    steps([
        "source env.sh; kiểm tra VENV_PY, model đã lưu, COMMENT_HASH_SALT, và không có job cùng tên đang chạy.",
        "Đặt trap INT/TERM để Ctrl+C luôn chạy stop_all().",
        "Khởi động Kafka (bỏ qua nếu đang chạy), tạo ba topic.",
        "Gọi run_stream.sh <run> --keep-text; script này chờ tới khi job in READY mới trả về.",
        "Chạy producer ở nền với --sample 2000 --loop (và --rate nếu có), ghi PID/log.",
        "Chạy Streamlit ở nền với --server.address 0.0.0.0, chờ cổng trả lời tối đa 60 giây.",
        "Nếu --duration > 0 thì sleep rồi stop_all(); nếu không thì giữ tiền cảnh và chờ dashboard thoát.",
        "stop_all() dừng dashboard → producer → job streaming (SIGTERM qua stop_stream.sh) → Kafka "
        "(trừ khi --keep-kafka).",
    ])
    note("Chạy lại cùng tên sẽ tiếp tục từ checkpoint cũ và cộng dồn vào outputs/stream/<tên>. "
         "Muốn bắt đầu lại từ đầu: xoá outputs/stream/<tên> và checkpoints/streaming/<tên>.",
         "warn")

    h2("12.2. run_stream.sh — chạy job streaming an toàn")
    p("Đây là lớp kiểm tra trước khi gọi spark-submit. Nó tồn tại vì hai lỗi thực tế: gửi dữ liệu "
      "trước khi job READY (mất bản ghi), và HDFS tắt/safe mode làm Spark không ghi được event log.")
    code("bash scripts/run_stream.sh <tên-lần-chạy> [tham số stream_job.py ...]")
    table(
        ["Bước", "Việc kiểm tra / làm"],
        [
            ["1", "Nếu đã có tiến trình stream_job.py cùng run-name → dừng, báo lỗi."],
            ["2", "Kiểm tra cổng Kafka localhost:9092; không kết nối được → báo chạy start_kafka.sh."],
            ["3", "Nếu HDFS không phản hồi → thêm --conf spark.eventLog.enabled=false cho riêng lần chạy."],
            ["4", "Nếu HDFS ở safe mode → chờ tối đa 90 giây; vẫn safe mode thì tắt event log."],
            ["5", "Chạy spark-submit --master local[2] --driver-memory 2g --packages $SPARK_KAFKA_PKG ở nền."],
            ["6", "Ghi PID vào logs/task8_stream_<tên>.pid, log vào logs/task8_stream_<tên>.log."],
            ["7", "Chờ tối đa 240 giây để log xuất hiện dòng READY; nếu job chết thì in 40 dòng cuối."],
        ],
        widths=[1.6, 14.8],
    )
    note("HDFS chỉ dùng cho event log. Khi HDFS tắt, sink và checkpoint trên ổ đĩa cục bộ vẫn hoạt động; "
         "chỉ Spark History Server không có lần chạy đó.", "info")

    h2("12.3. stop_stream.sh — dừng êm")
    p("Script tìm tiến trình Python driver là con của JVM spark-submit, gửi SIGTERM cho đúng tiến trình "
      "Python (không phải JVM), rồi chờ tối đa 60 giây. Handler trong stream_job.py gọi query.stop() "
      "cho từng query, làm nốt micro-batch và ghi checkpoint trước khi thoát.")
    code("bash scripts/stop_stream.sh <tên-lần-chạy>")
    bullets([
        "Không dùng kill -9: có thể cắt ngang lúc đang ghi file/Kafka và để lại batch dở.",
        "Structured Streaming vẫn an toàn về offset, nhưng kết quả có thể trùng khi chạy lại — đúng bản chất at-least-once.",
        "Nếu sau 60 giây job vẫn chạy, script in 20 dòng log cuối và gợi ý kiểm tra PID.",
    ])

    h2("12.4. Một phiên demo điển hình")
    table(
        ["Thời điểm", "Việc xảy ra"],
        [
            ["0:00", "run_demo.sh khởi động Kafka, tạo topic."],
            ["0:10–1:30", "Job streaming khởi động, nạp model, in READY. Chưa có dữ liệu."],
            ["1:30", "Producer bắt đầu gửi 2.000 review lặp, 50/giây."],
            ["1:30–2:00", "scored_detail bắt đầu có dòng; dashboard hiện dữ liệu đến."],
            ["3:00–4:00", "Cửa sổ 1 phút đầu tiên được ghi sau watermark; biểu đồ cảm xúc xuất hiện."],
            ["Bất kỳ lúc nào", "Ctrl+C hoặc run_demo.sh --stop: dừng ngược thứ tự, ghi nốt checkpoint."],
        ],
        widths=[3.4, 13.0],
    )

    h2("12.5. Dọn dẹp và chạy lại từ đầu")
    code("# dừng mọi thứ\nbash scripts/run_demo.sh --stop\n\n"
         "# xoá dữ liệu của một lần chạy (ví dụ demo) để bắt đầu lại\n"
         "rm -rf outputs/stream/demo checkpoints/streaming/demo\n"
         "rm -f logs/task8_stream_demo.log logs/task10_*_demo.log\n\n"
         "# kiểm tra còn tiến trình nào không\n"
         "pgrep -af 'stream_job.py|replay_producer.py|streamlit' || true")
    note("Không xoá outputs/models/sentiment_pipeline nếu chưa huấn luyện lại. Model là đầu vào của "
         "streaming, dashboard và app terminal.", "warn")


# ---------------------------------------------------------------------------
# Chương 13 — thư viện dùng chung
# ---------------------------------------------------------------------------
def ch13() -> None:
    chapter(13)
    h2("13.1. src/common/utils.py")
    table(
        ["Hàm", "Việc làm", "Ghi chú"],
        [
            ["load_config(path=None)", "Đọc YAML, mặc định config.yaml ở gốc dự án.",
             "Import yaml muộn để không kéo phụ thuộc vào mọi script."],
            ["get_salt()", "Đọc COMMENT_HASH_SALT từ biến môi trường.", "Thiếu thì raise MissingSaltError, không đoán."],
            ["salted_hash(user_id, salt=None, length=16)", "SHA-256(salt + user_id), lấy 16 hex.",
             "Cùng người + cùng muối → cùng hash; không tra ngược."],
            ["iter_json_array(path, chunk_size=1MB)", "Yield từng object trong mảng JSON lớn.",
             "Chỉ giữ một đoạn đệm nhỏ, không nạp cả GB vào RAM."],
        ],
        widths=[5.4, 6.8, 4.2],
    )

    h2("13.2. src/common/text_cleaning.py — chín bước làm sạch")
    p("Đây là file quan trọng nhất về tính nhất quán: cả huấn luyện và streaming đều gọi đúng hàm này. "
      "Thứ tự chín bước rất quan trọng; đổi thứ tự là đổi kết quả.")
    table(
        ["Bước", "Việc làm", "Ví dụ"],
        [
            ["1", "lower + trim", "'Not  BAD' → 'not  bad'"],
            ["2", "Bỏ thẻ HTML và entity", "'<i>good</i> &amp; bad' → ' good   & bad '"],
            ["3", "URL → <url>", "'see https://x.y' → 'see  <url> '"],
            ["4", "@mention → <user>", "'@john: hi' → ' <user> : hi'"],
            ["5", "Chuẩn hóa dấu câu unicode, bỏ ký tự vô hình", "’ “ ” – — → ' \" \" - -"],
            ["6", "Thay viết tắt theo ranh giới từ", "'u r gr8' → 'you are gr8'"],
            ["7", "Rút gọn ký tự lặp ≥3 thành 2", "'haaaay' → 'haay'"],
            ["8", "Tách emoji thành token riêng", "'hay😍😍' → 'hay 😍 😍'"],
            ["9", "Gộp khoảng trắng, trim", "'a   b' → 'a b'"],
        ],
        widths=[1.6, 8.4, 6.4],
    )
    p("Các hàm con: strip_html, replace_urls, replace_mentions, normalize_punctuation, "
      "apply_abbreviations, collapse_repeats, space_emoji, normalize_whitespace. Ngoài ra có "
      "token_count (đếm token theo khoảng trắng), dedup_key (khóa gần trùng: lower, bỏ dấu câu, "
      "sắp xếp từ, md5) và emoji_frequency (đếm emoji).")
    note("Hàm là idempotent: chạy hai lần cho cùng kết quả. Có test riêng trong tests/test_text_cleaning.py. "
         "Không dùng Python UDF — toàn bộ là hàm Spark SQL để Catalyst tối ưu.", "ok")

    h2("13.3. src/common/metrics.py")
    p("Chỉ dùng numpy, không phụ thuộc Spark, nên test được bằng dữ liệu nhỏ. Công thức:")
    code("precision_c = TP_c / (TP_c + FP_c)\n"
         "recall_c    = TP_c / (TP_c + FN_c)\n"
         "F1_c        = 2PR / (P + R)\n"
         "accuracy    = trace(cm) / sum(cm)\n"
         "macro-F1    = trung bình cộng F1 của các lớp CÓ MẶT\n"
         "weighted-F1 = trung bình F1 theo support của từng lớp")
    p("confusion_matrix(y_true, y_pred, n_labels) đếm cm[i, j] = số mẫu nhãn thật i bị đoán thành j. "
      "metrics_from_cm(cm, labels) trả về (chỉ số tổng, chỉ số từng lớp). Cả train.py và model_trial.py "
      "dùng cùng hàm này để số liệu không lệch nhau.")

    h2("13.4. src/common/plotting.py")
    p("Một bảng màu duy nhất cho mọi biểu đồ: negative #E76F51 (cam đỏ), neutral #9A9A9A (xám), "
      "positive #2A9D8F (xanh ngọc). STAGE_COLORS dùng cho sơ đồ kiến trúc. apply_style() đặt "
      "font DejaVu Sans, lưới mờ, backend Agg. save_fig() lưu PNG 200 dpi và ghi chú nguồn dưới hình.")
    code("from src.common.plotting import apply_style, save_fig\n"
         "apply_style()\n"
         "save_fig(fig, 'outputs/figures/06_class_distribution.png',\n"
         "         note='Source: outputs/tables/eda_class_distribution.csv')")


# ---------------------------------------------------------------------------
# Chương 14 — kiểm thử
# ---------------------------------------------------------------------------
def ch14() -> None:
    chapter(14)
    h2("14.1. Chạy toàn bộ kiểm thử")
    code("source scripts/env.sh\n"
         ".venv/bin/python -m pytest tests/ -q\n"
         "# hoặc từng file\n"
         ".venv/bin/python -m pytest tests/test_dashboard.py -q")
    p("test_text_cleaning.py dựng SparkSession thật nên chậm hơn các file khác. Nếu chỉ sửa dashboard "
      "hoặc model_trial, chạy riêng file tương ứng để tiết kiệm thời gian.")

    h2("14.2. Năm bộ kiểm thử")
    table(
        ["File", "Số test", "Kiểm tra điều gì"],
        [
            ["tests/test_utils.py", "8", "Băm có muối khớp giữa Python và Spark; ánh xạ nhãn; iter_json_array; "
             "các khóa config bắt buộc."],
            ["tests/test_text_cleaning.py", "20", "Idempotence; HTML/URL/mention; viết tắt; emoji; dedup_key; "
             "token_count — chạy trên SparkSession thật."],
            ["tests/test_prepare_sampling.py", "15", "Lấy mẫu tất định theo crc32; các mức lồng nhau; "
             "config cũ/mới; không phụ thuộc thứ tự."],
            ["tests/test_dashboard.py", "21", "Gộp cửa sổ, cảnh báo đúng quy tắc, che dữ liệu, biểu đồ; "
             "dùng cả dữ liệu giả và verify1 thật."],
            ["tests/test_model_trial.py", "13", "text_problem; confusion matrix; metrics; định dạng một dòng; "
             "resolve đường dẫn; prediction_records."],
        ],
        widths=[5.0, 1.8, 9.6],
    )
    p("Tổng cộng 77 test. Con số này lấy từ việc đếm test trong mã nguồn, không phải ước lượng.")

    h2("14.3. Cách đọc kết quả pytest")
    code("$ .venv/bin/python -m pytest tests/ -q\n"
         "...........................                                 [100%]\n"
         "77 passed in <số giây>s     # thời gian tùy máy")
    bullets([
        "Dấu chấm là test pass; F là fail; E là lỗi khi chạy (fixture, import).",
        "Dòng cuối 'N passed' là tổng kết. Nếu có 'failed', pytest in traceback của test đầu tiên.",
        "Muốn xem tên từng test: thêm -v. Muốn dừng ở lỗi đầu: -x.",
        "Test dashboard dùng dữ liệu verify1 thật, nên nếu xoá outputs/stream/verify1 thì một số test sẽ fail.",
    ])
    note("Không sửa test để che lỗi. Nếu một con số thật thay đổi (ví dụ chạy lại verify1 với dữ liệu khác), "
         "cập nhật test kèm giải thích trong commit.", "warn")


# ---------------------------------------------------------------------------
# Chương 15 — script tạo tài liệu
# ---------------------------------------------------------------------------
def ch15() -> None:
    chapter(15)
    h2("15.1. Quy tắc chung khi sinh tài liệu nộp")
    p("CLAUDE.md §11 đúc kết từ các lỗi thật khi làm Task 2–4. Mọi script sinh .docx/.pptx/.xlsx "
      "phải tuân thủ:")
    bullets([
        "KHÔNG sửa file trong TEMPLATES_DIR. Luôn shutil.copyfile sang deliverables/ rồi mới mở bản copy.",
        "Điền nội dung bằng cách nhân bản paragraph gốc (copy.deepcopy của w:p) để giữ font, cỡ chữ, giãn dòng.",
        "Xoá w:spacing trong w:rPr của run do mình tạo: template đặt letter-spacing -12, LibreOffice làm mất dấu cách.",
        "Ép màu chữ w:val=000000 và xoá themeColor/themeShade/themeTint — chữ xám là do theme shade.",
        "Mỗi bảng của template bắt đầu bằng page break cứng; nội dung dài hơn trMinimum sẽ sinh trang trắng.",
        "Sau khi điền, luôn chuyển PDF bằng soffice --headless --convert-to pdf, đếm trang và kiểm tra trang trắng.",
        "Kiểm tra bố cục bằng ảnh (pdftoppm), không chỉ bằng text.",
    ])
    code("# kiểm tra trang trắng sau khi sinh\n"
         "soffice --headless --convert-to pdf --outdir /tmp/pdfcheck deliverables/<file>.docx\n"
         "pdfinfo /tmp/pdfcheck/<file>.pdf | grep Pages\n"
         "for p in $(seq 1 N); do pdftotext -f $p -l $p /tmp/pdfcheck/<file>.pdf - \\\n"
         "  | tr -d '[:space:]' | wc -c; done\n"
         "# trang nào ~0 ký tự là trang trắng → rút gọn nội dung rồi chạy lại")

    h2("15.2. Các script sinh tài liệu")
    table(
        ["Script", "Template / nguồn", "Đầu ra", "Việc làm"],
        [
            ["fill_action_plan.py", "SIC_Big Data_Capstone Project_Action Plan.docx", "deliverables/Action_Plan.docx",
             "Điền Action Plan: mục tiêu, phạm vi, kết quả mong đợi, phân công."],
            ["fill_wbs.py", "SIC_Big Data_Capstone Project_Work Breakdown Structure.xlsx", "deliverables/WBS.xlsx",
             "Điền 20 ngày D1–D20, phân công, Gantt; sửa WBS ở các mốc kiểm tra."],
            ["fill_proposal_slides.py", "SIC_Big Data_Capstone Project_Presentation Slide Template.pptx",
             "deliverables/Proposal_Slides.pptx",
             "Dựng 5 slide đề xuất, giữ master/layout/màu/font; ghi chú thuyết trình."],
            ["fill_final_report.py", "SIC_Big Data_Capstone Project_Final Report.docx", "deliverables/Final_Report.docx",
             "Báo cáo cuối kỳ tiếng Anh theo template; chèn hình và bảng từ outputs/."],
            ["make_vi_technical_report.py", "tạo mới từ python-docx", "docs/bao_cao_ky_thuat_vi.docx (+ PDF)",
             "Báo cáo kỹ thuật tiếng Việt (tài liệu nội bộ), không phải bản nộp."],
            ["make_training_guide.py", "tạo mới từ python-docx", "docs/huong_dan_huan_luyen.docx",
             "Hướng dẫn huấn luyện tiếng Việt cho thành viên."],
            ["make_pipeline_diagram.py", "matplotlib", "outputs/figures/00_pipeline_architecture.png",
             "Vẽ sơ đồ kiến trúc pipeline, chữ tiếng Anh, 200 dpi."],
            ["install_template_fonts.py", "font nhúng trong template", "~/.local/share/fonts/course-templates/",
             "Giải mã và cài font của template; chỉ cần chạy lại nếu đổi máy."],
        ],
        widths=[4.8, 5.4, 4.6, 4.0],
    )
    note("Các script dùng python-docx/openpyxl/python-pptx phải chạy bằng /usr/bin/python3 vì .venv "
         "không cài các thư viện này. Kiểm tra bằng: /usr/bin/python3 -c 'import docx, openpyxl, pptx'.",
         "warn")

    h2("15.3. Vì sao dùng /usr/bin/python3")
    p("Môi trường .venv chỉ chứa các thư viện phục vụ chạy hệ thống (pyspark, kafka-python, pandas, "
      "streamlit...). python-docx, openpyxl và python-pptx được cài cho Python hệ thống để sinh tài liệu. "
      "Đây là lý do các lệnh sinh Word trong repo đều bắt đầu bằng /usr/bin/python3, còn lệnh chạy "
      "dashboard/producer bắt đầu bằng $VENV_PY.")


# ---------------------------------------------------------------------------
# Chương 16 — bảng tra lệnh
# ---------------------------------------------------------------------------
def ch16() -> None:
    chapter(16)
    p("Tất cả lệnh dưới đây chạy từ PROJECT_ROOT = /home/hadoop/capstone, sau khi source scripts/env.sh "
      "(trừ khi ghi chú khác). $VENV_PY = .venv/bin/python; $SPARK_HOME = /home/hadoop/spark-3.5.9.")
    h2("16.1. Môi trường và kiểm tra")
    code("source scripts/env.sh\nbash scripts/check_env.sh\nbash scripts/check_env.sh --smoke\n"
         "echo $JAVA_HOME $SPARK_HOME $VENV_PY $KAFKA_BOOTSTRAP")
    h2("16.2. Kafka")
    code("bash kafka/start_kafka.sh\nbash kafka/create_topics.sh\nbash kafka/stop_kafka.sh\n"
         "$KAFKA_HOME/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list\n"
         "$KAFKA_HOME/bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe")
    h2("16.3. Chuẩn bị dữ liệu và huấn luyện")
    code("PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\\n"
         "  --driver-memory 2g --master 'local[2]' src/training/prepare.py --sample 20000\n"
         "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\\n"
         "  --driver-memory 4g --master 'local[2]' src/training/train.py\n"
         "$VENV_PY src/training/train.py --figures-only")
    h2("16.4. Streaming")
    code("bash scripts/run_stream.sh verify1 --sink-dir outputs/stream/verify1 \\\n"
         "  --checkpoint-root checkpoints/streaming/verify1 --trigger-seconds 5\n"
         "bash scripts/stop_stream.sh verify1\n"
         "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\\n"
         "  --master 'local[2]' --driver-memory 2g src/streaming/verify_stream.py --run-name verify1")
    h2("16.5. Producer và kiểm tra message")
    code("$VENV_PY src/producer/replay_producer.py --sample 2000 --loop\n"
         "$VENV_PY src/producer/replay_producer.py --only-test --max 1000 --rate 50 \\\n"
         "  --labels-out outputs/stream/verify1/sent_labels.parquet\n"
         "$VENV_PY src/producer/test_consumer.py --topic comments_raw --expect 1000\n"
         "$VENV_PY scripts/send_bad_events.py --heartbeat 12 --heartbeat-interval 25 --late-probe")
    h2("16.6. Demo, dashboard, terminal, thử mô hình")
    code("bash scripts/run_demo.sh --duration 600\nbash scripts/run_demo.sh --stop\n"
         "$VENV_PY -m streamlit run src/app/app.py --server.address 0.0.0.0 --server.port 8501\n"
         "bash scripts/run_terminal_app.sh --fast --limit 20\n"
         "bash scripts/run_comment_stream.sh --limit 20\n"
         "bash scripts/run_model_trial.sh --examples\n"
         "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\\n"
         "  --driver-memory 2g --master 'local[2]' scripts/check_model.py")
    h2("16.7. EDA và kiểm thử")
    code("$VENV_PY src/eda/queries.py --dry-run --check\n"
         "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\\n"
         "  --driver-memory 4g --master 'local[2]' src/eda/queries.py\n"
         "$VENV_PY src/eda/plots.py\n"
         ".venv/bin/python -m pytest tests/ -q")
    h2("16.8. Sinh tài liệu")
    code("/usr/bin/python3 scripts/fill_action_plan.py\n"
         "/usr/bin/python3 scripts/fill_wbs.py\n"
         "/usr/bin/python3 scripts/fill_proposal_slides.py\n"
         "/usr/bin/python3 scripts/fill_final_report.py\n"
         "/usr/bin/python3 scripts/make_vi_technical_report.py\n"
         "/usr/bin/python3 scripts/make_training_guide.py\n"
         "/usr/bin/python3 scripts/make_pipeline_diagram.py\n"
         "/usr/bin/python3 scripts/install_template_fonts.py")
    h2("16.9. Git")
    code("git status --short\ngit add <file>\ngit commit -m \"...\"\ngit push origin main")
    note("Trước khi commit, kiểm tra không có file dữ liệu lớn hay bí mật. .gitignore đã loại data/raw, "
         "data/processed, checkpoints, .venv và templates.", "warn")


# ---------------------------------------------------------------------------
# Chương 17 — xử lý sự cố
# ---------------------------------------------------------------------------
def ch17() -> None:
    chapter(17)
    table(
        ["Triệu chứng", "Nguyên nhân", "Cách xử lý"],
        [
            ["PySpark báo RecursionError khi khởi động", "Chạy bằng Python 3.14",
             "Dùng PYSPARK_PYTHON=/usr/bin/python3.11 như env.sh."],
            ["Không kết nối được HDFS localhost:9000", "NameNode chưa chạy sau khi khởi động máy",
             "/usr/local/hadoop/sbin/start-dfs.sh; hoặc chạy run_stream.sh để tự tắt event log."],
            ["SafeModeException khi tạo /spark-logs", "HDFS vừa khởi động còn safe mode",
             "Chờ 90 giây (run_stream.sh tự chờ) hoặc hdfs dfsadmin -safemode leave."],
            ["Kafka báo UnsupportedClassVersionError", "Broker chạy bằng Java 8",
             "start_kafka.sh đặt JAVA_HOME=KAFKA_JAVA_HOME (Java 17)."],
            ["Producer gửi nhưng bảng chi tiết trống", "Job đọc startingOffsets=latest và chưa READY",
             "Chờ READY rồi mới phát; xem run_stream.sh."],
            ["Cửa sổ 1 phút rỗng vài phút đầu", "Watermark 2 phút chưa vượt window_end",
             "Chờ thêm hoặc phát heartbeat; dashboard tự tính từ scored_detail."],
            ["Cửa sổ cuối không xuất hiện sau khi ngừng phát", "Watermark chỉ tiến khi có bản ghi mới",
             "send_bad_events.py --heartbeat N --heartbeat-interval S."],
            ["Dashboard không mở từ máy thật", "Chưa port forwarding hoặc thiếu --server.address 0.0.0.0",
             "Xem src/app/README.md mục VirtualBox."],
            ["Thiếu COMMENT_HASH_SALT", "Chưa tạo ~/.capstone-secrets.sh", "Xem Chương 2.4."],
            ["Không thấy model", "Chưa chạy train.py hoặc đã xoá outputs/models",
             "Chạy train.py bản đầy đủ; kiểm tra metadata JSON."],
            ["Đã có job streaming cùng tên", "Lần chạy trước chưa dừng",
             "bash scripts/stop_stream.sh <tên>; kiểm tra pgrep."],
            ["Đầy đĩa hoặc /tmp đầy", "Spark ghi shuffle vào /tmp",
             "env.sh đã trỏ SPARK_LOCAL_DIRS sang /home/hadoop/spark-tmp; kiểm tra dung lượng."],
            ["Thiếu pandas cho Python 3.11", "Chưa cài cho đúng interpreter",
             "python3.11 -m pip install --user --break-system-packages pandas numpy."],
            ["Thiếu streamlit", "Chưa cài cho Python mặc định",
             "python3 -m pip install --user --break-system-packages streamlit."],
            ["Word/PDF mất dấu cách", "Letter-spacing -12 của template gặp LibreOffice",
             "Xoá w:spacing trong w:rPr của run do mình tạo (CLAUDE.md §11)."],
            ["Tài liệu có trang trắng", "Bảng tràn trang do trHeight tối thiểu",
             "Rút gọn nội dung, chuyển PDF, kiểm tra từng trang bằng pdftotext."],
            ["Font template hiển thị sai", "Chưa cài font đã giải mã",
             "/usr/bin/python3 scripts/install_template_fonts.py."],
            ["kafka-python báo lỗi api_version_auto_timeout_ms", "Dùng kafka-python 3.x đã bỏ tham số",
             "Dùng bootstrap_timeout_ms; code hiện tại đã tương thích."],
        ],
        widths=[5.6, 5.4, 5.4],
    )


# ---------------------------------------------------------------------------
# Chương 18 — thuật ngữ
# ---------------------------------------------------------------------------
def ch18() -> None:
    chapter(18)
    terms = [
        ("Kafka", "Hàng đợi sự kiện phân tán; producer ghi, consumer đọc theo offset."),
        ("Broker", "Một tiến trình Kafka. Dự án chạy một broker tại localhost:9092."),
        ("KRaft", "Chế độ Kafka không cần Zookeeper; Kafka 4.x dùng mặc định."),
        ("Topic", "Kênh logic chứa message. Dự án có comments_raw, comments_scored, comments_dlq."),
        ("Partition", "Đơn vị song song của topic; offset chỉ duy nhất trong một partition."),
        ("Offset", "Số thứ tự message trong partition; Spark commit offset theo micro-batch."),
        ("Producer", "Chương trình ghi message vào topic."),
        ("Consumer", "Chương trình đọc message từ topic."),
        ("Event time", "Thời điểm sự kiện xảy ra, lấy từ event_ts. Dùng cho cửa sổ và watermark."),
        ("Processing time", "Thời điểm hệ thống xử lý. Không dùng thay event time trong dự án."),
        ("Watermark", "Mốc muộn tối đa chấp nhận; dữ liệu cũ hơn bị bỏ và đếm vào cột dropped."),
        ("Window", "Cửa sổ thời gian để gộp. Dự án có cửa sổ nhảy 1 phút và cửa sổ trượt 10 giây/5 giây."),
        ("Micro-batch", "Một lần xử lý của Structured Streaming, thường theo trigger 10 giây."),
        ("Checkpoint", "Thư mục lưu offset/state để job tiếp tục đúng chỗ sau khi dừng."),
        ("Sink", "Đích ghi kết quả: Parquet, Kafka hoặc DLQ."),
        ("DLQ", "Dead-letter queue — nơi ghi bản ghi lỗi kèm lý do, không âm thầm bỏ."),
        ("At-least-once", "Mỗi bản ghi được xử lý ít nhất một lần; có thể trùng khi lỗi. Đây là ngữ nghĩa đã kiểm chứng."),
        ("Exactly-once", "Mỗi bản ghi được xử lý đúng một lần. CHƯA kiểm chứng trong dự án."),
        ("Pipeline", "Chuỗi stage Spark ML: tokenizer → stopwords → ngram → TF-IDF → classifier."),
        ("PipelineModel", "Pipeline đã fit, lưu ra đĩa và nạp lại để chấm điểm."),
        ("TF-IDF", "Term Frequency × Inverse Document Frequency — trọng số từ theo tần suất trong văn bản và toàn tập."),
        ("Token", "Đơn vị từ sau khi tách; với emoji, mỗi emoji là một token."),
        ("N-gram", "Chuỗi n token liên tiếp; n=2 giữ được cụm như 'not good'."),
        ("Stopword", "Từ phổ biến bị bỏ; dự án giữ lại từ phủ định."),
        ("Confusion matrix", "Bảng đếm nhãn thật × nhãn dự đoán."),
        ("Macro-F1", "Trung bình cộng F1 của các lớp — không bị lớp đông lấn át."),
        ("Weighted-F1", "Trung bình F1 theo số mẫu của từng lớp."),
        ("Replay", "Phát lại dữ liệu cũ với event_ts mới; KHÔNG phải livestream thật."),
        ("Sidecar labels", "File nhãn để đánh giá, tách khỏi luồng Kafka, ghép theo comment_id."),
        ("Salted hash", "Băm có muối; cùng người → cùng mã, không tra ngược."),
        ("Parquet", "Định dạng cột nén, dùng cho bảng chi tiết và cửa sổ."),
        ("UDF", "User-defined function. Dự án tránh Python UDF ở khâu làm sạch."),
    ]
    table(["Thuật ngữ", "Nghĩa trong dự án"], [[a, b] for a, b in terms], widths=[4.2, 12.2])


# ---------------------------------------------------------------------------
# Phụ lục
# ---------------------------------------------------------------------------
def appendix_a() -> None:
    h1("Phụ lục A — Bảng tra file → chức năng → đầu ra")
    files = [
        ("scripts/env.sh", "Biến môi trường dùng chung", "—"),
        ("scripts/check_env.sh", "Kiểm tra Java/HDFS/Spark/pandas/streamlit", "màn hình, mã thoát"),
        ("kafka/start_kafka.sh", "Khởi động Kafka KRaft", "broker.log"),
        ("kafka/stop_kafka.sh", "Dừng Kafka", "—"),
        ("kafka/create_topics.sh", "Tạo 3 topic", "topic trên broker"),
        ("src/training/prepare.py", "Làm sạch, chia tập", "train/val/test/eval_labels parquet + bảng thống kê"),
        ("src/training/train.py", "Huấn luyện và đánh giá", "PipelineModel + metrics + hình 01–05"),
        ("src/streaming/stream_job.py", "6 query streaming", "scored_detail, Kafka, 2 bảng cửa sổ, DLQ"),
        ("src/streaming/verify_stream.py", "Đối soát và macro-F1 trên luồng", "stream_verification.csv, verification.json"),
        ("src/producer/replay_producer.py", "Phát review vào Kafka", "message trên comments_raw, sent_labels"),
        ("src/producer/test_consumer.py", "Kiểm tra message", "màn hình, mã thoát"),
        ("scripts/send_bad_events.py", "Gửi 11 ca lỗi + heartbeat", "message trên comments_raw"),
        ("src/eda/queries.py", "13 truy vấn Spark SQL", "outputs/tables/eda_*.csv"),
        ("src/eda/plots.py", "Vẽ hình và sinh insight", "hình 06–15, insights.md"),
        ("src/app/app.py", "Dashboard Streamlit 3 tab", "giao diện web"),
        ("src/app/terminal_app.py", "Walkthrough 8 giai đoạn", "màn hình, outputs/terminal_demo/"),
        ("src/app/model_trial.py", "Thử mô hình bằng câu nhập tay", "model_trial_predictions/summary/report"),
        ("src/common/utils.py", "Config, băm, đọc JSON lớn", "—"),
        ("src/common/text_cleaning.py", "Làm sạch văn bản dùng chung", "cột text_clean"),
        ("src/common/metrics.py", "Confusion matrix và metrics", "—"),
        ("src/common/plotting.py", "Bảng màu và lưu hình", "PNG 200 dpi"),
        ("scripts/run_stream.sh", "Chạy job streaming an toàn", "logs/task8_stream_<run>.log"),
        ("scripts/stop_stream.sh", "Dừng êm job streaming", "—"),
        ("scripts/run_demo.sh", "Chạy toàn hệ thống", "logs/task10_*, outputs/stream/demo"),
        ("scripts/run_terminal_app.sh", "Chạy app terminal", "màn hình"),
        ("scripts/run_comment_stream.sh", "Chạy chế độ từng comment", "màn hình"),
        ("scripts/run_model_trial.sh", "Chạy model_trial", "báo cáo theo chế độ"),
        ("scripts/check_model.py", "Kiểm tra model đã lưu", "màn hình"),
        ("scripts/make_program_guide.py", "Sinh tài liệu này", "docs/giai_thich_chuong_trinh.docx"),
        ("scripts/make_pipeline_diagram.py", "Vẽ sơ đồ kiến trúc", "00_pipeline_architecture.png"),
        ("scripts/fill_action_plan.py", "Điền Action Plan", "deliverables/Action_Plan.docx"),
        ("scripts/fill_wbs.py", "Điền WBS", "deliverables/WBS.xlsx"),
        ("scripts/fill_proposal_slides.py", "Dựng slide đề xuất", "deliverables/Proposal_Slides.pptx"),
        ("scripts/fill_final_report.py", "Điền báo cáo cuối kỳ", "deliverables/Final_Report.docx"),
        ("scripts/make_vi_technical_report.py", "Báo cáo kỹ thuật tiếng Việt", "docs/bao_cao_ky_thuat_vi.docx"),
        ("scripts/make_training_guide.py", "Hướng dẫn huấn luyện", "docs/huong_dan_huan_luyen.docx"),
        ("scripts/install_template_fonts.py", "Cài font template", "~/.local/share/fonts/course-templates/"),
        ("config.yaml", "Tham số dùng chung", "—"),
        ("tests/*.py", "77 test", "kết quả pytest"),
    ]
    # spacer=False: bảng dài kết thúc sát đáy trang; thêm paragraph trống sau bảng
    # sẽ đẩy nó sang trang riêng và sinh trang trắng trước Phụ lục B.
    table(["File", "Chức năng", "Đầu ra"], [[a, b, c] for a, b, c in files],
          widths=[6.0, 6.4, 4.0], font_size=8.2, spacer=False)


def appendix_b() -> None:
    h1("Phụ lục B — Lộ trình đọc code trong 30 phút")
    steps([
        "5 phút — Đọc Chương 1 và Chương 2 của tài liệu này; mở config.yaml để thấy các tham số.",
        "5 phút — Chạy bash scripts/check_env.sh và bash scripts/run_terminal_app.sh --fast --limit 5 "
        "để thấy luồng hoạt động bằng mắt.",
        "5 phút — Mở src/common/text_cleaning.py, đọc docstring 9 bước và hàm clean_text().",
        "5 phút — Mở src/training/train.py, đọc build_pipeline() và phần main() từ bước nạp dữ liệu "
        "đến lưu model.",
        "5 phút — Mở src/streaming/stream_job.py, đọc parse_stream(), add_cleaning_and_reason(), "
        "score_stream() và start_all_queries().",
        "5 phút — Mở src/app/app.py, đọc ba hàm tab_live, tab_try_it, tab_about; sau đó mở "
        "src/app/terminal_app.py, đọc stage_1 đến stage_8.",
    ])
    p("Sau 30 phút này, bạn có thể tự trả lời: dữ liệu đi qua những đâu, chỗ nào dễ sai, "
      "và muốn thay đổi một hành vi thì sửa file nào. Để đi sâu, dùng bảng tra ở Phụ lục A "
      "và bảng lệnh ở Chương 16.")
    note("Khi trình bày với hội đồng, luôn mở đầu bằng: dữ liệu là replay IMDb công khai, không phải "
         "livestream thật; hệ thống chỉ khẳng định at-least-once; tập test chỉ dùng một lần. "
         "Ba câu này thể hiện sự trung thực và tránh bị hỏi ngược.", "info", "KHI BÁO CÁO")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _render(page_map: dict[str, int]) -> None:
    global doc, PAGE_MAP
    doc = Document()
    PAGE_MAP = dict(page_map)
    _style_document()
    cover()
    toc()
    for fn in (ch1, ch2, ch3, ch4, ch5, ch6, ch7, ch8, ch9, ch10, ch11,
               ch12, ch13, ch14, ch15, ch16, ch17, ch18, appendix_a, appendix_b):
        fn()

    doc.core_properties.title = "Hướng dẫn đọc và hiểu chương trình — SentimentGuard"
    doc.core_properties.subject = "Giải thích mã nguồn và cách vận hành dự án Capstone"
    doc.core_properties.author = "Nhóm 6 — SIC Big Data"
    doc.core_properties.keywords = "Spark, Kafka, streaming, sentiment, capstone"


def _to_pdf(docx_path: Path, outdir: Path) -> Path | None:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return None
    try:
        subprocess.run(
            [exe, "--headless", "--convert-to", "pdf", "--outdir", str(outdir), str(docx_path)],
            check=True, capture_output=True, timeout=300)
    except (subprocess.SubprocessError, OSError):
        return None
    pdf = outdir / (docx_path.stem + ".pdf")
    return pdf if pdf.exists() else None


def _page_map_from_pdf(pdf: Path) -> dict[str, int]:
    """Tìm trang bắt đầu của từng chương/phụ lục trong PDF đã xuất."""
    if not (shutil.which("pdfinfo") and shutil.which("pdftotext")):
        return {}
    try:
        info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, timeout=60)
        m = re.search(r"^Pages:\s+(\d+)", info.stdout, re.M)
        if not m:
            return {}
        n_pages = int(m.group(1))
    except (subprocess.SubprocessError, OSError):
        return {}
    found: dict[str, int] = {}
    for p in range(1, n_pages + 1):
        try:
            txt = subprocess.run(
                ["pdftotext", "-f", str(p), "-l", str(p), str(pdf), "-"],
                capture_output=True, text=True, timeout=60).stdout
        except (subprocess.SubprocessError, OSError):
            continue
        flat = " ".join(txt.split())
        for i in range(1, len(CH) + 1):
            key = f"C{i}"
            if key not in found and re.search(rf"Chương\s+{i}\s*—", flat):
                found[key] = p
        for j, letter in enumerate("AB"):
            if letter not in found and re.search(rf"Phụ lục\s+{letter}\s*—", flat):
                found[letter] = p
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description="Sinh tài liệu Word giải thích chương trình")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="đường dẫn file .docx đầu ra")
    ap.add_argument("--no-page-numbers", action="store_true",
                    help="không dò số trang cho mục lục (không cần LibreOffice)")
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    page_map: dict[str, int] = {}
    if not args.no_page_numbers:
        # Lượt 1: dựng không số trang → xuất PDF → dò trang bắt đầu từng chương.
        _render({})
        with tempfile.TemporaryDirectory(prefix="guide_pass1_") as td:
            tmp_docx = Path(td) / "guide.docx"
            doc.save(str(tmp_docx))
            pdf = _to_pdf(tmp_docx, Path(td))
            if pdf:
                page_map = _page_map_from_pdf(pdf)
        if not page_map:
            print("CẢNH BÁO: không dò được số trang (thiếu soffice/pdfinfo/pdftotext) — mục lục để trống số.",
                  file=sys.stderr)

    # Lượt 2: dựng lại với số trang.
    _render(page_map)
    doc.save(str(out))

    # Kiểm tra số trang không đổi sau khi thêm số vào mục lục; nếu có, dựng lại một lần.
    if page_map:
        with tempfile.TemporaryDirectory(prefix="guide_pass2_") as td:
            pdf2 = _to_pdf(out, Path(td))
            check = _page_map_from_pdf(pdf2) if pdf2 else {}
            if check and check != page_map:
                _render(check)
                doc.save(str(out))
                print("Ghi chú: mục lục được dựng lại để khớp số trang sau cùng.", file=sys.stderr)

    print(f"Đã ghi: {out}")
    print(f"Số chương: {_total_chapters} + {len(APX)} phụ lục")
    return 0


if __name__ == "__main__":
    sys.exit(main())
