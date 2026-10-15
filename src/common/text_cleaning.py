"""text_cleaning.py — Làm sạch văn bản bằng HÀM SPARK SQL, dùng chung cho
huấn luyện (`src/training`) và streaming (`src/streaming`).

Vì sao chỉ dùng hàm Spark SQL (lower, regexp_replace, trim, ...):
- Không phải Python UDF ⇒ không chặn tối ưu hóa của Catalyst/WSCG, chạy được
  trong executor JVM (CLAUDE.md §4).
- Cùng một đoạn code cho cả hai phía ⇒ văn bản lúc train và lúc chạy thật
  được xử lý GIỐNG HỆT NHAU (không lệch phân phối).

Thứ tự xử lý (quan trọng — đổi thứ tự là đổi kết quả):
    1. chữ thường (lower)
    2. bỏ thẻ/entity HTML  (làm TRƯỚC khi chèn token <url>/<user> để regex
       bắt thẻ HTML không ăn mất chính token của mình)
    3. URL        -> <url>
    4. @mention   -> <user>
    5. chuẩn hóa dấu câu unicode (’ ‘ “ ” – — → ' " -), bỏ ký tự vô hình
    6. từ điển viết tắt/teencode (config.yaml: cleaning.abbreviations)
    7. rút gọn ký tự lặp: "haaaay" -> "haay"
    8. emoji tách thành token riêng (đếm được tần suất)
    9. gộp khoảng trắng, trim

Ghi chú cho bước tách từ (tokenization) ở Task 7: vì emoji đã được tách bằng
dấu cách và <url>/<user> là token có sẵn, RegexTokenizer chỉ cần pattern "\\s+".

KHÔNG dùng tiếng Việt cho bộ dữ liệu hiện tại (IMDb là tiếng Anh), nên KHÔNG
cần underthesea/pyvi. Nếu sau này đổi sang dữ liệu tiếng Việt: thêm bước tách từ
bằng pandas_udf — chi phí thực đo trên máy này: pandas_udf chạy Arrow theo lô,
chậm hơn hàm SQL khoảng 5–20 lần trên mỗi triệu dòng (thử lại và ghi số đo thật
trước khi dùng; xem docs/data_dictionary.md §5).
"""

from __future__ import annotations

import re

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

# --- Regex (viết theo cú pháp Java của Spark) ------------------------------
URL_RE = r"https?://\S+|www\.\S+"
MENTION_RE = r"@[\w.\-]{1,64}"
# Thẻ HTML thật (mở/đóng) — yêu cầu ký tự đầu sau '<' là chữ cái hoặc '/'.
# Negative lookahead để KHÔNG ăn mất token của chính mình (<url>, <user>), nhờ đó
# hàm làm sạch là idempotent (chạy hai lần vẫn ra cùng kết quả — xem test).
HTML_TAG_RE = r"</?(?!url>|user>)[a-zA-Z][^>]{0,200}>"
HTML_ENTITY_RE = r"&(?:amp|lt|gt|quot|apos|nbsp|hellip|mdash|ndash|#\d{1,5}|#x[0-9a-fA-F]{1,5});"
REPEAT_RE = r"(.)\1{2,}"                       # 3 ký tự giống nhau trở lên
INVISIBLE_RE = "[\\x{200B}\\x{200C}\\x{FEFF}\\x{00AD}]"   # zero-width, soft hyphen
# Các dải emoji TƯỜNG MINH (mặt cười, cờ, ký hiệu, ngôi sao...). Tách riêng
# khỏi EMOJI_CLASS vì cần dùng khi lọc CHẶT: lớp \p{So} ở dưới bao gồm cả ký tự
# typography không phải emoji — "°" (U+00B0, 59 lần trong top-30 emoji toàn bộ
# dữ liệu), "©" (U+00A9), "™" (U+2122). Thống kê emoji cho báo cáo phải dùng
# dải tường minh này, nếu không bảng "emoji" sẽ lẫn ký tự vô nghĩa.
EMOJI_SYMBOL_RANGES = ("\\x{1F000}-\\x{1FAFF}\\x{1F1E6}-\\x{1F1FF}"
                       "\\x{2600}-\\x{27BF}\\x{2B00}-\\x{2BFF}")

# Lớp dùng để TÁCH emoji thành token khi làm sạch: rộng hơn (thêm \p{So}) và
# thêm các ký tự NỐI (variation selector, ZWJ, keycap) để không cắt vụn emoji.
# KHÔNG lấy lớp \p{Sk} (modifier symbol): nó gồm cả dấu mũ/trăng treo như "¨"
# (U+00A8) — đo trên dữ liệu thật thấy "¨" đứng đầu bảng tần suất với 394 lần,
# rõ ràng là rác mã hóa chứ không phải emoji, nên loại khỏi lớp này.
EMOJI_CLASS = "[\\p{So}" + EMOJI_SYMBOL_RANGES + "\\x{FE0F}\\x{200D}\\x{20E3}]"

_PUNCT_MAP = {"’": "'", "‘": "'", "ʼ": "'", "´": "'",
              "“": '"', "”": '"', "„": '"',
              "–": "-", "—": "-", "−": "-"}


