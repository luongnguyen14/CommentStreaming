#!/usr/bin/env python3
"""stream_job.py — Spark Structured Streaming chấm điểm cảm xúc bình luận (Task 8).

Luồng dữ liệu (đúng sơ đồ kiến trúc `outputs/figures/00_pipeline_architecture.png`):

    Kafka `comments_raw` -> from_json (schema TƯỜNG MINH) -> tách hợp lệ / lỗi
        |                                                        |
        |  (lỗi: JSON hỏng, thiếu trường, event_ts sai,          `-> DLQ: topic `comments_dlq`
        |   văn bản rỗng/quá ngắn/quá dài)                          + <sink>/dlq (parquet)
        v
    clean_text() — ĐÚNG hàm dùng ở huấn luyện (src/common/text_cleaning.py)
        v
    PipelineModel đã lưu (TF-IDF nằm trong model) -> nhãn + xác suất lớp cao nhất
        v
    3 đầu ra, MỖI QUERY MỘT CHECKPOINT RIÊNG (CLAUDE.md §5):
        (a) `detail`   — Parquet phân vùng event_date/event_hour (mặc định KHÔNG giữ văn bản)
        (b) `kafka`    — JSON -> topic `comments_scored`
        (c) `window` / `sliding` — gộp theo cửa sổ 1 phút (nhảy) và 10 giây trượt (slide 5 giây)
                                   theo `stream_id`: số bình luận mỗi lớp + tỷ lệ tiêu cực
    (+ `dlq_kafka`, `dlq_parquet` — hai query cho DLQ ở bước tách lỗi)

Cách đo độ trễ (nêu rõ để không hiểu nhầm số liệu):
    latency_ms       = lúc micro-batch xử lý (`current_timestamp()`) − `event_time`
    kafka_latency_ms = lúc broker nhận (`kafka.timestamp`)            − `event_time`
    queue_latency_ms = latency_ms − kafka_latency_ms   (thời gian nằm chờ trong topic)
Vì `current_timestamp()` trong Structured Streaming được chốt ở ĐẦU mỗi micro-batch, số
đo này là độ trễ ở mức LÔ (mọi dòng cùng một batch dùng chung một mốc) và **bao gồm cả
thời gian chờ trigger** — đây không phải độ trễ từng bản ghi kiểu hệ thống real-time
phân tán. Chạy cùng máy nên không có độ trễ mạng giữa các máy.

Chạy (xem README để biết cách dừng an toàn):

    source scripts/env.sh
    PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \
        --master 'local[2]' --driver-memory 2g \
        --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.9 \
        src/streaming/stream_job.py --run-name main

LƯU Ý TRUNG THỰC (CLAUDE.md §9): dữ liệu vào topic là **bản phát lại (replay)** bộ dữ
liệu IMDb, KHÔNG phải bình luận livestream thật. Mọi báo cáo phải nói rõ điều này.
"""

from __future__ import annotations

import argparse
import csv
import json
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from pyspark.ml import PipelineModel                                    # noqa: E402
from pyspark.ml.functions import vector_to_array                        # noqa: E402
from pyspark.sql import DataFrame, SparkSession, functions as F         # noqa: E402
from pyspark.sql.streaming import StreamingQueryListener               # noqa: E402
from pyspark.sql.types import StringType, StructField, StructType       # noqa: E402

from src.common.text_cleaning import clean_text, dedup_key              # noqa: E402
from src.common.utils import load_config                                # noqa: E402

