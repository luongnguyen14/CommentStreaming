"""queries.py — Truy vấn Spark SQL cho EDA (Task 9).

Script này CHỈ chạy SQL và ghi kết quả ra `outputs/tables/*.csv`.
Việc vẽ hình nằm ở `src/eda/plots.py` (đọc lại chính các CSV đó), nhờ vậy:
  - sửa hình không phải chạy lại Spark (nhanh hơn nhiều);
  - mọi con số trên hình đều truy vết được về một file CSV thật.

Mỗi truy vấn nằm trong MỘT file `.sql` riêng ở `src/eda/sql/` để đưa nguyên văn
vào báo cáo. File SQL là văn bản thuần; script này chỉ thay các chỗ giữ chỗ
`{{tên_tham_số}}` bằng giá trị đọc từ `config.yaml`.

Bảng tạm (temp view) đăng ký trước khi chạy SQL:
    train / val / test   data/processed/*.parquet            (dữ liệu huấn luyện)
    stream_detail        outputs/stream/<run>/scored_detail  (bảng chi tiết streaming)
    window_1min          outputs/stream/<run>/window_1min    (cửa sổ nhảy 1 phút)
    window_sliding_10s   outputs/stream/<run>/window_sliding_10s (cửa sổ trượt 10 s)
    stopwords            danh sách StopWordsRemover của Task 7 (1 cột `w`)

Chạy:
    source scripts/env.sh
    PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \\
        --driver-memory 4g --master 'local[2]' src/eda/queries.py --sample 20000
    ... src/eda/queries.py                        # bản đầy đủ (chạy khoảng vài phút)
    ... src/eda/queries.py --only class_distribution   # chạy 1 truy vấn
    ... src/eda/queries.py --dry-run --check           # chỉ kiểm tra tham số/SQL

Chế độ `--sample N` ghi kết quả ra `<tên>_sample.csv` (KHÔNG ghi đè bảng thật)
để không ai nhầm số liệu chạy thử với số liệu báo cáo.

Quy ước liên quan: CLAUDE.md §3 (tham số trong config, không hard-code),
§8 (bảng số liệu nền của mỗi hình nằm ở `outputs/tables/`), §9 (không bịa số).
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pyspark.sql import SparkSession, functions as F      # noqa: E402

from src.common.text_cleaning import (                    # noqa: E402
    EMOJI_CLASS,
    EMOJI_SYMBOL_RANGES,
)
from src.common.utils import PROJECT_ROOT, load_config    # noqa: E402
from src.training.train import build_stopwords            # noqa: E402

SQL_DIR = PROJECT_ROOT / "src" / "eda" / "sql"

# (tên, file SQL, tên bảng ra (không gồm .csv), mô tả ngắn)
QUERIES: list[tuple[str, str, str, str]] = [
    ("overview", "q00_overview.sql", "eda_overview",
     "Số kiểm tra quy mô dữ liệu (không vẽ hình)"),
    ("class_distribution", "q01_class_distribution.sql", "eda_class_distribution",
     "Hình 06 — phân bố nhãn cảm xúc"),
    ("length_quantiles", "q02_length_quantiles.sql", "eda_length_quantiles",
     "Hình 07 — phân vị độ dài theo lớp"),
    ("length_histogram", "q03_length_histogram.sql", "eda_length_histogram",
     "Hình 07 — phân bố độ dài theo lớp"),
    ("top_words", "q04_top_words_by_class.sql", "eda_top_words_by_class",
     "Hình 08 — top 20 từ đặc trưng mỗi lớp"),
    ("emoji_by_class", "q05_emoji_by_class.sql", "eda_emoji_by_class",
     "Hình 09 — emoji theo lớp cảm xúc"),
    ("sentiment_per_minute", "q06_sentiment_per_minute.sql", "eda_sentiment_per_minute",
     "Hình 10 — cảm xúc theo phút (cửa sổ 1 phút)"),
    ("sentiment_per_10s", "q07_sentiment_per_10s.sql", "eda_sentiment_per_10s",
     "Hình 10 — cảm xúc theo cửa sổ trượt 10 giây"),
    ("throughput_per_second", "q08_throughput_per_second.sql", "eda_throughput_per_second",
     "Hình 11 — thông lượng mỗi giây + bùng nổ"),
    ("negative_share_alert", "q09_negative_share_alert.sql", "eda_negative_share_alert",
     "Hình 12 — tỷ lệ tiêu cực + ngưỡng cảnh báo"),
    ("latency_quantiles", "q10_latency_quantiles.sql", "eda_latency_quantiles",
     "Hình 13 — phân vị độ trễ"),
    ("latency_histogram", "q11_latency_histogram.sql", "eda_latency_histogram",
     "Hình 13 — phân bố độ trễ"),
    ("token_vocab", "q12_token_vocab.sql", "eda_token_vocab",
     "Hạn chế của bước tách từ (không vẽ hình)"),
]

PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def local_uri(path: str | Path) -> str:
    """HDFS là filesystem mặc định của Spark ở máy này -> đường dẫn cục bộ phải
    ghi rõ `file://`, nếu không Spark đi tìm trên HDFS (đã gặp thật ở Task 6)."""
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return "file://" + str(p)


def sql_list(values: list[str]) -> str:
    """Danh sách Python -> danh sách literal SQL ('a', 'b')."""
    return ", ".join("'" + str(v).replace("'", "''") + "'" for v in values)


def build_params(cfg: dict, run_name: str) -> dict[str, str]:
    """Giá trị thay vào các chỗ giữ chỗ `{{...}}` trong file SQL.

    Mọi tham số đọc từ config.yaml — không hard-code trong file SQL.
    """
    eda = cfg["eda"]
    tcfg = cfg["training"]
    return {
        "streaming_run": run_name,
        # --- tham số phân tích ---
        "length_bin_width": str(eda["length_bin_width"]),
        "length_bin_max": str(eda["length_bin_max"]),
        "top_words_n": str(eda["top_words_n"]),
        "top_words_min_count": str(eda["top_words_min_count"]),
        "log_odds_prior": str(eda["log_odds_prior"]),
        "emoji_per_class_n": str(eda["emoji_per_class_n"]),
        "latency_bins_per_decade": str(eda["latency_bins_per_decade"]),
        "burst_sigma": str(eda["burst"]["sigma"]),
        "alert_threshold": str(eda["alert"]["negative_share_threshold"]),
        "alert_min_comments": str(eda["alert"]["min_comments"]),
        "alert_basis": str(eda["alert"]["basis"]),
        "synthetic_ids": sql_list(eda["synthetic_stream_ids"]),
        # Trần lý thuyết của một đợt bùng nổ do producer tạo ra (config replay).
        "burst_ceiling": str(cfg["replay"]["rate"] * cfg["replay"]["burst_factor"]),
        # Lớp ký tự emoji: dùng ĐÚNG hằng số của text_cleaning.py. Phải nhân đôi
        # dấu `\` vì chuỗi literal của Spark SQL xử lý escape.
        "emoji_class": EMOJI_CLASS.replace("\\", "\\\\"),
        # Lọc chặt hơn cho thống kê ở Hình 09: chỉ nhận token có ký tự nằm trong
        # DẢI EMOJI TƯỜNG MINH, loại ký tự typography mà \p{So} bắt nhầm
        # ("°" U+00B0, "©", "™"). Xem text_cleaning.EMOJI_SYMBOL_RANGES.
        "emoji_symbol_ranges": "[" + EMOJI_SYMBOL_RANGES.replace("\\", "\\\\") + "]",
    }


def render(sql_text: str, params: dict[str, str], name: str) -> str:
    """Thay {{tham_số}} bằng giá trị; thiếu tham số thì báo lỗi rõ ràng."""

    def repl(m: re.Match) -> str:
        key = m.group(1)
        if key not in params:
            raise KeyError(f"{name}: SQL dùng tham số `{key}` nhưng không có trong "
                           f"config/params (các tham số hiện có: "
                           f"{', '.join(sorted(params))})")
        return params[key]

    out = PLACEHOLDER_RE.sub(repl, sql_text)
    leftover = PLACEHOLDER_RE.search(out)
    if leftover:                                   # phòng khi lồng ngoặc
        raise ValueError(f"{name}: còn sót chỗ giữ chỗ {leftover.group(0)}")
    return out


def register_views(spark: SparkSession, cfg: dict, run_name: str,
                   sample: int | None) -> dict[str, int]:
    """Đăng ký bảng tạm cho dữ liệu huấn luyện và đầu ra streaming."""
    counts: dict[str, int] = {}
    for name in ("train", "val", "test"):
        df = spark.read.parquet(local_uri(cfg["paths"][name]))
        if sample:
            # Cắt theo crc32(comment_id) — tất định, không lấy N dòng đầu
            # (dữ liệu xếp theo phim nên N dòng đầu sẽ chỉ gồm vài phim).
            df = df.orderBy(F.crc32(F.col("comment_id"))).limit(sample)
        df.createOrReplaceTempView(name)
        counts[name] = df.count()

    sink = Path(cfg["streaming"]["sink_root"]) / run_name
    if not sink.exists():
        raise FileNotFoundError(
            f"Không thấy đầu ra streaming ở {sink}. Chạy Task 8 trước "
            f"(scripts/run_stream.sh) hoặc đổi eda.streaming_run trong config.yaml.")
    for view, sub in (("stream_detail", "scored_detail"),
                      ("window_1min", "window_1min"),
                      ("window_sliding_10s", "window_sliding_10s")):
        df = spark.read.parquet(local_uri(sink / sub))
        df.createOrReplaceTempView(view)
        counts[view] = df.count()

    # Danh sách stopword: dùng chung hàm với Task 7 (không chép lại danh sách).
    sw = build_stopwords(cfg["training"])
    spark.createDataFrame([(w,) for w in sw], "w string").createOrReplaceTempView("stopwords")
    counts["stopwords"] = len(sw)
    return counts


def run_query(spark: SparkSession, name: str, sql_file: str, table: str,
              params: dict[str, str], tables_dir: Path, suffix: str,
              show_rows: int = 6) -> Path | None:
    """Chạy một file SQL, ghi CSV, in vài dòng đầu ra log."""
    path = SQL_DIR / sql_file
    sql_text = path.read_text(encoding="utf-8")
    sql = render(sql_text, params, name)
    t0 = time.time()
    df = spark.sql(sql)
    pdf = df.toPandas()
    out = tables_dir / f"{table}{suffix}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.to_csv(out, index=False)
    log(f"  {name:22s} -> {out.relative_to(PROJECT_ROOT)}  "
        f"({len(pdf)} dòng, {time.time() - t0:.1f}s)")
    if show_rows:
        with_banner = pdf.head(show_rows).to_string(index=False, max_colwidth=40)
        for line in with_banner.splitlines():
            log(f"      {line}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Truy vấn Spark SQL cho EDA (Task 9)")
    ap.add_argument("--config", default=None, help="đường dẫn config.yaml")
    ap.add_argument("--run-name", default=None,
                    help="lần chạy streaming (mặc định: eda.streaming_run trong config)")
    ap.add_argument("--sample", type=int, default=0,
                    help="chạy thử với N dòng mỗi tập (ghi ra file *_sample.csv)")
    ap.add_argument("--only", action="append", default=None,
                    help="chỉ chạy truy vấn này (dùng được nhiều lần)")
    ap.add_argument("--dry-run", action="store_true",
                    help="chỉ thay tham số và kiểm tra SQL, không chạy Spark")
    ap.add_argument("--check", action="store_true",
                    help="đi kèm --dry-run: in luôn SQL đã thay tham số")
    args = ap.parse_args()

    cfg = load_config(args.config)
    run_name = args.run_name or cfg["eda"]["streaming_run"]
    tables_dir = PROJECT_ROOT / cfg["paths"]["outputs_tables"]
    params = build_params(cfg, run_name)

    todo = [q for q in QUERIES if not args.only or q[0] in args.only]
    if not todo:
        log(f"Không có truy vấn nào khớp --only {args.only}. "
            f"Tên hợp lệ: {', '.join(q[0] for q in QUERIES)}")
        return 2

    if args.dry_run:
        for name, sql_file, _table, _desc in todo:
            sql = render((SQL_DIR / sql_file).read_text(encoding="utf-8"), params, name)
            log(f"{name}: {sql_file} — OK ({len(sql)} ký tự)")
            if args.check:
                print(sql)
        return 0

    spark = (SparkSession.builder
             .appName("capstone-task9-eda-queries")
             # Mọi mốc thời gian là UTC: event_time do producer sinh theo ISO-8601
             # UTC, máy này ở +07 nên phải ghim múi giờ, không để Spark tự đổi.
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.sql.shuffle.partitions", "8")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    suffix = "_sample" if args.sample else ""
    log(f"EDA — run streaming `{run_name}` | "
        + (f"CHẾ ĐỘ CHẠY THỬ {args.sample} dòng/tập (ghi ra *_sample.csv)" if args.sample
           else "chạy đầy đủ"))
    counts = register_views(spark, cfg, run_name, args.sample or None)
    log("Bảng tạm: " + " | ".join(f"{k}={v:,}" for k, v in counts.items()))

    if args.sample:
        log("⚠️  Chạy thử: số liệu KHÔNG dùng cho báo cáo (bảng thật không bị ghi đè).")

    written = []
    for name, sql_file, table, desc in todo:
        log(f"[{desc}]")
        out = run_query(spark, name, sql_file, table, params, tables_dir, suffix)
        if out:
            written.append(out)

    log(f"Xong {len(written)} truy vấn -> {tables_dir.relative_to(PROJECT_ROOT)}/"
        + (suffix or ""))
    log("Vẽ hình + viết insights: $VENV_PY src/eda/plots.py")
    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
