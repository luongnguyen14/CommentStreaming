"""Test nhỏ cho các hàm dùng chung (Task 6).

Chạy:
    source scripts/env.sh
    .venv/bin/python -m pytest tests/ -q

Trọng tâm: **băm có muối phải cho CÙNG kết quả ở hai phía** — Spark (lúc tạo
train/val/test) và Python (lúc replay/streaming). Lệch nhau ở đây thì
`user_hash` giữa dữ liệu huấn luyện và dữ liệu chạy thật sẽ không ghép được,
mà lỗi loại này rất khó phát hiện bằng mắt.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pyspark.sql import SparkSession  # noqa: E402

from src.common.utils import iter_json_array, load_config, salted_hash  # noqa: E402
from src.training.prepare import SALT_LEN, label_expr, user_hash_expr  # noqa: E402

SALT = "0123456789abcdef0123456789abcdef"        # muối giả cho test (không phải muối thật)


@pytest.fixture(scope="module")
def spark():
    s = (SparkSession.builder
         .master("local[2]")
         .appName("test-utils")
         .config("spark.sql.shuffle.partitions", "2")
         .config("spark.ui.enabled", "false")
         .getOrCreate())
    s.sparkContext.setLogLevel("ERROR")
    yield s
    s.stop()


def spark_hash(spark, salt: str, ids: list[str | None]) -> list[str | None]:
    """Băm từng id bằng biểu thức của Spark (giống hệt lúc chuẩn bị dữ liệu)."""
    rows = [(i,) for i in ids]
    df = spark.createDataFrame(rows, "reviewer string")
    out = df.select(user_hash_expr(salt).alias("h")).collect()
    return [r["h"] for r in out]


# --------------------------------------------------- băm có muối (quan trọng) ---
def test_bam_spark_khop_python(spark):
    ids = ["u1", "john_doe", "Nguyễn Văn A", "người_dùng_😀", "a" * 200, ""]
    got = spark_hash(spark, SALT, ids)
    want = [salted_hash(i, salt=SALT.encode("utf-8"), length=SALT_LEN) for i in ids]
    assert got == want, "băm của Spark khác băm của Python -> train/serve lệch nhau"


def test_bam_nguoi_dung_thieu_ma(spark):
    """reviewer NULL -> băm của chuỗi rỗng (khớp salted_hash("")), không phải NULL."""
    got = spark_hash(spark, SALT, [None])
    assert got == [salted_hash("", salt=SALT.encode("utf-8"), length=SALT_LEN)]


def test_do_dai_bam(spark):
    got = spark_hash(spark, SALT, ["u1"])
    assert len(got[0]) == SALT_LEN == 16
    assert all(c in "0123456789abcdef" for c in got[0])


def test_muoi_khac_thi_bam_khac(spark):
    """Cùng người dùng nhưng muối khác -> hash khác (đúng tính chất của muối)."""
    h1 = spark_hash(spark, SALT, ["u1"])[0]
    h2 = spark_hash(spark, "ffffffffffffffffffffffffffffffff", ["u1"])[0]
    assert h1 != h2


def test_cung_nguoi_dung_thi_cung_bam(spark):
    assert len(set(spark_hash(spark, SALT, ["u1", "u1", "u2"]))) == 2


# --------------------------------------------------------------- ánh xạ nhãn ---
def test_anh_xa_nhan_phu_1_den_10(spark):
    """Mọi rating 1–10 phải có nhãn; ngoài khoảng hoặc thiếu thì NULL (bị loại sau)."""
    df = spark.createDataFrame([(str(r),) for r in range(1, 13)] + [(None,)], "rating string")
    rows = {r["rating"]: r["label"]
            for r in df.select("rating", label_expr(load_config()).alias("label")).collect()}
    assert rows["1"] == rows["4"] == "negative"
    assert rows["5"] == rows["6"] == "neutral"
    assert rows["7"] == rows["10"] == "positive"
    assert rows["11"] is None and rows["12"] is None and rows[None] is None


# ------------------------------------------------------------------ tiện ích ---
def test_iter_json_array_doc_tung_ban_ghi(tmp_path):
    """Đọc mảng JSON lớn theo từng object, không nạp cả file (dữ liệu gốc 1,1 GB)."""
    p = tmp_path / "nho.json"
    recs = [{"review_id": f"r{i}", "text": "x" * 50} for i in range(5)]
    p.write_text("[\n" + ",\n".join(json.dumps(r) for r in recs) + "\n]\n", encoding="utf-8")
    assert list(iter_json_array(p)) == recs


def test_config_co_du_khoa_bat_buoc():
    cfg = load_config()
    for key in ("seed", "paths", "labels", "cleaning", "split", "prepare", "kafka"):
        assert key in cfg, f"config.yaml thiếu mục {key}"
    assert cfg["seed"] == 42
    assert cfg["cleaning"]["min_chars"] < cfg["cleaning"]["max_chars"]
    assert abs(sum(cfg["split"]["ratios"].values()) - 1.0) < 1e-9