# ---------------------------------------------------------------------------
# Schema KHAI BÁO TƯỜNG MINH (CLAUDE.md §5: "không suy luận schema từ dữ liệu").
# Đây chính là 5 trường producer gửi (src/producer/replay_producer.py) — KHÔNG có
# nhãn: nhãn chỉ dùng để đánh giá, nằm ở data/processed/eval_labels.parquet
# (CLAUDE.md §6: không đưa nhãn vào luồng streaming).
#   lưu ý: trường thừa trong JSON bị BỎ QUA (mode PERMISSIVE) — đã ghi rõ ở README,
#   không phải "âm thầm bỏ qua" vì đây là quyết định có chủ đích và có tài liệu.
# ---------------------------------------------------------------------------
RAW_SCHEMA = StructType([
    StructField("comment_id", StringType(), True),
    StructField("stream_id", StringType(), True),
    StructField("user_hash", StringType(), True),
    StructField("text", StringType(), True),
    StructField("event_ts", StringType(), True),      # chuỗi ISO-8601 UTC -> event_time
    # ĐO THẬT trên Spark 3.5.9: `from_json` KHÔNG tự thêm trường chứa bản ghi hỏng,
    # dù đã đặt option `columnNameOfCorruptRecord` — phải KHAI BÁO trường đó trong
    # schema thì nó mới được điền (JSON hỏng -> chỉ trường này có giá trị).
    StructField("_corrupt", StringType(), True),
])
REQUIRED_FIELDS = ("comment_id", "stream_id", "user_hash", "text", "event_ts")
TS_FORMAT = "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"           # ví dụ 2026-10-15T00:31:07.123Z

# Tên lớp theo chỉ số Spark ML (config.yaml `labels.index`) — điền trong main().
LABEL_INDEX: dict[str, int] = {}
INDEX_LABEL: dict[int, str] = {}

STOP_FLAG = {"stop": False, "signal": None}
LOG_LOCK = threading.Lock()


def log(msg: str) -> None:
    """In log có mốc thời gian (flush ngay để theo dõi được khi chạy nền)."""
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    with LOG_LOCK:
        print(f"[{ts}] {msg}", flush=True)


def local_uri(path: str | Path) -> str:
    """HDFS là filesystem mặc định của Spark ở máy này -> đường dẫn cục bộ phải có file://."""
    return "file://" + str(path)


def resolve(path: str | Path) -> Path:
    """Đường dẫn tương đối -> tuyệt đối tính từ PROJECT_ROOT."""
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _on_signal(signum, frame) -> None:      # Ctrl+C (SIGINT) hoặc `kill` (SIGTERM)
    STOP_FLAG["stop"] = True
    STOP_FLAG["signal"] = signum


# ---------------------------------------------------------------------------
# 1) Nguồn Kafka + parse JSON
# ---------------------------------------------------------------------------
def read_raw_stream(spark: SparkSession, cfg: dict, args) -> DataFrame:
    """readStream từ topic `comments_raw` (CLAUDE.md §5: có event time, có checkpoint riêng).

    Giữ thêm cột metadata của Kafka (partition/offset/timestamp) để truy vết được
    từng bản ghi — dùng cho cả việc giải thích độ trễ và đối chiếu số lượng.
    """
    reader = (spark.readStream.format("kafka")
              .option("kafka.bootstrap.servers", cfg["kafka"]["bootstrap_servers"])
              .option("subscribe", cfg["kafka"]["topic_raw"])
              .option("startingOffsets", args.starting_offsets)
              # failOnDataLoss=false: topic bị xoá/compact thì job không chết (bản ghi
              # mất sẽ được ghi nhận là "mất dữ liệu", không âm thầm coi là đã xử lý).
              .option("failOnDataLoss", "false"))
    if args.max_offsets and args.max_offsets > 0:
        reader = reader.option("maxOffsetsPerTrigger", str(args.max_offsets))
    return reader.load().select(
        F.col("value").cast("string").alias("json_raw"),
        F.col("partition").alias("kafka_partition"),
        F.col("offset").alias("kafka_offset"),
        F.col("timestamp").alias("kafka_ts"),
    )


def parse_stream(raw: DataFrame) -> DataFrame:
    """from_json với schema tường minh -> các cột phẳng + cột `_corrupt` cho JSON hỏng.

    Chuyển `event_ts` (chuỗi ISO-8601) thành `event_time` (timestamp) NGAY Ở ĐÂY,
    bằng chính bộ phân tích của Spark (định dạng khai báo tường minh, không đoán).
    """
    parsed = raw.withColumn(
        "data",
        F.from_json(
            F.col("json_raw"), RAW_SCHEMA,
            {"mode": "PERMISSIVE", "columnNameOfCorruptRecord": "_corrupt",
             "timestampFormat": TS_FORMAT},
        ),
    )
    # `data.*` đã gồm `_corrupt` (khai báo trong RAW_SCHEMA) — không thêm lần nữa.
    return (parsed
            .select(F.col("data.*"), "json_raw", "kafka_partition",
                    "kafka_offset", "kafka_ts")
            .withColumn("event_time", F.to_timestamp(F.col("event_ts"), TS_FORMAT)))