def clean_text(col: Column, abbreviations: dict[str, str] | None = None) -> Column:
    """Làm sạch một CỘT văn bản Spark, trả về cột mới đã sạch.

    `abbreviations`: từ điển viết tắt (đọc từ config.yaml, mục
    `cleaning.abbreviations`). Truyền `None` nếu không muốn thay viết tắt.
    Đầu vào NULL -> trả về chuỗi rỗng "" (để bộ lọc `text != ''` bắt được).
    """
    if abbreviations is None:
        abbreviations = {}
    c = F.lower(F.trim(col))
    c = strip_html(c)
    c = replace_urls(c)
    c = replace_mentions(c)
    c = normalize_punctuation(c)
    if abbreviations:
        c = apply_abbreviations(c, abbreviations)
    c = collapse_repeats(c)
    c = space_emoji(c)
    c = normalize_whitespace(c)
    return F.coalesce(c, F.lit(""))


def strip_html(col: Column) -> Column:
    """Bỏ thẻ HTML và entity (&amp; &quot; &#39; ...) — IMDb có lẫn các chuỗi này."""
    c = F.regexp_replace(col, HTML_TAG_RE, " ")
    return F.regexp_replace(c, HTML_ENTITY_RE, " ")


def replace_urls(col: Column) -> Column:
    """Mọi URL (http/https/www) -> token <url>."""
    return F.regexp_replace(col, URL_RE, " <url> ")


def replace_mentions(col: Column) -> Column:
    """@tên_người_dùng -> token <user> (không giữ danh tính — CLAUDE.md §7)."""
    return F.regexp_replace(col, MENTION_RE, " <user> ")


def normalize_punctuation(col: Column) -> Column:
    """Đưa dấu câu unicode về dạng ASCII, bỏ ký tự vô hình."""
    c = F.regexp_replace(col, INVISIBLE_RE, "")
    for src, dst in _PUNCT_MAP.items():
        c = F.regexp_replace(c, re.escape(src), dst)
    return c


def apply_abbreviations(col: Column, mapping: dict[str, str]) -> Column:
    """Thay viết tắt/teencode theo RANH GIỚI TỪ (\\b...\\b), không thay giữa từ.

    Từ điển đọc từ config.yaml nên sửa được mà không cần đổi code.
    Khóa dài được thay trước (tránh "ur" ăn mất phần đầu của "urs").
    """
    c = col
    for key in sorted(mapping, key=len, reverse=True):
        value = str(mapping[key])
        c = F.regexp_replace(c, r"\b" + re.escape(key) + r"\b", value.replace("\\", "\\\\"))
    return c


def collapse_repeats(col: Column) -> Column:
    """Rút gọn ký tự lặp từ 3 lần trở lên thành 2: "haaaay" -> "haay", "sooo" -> "soo"."""
    return F.regexp_replace(col, REPEAT_RE, "$1$1")


def space_emoji(col: Column) -> Column:
    """Tách emoji thành token riêng: "hay quá😍😍" -> "hay quá 😍 😍".

    Hạn chế đã biết: emoji ghép bằng ZWJ (👨👩👧) bị tách thành từng mảnh —
    chấp nhận được vì mục tiêu là ĐẾM và giữ tín hiệu cảm xúc, không phải hiển thị.
    """
    return F.regexp_replace(col, f"({EMOJI_CLASS})", " $1 ")


def normalize_whitespace(col: Column) -> Column:
    """Gộp mọi khoảng trắng liên tiếp thành một và trim hai đầu."""
    return F.trim(F.regexp_replace(col, r"\s+", " "))


def token_count(col: Column) -> Column:
    """Số token (tách theo khoảng trắng — khớp cách RegexTokenizer sẽ dùng ở Task 7)."""
    return F.size(F.split(F.trim(col), r"\s+"))


def dedup_key(col: Column) -> Column:
    """Khóa chống trùng: chữ thường, bỏ dấu câu, gộp khoảng trắng, sắp xếp từ.

    Dùng cho cả trùng chính xác lẫn gần trùng (hai câu cùng bộ từ chỉ khác thứ
    tự hoặc dấu câu sẽ ra cùng khóa) — xem `src/training/prepare.py`.
    """
    c = F.lower(col)
    c = F.regexp_replace(c, r"[^\p{L}\p{N}\s<>]", " ")     # giữ chữ, số, <url>, <user>
    c = F.regexp_replace(c, r"\s+", " ")
    c = F.trim(c)
    words = F.array_sort(F.array_distinct(F.split(c, r"\s+")))
    return F.md5(F.concat_ws(" ", words))


def emoji_frequency(df: DataFrame, text_col: str = "text", top_n: int = 30) -> DataFrame:
    """Bảng tần suất emoji: explode token và đếm những token là emoji."""
    toks = df.select(F.explode(F.split(F.col(text_col), r"\s+")).alias("emoji"))
    return (toks.where(F.col("emoji").rlike(EMOJI_CLASS))
                .groupBy("emoji")
                .agg(F.count("*").alias("count"))
                .orderBy(F.desc("count"), F.asc("emoji"))
                .limit(top_n))
