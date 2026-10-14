"""Test nhỏ cho src/common/text_cleaning.py (Task 6).

Chạy:
    source scripts/env.sh
    .venv/bin/python -m pytest tests/ -q

Test chạy trên SparkSession THẬT (local[2]) với DataFrame nhỏ — đúng như cách
hàm được dùng trong pipeline, không test bằng chuỗi Python thuần.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pyspark.sql import SparkSession  # noqa: E402

from src.common.text_cleaning import (  # noqa: E402
    apply_abbreviations,
    clean_text,
    collapse_repeats,
    dedup_key,
    emoji_frequency,
    replace_mentions,
    replace_urls,
    token_count,
)

ABBREV = {"u": "you", "ur": "your", "urs": "yours", "pls": "please", "thx": "thanks"}


@pytest.fixture(scope="module")
def spark():
    s = (SparkSession.builder
         .master("local[2]")
         .appName("test-text-cleaning")
         .config("spark.sql.shuffle.partitions", "2")
         .config("spark.ui.enabled", "false")
         .getOrCreate())
    s.sparkContext.setLogLevel("ERROR")
    yield s
    s.stop()


def one(spark, col_expr, value):
    """Áp một biểu thức cột lên một giá trị duy nhất và trả về kết quả."""
    df = spark.createDataFrame([(value,)], "value string")
    return df.select(col_expr.alias("out")).first()["out"]


# ---------------------------------------------------------------- cơ bản ---
def test_lower_trim_whitespace(spark):
    out = one(spark, clean_text("value"), "  Hello   WORLD  ")
    assert out == "hello world"


def test_null_thanh_chuoi_rong(spark):
    out = one(spark, clean_text("value"), None)
    assert out == ""


def test_rong_van_rong(spark):
    assert one(spark, clean_text("value"), "   ") == ""


# ------------------------------------------------------------------- URL ---
def test_thay_url(spark):
    out = one(spark, replace_urls("value"),
              "xem https://example.com/a?b=1 và www.foo.vn nhe")
    assert out.count("<url>") == 2
    assert "http" not in out and "www." not in out


def test_thay_mention(spark):
    out = one(spark, replace_mentions("value"), "cảm ơn @john_doe và @maria.94 nhé")
    assert out.count("<user>") == 2
    assert "john_doe" not in out and "maria" not in out


def test_bo_the_va_entity_html(spark):
    out = one(spark, clean_text("value"), "phim <br> hay &amp; y nghia &quot;qua&quot;")
    assert "<br>" not in out and "&amp;" not in out and "&quot;" not in out
    assert "hay" in out


# ------------------------------------------------------- rút gọn ký tự lặp ---
def test_rut_gon_ky_tu_lap(spark):
    assert one(spark, collapse_repeats("value"), "haaaay") == "haay"


def test_lap_3_lan_thanh_2(spark):
    assert one(spark, collapse_repeats("value"), "sooooo") == "soo"


def test_lap_2_lan_giu_nguyen(spark):
    assert one(spark, collapse_repeats("value"), "too good") == "too good"


# ------------------------------------------------------------- viết tắt ---
def test_tu_dien_viet_tat(spark):
    out = one(spark, apply_abbreviations("value", ABBREV), "pls help u")
    assert out == "please help you"


def test_tu_dien_theo_ranh_gioi_tu(spark):
    # "urb" / "plsx" không được thay vì không phải từ riêng
    out = one(spark, apply_abbreviations("value", ABBREV), "urb plsx u")
    assert out == "urb plsx you"


def test_khoa_dai_thay_truoc(spark):
    # "urs" phải thành "yours", không thành "yours s" (do "ur" ăn trước)
    assert one(spark, apply_abbreviations("value", ABBREV), "urs is mine") == "yours is mine"


# ------------------------------------------------------------------ emoji ---
def test_emoji_tach_thanh_token_rieng(spark):
    out = one(spark, clean_text("value"), "love it😍🔥")
    assert out == "love it 😍 🔥"


def test_emoji_khong_dinh_vao_tu(spark):
    out = one(spark, clean_text("value"), "hay👍quá")
    assert out == "hay 👍 quá"


def test_emoji_frequency(spark):
    # Dùng đúng như trong pipeline: đếm emoji trên văn bản ĐÃ làm sạch
    raw = spark.createDataFrame([("😍 great 😍",), ("😍 ok 🔥",), ("🔥🔥 hot",)], "text string")
    df = raw.withColumn("text", clean_text("text"))
    rows = {(r["emoji"], r["count"]) for r in emoji_frequency(df, top_n=10).collect()}
    # "🔥🔥" được tách thành hai token "🔥" nên tổng là 1 + 2 = 3
    assert ("😍", 3) in rows and ("🔥", 3) in rows


# ---------------------------------------------------------- làm sạch toàn bộ ---
def test_lam_sach_tong_hop(spark):
    raw = "  OMG!!! This is SOOOOO Good 😍😍  check https://a.bc  thx @fan1 "
    out = one(spark, clean_text("value", ABBREV), raw)
    # "!!!" (3 ký tự lặp) -> "!!", "sooooo" -> "soo", emoji tách bằng dấu cách,
    # URL/@mention thành token, "thx" -> "thanks", khoảng trắng gộp + trim
    assert out == "omg!! this is soo good 😍 😍 check <url> thanks <user>"


def test_idempotent(spark):
    """Làm sạch hai lần phải cho cùng kết quả — nếu không, train/serve sẽ lệch."""
    raw = "  WOW 😍  haaaay https://x.y @abc thx  "
    once = one(spark, clean_text("value", ABBREV), raw)
    twice = one(spark, clean_text("value", ABBREV), once)
    assert once == twice


# ------------------------------------------------------------------ khác ---
def test_token_count(spark):
    assert one(spark, token_count("value"), "a b  c") == 3
    assert one(spark, token_count("value"), "") == 0 or one(spark, token_count("value"), "") == 1


def test_dedup_key_gop_dau_cau_va_thu_tu(spark):
    k1 = one(spark, dedup_key("value"), "Hello, world! This is GREAT")
    k2 = one(spark, dedup_key("value"), "great this is world hello")
    assert k1 == k2


def test_dedup_key_khac_noi_dung_thi_khac(spark):
    k1 = one(spark, dedup_key("value"), "the movie is great")
    k2 = one(spark, dedup_key("value"), "the movie is awful")
    assert k1 != k2