def add_cleaning_and_reason(df: DataFrame, cfg: dict) -> DataFrame:
    """Làm sạch bằng ĐÚNG hàm dùng ở huấn luyện + gán LÝ DO cho bản ghi không hợp lệ.

    Ngưỡng lọc lấy từ `cleaning.min_chars`/`max_chars` trong config.yaml — giống hệt
    `src/training/prepare.py`, nếu lệch thì phân phối lúc chạy khác lúc huấn luyện.
    Bản ghi hợp lệ ⇔ `dlq_reason IS NULL` (mọi bản ghi đều vào đúng một nhánh, không
    có bản ghi nào bị bỏ im lặng).
    """
    cl = cfg["cleaning"]
    min_chars, max_chars = int(cl["min_chars"]), int(cl["max_chars"])

    df = (df.withColumn("text_clean", clean_text(F.col("text"), cl["abbreviations"]))
            .withColumn("n_chars", F.length("text_clean")))

    # Các trường bắt buộc bị thiếu (concat_ws tự bỏ qua null -> ra "comment_id,text")
    missing = F.concat_ws(",", *[F.when(F.col(c).isNull(), F.lit(c)) for c in REQUIRED_FIELDS])

    reason = (
        F.when(F.col("_corrupt").isNotNull(), F.lit("json_khong_hop_le"))
         .when(F.length(missing) > 0, F.concat(F.lit("thieu_truong:"), missing))
         .when(F.col("event_time").isNull(), F.lit("event_ts_khong_doc_duoc"))
         .when(F.col("text_clean") == "", F.lit("van_ban_rong_sau_lam_sach"))
         .when(F.col("n_chars") < min_chars, F.lit(f"van_ban_qua_ngan_duoi_{min_chars}_ky_tu"))
         .when(F.col("n_chars") > max_chars, F.lit(f"van_ban_qua_dai_tren_{max_chars}_ky_tu"))
    )
    return df.withColumn("dlq_reason", reason)


def score_stream(df: DataFrame, model: PipelineModel) -> DataFrame:
    """Chấm điểm bằng PipelineModel đã lưu: nhãn dự đoán + xác suất cao nhất + độ trễ.

    Văn bản đưa vào model là cột `text_clean` đã đặt tên lại `text` — ĐÚNG tên cột
    và ĐÚNG hàm làm sạch như lúc huấn luyện (CLAUDE.md §4).
    """
    scored = model.transform(df.withColumn("text", F.col("text_clean")))

    prob = vector_to_array(F.col("probability"))
    processing_ts = F.current_timestamp()

    # Dịch chỉ số lớp -> tên lớp. `when()` chỉ nối được tiếp trên một Column do
    # chính `when()` sinh ra, nên phải mở chuỗi bằng when() chứ không phải F.lit().
    items = sorted(INDEX_LABEL.items())          # [(0, 'negative'), (1, 'neutral'), ...]
    label_case = F.when(F.col("prediction") == items[0][0], F.lit(items[0][1]))
    for idx, name in items[1:]:
        label_case = label_case.when(F.col("prediction") == idx, F.lit(name))
    label_case = label_case.otherwise(F.lit(None).cast("string"))   # chỉ số lạ -> NULL

    return (scored
            .withColumn("pred_class", F.col("prediction").cast("int"))
            .withColumn("confidence", F.round(F.array_max(prob), 4))
            .withColumn("pred_label", label_case)
            .withColumn("processing_ts", processing_ts)
            .withColumn("latency_ms",
                        F.unix_millis(processing_ts) - F.unix_millis(F.col("event_time")))
            .withColumn("kafka_latency_ms",
                        F.unix_millis(F.col("kafka_ts")) - F.unix_millis(F.col("event_time")))
            .withColumn("queue_latency_ms",
                        F.col("latency_ms") - F.col("kafka_latency_ms"))
            .withColumn("event_date", F.date_format(F.col("event_time"), "yyyy-MM-dd"))
            .withColumn("event_hour", F.hour(F.col("event_time")))
            .withColumn("text_len", F.col("n_chars")))


