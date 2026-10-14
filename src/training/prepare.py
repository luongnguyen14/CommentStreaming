#!/usr/bin/env python3
"""prepare.py — Chuẩn bị dữ liệu huấn luyện từ IMDb (Task 6).

Các bước (đúng theo yêu cầu Task 6):
 1. Chuyển `data/raw/part-01.json` (mảng JSON 1,1 GB) sang JSONL để Spark đọc
    song song được (JSON gốc là 1 mảng lớn, `multiLine=true` sẽ dồn 1 task).
    Chỉ giữ tập con ~20% (~200 MB) theo `prepare.subsample_mod` cho vừa máy ảo;
    cách chọn tất định theo crc32(review_id) nên chạy lại ra đúng tập con đó.
 2. Làm sạch văn bản bằng hàm dùng chung `src/common/text_cleaning.py`.
 3. Ánh xạ `rating` -> 3 lớp theo `labels.mapping` trong config.yaml.
 4. Loại bản ghi rỗng / quá ngắn / quá dài (ngưỡng trong config.yaml).
 5. Loại trùng CHÍNH XÁC và GẦN TRÙNG (trùng bộ từ sau chuẩn hóa).
 6. Chia train/val/test 70/15/15 SAU khi loại trùng — mặc định theo NHÓM PHIM
    (một phim không nằm ở hai tập) và cân bằng nhãn bằng tham lam, seed 42.
 7. Ghi parquet + nhãn tập test cho producer + các bảng thống kê.

Ví dụ:
    # chạy thử trước (quy ước CLAUDE.md §3)
    PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \
        --driver-memory 2g src/training/prepare.py --sample 20000
    # chạy đầy đủ
    PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \
        --driver-memory 2g src/training/prepare.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import zlib
from pathlib import Path

import numpy as np
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.common.text_cleaning import clean_text, dedup_key, emoji_frequency, token_count  # noqa: E402
from src.common.utils import get_salt, iter_json_array, load_config  # noqa: E402

RAW_SCHEMA = StructType([
    StructField("review_id", StringType()),
    StructField("reviewer", StringType()),
    StructField("movie", StringType()),
    StructField("rating", StringType()),
    StructField("review_date", StringType()),
    StructField("review_detail", StringType()),
])

OUT_COLS = ["comment_id", "stream_id", "user_hash", "label", "rating",
            "text", "review_date", "n_chars", "n_tokens"]

SALT_LEN = 16        # độ dài user_hash — phải khớp src/common/utils.salted_hash


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def local_uri(p: Path) -> str:
    """Đường dẫn local dạng file:// — máy này có HDFS làm default FS, nếu để trần
    đường dẫn thì Spark sẽ đi tìm trên HDFS (và không thấy)."""
    return "file://" + str(p)


# --------------------------------------------------------------------------- #
# 1. Chuyển mảng JSON -> JSONL (một lần; lần sau đọc manifest để bỏ qua)
# --------------------------------------------------------------------------- #
def ensure_jsonl(raw_path: Path, jsonl_dir: Path, truncate: int, subsample_mod: int = 1) -> tuple[Path, int]:
    # Tên bắt đầu bằng "_" để Spark BỎ QUA khi đọc cả thư mục: nếu đặt là
    # manifest.json, `spark.read.json(dir)` sẽ đọc luôn nó thành 1 bản ghi rỗng
    # (đã từng xảy ra: Spark đếm 1.010.294 trong khi file có 1.010.293 dòng).
    manifest_path = jsonl_dir / "_manifest.json"
    if manifest_path.exists():
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (m.get("source") == raw_path.name and m.get("source_size") == raw_path.stat().st_size
                and m.get("truncate") == truncate and m.get("subsample_mod") == subsample_mod):
            log(f"JSONL đã có sẵn: {m['n_records']:,} bản ghi -> {jsonl_dir}")
            return jsonl_dir, m["n_records"]

    jsonl_dir.mkdir(parents=True, exist_ok=True)
    out_path = jsonl_dir / "part-000.jsonl"
    n = 0
    n_seen = 0
    t0 = time.time()
    subsample_mod = max(1, int(subsample_mod))
    log(f"Đang chuyển {raw_path.name} -> JSONL (cắt review_detail ở {truncate} ký tự, "
        f"giữ crc32(review_id) %% {subsample_mod} == 0) ...")
    with open(out_path, "w", encoding="utf-8") as out:
        for rec in iter_json_array(raw_path):
            n_seen += 1
            rid = rec.get("review_id") or ""
            # Chọn tập con TẤT ĐỊNH theo id (không theo vị trí trong file) để
            # không lệch theo thứ tự phim của bộ dữ liệu gốc.
            if subsample_mod > 1 and zlib.crc32(rid.encode("utf-8")) % subsample_mod != 0:
                continue
            detail = rec.get("review_detail") or ""
            row = {
                "review_id": rec.get("review_id"),
                "reviewer": rec.get("reviewer"),
                "movie": rec.get("movie"),
                "rating": rec.get("rating"),
                "review_date": rec.get("review_date"),
                "review_detail": detail[:truncate],
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
            if n % 200_000 == 0:
                log(f"  ... {n:,} bản ghi giữ lại ({time.time() - t0:.0f}s)")
    manifest_path.write_text(json.dumps({
        "source": raw_path.name, "source_size": raw_path.stat().st_size,
        "truncate": truncate, "subsample_mod": subsample_mod,
        "n_records": n, "n_seen": n_seen,
    }), encoding="utf-8")
    size_mb = out_path.stat().st_size / 1024 / 1024
    log(f"Xong JSONL: {n:,}/{n_seen:,} bản ghi giữ lại ({n / max(n_seen, 1):.1%}), "
        f"{size_mb:.0f} MB, {time.time() - t0:.0f}s -> {out_path}")
    return jsonl_dir, n


# --------------------------------------------------------------------------- #
# 2. Biểu thức nhãn + băm người dùng (dùng hàm Spark SQL, khớp bản Python)
# --------------------------------------------------------------------------- #
def label_expr(cfg: dict):
    """Cột `label` từ `rating` theo ánh xạ trong config.yaml."""
    mapping = cfg["labels"]["mapping"]
    expr = None
    for name in ("negative", "neutral", "positive"):     # thứ tự cố định
        values = [str(v) for v in mapping[name]]
        cond = F.col("rating").isin(values)
        expr = F.when(cond, F.lit(name)) if expr is None else expr.when(cond, F.lit(name))
    return expr.otherwise(F.lit(None).cast("string"))


def user_hash_expr(salt: str):
    """Băm có muối bằng sha2 của Spark — cho CÙNG kết quả với utils.salted_hash.

    `coalesce(reviewer, "")` để người dùng thiếu mã vẫn ra cùng giá trị với phía
    Python (`salted_hash("")`) thay vì NULL — có test đối chiếu ở tests/test_utils.py.
    """
    return F.substring(
        F.sha2(F.concat(F.lit(salt), F.coalesce(F.col("reviewer"), F.lit(""))), 256),
        1, SALT_LEN)


# --------------------------------------------------------------------------- #
# 3. Chia tập
# --------------------------------------------------------------------------- #
SPLITS = ["train", "val", "test"]


def split_group_movie_balanced(df: DataFrame, cfg: dict, seed: int, spark: SparkSession) -> DataFrame:
    """Chia theo NHÓM PHIM + cân bằng nhãn (tham lam, tất định theo seed).

    Ý tưởng: mỗi phim là một nhóm không thể tách; duyệt các phim theo thứ tự
    ngẫu nhiên (phim nhiều review trước) và xếp mỗi phim vào tập đang "thiếu"
    nhãn nhiều nhất so với tỷ lệ mục tiêu. Nhờ vậy không phim nào nằm ở hai tập
    (chống rò rỉ) mà phân bố lớp vẫn sát tỷ lệ mong muốn. Chạy 32 lần với thứ
    tự khác nhau (seed 42 + k) rồi lấy phương án lệch ít nhất — vẫn tất định.
    """
    t0 = time.time()
    stats = (df.groupBy("stream_id")
               .agg(F.count("*").alias("n"),
                    F.sum(F.when(F.col("label") == "negative", 1).otherwise(0)).alias("neg"),
                    F.sum(F.when(F.col("label") == "neutral", 1).otherwise(0)).alias("neu"),
                    F.sum(F.when(F.col("label") == "positive", 1).otherwise(0)).alias("pos"))
               .toPandas())
    counts = stats[["neg", "neu", "pos"]].to_numpy(dtype=np.int64)
    sizes = counts.sum(axis=1)
    m = len(stats)

    ratios = cfg["split"]["ratios"]
    targets = np.outer(counts.sum(axis=0), np.array([ratios[s] for s in SPLITS]))  # (3 nhãn, 3 tập)
    target_sum = targets.sum(axis=0)                        # (3,) — cỡ mong muốn từng tập
    total = float(targets.sum())

    def greedy(order: np.ndarray):
        """Xếp lần lượt từng phim vào tập đang thiếu hụt (theo mục tiêu) nhiều nhất."""
        assigned = np.zeros((3, 3), dtype=np.int64)
        split_of = np.zeros(m, dtype=np.int8)
        for i in order:
            v = counts[i]
            # Thiếu hụt SAU khi xếp phim này vào, lấy max (không phải min): tập đã
            # vượt mục tiêu có deficit = 0 nên không bị dồn thêm. Chia cho cỡ mục
            # tiêu để tập lớn (train) không bị "đói" so với tập nhỏ.
            # (Bản đầu dùng |đã xếp + v - mục tiêu| rồi argmin — đo sai hướng nên
            # dồn hết vào val/test, train = 0 dòng.)
            after = assigned + v[:, None]
            deficit = np.maximum(targets - after, 0).sum(axis=0) / target_sum
            s = int(np.argmax(deficit - assigned.sum(axis=0) * 1e-9))  # hòa -> tập ít dòng hơn
            split_of[i] = s
            assigned[:, s] += v
        return split_of, assigned

    def deviation(assigned: np.ndarray) -> float:
        return float(np.abs(assigned - targets).sum() / total)

    # Tham lam phụ thuộc thứ tự duyệt, nên thử nhiều thứ tự (seed 42 + k, tất
    # định) rồi lấy phương án lệch ít nhất so với mục tiêu — cả về số dòng lẫn
    # tỷ lệ từng lớp.
    n_restarts = 32
    best = None
    for k in range(n_restarts):
        rng = np.random.default_rng(seed + k)
        order = np.lexsort((rng.random(m), -sizes))    # phim lớn trước
        split_of, assigned = greedy(order)
        d = deviation(assigned)
        if best is None or d < best[0]:
            best = (d, split_of, assigned)
    err, split_of, assigned = best
    log(f"Chia theo nhóm phim: {m:,} phim, {n_restarts} lần thử, "
        f"lệch {err:.2%} so với mục tiêu (tính trong {time.time() - t0:.0f}s)")

    # Cải thiện cục bộ bằng HOÁN ĐỔI hai phim giữa hai tập: hoán đổi giữ nguyên
    # tổng số dòng của cả hai tập nên sửa được lệch TỶ LỆ LỚP (thứ mà tham lam
    # theo số lượng không sửa được). Chỉ nhận khi hàm mục tiêu giảm; dừng sau
    # `n_swap_try` lần thử — tất định theo seed.
    members = [np.flatnonzero(split_of == s) for s in range(3)]
    rng = np.random.default_rng(seed)
    n_swap_try = 200_000
    n_swap_ok = 0
    for _ in range(n_swap_try):
        a = int(rng.integers(0, 3))
        b = int(rng.integers(0, 3))
        if a == b:
            continue
        i = int(members[a][rng.integers(len(members[a]))])
        j = int(members[b][rng.integers(len(members[b]))])
        if split_of[i] != a or split_of[j] != b:      # danh sách có thể đã cũ
            continue
        col_a = assigned[:, a] - counts[i] + counts[j]
        col_b = assigned[:, b] - counts[j] + counts[i]
        old = (np.abs(assigned[:, a] - targets[:, a]).sum()
               + np.abs(assigned[:, b] - targets[:, b]).sum())
        new = (np.abs(col_a - targets[:, a]).sum() + np.abs(col_b - targets[:, b]).sum())
        if new < old:
            assigned[:, a] = col_a
            assigned[:, b] = col_b
            split_of[i], split_of[j] = b, a
            n_swap_ok += 1
    if n_swap_ok:
        log(f"  hoán đổi cục bộ: nhận {n_swap_ok:,}/{n_swap_try:,} lần -> lệch {deviation(assigned):.2%}")
    for s_idx, s_name in enumerate(SPLITS):
        n_s = int(assigned[:, s_idx].sum())
        log(f"  {s_name:5s}: {n_s:>9,} dòng ({n_s / target_sum[s_idx]:.1%} mục tiêu) "
            f"(neg={assigned[0, s_idx]:,} neu={assigned[1, s_idx]:,} pos={assigned[2, s_idx]:,})")
    mapping = stats[["stream_id"]].copy()
    mapping["split"] = [SPLITS[i] for i in split_of]
    mapping_df = spark.createDataFrame(mapping)
    return df.join(mapping_df, on="stream_id", how="left")


def split_stratified(df: DataFrame, cfg: dict, seed: int) -> DataFrame:
    """Chia ngẫu nhiên PHÂN TẦNG theo nhãn (không nhóm theo phim) — phương án dự phòng."""
    ratios = cfg["split"]["ratios"]
    cum = (F.row_number().over(Window.partitionBy("label").orderBy("hash_key")) /
           F.count("*").over(Window.partitionBy("label")))
    return (df.withColumn("hash_key", F.md5(F.concat(F.col("comment_id"), F.lit(str(seed)))))
              .withColumn("cum", cum)
              .withColumn("split", F.when(F.col("cum") <= ratios["train"], "train")
                                    .when(F.col("cum") <= ratios["train"] + ratios["val"], "val")
                                    .otherwise("test"))
              .drop("hash_key", "cum"))


# --------------------------------------------------------------------------- #
# 4. Ghi bảng thống kê
# --------------------------------------------------------------------------- #
def write_cleaning_log(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["step", "rows_in", "rows_removed", "rows_out", "note"])
        w.writeheader()
        w.writerows(rows)


def write_class_distribution(path: Path, dist_rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["split", "label", "count", "share_in_split"])
        for r in dist_rows:
            w.writerow([r["split"], r["label"], r["count"], f"{r['share']:.4f}"])


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Chuẩn bị dữ liệu huấn luyện từ IMDb (Task 6)")
    ap.add_argument("--config", default=str(PROJECT_ROOT / "config.yaml"))
    ap.add_argument("--sample", type=int, default=0,
                    help="chỉ dùng khoảng N bản ghi (chạy thử trước khi chạy đầy đủ)")
    ap.add_argument("--method", default=None, help="ghi đè split.method trong config")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    seed = args.seed if args.seed is not None else cfg["seed"]
    method = args.method or cfg["split"]["method"]
    raw_path = PROJECT_ROOT / cfg["paths"]["raw_comments"]
    jsonl_dir = PROJECT_ROOT / cfg["paths"]["raw_jsonl"]
    p = cfg["paths"]
    paths = {k: PROJECT_ROOT / p[k] for k in ("train", "val", "test", "eval_labels")}
    tables = PROJECT_ROOT / p["outputs_tables"]
    cl = cfg["cleaning"]

    try:
        salt = get_salt().decode("utf-8")
    except Exception as e:                       # thiếu muối -> dừng, không đoán
        print(f"LỖI: {e}", file=sys.stderr)
        return 2

    t_start = time.time()
    jsonl_dir, n_manifest = ensure_jsonl(raw_path, jsonl_dir, cfg["prepare"]["truncate_raw_detail"],
                                        cfg["prepare"].get("subsample_mod", 1))

    spark = (SparkSession.builder
             .appName("prepare-training-data")
             .config("spark.sql.shuffle.partitions", "64")
             .config("spark.sql.adaptive.enabled", "true")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    raw = spark.read.schema(RAW_SCHEMA).json(local_uri(jsonl_dir))
    n_loaded = raw.count()
    if n_loaded != n_manifest:     # file lạ trong thư mục sẽ bị đọc thành bản ghi rỗng
        log(f"CẢNH BÁO: JSONL có {n_manifest:,} dòng nhưng Spark đọc được {n_loaded:,} "
            f"(chênh {n_loaded - n_manifest:+,}) — kiểm tra file lạ trong {jsonl_dir.name}/")
    if args.sample:
        frac = min(1.0, args.sample * 2.5 / max(n_loaded, 1))
        raw = raw.sample(fraction=frac, seed=seed).limit(args.sample)
        log(f"CHẠY THỬ: lấy mẫu ~{args.sample:,} bản ghi trong {n_loaded:,} (fraction={frac:.4f})")
    else:
        log(f"Nạp {n_loaded:,} bản ghi từ {jsonl_dir.name}")

    # ---- làm sạch + nhãn ----
    df = (raw.select(
              F.col("review_id").alias("comment_id"),
              F.col("movie").alias("stream_id"),
              F.col("reviewer"),
              F.col("rating"),
              F.col("review_date"),
              F.col("review_detail"),
          )
          .withColumn("user_hash", user_hash_expr(salt))
          .withColumn("text", clean_text(F.col("review_detail"), cl["abbreviations"]))
          .withColumn("n_chars", F.length("text"))
          .withColumn("n_tokens", token_count("text"))
          .withColumn("label", label_expr(cfg))
          .drop("review_detail", "reviewer"))

    f_text = F.col("n_chars") > 0
    f_label = F.col("label").isNotNull()
    f_short = F.col("n_chars") < int(cl["min_chars"])
    f_long = F.col("n_chars") > int(cl["max_chars"])
    keep = f_text & f_label & ~f_short & ~f_long

    counts = df.agg(
        F.count("*").alias("total"),
        F.sum((~f_text).cast("int")).alias("empty_text"),
        F.sum((f_text & ~f_label).cast("int")).alias("no_label"),
        F.sum((f_text & f_label & f_short).cast("int")).alias("too_short"),
        F.sum((f_text & f_label & f_long).cast("int")).alias("too_long"),
    ).first()
    log(f"Tổng {counts['total']:,} | rỗng {counts['empty_text']:,} | thiếu nhãn {counts['no_label']:,} "
        f"| quá ngắn {counts['too_short']:,} | quá dài {counts['too_long']:,}")

    valid = df.filter(keep).persist()
    n_valid = valid.count()

    # ---- loại trùng chính xác (cùng văn bản đã làm sạch) ----
    w_exact = Window.partitionBy("key_exact").orderBy("comment_id")
    ex = valid.withColumn("key_exact", F.md5("text")).withColumn("rn", F.row_number().over(w_exact))
    n_exact_dup = ex.filter(F.col("rn") > 1).count()
    ex1 = ex.filter(F.col("rn") == 1).drop("rn", "key_exact").persist()
    n_after_exact = ex1.count()
    valid.unpersist()
    log(f"Trùng chính xác: bỏ {n_exact_dup:,} -> còn {n_after_exact:,}")

    # ---- loại gần trùng (trùng bộ từ sau chuẩn hóa) ----
    n_near_dup = 0
    if cfg["dedup"]["near_dup"]:
        w_near = Window.partitionBy("key_near").orderBy("comment_id")
        ne = ex1.withColumn("key_near", dedup_key("text")).withColumn("rn", F.row_number().over(w_near))
        n_near_dup = ne.filter(F.col("rn") > 1).count()
        clean = ne.filter(F.col("rn") == 1).drop("rn", "key_near").persist()
        n_final = clean.count()
        ex1.unpersist()
        log(f"Gần trùng: bỏ {n_near_dup:,} -> còn {n_final:,}")
    else:
        clean = ex1
        n_final = n_after_exact

    # ---- chia tập ----
    log(f"Chia tập theo phương thức: {method}")
    split_df = (split_group_movie_balanced(clean, cfg, seed, spark) if method == "group_movie_balanced"
                else split_stratified(clean, cfg, seed))
    split_df.persist()
    n_split = split_df.count()
    assert n_split == n_final, f"chia tập làm mất dòng: {n_split} != {n_final}"

    # ---- kiểm tra rò rỉ (đo thật, in ra để báo cáo) ----
    movie_leak = (split_df.groupBy("stream_id").agg(F.countDistinct("split").alias("k"))
                          .filter(F.col("k") > 1).count())
    user_leak = (split_df.groupBy("user_hash").agg(F.countDistinct("split").alias("k"))
                         .filter(F.col("k") > 1).count())
    log(f"Kiểm tra rò rỉ: phim nằm ở >1 tập: {movie_leak} | người dùng ở >1 tập: {user_leak:,}")
    assert movie_leak == 0, "có phim nằm ở nhiều tập — chia sai"

    # ---- ghi parquet ----
    for name in SPLITS:
        out = paths[name]
        (split_df.filter(F.col("split") == name).select(*OUT_COLS)
         .repartition(4 if args.sample else 16)
         .write.mode("overwrite").parquet(local_uri(out)))
        log(f"Đã ghi {name}: {out.relative_to(PROJECT_ROOT)}")

    # ---- nhãn đánh giá của tập test (producer dùng) ----
    (split_df.filter(F.col("split") == "test").select(
        F.col("comment_id"), F.col("label"), F.col("rating"))
     .write.mode("overwrite").parquet(local_uri(paths["eval_labels"])))
    log(f"Đã ghi nhãn test: {paths['eval_labels'].relative_to(PROJECT_ROOT)}")

    # ---- bảng phân bố lớp ----
    dist = split_df.groupBy("split", "label").count().collect()
    rows = []
    totals = {s: sum(r["count"] for r in dist if r["split"] == s) for s in SPLITS}
    for s in SPLITS + ["ALL"]:
        for lab in ("negative", "neutral", "positive"):
            if s == "ALL":        # dòng "ALL" gộp cả ba tập, không lọc theo cột split
                c = sum(r["count"] for r in dist if r["label"] == lab)
            else:
                c = sum(r["count"] for r in dist if r["split"] == s and r["label"] == lab)
            denom = n_final if s == "ALL" else totals[s]
            rows.append({"split": s, "label": lab, "count": c, "share": c / denom if denom else 0.0})
    write_class_distribution(tables / "class_distribution.csv", rows)
    log(f"Đã ghi bảng phân bố lớp: {len(rows)} dòng")

    # ---- nhật ký làm sạch ----
    log_rows = [
        {"step": "01_nap_raw", "rows_in": n_loaded, "rows_removed": n_loaded - counts["total"],
         "rows_out": counts["total"], "note": "nạp từ JSONL (ảnh hưởng của --sample)"},
        {"step": "02_thieu_van_ban", "rows_in": counts["total"], "rows_removed": counts["empty_text"],
         "rows_out": counts["total"] - counts["empty_text"], "note": "text rỗng sau khi làm sạch"},
        {"step": "03_thieu_nhan", "rows_in": counts["total"] - counts["empty_text"],
         "rows_removed": counts["no_label"], "rows_out": counts["total"] - counts["empty_text"] - counts["no_label"],
         "note": f"rating thiếu hoặc ngoài ánh xạ {cfg['labels']['mapping']}"},
        {"step": "04_qua_ngan", "rows_in": None, "rows_removed": counts["too_short"], "rows_out": None,
         "note": f"n_chars < {cl['min_chars']}"},
        {"step": "05_qua_dai", "rows_in": None, "rows_removed": counts["too_long"], "rows_out": None,
         "note": f"n_chars > {cl['max_chars']}"},
        {"step": "06_trung_chinh_xac", "rows_in": n_valid, "rows_removed": n_exact_dup,
         "rows_out": n_after_exact, "note": "trùng khít văn bản đã làm sạch"},
        {"step": "07_trung_gan", "rows_in": n_after_exact, "rows_removed": n_near_dup,
         "rows_out": n_final, "note": "trùng bộ từ sau chuẩn hóa (khác thứ tự/dấu câu)"},
        {"step": "08_con_lai", "rows_in": n_final, "rows_removed": 0, "rows_out": n_final,
         "note": "dữ liệu sạch dùng để chia tập"},
    ]
    # 04/05 có rows_in/rows_out suy ra từ bước 03
    base = counts["total"] - counts["empty_text"] - counts["no_label"]
    log_rows[3]["rows_in"] = base
    log_rows[3]["rows_out"] = base - counts["too_short"]
    log_rows[4]["rows_in"] = base - counts["too_short"]
    log_rows[4]["rows_out"] = base - counts["too_short"] - counts["too_long"]
    write_cleaning_log(tables / "cleaning_log.csv", log_rows)
    log("Đã ghi nhật ký làm sạch: outputs/tables/cleaning_log.csv")

    # ---- mẫu 1000 dòng (kèm văn bản gốc để đối chiếu bằng mắt) ----
    n_out = cfg["prepare"]["sample_rows_out"]
    frac = min(1.0, n_out * 2.5 / max(n_final, 1))
    sample = (split_df.select("comment_id", "stream_id", "user_hash", "label", "rating",
                              "text", "review_date", "split")
                      .sample(fraction=frac, seed=seed).limit(n_out).toPandas())
    orig = (raw.select(F.col("review_id").alias("comment_id"), F.col("review_detail").alias("text_raw"))
               .where(F.col("comment_id").isin(list(sample["comment_id"]))).toPandas())
    sample = sample.merge(orig, on="comment_id", how="left")
    sample.to_csv(tables / "clean_sample.csv", index=False,
                  columns=["comment_id", "stream_id", "user_hash", "label", "rating", "split",
                           "review_date", "text", "text_raw"])
    log(f"Đã ghi mẫu: {len(sample)} dòng -> outputs/tables/clean_sample.csv")

    # ---- emoji ----
    n_emoji = cfg["prepare"]["emoji_top_n"]
    emoji_frequency(split_df, "text", n_emoji).toPandas().to_csv(
        tables / "emoji_frequency.csv", index=False)
    log(f"Đã ghi tần suất emoji: top {n_emoji} -> outputs/tables/emoji_frequency.csv")

    split_df.unpersist()
    log(f"HOÀN TẤT sau {time.time() - t_start:.0f}s")
    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
