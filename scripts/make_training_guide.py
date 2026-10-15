#!/usr/bin/env python3
"""make_training_guide.py — Sinh tài liệu hướng dẫn tự huấn luyện lại mô hình.

Xuất ra: `docs/huong_dan_huan_luyen.docx` (tiếng Việt, tài liệu NỘI BỘ — không phải
bản nộp cho giảng viên; bản nộp nằm ở `deliverables/` và viết bằng tiếng Anh).

    /usr/bin/python3 scripts/make_training_guide.py

⚠️ Phải chạy bằng `/usr/bin/python3`, KHÔNG dùng `.venv/bin/python`: chỉ interpreter
hệ thống mới có `python-docx` (venv của dự án không cài). Script tự kiểm và báo lỗi
rõ ràng nếu thiếu.

Chạy lại được nhiều lần, mỗi lần ghi đè bản cũ (tiền lệ: `scripts/make_pipeline_diagram.py`).

## Vài quyết định đã kiểm chứng trên chính máy này

- **Thân bài dùng `Calibri`**: có sẵn trên Word của nhóm; khi render PDF ở đây,
  LibreOffice tự thay bằng `Carlito` (đã đo bằng `pdffonts`: PDF nhúng
  `Carlito-Regular`) — Carlito đủ 100% dấu tiếng Việt nên bản PDF kiểm tra vẫn đúng.
- **Khối lệnh dùng `Courier New`**, KHÔNG dùng `DejaVu Sans Mono` (đã đo: thiếu
  `ế` U+1EBF) và KHÔNG dùng `Consolas` (không có trên máy, rơi về NotoSerif).
- **Mục lục gõ tay**, không dùng field TOC của Word: `soffice --convert-to pdf`
  không cập nhật field nên mục lục sẽ ra TRỐNG, trông như tài liệu lỗi.
- **Khối lệnh là các ĐOẠN VĂN có nền xám**, không phải bảng 1×1: bảng không tự
  tách qua trang, khối dài sẽ đẩy sang trang sau để lại khoảng trắng lớn
  (đúng loại lỗi ở CLAUDE.md §11).

Sau khi sinh, LUÔN kiểm bố cục theo CLAUDE.md §11 (xem cuối file).
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import docx
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
except ImportError:                                    # pragma: no cover
    sys.exit("Thiếu python-docx. Chạy bằng: /usr/bin/python3 scripts/make_training_guide.py")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DOCX = PROJECT_ROOT / "docs" / "huong_dan_huan_luyen.docx"

FONT_BODY = "Calibri"          # -> LibreOffice thay bằng Carlito khi render PDF
FONT_CODE = "Courier New"      # đủ dấu tiếng Việt, có trên mọi bản Word
FONT_SIZE = 10.5
CODE_SIZE = 8.5
MAX_CODE_LEN = 92              # 17 cm bề rộng thực ở 8,5 pt Courier New chứa ~94 ký tự

# Ký tự ĐÃ ĐO là không font nào trong tài liệu phủ được (xem ghi chú ở `dat_font`).
KY_TU_CAM = "⊂⊃⇒"

SHADE_CODE = "F2F2F2"
SHADE_HEAD = "D9D9D9"
SHADE_WARN = "FCE4E4"
SHADE_NOTE = "FFF7E0"

# Số đo THẬT của lần chạy 15/10/2026 với subsample_pct = 64 (không phải ước lượng).
DO_THAT = {
    "pct": 64,
    "n_nguon": 1_010_293,
    "n_giu": 646_249,
    "mb_jsonl": 608.8,
    "giay_sinh_jsonl": 24,
    "ngay": "15/10/2026",
}


# --------------------------------------------------------------------------- #
# Hàm dựng tài liệu
# --------------------------------------------------------------------------- #
# KÝ TỰ CẤM: ⊂ (U+2282), ⊃ (U+2283), ⇒ (U+21D2) — đã đo bằng fontTools, CẢ Carlito
# LẪN Courier New đều không có, nên LibreOffice âm thầm thay bằng DejaVuSerif (thấy
# trong `pdffonts`; trên Word của nhóm thì rơi về Cambria Math). Viết bằng chữ
# ("nằm trong", "nên") thay vì ký hiệu. `dat_font` chặn sẵn — xem KY_TU_CAM.


def dat_font(run, ten: str = FONT_BODY, co: float = FONT_SIZE,
             dam: bool = False, nghieng: bool = False, mau: str = "000000") -> None:
    """Đặt font TƯỜNG MINH cho một run.

    Phải đặt trên từng run: python-docx để `Normal.font.name = None` (thừa hưởng từ
    `docDefaults`), nếu không LibreOffice tự chọn font khác khi render PDF.

    Mọi chữ trong tài liệu đều đi qua đây nên cũng là chỗ chặn ký tự không font nào phủ.
    """
    for c in run.text:
        assert c not in KY_TU_CAM, (
            f"ký tự {c!r} (U+{ord(c):04X}) không có trong {FONT_BODY} lẫn {FONT_CODE} "
            f"— sẽ bị thay bằng DejaVuSerif khi render. Đổi sang chữ.")
    run.font.name = ten
    run.font.size = Pt(co)
    run.font.bold = dam
    run.font.italic = nghieng
    run.font.color.rgb = RGBColor.from_string(mau)
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.insert(0, rf)
    for thuoc_tinh in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(thuoc_tinh), ten)


def to_nen(doi_tuong, mau: str) -> None:
    """Đổ nền cho đoạn văn hoặc ô bảng — python-docx không có API, phải ghi XML."""
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), mau)
    if hasattr(doi_tuong, "_p"):                     # paragraph
        doi_tuong._p.get_or_add_pPr().append(shd)
    else:                                            # table cell
        doi_tuong._tc.get_or_add_tcPr().append(shd)


def viet(doc, text: str, dam: bool = False, nghieng: bool = False,
         co: float = FONT_SIZE, mau: str = "000000", canh: str | None = None,
         cach_truoc: float = 0, cach_sau: float = 4, thut: float = 0,
         nhan: str | None = None):
    """Một đoạn văn. `nhan` = đoạn mở đầu in đậm (tiêu đề phụ trong đoạn)."""
    p = doc.add_paragraph()
    if cach_truoc or cach_sau or thut:
        pf = p.paragraph_format
        pf.space_before = Pt(cach_truoc)
        pf.space_after = Pt(cach_sau)
        if thut:
            pf.left_indent = Cm(thut)
    if canh == "giua":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if nhan:
        dat_font(p.add_run(nhan), dam=True, mau=mau)
    if text:
        dat_font(p.add_run(text), dam=dam, nghieng=nghieng, co=co, mau=mau)
    return p


def tieu_de(doc, so: str, text: str, cap: int = 1):
    """Tiêu đề mục — dùng style Heading thật để PDF/Word có outline điều hướng,
    nhưng SỐ MỤC gõ tay (không dùng numPr) cho chắc chắn hiện đúng."""
    p = doc.add_heading(level=cap)
    p.paragraph_format.space_before = Pt(14 if cap == 1 else 10)
    p.paragraph_format.space_after = Pt(6)
    dat_font(p.add_run(f"{so}. {text}" if so else text),
             co={1: 15, 2: 12.5, 3: 11}[cap], dam=True,
             mau="1F3864" if cap == 1 else "2E5496")
    return p


def gach_dau_dong(doc, muc: list, ky_hieu: str = "•") -> None:
    for m in muc:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.75)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.first_line_indent = Cm(-0.35)
        dat_font(p.add_run(f"{ky_hieu}  "))
        if isinstance(m, tuple):                     # (đậm, thường)
            dat_font(p.add_run(m[0]), dam=True)
            dat_font(p.add_run(m[1]))
        else:
            dat_font(p.add_run(m))


def khoi_lenh(doc, cac_dong, chu_thich: str | None = None) -> None:
    """Khối lệnh copy-paste được: mỗi dòng một đoạn văn nền xám, font mono.

    Dùng nền ở mức ĐOẠN VĂN (không phải bảng) để khối dài tự tách trang được.
    """
    if isinstance(cac_dong, str):
        cac_dong = cac_dong.strip("\n").split("\n")
    qua_dai = [d for d in cac_dong if len(d) > MAX_CODE_LEN]
    assert not qua_dai, (f"dòng lệnh dài quá {MAX_CODE_LEN} ký tự sẽ tràn lề: "
                         f"{qua_dai[0][:60]}...")
    if chu_thich:
        viet(doc, chu_thich, nghieng=True, co=9.5, cach_truoc=6, cach_sau=2)
    for i, dong in enumerate(cac_dong):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_before = Pt(4 if i == 0 else 0)
        pf.space_after = Pt(4 if i == len(cac_dong) - 1 else 0)
        pf.line_spacing = 1.0
        pf.left_indent = Cm(0.3)
        pf.right_indent = Cm(0.2)
        to_nen(p, SHADE_CODE)
        dat_font(p.add_run(dong if dong.strip() else " "), ten=FONT_CODE, co=CODE_SIZE)


def hop(doc, text: str, loai: str = "GHI CHÚ") -> None:
    """Ô ghi chú / cảnh báo nổi bật (nền vàng nhạt hoặc hồng nhạt)."""
    mau = {"GHI CHÚ": SHADE_NOTE, "CẢNH BÁO": SHADE_WARN,
           "QUAN TRỌNG": SHADE_WARN}.get(loai, SHADE_NOTE)
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before, pf.space_after = Pt(6), Pt(8)
    pf.left_indent, pf.right_indent = Cm(0.3), Cm(0.2)
    to_nen(p, mau)
    dat_font(p.add_run(f"{loai}: "), dam=True, co=10)
    dat_font(p.add_run(text), co=10)


def bang(doc, tieu_de_cot: list, cac_dong: list, rong_cm: list | None = None) -> None:
    t = doc.add_table(rows=1, cols=len(tieu_de_cot))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    rong_cm = rong_cm or [17 / len(tieu_de_cot)] * len(tieu_de_cot)

    hang = t.rows[0]
    # Lặp lại hàng tiêu đề khi bảng sang trang
    trpr = hang._tr.get_or_add_trPr()
    trpr.append(OxmlElement("w:tblHeader"))
    for i, ten in enumerate(tieu_de_cot):
        o = hang.cells[i]
        o.width = Cm(rong_cm[i])
        to_nen(o, SHADE_HEAD)
        p = o.paragraphs[0]
        p.paragraph_format.space_after = Pt(1)
        dat_font(p.add_run(ten), dam=True, co=9.5)

    for dong in cac_dong:
        hang = t.add_row()
        for i, gia_tri in enumerate(dong):
            o = hang.cells[i]
            o.width = Cm(rong_cm[i])
            p = o.paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            dat_font(p.add_run(str(gia_tri)), co=9.5)
    viet(doc, "", cach_sau=2)


# --------------------------------------------------------------------------- #
# Đọc số đo thật từ các file kết quả (thiếu file -> None, KHÔNG bịa)
# --------------------------------------------------------------------------- #
def doc_so_do() -> dict:
    out: dict = {}
    g = PROJECT_ROOT
    try:
        out["manifest"] = json.loads(
            (g / "data/processed/imdb_jsonl/_manifest.json").read_text(encoding="utf-8"))
    except Exception:
        out["manifest"] = None

    def doc_csv(p: Path) -> list | None:
        try:
            with open(p, encoding="utf-8") as f:
                return list(csv.DictReader(f))
        except Exception:
            return None

    out["cleaning"] = doc_csv(g / "outputs/tables/cleaning_log.csv")
    out["classes"] = doc_csv(g / "outputs/tables/class_distribution.csv")
    out["test_log"] = doc_csv(g / "outputs/tables/test_eval_log.csv")
    try:
        out["meta"] = json.loads(
            (g / "outputs/models/sentiment_pipeline_metadata.json").read_text(encoding="utf-8"))
    except Exception:
        out["meta"] = None
    out["co_canh_bao_ro_ri"] = (g / "outputs/tables/leakage_alert.txt").exists()
    out["giay"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    return out


def tom_tat_trang_thai(m: dict) -> list:
    """Vài dòng mô tả trạng thái dữ liệu HIỆN CÓ trên đĩa — nói đúng cái đang thấy."""
    rows = []
    man = m.get("manifest")
    if man:
        pct = man.get("subsample_pct", "(khóa cũ — chưa chạy lại)")
        rows.append(("JSONL hiện có", f"{man['n_records']:,} bản ghi / {man['n_seen']:,} "
                                      f"({man['n_records'] / man['n_seen'] * 100:.1f}%), "
                                      f"subsample_pct = {pct}"))
    else:
        rows.append(("JSONL hiện có", "chưa có — chạy Bước 2"))
    cl = m.get("cleaning")
    if cl:
        cuoi = cl[-1]
        rows.append(("Dòng sạch sau làm sạch", f"{int(cuoi['rows_out']):,}"))
    meta = m.get("meta")
    if meta:
        s = meta["sizes"]
        rows.append(("Cỡ 3 tập (model đang lưu)",
                     f"train {s['train']:,} · val {s['val']:,} · test {s['test']:,}"))
        rows.append(("Model đang lưu", f"{meta['model_name']} "
                                       f"(test macro-F1 {meta['metrics']['test']['macro_f1']:.4f})"))
    tl = m.get("test_log")
    if tl:
        rows.append(("Số lần đã chạm tập test", f"{len(tl)} lần (xem test_eval_log.csv)"))
    return rows


# --------------------------------------------------------------------------- #
# Nội dung tài liệu
# --------------------------------------------------------------------------- #
def trang_bia(doc) -> None:
    for _ in range(3):
        doc.add_paragraph()
    viet(doc, "HƯỚNG DẪN TỰ HUẤN LUYỆN LẠI MÔ HÌNH", dam=True, co=22,
         canh="giua", cach_sau=4)
    viet(doc, "Phân loại cảm xúc bình luận — dùng ~64% dữ liệu nguồn (~700 MB)", co=13,
         canh="giua", cach_sau=28)
    for nhan, gt in [
        ("Nhóm", "Nhóm 6 — Samsung Innovation Campus, Big Data"),
        ("Đề tài", "Mô hình phân loại cảm xúc dựa trên bình luận trực tuyến"),
        ("Phạm vi", "Chuẩn bị dữ liệu → huấn luyện → kiểm chứng mô hình"),
        ("Ngày", DO_THAT["ngay"]),
    ]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(3)
        dat_font(p.add_run(f"{nhan}: "), dam=True, co=11)
        dat_font(p.add_run(gt), co=11)
    doc.add_paragraph()
    viet(doc, "Tài liệu nội bộ — không phải bản nộp cho giảng viên.", nghieng=True,
         co=10, canh="giua")
    doc.add_page_break()


MUC_LUC = [
    ("1", "Mục tiêu và phạm vi"),
    ("2", "Trước khi bắt đầu: môi trường và RAM"),
    ("3", "Bước 0 — Sao lưu dữ liệu đang có (BẮT BUỘC)"),
    ("4", "Bước 1 — Chọn tỷ lệ dữ liệu trong config.yaml"),
    ("5", "Bước 2 — Chạy prepare.py"),
    ("6", "Bước 3 — Chạy train.py"),
    ("7", "Bước 4 — Làm sao biết mô hình chạy đúng"),
    ("8", "Bước 5 — Ghi lại kết quả"),
    ("9", "Những gì sẽ lệch sau khi huấn luyện lại"),
    ("10", "Xử lý sự cố"),
    ("11", "Phụ lục — bảng tra nhanh"),
]


def muc_1(doc) -> None:
    tieu_de(doc, "1", "Mục tiêu và phạm vi")
    viet(doc, "Tài liệu này hướng dẫn huấn luyện lại mô hình phân loại cảm xúc với "
              "nhiều dữ liệu hơn: từ tập con 20% (~190 MB, 201.074 bản ghi) lên ~64% "
              "(~609 MB, 646.249 bản ghi).")
    viet(doc, "Phạm vi", dam=True, cach_truoc=6, cach_sau=2)
    gach_dau_dong(doc, [
        "Chuẩn bị dữ liệu (prepare.py) và huấn luyện (train.py)",
        "Cách kiểm chứng mô hình sau khi huấn luyện CHẠY ĐÚNG",
        "Cảnh báo những tài liệu/số liệu sẽ lệch sau khi huấn luyện lại (Mục 9)",
    ])
    viet(doc, "Ngoài phạm vi (chưa làm lần này)", dam=True, cach_truoc=6, cach_sau=2)
    gach_dau_dong(doc, [
        "Chạy lại EDA (Task 9) và các biểu đồ 06–14",
        "Chạy lại luồng streaming (Task 8) với mô hình mới",
        "Cập nhật dashboard (Task 10) và báo cáo cuối",
    ])
    hop(doc, "Huấn luyện lại là một THÍ NGHIỆM MỚI, không phải \"chạy lại cái cũ với "
             "nhiều dữ liệu hơn\". Tập test sẽ là tập KHÁC (khoảng 89.000 dòng thay vì "
             "27.792), nên chỉ số mới KHÔNG so sánh trực tiếp được với macro-F1 0,6233 "
             "đã báo cáo. Phải gọi đúng tên khi viết báo cáo.", "QUAN TRỌNG")


def muc_2(doc) -> None:
    tieu_de(doc, "2", "Trước khi bắt đầu: môi trường và RAM")
    viet(doc, "Đây là rủi ro số một. Máy ảo chỉ có 7.208 MB RAM, và bộ nhớ đệm của "
              "Spark cho riêng tập train đã KHÔNG VỪA ở mức 20% — log Task 7 ghi rõ:")
    khoi_lenh(doc, [
        "26/10/14 23:51:44 INFO MemoryStore: MemoryStore started with capacity 912.3 MiB",
        "26/10/15 00:00:49 WARN MemoryStore: Not enough space to cache rdd_1604_1",
        "                          in memory! (computed 346.9 MiB so far)",
        "26/10/15 00:00:49 WARN BlockManager: Persisting block rdd_1604_0 to disk instead.",
    ], "Trích logs/task7_train_full.log — tập train chỉ có 129.701 dòng mà cache 912 MiB "
       "đã tràn ra đĩa liên tục.")
    viet(doc, "Không phải một lần lẻ: log Task 7 có ĐÚNG 70 dòng "
              "\"Not enough space to cache\", rải đều từ 00:00 đến 00:04 — tức suốt quá "
              "trình huấn luyện. Đây là số đếm được, không phải suy đoán.")
    viet(doc, f"Ở 64% lượng dữ liệu gấp ~3,2 lần, nên chắc chắn sẽ tràn nhiều hơn. "
              f"Spark vẫn chạy được (đẩy ra đĩa tại "
              f"/home/hadoop/spark-tmp, còn 212 GB), nhưng CHẬM hơn đáng kể.")

    viet(doc, "Kiểm tra trước khi chạy", dam=True, cach_truoc=8, cach_sau=2)
    khoi_lenh(doc, [
        "cd /home/hadoop/capstone",
        "source scripts/env.sh          # Java 8 + Spark 3.5.9 + Python 3.11 cho PySpark",
        "free -m                        # cần 'available' >= ~4000 MB",
        "df -h /home                    # cần >= ~10 GB trống",
    ])
    hop(doc, "PHẢI TẮT DEMO TRƯỚC. Đo lúc demo Task 10 đang chạy (15/10/2026 12:40), "
             "nó chiếm ~2,8 GB: Spark driver 1.875 MB + Streamlit 778 MB + job streaming "
             "+ producer; khi đó chỉ còn 1.300 MB trống và swap đã dùng 2.814/3.090 MB. "
             "Sau khi tắt, máy còn 5.124 MB trống. Dừng bằng:", "CẢNH BÁO")
    khoi_lenh(doc, "bash scripts/run_demo.sh --stop        # dừng sạch, giữ nguyên checkpoint")
    viet(doc, "HDFS và Kafka KHÔNG cần tắt: chúng chỉ chiếm ~370 MB và train.py không "
              "dùng đến. HDFS trên máy này không tự chạy lại sau khi khởi động lại — "
              "nếu Spark báo lỗi kết nối localhost:9000, xem Mục 10.")


def muc_3(doc) -> None:
    tieu_de(doc, "3", "Bước 0 — Sao lưu dữ liệu đang có (BẮT BUỘC)")
    viet(doc, "Có HAI lý do độc lập, mỗi lý do một mình đã đủ để bắt buộc sao lưu:")
    gach_dau_dong(doc, [
        ("Mọi lần chạy prepare.py đều GHI ĐÈ data/processed/. ",
         "Kể cả lần chạy thử. Thư mục này không nằm trong git (.gitignore dòng 6), "
         "nên không có cách nào lấy lại bằng git."),
        ("Tập 20% cũ sẽ KHÔNG tái lập được bằng code mới. ",
         "Luật cũ giữ các id có crc32 % 5 == 0 (một cấp số cộng các số dư); luật mới "
         "giữ một dải tiền tố crc32 % 1000 < 640. Hai tập cùng cỡ nhưng KHÁC NHAU. "
         "Tập cũ chỉ dựng lại được bằng code cũ (còn trong git history)."),
    ])
    khoi_lenh(doc, [
        "cd /home/hadoop/capstone",
        "mkdir -p data/processed/_backup_20pct",
        "cp -a data/processed/train.parquet data/processed/val.parquet \\",
        "      data/processed/test.parquet data/processed/eval_labels.parquet \\",
        "      data/processed/imdb_jsonl data/processed/_backup_20pct/",
        "du -sh data/processed/_backup_20pct        # phải ra ~287 MB",
        "git check-ignore data/processed/_backup_20pct   # phải in ra đường dẫn = được bỏ qua",
    ], "Đường dẫn `_backup_20pct` khớp mẫu `data/processed/*` trong .gitignore nên KHÔNG lọt vào commit.")
    hop(doc, "Các bảng ở outputs/tables/ (class_distribution.csv, cleaning_log.csv, "
             "clean_sample.csv, emoji_frequency.csv) cũng bị prepare.py ghi đè. Bốn file "
             "này CÓ trong git nên lấy lại được bằng: git checkout outputs/tables/", "GHI CHÚ")


def muc_4(doc) -> None:
    tieu_de(doc, "4", "Bước 1 — Chọn tỷ lệ dữ liệu trong config.yaml")
    viet(doc, "Mở config.yaml, mục prepare. Tham số quyết định lượng dữ liệu là "
              "subsample_pct (phần trăm, 1–100):")
    khoi_lenh(doc, [
        "prepare:",
        "  truncate_raw_detail: 20000",
        "  subsample_pct: 64        # <- đổi số này để tăng/giảm lượng dữ liệu",
        "  sample_rows_out: 1000",
        "  emoji_top_n: 30",
    ])
    viet(doc, "Cách nó hoạt động", dam=True, cach_truoc=6, cach_sau=2)
    viet(doc, "Giữ bản ghi nếu crc32(review_id) % 1000 < subsample_pct × 10. Đây là "
              "hàm keep_record() trong prepare.py. Ba tính chất quan trọng:")
    gach_dau_dong(doc, [
        ("Tất định. ", "Chạy lại ra đúng tập cũ — mọi số liệu báo cáo dựa vào điều này."),
        ("Không lệch theo thứ tự phim. ", "Chọn theo review_id chứ không theo vị trí "
         "trong file; bộ dữ liệu gốc xếp theo phim nên cắt N dòng đầu sẽ chỉ lấy được "
         "một số ít phim."),
        ("Các mức LỒNG NHAU. ", "Tập 20% nằm TRỌN trong tập 64%, tập 64% nằm trọn "
         "trong tập 100% — tăng tỷ lệ là THÊM bản ghi, không phải đổi sang tập khác."),
    ])
    bang(doc,
         ["subsample_pct", "Số bản ghi (dự kiến)", "JSONL", "Ghi chú"],
         [["20", "~201.000", "~190 MB", "tập đang có trên đĩa (luật cũ)"],
          ["64", f"~{DO_THAT['n_giu']:,}", f"~{DO_THAT['mb_jsonl']} MB", "mức đang đặt"],
          ["70", "~707.000", "~666 MB", "nếu muốn đúng 700 MB JSONL"],
          ["100", "1.010.293", "~953 MB", "toàn bộ, nặng nhất"]],
         [3.0, 4.2, 2.8, 7.0])


def muc_5(doc) -> None:
    tieu_de(doc, "5", "Bước 2 — Chạy prepare.py")
    hop(doc, "Chạy THỬ trước, chạy THẬT sau — không bao giờ ngược lại. "
             "--sample của prepare.py KHÔNG ghi ra thư mục riêng: nó ghi vào CÙNG "
             "data/processed/*.parquet (prepare.py dòng 436–447, mode \"overwrite\"). "
             "Chạy thử SAU khi đã chạy thật sẽ âm thầm thay tập train thật bằng bản "
             "20.000 dòng, và train.py sau đó sẽ học trên 20k dòng mà không báo gì.",
        "CẢNH BÁO")

    viet(doc, "Chạy thử", dam=True, cach_truoc=6, cach_sau=2)
    khoi_lenh(doc, [
        "cd /home/hadoop/capstone && source scripts/env.sh",
        "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\",
        "    --driver-memory 2g --master 'local[2]' \\",
        "    src/training/prepare.py --sample 20000",
    ], "Khoảng 1–2 phút. --sample ở đây là lát cắt THỨ HAI nằm TRONG tập đã lấy mẫu "
       "(20.000 dòng rút từ 646.249), không phải từ toàn nguồn 1.010.293.")

    viet(doc, "Chạy thật", dam=True, cach_truoc=8, cach_sau=2)
    khoi_lenh(doc, [
        "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\",
        "    --driver-memory 2g --master 'local[2]' \\",
        "    src/training/prepare.py 2>&1 | tee logs/prepare_64.log",
    ], "Lần đầu sẽ sinh lại JSONL (mất ~24 giây, đã đo) vì manifest cũ không khớp khóa "
       "subsample_pct mới. Các lần sau đọc manifest nên bỏ qua bước này.")

    viet(doc, "Đọc kết quả", dam=True, cach_truoc=8, cach_sau=2)
    viet(doc, "prepare.py chạy 16 bước và in tiến độ ra log. Con số cần đối chiếu "
              f"(đo thật với 64%, ngày {DO_THAT['ngay']}):")
    giu = DO_THAT["n_giu"]
    bang(doc,
         ["Bước", "Dòng log / file", "Giá trị đúng"],
         [["Chuyển JSONL", "Xong JSONL: N/1.010.293",
           f"~{giu:,} (64,0%), ~{DO_THAT['mb_jsonl']} MB"],
          ["Spark đọc lại", "raw.count() so với manifest",
           "hai số BẰNG NHAU (lệch = có file lạ trong thư mục JSONL)"],
          ["Bỏ nhãn/ngắn/dài", "Tổng N | rỗng … | thiếu nhãn …",
           "~5% bị loại vì thiếu nhãn (rating ngoài 1–10)"],
          ["Loại trùng", "Trùng mã / chính xác / gần trùng",
           "tỷ lệ trùng TĂNG khi dữ liệu nhiều lên — bình thường"],
          ["Chia tập", "train / val / test",
           "tỷ lệ 70/15/15, cả ba dòng đều ghi (100.0% mục tiêu)"],
          ["Rò rỉ", "phim ở >1 tập: 0",
           "BẮT BUỘC bằng 0 (có assert, khác 0 là script dừng)"]],
         [3.2, 5.3, 8.5])
    hop(doc, "Dòng \"người dùng ở >1 tập\" chỉ được GHI LOG, không chặn — ở mức 20% con "
             "số này là 11.427 và đây là rủi ro rò rỉ đã biết, chưa xử lý. Đừng bỏ qua "
             "khi viết phần hạn chế của báo cáo.")

    tt = tom_tat_trang_thai(doc_so_do())
    if tt:
        viet(doc, f"Trạng thái hiện tại trên máy ({datetime.now().strftime('%d/%m/%Y %H:%M')})",
             dam=True, cach_truoc=8, cach_sau=2)
        bang(doc, ["Mục", "Giá trị đọc được"], tt, [5.0, 12.0])
        viet(doc, "Đây là số đọc trực tiếp từ file, không phải số dự kiến. Nếu "
                  "subsample_pct vẫn là khóa cũ thì bạn chưa chạy lại Bước 2.",
             nghieng=True, co=9.5)


def muc_6(doc) -> None:
    tieu_de(doc, "6", "Bước 3 — Chạy train.py")
    viet(doc, "train.py dựng Pipeline (RegexTokenizer → StopWordsRemover → NGram → "
              "CountVectorizer → IDF → Normalizer → bộ phân loại), huấn luyện 4 mô "
              "hình + baseline đa số, chọn siêu tham số bằng TrainValidationSplit "
              "BÊN TRONG tập train, chọn mô hình trên validation, rồi đánh giá cuối "
              "cùng MỘT LẦN trên test.")
    khoi_lenh(doc, [
        "# chạy thử trước (tự bật --no-test, không đụng test, không lưu model)",
        "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\",
        "    --driver-memory 2g --master 'local[2]' \\",
        "    src/training/train.py --sample 20000",
        "",
        "# chạy thật — KHUYẾN NGHỊ nâng lên 4g (xem bên dưới)",
        "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\",
        "    --driver-memory 4g --master 'local[2]' \\",
        "    src/training/train.py --models nb,lr,svc,rf 2>&1 | tee logs/train_64.log",
    ])
    hop(doc, "Chạy thử KHÔNG THỂ làm hỏng gì: --sample tự bật --no-test, và --no-test "
             "cũng bỏ luôn bước lưu model (train.py dòng 838–840). Vậy nó không đụng "
             "tập test và không ghi đè outputs/models/sentiment_pipeline.", "GHI CHÚ")

    viet(doc, "Vì sao khuyến nghị --driver-memory 4g", dam=True, cach_truoc=8, cach_sau=2)
    gach_dau_dong(doc, [
        "train.py giữ 5 bảng validation kéo về driver (toPandas, kèm NGUYÊN văn bản) "
        "cho 4 mô hình + baseline và không giải phóng — ở 64% ước tính ~400 MB.",
        "Tập train được cache() trong bộ nhớ, cộng vector TF-IDF thưa.",
        "train.py đặt spark.sql.shuffle.partitions = 8 (dòng 679) — rất ít cho ~450.000 "
        "dòng. Đây là nguyên nhân chính gây chậm/tràn bộ nhớ.",
    ])
    viet(doc, "Tiền lệ: src/eda/README.md đã dùng --driver-memory 4g trên chính máy này. "
              "Nếu vẫn bị OOM, xem phương án lùi ở Mục 10.")

    viet(doc, "Thời gian dự kiến", dam=True, cach_truoc=8, cach_sau=2)
    viet(doc, "Bản 20% mất 13 phút 25 giây (đo từ log Task 7: 23:51:42 → 00:05:07), "
              "chia ra NB 108 s · LR 245 s · SVC 116 s · RF 282 s. "
              "Dữ liệu 64% gấp ~3,2 lần, nên ước tính 45–60 phút, có thể lâu hơn nếu "
              "tràn bộ nhớ nhiều. Đây là NGOẠI SUY, chưa chạy thật ở 64% — hãy bấm "
              "giờ và ghi lại số thật.")


def muc_7(doc) -> None:
    tieu_de(doc, "7", "Bước 4 — Làm sao biết mô hình chạy đúng")
    viet(doc, "Kiểm theo đúng thứ tự này. Mỗi dòng có cách kiểm riêng, không cần "
              "đọc code.")
    bang(doc,
         ["Việc kiểm", "Cách kiểm", "Kết quả ĐÚNG"],
         [["Dữ liệu đúng cỡ",
           "cat data/processed/imdb_jsonl/_manifest.json",
           "subsample_pct = 64, n_records trong khoảng 644.000–649.000"],
          ["Spark đọc đủ dòng",
           "log dòng \"Nạp … bản ghi\"",
           "khớp n_records trong manifest"],
          ["Tập test chưa bị chạm",
           "wc -l outputs/tables/test_eval_log.csv",
           "nhiều hơn TRƯỚC đúng 1 dòng"],
          ["Metadata hợp lệ",
           "cat outputs/models/sentiment_pipeline_metadata.json",
           "label_index = {negative: 0, neutral: 1, positive: 2}; sizes.* khớp dữ liệu vừa tạo; 7 pipeline_stages"],
          ["Không rò rỉ",
           "cat outputs/tables/leak_check.json",
           "cả ba số đều bằng 0"],
          ["Không có cảnh báo rò rỉ",
           "ls outputs/tables/leakage_alert.txt",
           "KHÔNG tồn tại file này"],
          ["Chỉ số từng lớp",
           "cat outputs/tables/per_class_metrics.csv",
           "đọc F1 TỪNG LỚP, không chỉ accuracy"],
          ["Model nạp lại được",
           "spark-submit scripts/check_model.py",
           "in ra nhãn + xác suất cho 5 câu thử"],
          ["Chạy thật trong app",
           "mở dashboard, tab \"Try It\"",
           "gõ một câu, ra nhãn + xác suất"]],
         [3.4, 6.2, 7.4])

    viet(doc, "Về test_eval_log.csv — cơ chế \"test dùng một lần\"", dam=True,
         cach_truoc=8, cach_sau=2)
    hop(doc, "File outputs/tables/test_eval_log.csv là NHẬT KÝ GHI THÊM, KHÔNG CHẶN. "
             "train.py chỉ ghi thêm một dòng mỗi lần đánh giá test (dòng 767–777) — nó "
             "không từ chối, không cảnh báo, không hỏi. Nghĩa là kỷ luật \"tập test chỉ "
             "dùng một lần\" do NGƯỜI CHẠY giữ, code không giữ hộ. Nếu bạn chạy "
             "train.py bản đầy đủ nhiều lần, file sẽ có nhiều dòng và tập test đã bị "
             "xem nhiều lần — khi đó báo cáo phải nói rõ.")
    viet(doc, "Chốt danh sách mô hình TRƯỚC khi chạy: cờ --models không cộng dồn, mỗi "
              "lần chạy ghi đè model_results.csv, các hình, và cả "
              "outputs/models/sentiment_pipeline.")

    viet(doc, "Nếu macro-F1 cao bất thường", dam=True, cach_truoc=8, cach_sau=2)
    viet(doc, "train.py có chốt an toàn: macro-F1 trên test vượt 0,95 thì nó coi là rò "
              "rỉ dữ liệu, ghi outputs/tables/leakage_alert.txt và KHÔNG lưu model "
              "(config: training.leakage_threshold_macro_f1). Thấy file cảnh báo này "
              "thì đừng báo cáo chỉ số — phải đi kiểm dữ liệu trùng trước "
              "(CLAUDE.md §6).")


def muc_8(doc) -> None:
    tieu_de(doc, "8", "Bước 5 — Ghi lại kết quả")
    gach_dau_dong(doc, [
        ("PROGRESS.md: ", "một dòng theo đúng định dạng bảng của file."),
        ("outputs/modeling_summary.md: ", "toàn bộ số liệu Task 7 trong file này đã cũ, "
         "phải viết lại từ outputs/tables/model_results.csv và "
         "sentiment_pipeline_metadata.json."),
        ("outputs/models/README.md: ", "đang ghi đích danh \"Logistic Regression\" — nếu "
         "lần này mô hình thắng là mô hình khác thì phải sửa."),
        ("docs/data_dictionary.md: ", "mục tập con JSONL (số bản ghi, dung lượng, cách chọn)."),
        ("data/processed/README.md và src/training/README.md: ", "số liệu tập con."),
        ("Git: ", "commit kèm thông điệp rõ ràng."),
    ])


def muc_9(doc) -> None:
    tieu_de(doc, "9", "Những gì sẽ lệch sau khi huấn luyện lại")
    viet(doc, "Danh sách này để không ai vô tình báo cáo số cũ. Mỗi dòng là một file "
              "hoặc một chỗ cụ thể.")
    bang(doc,
         ["Chỗ bị lệch", "Lệch thế nào"],
         [["outputs/insights.md + hình 06–14 (outputs/figures/)",
           "EDA đọc train/val/test — cỡ tập và phân bố lớp đều đổi. Phải chạy lại "
           "src/eda/queries.py rồi plots.py."],
          ["outputs/streaming_summary.md",
           "Số liệu luồng Task 8 sinh từ mô hình cũ trên tập test cũ."],
          ["tests/test_dashboard.py",
           "Khoá cứng số liệu của lần chạy \"verify1\" (1 cửa sổ vượt ngưỡng, "
           "share_negative 0,3846, 13 bình luận). Model mới thì test này đổ."],
          ["config.yaml — mục eda.alert",
           "negative_share_threshold 0,30 được suy từ tỷ lệ lớp negative của tập test "
           "cũ (0,2506 + biên 5 điểm %). Đổi tập test thì nên tính lại."],
          ["src/app/app.py — tab About",
           "Hard-code 86% / 0,38 / 99% / +3,27 / 66% (kết quả đo của model cũ)."],
          ["src/eda/plots.py",
           "Vài con số vẽ thẳng lên hình (0,02 / 0,378 / 0,63 / 0,44)."],
          ["scripts/make_pipeline_diagram.py",
           "In \"1.010.296 reviews\" trên sơ đồ — con số này ĐÃ SAI SẴN 3 đơn vị so "
           "với thực tế 1.010.293."],
          ["Bản nộp trong deliverables/",
           "Action Plan, WBS, Proposal Slides KHÔNG chứa số liệu Task 7/8 nên KHÔNG lệch."]],
         [6.0, 11.0])

    hop(doc, "Chạy lại luồng streaming CÙNG TÊN sẽ TRỘN kết quả của mô hình cũ với mô "
             "hình mới trong cùng một thư mục. Muốn chạy sạch thì xóa cả hai trước: "
             "checkpoints/streaming/<tên> và outputs/stream/<tên>.", "CẢNH BÁO")

    viet(doc, "Và điều quan trọng nhất", dam=True, cach_truoc=8, cach_sau=2)
    hop(doc, "Tập test mới là tập KHÁC. Đừng viết \"macro-F1 tăng từ 0,62 lên X\" như "
             "thể đo trên cùng một thước. Câu đúng là: \"trên thí nghiệm mới với 64% dữ "
             "liệu và tập test ~89.000 dòng, macro-F1 là X\".", "QUAN TRỌNG")


def muc_10(doc) -> None:
    tieu_de(doc, "10", "Xử lý sự cố")
    bang(doc,
         ["Hiện tượng", "Nguyên nhân", "Cách chữa"],
         [["Job bị kill, log có OutOfMemoryError hoặc máy đứng",
           "Hết RAM — cache không vừa",
           "Tắt demo; tăng --driver-memory lên 4g; nếu vẫn lỗi thì bỏ RandomForest: "
           "--models nb,lr,svc (RF chậm nhất — 282 s — và yếu nhất — macro-F1 trên "
           "validation 0,5343 so với 0,62-0,63 của ba mô hình kia); cuối cùng là "
           "giảm subsample_pct."],
          ["Chạy rất chậm, đĩa kêu liên tục",
           "Spark đẩy block ra đĩa (spill)",
           "Bình thường ở mức dữ liệu này. Kiểm df -h /home. Đừng đặt "
           "SPARK_LOCAL_DIRS vào /tmp — /tmp là tmpfs chỉ 3,6 GB. "
           "scripts/env.sh đã trỏ sẵn sang /home/hadoop/spark-tmp."],
          ["Connection refused tới localhost:9000",
           "HDFS tắt (máy này HDFS không tự chạy lại sau reboot)",
           "/usr/local/hadoop/sbin/start-dfs.sh — hoặc chạy spark-submit kèm "
           "--conf spark.eventLog.enabled=false. HDFS chỉ dùng cho event log, "
           "sink và checkpoint đều ở đĩa cục bộ."],
          ["SafeModeException khi tạo /spark-logs",
           "NameNode vừa khởi động còn ở safe mode vài giây",
           "Chờ ~30 giây rồi chạy lại. Kiểm bằng: hdfs dfsadmin -safemode get"],
          ["ModelNotFound / lỗi đường dẫn khi nạp model",
           "Thiếu tiền tố file:// — máy này HDFS là default FS",
           "Luôn dùng PipelineModel.load(\"file://\" + đường_dẫn_tuyệt_đối)"],
          ["AssertionError: có phim nằm ở nhiều tập",
           "assert movie_leak == 0 nổ",
           "Đọc dòng log ngay TRƯỚC đó để biết bước nào lệch. Thường là do chạy "
           "prepare.py hai lần đan xen hoặc seed bị đổi."],
          ["pytest đổ ở test_dashboard.py",
           "Test khoá số liệu của lần chạy verify1 (Task 8)",
           "Đúng như dự kiến sau khi đổi model — xem Mục 9. Phải chạy lại luồng "
           "streaming và cập nhật số trong test."]],
         [4.0, 5.0, 8.0])


def muc_11(doc) -> None:
    tieu_de(doc, "11", "Phụ lục — bảng tra nhanh")
    viet(doc, "Toàn bộ quy trình, từ đầu đến khi có mô hình mới", dam=True, cach_sau=2)
    khoi_lenh(doc, [
        "cd /home/hadoop/capstone && source scripts/env.sh",
        "",
        "# 0. Tắt demo + sao lưu",
        "bash scripts/run_demo.sh --stop",
        "mkdir -p data/processed/_backup_20pct",
        "cp -a data/processed/*.parquet data/processed/imdb_jsonl \\",
        "      data/processed/_backup_20pct/",
        "",
        "# 1. Kiểm tỷ lệ trong config.yaml (prepare.subsample_pct: 64)",
        "",
        "# 2. prepare.py — thử rồi thật",
        "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\",
        "    --driver-memory 2g --master 'local[2]' src/training/prepare.py --sample 20000",
        "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\",
        "    --driver-memory 2g --master 'local[2]' src/training/prepare.py",
        "",
        "# 3. train.py — thử rồi thật (chạy thật ~45-60 phút)",
        "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\",
        "    --driver-memory 2g --master 'local[2]' src/training/train.py --sample 20000",
        "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\",
        "    --driver-memory 4g --master 'local[2]' src/training/train.py",
        "",
        "# 4. Kiểm chứng",
        "PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\",
        "    --driver-memory 2g --master 'local[2]' scripts/check_model.py",
        ".venv/bin/python -m pytest tests/ -q",
    ])
    bang(doc,
         ["Script", "Sinh ra", "Thời gian"],
         [["prepare.py", "data/processed/ — 4 file parquet",
           "~1–2 phút (đo: 74 s)"],
          ["prepare.py", "outputs/tables/ — 4 bảng thống kê (Task 6)", "cùng lần chạy"],
          ["train.py", "outputs/models/sentiment_pipeline/",
           "45–60 phút (ước tính)"],
          ["train.py", "outputs/tables/ — 5 bảng kết quả (Task 7)", "cùng lần chạy"],
          ["train.py", "outputs/figures/01..05*.png", "cùng lần chạy"],
          ["train.py", "outputs/models/sentiment_pipeline_metadata.json", "cùng lần chạy"]],
         [2.8, 8.2, 6.0])

    viet(doc, "Kiểm bố cục tài liệu này (quy ước CLAUDE.md §11)", dam=True,
         cach_truoc=8, cach_sau=2)
    khoi_lenh(doc, [
        "soffice --headless --convert-to pdf --outdir /tmp/pdfcheck \\",
        "    docs/huong_dan_huan_luyen.docx",
        "pdfinfo /tmp/pdfcheck/huong_dan_huan_luyen.pdf | grep Pages",
        "pdffonts /tmp/pdfcheck/huong_dan_huan_luyen.pdf   # phải thấy Carlito",
    ])


def main() -> int:
    doc = docx.Document()

    # Trang A4, lề 2 cm (mặc định của python-docx là Letter — đổi lại cho đúng khổ A4)
    for s in doc.sections:
        s.page_width, s.page_height = Cm(21.0), Cm(29.7)
        s.left_margin = s.right_margin = Cm(2.0)
        s.top_margin = s.bottom_margin = Cm(1.8)

    st = doc.styles["Normal"]
    st.font.name = FONT_BODY
    st.font.size = Pt(FONT_SIZE)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT_BODY)

    trang_bia(doc)

    tieu_de(doc, "", "Mục lục", cap=1)
    for so, ten in MUC_LUC:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.left_indent = Cm(0.6)
        dat_font(p.add_run(f"{so:>2}."), dam=True, co=11)
        dat_font(p.add_run("   " + ten), co=11)
    viet(doc, "Tài liệu này gồm 11 mục; mục 3–7 là các bước thực hiện, mục 7 là phần "
              "kiểm chứng mô hình.", nghieng=True, co=9.5, cach_truoc=8)
    doc.add_page_break()

    for ham in (muc_1, muc_2, muc_3, muc_4, muc_5, muc_6, muc_7, muc_8, muc_9,
                muc_10, muc_11):
        ham(doc)

    OUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT_DOCX)
    print(f"Đã ghi: {OUT_DOCX.relative_to(PROJECT_ROOT)}")
    print("\nKiểm bố cục (CLAUDE.md §11):")
    print("  soffice --headless --convert-to pdf --outdir /tmp/pdfcheck "
          f"{OUT_DOCX.relative_to(PROJECT_ROOT)}")
    print("  pdfinfo /tmp/pdfcheck/huong_dan_huan_luyen.pdf | grep Pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