# ---------------------------------------------------------------------------
# 2) DataFrame cho từng đầu ra
# ---------------------------------------------------------------------------
DETAIL_COLS = ["comment_id", "stream_id", "user_hash", "event_time", "event_date",
               "event_hour", "pred_class", "pred_label", "confidence", "text_len",
               "latency_ms", "kafka_latency_ms", "queue_latency_ms", "processing_ts",
               "kafka_partition", "kafka_offset"]


def detail_frame(scored: DataFrame, keep_text: bool) -> DataFrame:
    """Bảng chi tiết đã chấm điểm. Mặc định KHÔNG có văn bản (riêng tư — CLAUDE.md §7).

    `text_hash` là băm md5 của bộ từ đã chuẩn hóa (`dedup_key`): đủ để phát hiện
    bình luận trùng/copy-paste mà không lưu nội dung. Bật
    `streaming.privacy.keep_text: true` nếu cần giữ văn bản đã làm sạch.
    """
    if keep_text:
        return scored.select(*DETAIL_COLS, "text_clean")
    # Băm phải tính TRƯỚC khi select (sau select thì `text_clean` đã bị bỏ).
    df = scored.withColumn("text_hash", dedup_key(F.col("text_clean")))
    return df.select(*DETAIL_COLS, "text_hash")


def kafka_scored_frame(scored: DataFrame, keep_text: bool) -> DataFrame:
    """JSON gửi topic `comments_scored` (khóa = comment_id để giữ thứ tự theo bình luận)."""
    fields = [F.col("comment_id"), F.col("stream_id"), F.col("user_hash"),
              F.col("event_time"), F.col("pred_class"), F.col("pred_label"),
              F.col("confidence"), F.col("text_len"), F.col("latency_ms"),
              F.col("processing_ts")]
    if keep_text:
        fields.append(F.col("text_clean"))
    return scored.select(
        F.col("comment_id").alias("key"),
        F.to_json(F.struct(*fields)).alias("value"),
    )


def dlq_frame(df: DataFrame) -> DataFrame:
    """Bản ghi lỗi: giữ nguyên payload gốc + LÝ DO + vị trí trong topic (truy vết được)."""
    return df.filter(F.col("dlq_reason").isNotNull()).select(
        F.coalesce(F.col("comment_id"), F.lit("(khong-co-id)")).alias("comment_id"),
        F.col("dlq_reason").alias("reason"),
        F.col("json_raw"),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
        F.col("event_ts"),
        F.current_timestamp().alias("dlq_ts"),
    )


def window_agg_frame(scored: DataFrame, window_duration: str, slide: str | None,
                     watermark: str) -> DataFrame:
    """Gộp theo cửa sổ thời gian gian theo `stream_id`: số bình luận mỗi lớp + tỷ lệ tiêu cực.

    Dùng EVENT TIME + watermark (CLAUDE.md §5) — không dùng processing time.
    Cửa sổ 1 phút (slide = duration) là cửa sổ NHẢY; cửa sổ 10 giây với slide 5 giây
    là cửa sổ TRƯỢT thật sự (hai cửa sổ liền nhau chồng lên nhau 5 giây).
    """
    w = F.window(F.col("event_time"), window_duration, slide) if slide \
        else F.window(F.col("event_time"), window_duration)
    agg = (scored
           .withWatermark("event_time", watermark)
           .groupBy(w.alias("window"), F.col("stream_id"))
           .agg(F.count("*").alias("n_comments"),
                F.sum((F.col("pred_label") == "negative").cast("int")).alias("n_negative"),
                F.sum((F.col("pred_label") == "neutral").cast("int")).alias("n_neutral"),
                F.sum((F.col("pred_label") == "positive").cast("int")).alias("n_positive"),
                F.round(F.avg("confidence"), 4).alias("avg_confidence"),
                F.round(F.avg("latency_ms"), 1).alias("avg_latency_ms")))
    return (agg
            .withColumn("window_start", F.col("window.start"))
            .withColumn("window_end", F.col("window.end"))
            .withColumn("share_negative", F.round(F.col("n_negative") / F.col("n_comments"), 4))
            .withColumn("share_neutral", F.round(F.col("n_neutral") / F.col("n_comments"), 4))
            .withColumn("share_positive", F.round(F.col("n_positive") / F.col("n_comments"), 4))
            .drop("window"))


# ---------------------------------------------------------------------------
# 3) StreamingQueryListener — log số bản ghi mỗi micro-batch (task 8.5)
# ---------------------------------------------------------------------------
class BatchLogListener(StreamingQueryListener):
    """Ghi mỗi micro-batch một dòng CSV + in ra log (số bản ghi, thời lượng, watermark).

    `numRowsDroppedByWatermark` là số bản ghi bị bỏ vì đến muộn hơn watermark — chỉ
    xuất hiện ở query gộp cửa sổ; bằng 0 nghĩa là watermark 2 phút đủ rộng.
    """

    def __init__(self, csv_path: Path, run_name: str):
        super().__init__()
        self.csv_path = csv_path
        self.run_name = run_name
        self.lock = threading.Lock()
        self.rows_logged = 0
        self.rows_dropped = 0

    def onQueryStarted(self, event):
        log(f"  >> query bắt đầu: {event.name} (id={event.id})")

    def onQueryProgress(self, event):
        p = event.progress
        dur = p.durationMs or {}
        dropped = int(getattr(p, "numRowsDroppedByWatermark", 0) or 0)
        row = {
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "run_name": self.run_name,
            "query_name": p.name,
            "batch_id": p.batchId,
            "num_input_rows": p.numInputRows,
            "input_rows_per_second": round(p.inputRowsPerSecond, 2),
            "processed_rows_per_second": round(p.processedRowsPerSecond, 2),
            "trigger_execution_ms": dur.get("triggerExecution"),
            "add_batch_ms": dur.get("addBatch"),
            "num_rows_dropped_by_watermark": dropped,
            "state_operators": p.stateOperators[0].numRowsTotal if p.stateOperators else 0,
        }
        with self.lock:
            self.rows_logged += p.numInputRows
            self.rows_dropped += dropped
            new_file = not self.csv_path.exists()
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(row))
                if new_file:
                    w.writeheader()
                w.writerow(row)
        log(f"  [{p.name:16s}] batch {p.batchId:3d}: {p.numInputRows:5d} bản ghi | "
            f"trigger {dur.get('triggerExecution', 0):5d} ms | bỏ do watermark {dropped} | "
            f"state {row['state_operators']}")

    def onQueryTerminated(self, event):
        err = event.exception
        log(f"  << query kết thúc: {event.name} (id={event.id})"
            + (f" — LỖI: {err}" if err else " — bình thường"))


# ---------------------------------------------------------------------------
# 4) Dựng và khởi chạy các query
# ---------------------------------------------------------------------------
class Sinks:
    def __init__(self, root: Path):
        self.root = root
        self.detail = root / "scored_detail"
        self.dlq = root / "dlq"
        self.window = root / "window_1min"
        self.sliding = root / "window_sliding_10s"


def start_query(df: DataFrame, name: str, checkpoint_root: Path, trigger_s: int, writer):
    """Khởi chạy một query: MỖI QUERY MỘT checkpointLocation riêng (CLAUDE.md §5)."""
    cp = checkpoint_root / name
    return (writer(df)
            .queryName(name)
            .option("checkpointLocation", local_uri(cp))
            .trigger(processingTime=f"{trigger_s} seconds")
            .start())


def start_all_queries(spark: SparkSession, cfg: dict, args, model: PipelineModel,
                      sinks: Sinks, checkpoint_root: Path) -> list:
    """Khởi chạy các query đã chọn. Nguồn Kafka được đọc LẠI cho từng query để mỗi
    query có offset + checkpoint độc lập (đổi lại: mỗi query tự parse/làm sạch/chấm
    điểm dữ liệu của mình — đúng yêu cầu "mỗi query một checkpoint riêng")."""
    scfg = cfg["streaming"]
    keep_text = bool(scfg["privacy"]["keep_text"])
    watermark = args.watermark
    trigger_s = args.trigger_seconds
    want = set(args.queries.split(",")) if args.queries != "all" else {
        "detail", "kafka", "window", "sliding", "dlq_kafka", "dlq_parquet"}
    queries = []

    def scored_and_dlq():
        """(df đã chấm điểm, df bản ghi lỗi) — bản ghi lỗi KHÔNG bao giờ được chấm điểm.

        Đây là điểm dễ sai đã gặp thật khi chạy thử: nếu chấm điểm cả bản ghi lỗi thì
        bảng chi tiết lẫn số liệu cửa sổ đều bị nhiễu bởi văn bản rỗng/quá ngắn/quá dài
        (mà lúc huấn luyện đã bị loại) — và điều kiện đối chiếu
        "đã chấm điểm + vào DLQ = đã gửi" sẽ sai.
        """
        prepared = add_cleaning_and_reason(parse_stream(read_raw_stream(spark, cfg, args)), cfg)
        valid = prepared.filter(F.col("dlq_reason").isNull())
        return score_stream(valid, model), prepared

    if "detail" in want:
        scored, _ = scored_and_dlq()
        df = detail_frame(scored, keep_text)
        queries.append(start_query(df, "detail", checkpoint_root, trigger_s,
                                   lambda d: d.writeStream
                                   .outputMode("append").format("parquet")
                                   .partitionBy("event_date", "event_hour")
                                   .option("path", local_uri(sinks.detail))))
        log(f"  query `detail`      -> {sinks.detail.relative_to(PROJECT_ROOT)} "
            f"(parquet, phân vùng event_date/event_hour, giữ văn bản: {keep_text})")

    if "kafka" in want:
        scored, _ = scored_and_dlq()
        df = kafka_scored_frame(scored, keep_text)
        topic = cfg["kafka"]["topic_scored"]
        queries.append(start_query(df, "kafka", checkpoint_root, trigger_s,
                                   lambda d: d.writeStream
                                   .outputMode("append").format("kafka")
                                   .option("kafka.bootstrap.servers",
                                           cfg["kafka"]["bootstrap_servers"])
                                   .option("topic", topic)))
        log(f"  query `kafka`       -> topic {topic} (JSON, khóa = comment_id)")

    if "window" in want:
        scored, _ = scored_and_dlq()
        df = window_agg_frame(scored, scfg["window_duration"], None, watermark)
        queries.append(start_query(df, "window", checkpoint_root, trigger_s,
                                   lambda d: d.writeStream
                                   .outputMode("append").format("parquet")
                                   .option("path", local_uri(sinks.window))))
        log(f"  query `window`      -> {sinks.window.relative_to(PROJECT_ROOT)} "
            f"(cửa sổ {scfg['window_duration']}, watermark {watermark})")

    if "sliding" in want:
        scored, _ = scored_and_dlq()
        df = window_agg_frame(scored, scfg["sliding_window_duration"],
                              scfg["sliding_window_slide"], watermark)
        queries.append(start_query(df, "sliding", checkpoint_root, trigger_s,
                                   lambda d: d.writeStream
                                   .outputMode("append").format("parquet")
                                   .option("path", local_uri(sinks.sliding))))
        log(f"  query `sliding`     -> {sinks.sliding.relative_to(PROJECT_ROOT)} "
            f"(cửa sổ {scfg['sliding_window_duration']} trượt "
            f"{scfg['sliding_window_slide']}, watermark {watermark})")

    if "dlq_kafka" in want and scfg["dlq"]["to_kafka"]:
        _, prepared = scored_and_dlq()
        # Kafka sink cần hai cột `key`/`value`; value = JSON đầy đủ kèm lý do.
        df = dlq_frame(prepared).selectExpr(
            "comment_id AS key", "to_json(struct(*)) AS value")
        topic = cfg["kafka"]["topic_dlq"]
        queries.append(start_query(df, "dlq_kafka", checkpoint_root, trigger_s,
                                   lambda d: d.writeStream
                                   .outputMode("append").format("kafka")
                                   .option("kafka.bootstrap.servers",
                                           cfg["kafka"]["bootstrap_servers"])
                                   .option("topic", topic)))
        log(f"  query `dlq_kafka`   -> topic {topic} (JSON kèm lý do)")

    if "dlq_parquet" in want and scfg["dlq"]["to_parquet"]:
        _, prepared = scored_and_dlq()
        df = dlq_frame(prepared)
        queries.append(start_query(df, "dlq_parquet", checkpoint_root, trigger_s,
                                   lambda d: d.writeStream
                                   .outputMode("append").format("parquet")
                                   .option("path", local_uri(sinks.dlq))))
        log(f"  query `dlq_parquet` -> {sinks.dlq.relative_to(PROJECT_ROOT)}")

    return queries


def stop_queries(spark: SparkSession, queries: list) -> None:
    """Dừng AN TOÀN: dừng từng query, chờ nó kết thúc, rồi mới đóng Spark.

    Offset đã xử lý nằm trong checkpoint nên lần chạy sau tiếp tục đúng chỗ dừng
    (cùng `--run-name`). Không dùng kill -9: có thể bỏ dở một micro-batch đang ghi.
    """
    for q in queries:
        if q.isActive:
            last_batch = q.lastProgress["batchId"] if q.lastProgress else "chưa có"
            log(f"  đang dừng query `{q.name}` (batch cuối: {last_batch}) ...")
            q.stop()
    for q in queries:
        try:
            q.awaitTermination(30)
            log(f"  query `{q.name}` đã dừng sạch.")
        except Exception as e:                                # pragma: no cover
            log(f"  query `{q.name}` không dừng được trong 30 s: {e}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Spark Structured Streaming chấm điểm cảm xúc bình luận (Task 8)")
    ap.add_argument("--config", default=str(PROJECT_ROOT / "config.yaml"))
    ap.add_argument("--run-name", default="main",
                    help="tên lần chạy: quyết định thư mục checkpoint + sink mặc định")
    ap.add_argument("--model-path", default=None,
                    help="thư mục PipelineModel (mặc định: training.model_out)")
    ap.add_argument("--sink-dir", default=None,
                    help="thư mục ghi kết quả (mặc định: <streaming.sink_root>/<run-name>)")
    ap.add_argument("--checkpoint-root", default=None,
                    help="thư mục checkpoint (mặc định: <streaming.checkpoint_root>/<run-name>)")
    ap.add_argument("--trigger-seconds", type=int, default=None,
                    help="chu kỳ micro-batch (mặc định: streaming.trigger_seconds)")
    ap.add_argument("--max-offsets", type=int, default=None,
                    help="trần số bản ghi mỗi micro-batch (mặc định: streaming.max_offsets_per_trigger)")
    ap.add_argument("--starting-offsets", default=None,
                    help="latest | earliest | chuỗi JSON offset (mặc định: streaming.starting_offsets)")
    ap.add_argument("--watermark", default=None, help="ví dụ '2 minutes'")
    ap.add_argument("--queries", default="all",
                    help="all hoặc danh sách: detail,kafka,window,sliding,dlq_kafka,dlq_parquet")
    ap.add_argument("--duration-seconds", type=int, default=0,
                    help="tự dừng sau N giây (0 = chạy tới khi Ctrl+C/kill)")
    # Ghi đè streaming.privacy.keep_text (mặc định false). Bật lên thì bảng chi tiết
    # và topic comments_scored GIỮ văn bản đã làm sạch — cần cho dashboard Task 10
    # (khung "bình luận mới nhất"). Chỉ bật khi demo trên dữ liệu công khai (IMDb),
    # KHÔNG bật khi thu bình luận thật (CLAUDE.md §7).
    ap.add_argument("--keep-text", dest="keep_text", action="store_true", default=None,
                    help="giữ văn bản đã làm sạch trong kết quả (mặc định: theo config)")
    ap.add_argument("--no-keep-text", dest="keep_text", action="store_false",
                    help="không giữ văn bản (mặc định của dự án)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    scfg = cfg["streaming"]
    args.trigger_seconds = args.trigger_seconds or int(scfg["trigger_seconds"])
    args.max_offsets = args.max_offsets if args.max_offsets is not None \
        else int(scfg["max_offsets_per_trigger"])
    args.starting_offsets = args.starting_offsets or str(scfg["starting_offsets"])
    args.watermark = args.watermark or str(scfg["watermark"])
    if args.keep_text is not None:      # cờ dòng lệnh thắng config (đã ghi rõ trong --help)
        scfg["privacy"]["keep_text"] = bool(args.keep_text)
        log(f"Ghi đè privacy.keep_text = {bool(args.keep_text)} (từ dòng lệnh)")

    global LABEL_INDEX, INDEX_LABEL
    LABEL_INDEX = {k: int(v) for k, v in cfg["labels"]["index"].items()}
    INDEX_LABEL = {v: k for k, v in LABEL_INDEX.items()}

    model_path = resolve(args.model_path or cfg["training"]["model_out"])
    sink_root = resolve(args.sink_dir) if args.sink_dir \
        else resolve(scfg["sink_root"]) / args.run_name
    checkpoint_root = resolve(args.checkpoint_root) if args.checkpoint_root \
        else resolve(scfg["checkpoint_root"]) / args.run_name
    batch_log = resolve(scfg["batch_log"])

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    spark = (SparkSession.builder
             .appName(f"capstone-task8-stream-{args.run_name}")
             .config("spark.sql.shuffle.partitions", "4")
             # Mọi mốc thời gian (cửa sổ, event_date/event_hour) tính theo UTC cho khớp
             # với `event_ts` mà producer phát (ISO-8601 UTC) — không phụ thuộc múi giờ máy.
             .config("spark.sql.session.timeZone", "UTC")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    listener = BatchLogListener(batch_log, args.run_name)
    spark.streams.addListener(listener)
    queries = []
    try:
        load_start = time.time()
        model = PipelineModel.load(local_uri(model_path))
        meta_path = Path(str(model_path) + "_metadata.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        log(f"Spark {spark.version} | run `{args.run_name}` | mô hình {meta.get('model_name', '?')} "
            f"(nạp {time.time() - load_start:.1f}s) | nhãn {INDEX_LABEL}")
        log(f"nguồn: topic {cfg['kafka']['topic_raw']} @ {cfg['kafka']['bootstrap_servers']} | "
            f"startingOffsets={args.starting_offsets} | maxOffsetsPerTrigger={args.max_offsets} | "
            f"trigger={args.trigger_seconds}s | watermark={args.watermark}")
        log(f"sink: {sink_root} | checkpoint: {checkpoint_root} | log batch: {batch_log}")

        queries = start_all_queries(spark, cfg, args, model, Sinks(sink_root), checkpoint_root)
        if not queries:
            log("Không có query nào được chọn — kiểm tra --queries")
            return 1
        log(f"ĐÃ CHẠY {len(queries)} query. Sẵn sàng nhận dữ liệu (chờ micro-batch đầu tiên ...)")

        # Chờ tới khi mọi query hoàn thành micro-batch đầu (nguồn Kafka đã được gắn
        # offset) rồi mới báo READY — để bên phát dữ liệu không gửi sớm hơn mốc offset.
        t0 = time.time()
        while any(q.lastProgress is None for q in queries) and time.time() - t0 < 120 \
                and not STOP_FLAG["stop"]:
            time.sleep(1)
        log("READY — đã sẵn sàng; có thể bắt đầu phát dữ liệu vào topic.")

        deadline = time.time() + args.duration_seconds if args.duration_seconds else None
        while not STOP_FLAG["stop"]:
            time.sleep(2)
            if not spark.streams.active:
                log("Tất cả query đã kết thúc.")
                break
            if deadline and time.time() >= deadline:
                log(f"Đã đủ {args.duration_seconds}s (--duration-seconds) — tự dừng.")
                break
        if STOP_FLAG["signal"]:
            log(f"Nhận tín hiệu {STOP_FLAG['signal']} — dừng an toàn ...")
    except Exception as e:                                        # pragma: no cover
        log(f"LỖI khi chạy job: {type(e).__name__}: {e}")
        stop_queries(spark, queries)
        spark.stop()
        return 1

    stop_queries(spark, queries)
    log(f"Tổng số bản ghi đã đọc qua các query: {listener.rows_logged:,} | "
        f"bỏ do watermark: {listener.rows_dropped:,}")
    spark.stop()
    log("Đã dừng Spark. Kết quả nằm trong " + str(sink_root.relative_to(PROJECT_ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
