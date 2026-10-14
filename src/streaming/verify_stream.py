#!/usr/bin/env python3
"""verify_stream.py — Kiểm chứng kết quả job streaming (Task 8, mục 6).

Chạy SAU khi job streaming đã dừng êm (đọc lại file Parquet trên đĩa, không đọc
trực tiếp state của query):

    source scripts/env.sh
    PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY \
    $SPARK_HOME/bin/spark-submit --driver-memory 2g --master 'local[2]' \
      src/streaming/verify_stream.py --run-name verify1 \
      --sink-dir outputs/stream/verify1 --sent-labels outputs/stream/verify1/sent_labels.json \
      --extra-valid 9 --bad-injected 10

Năm việc, theo đúng yêu cầu:

 1) ĐỐI CHIẾU SỐ LƯỢNG: bảng chi tiết (đã chấm điểm) + DLQ = số bản ghi đã gửi.
    Số đã gửi KHÔNG đoán: `--sent-labels` là file `replay_producer --labels-out` ghi
    ra (đúng danh sách comment_id đã phát — cũng dùng để biết bản ghi nào của
    producer vướng luật làm sạch nên phải vào DLQ). `--extra-valid`/`--bad-injected`
    là số bản ghi hợp lệ thêm và số ca lỗi cố ý, in ra ở cuối `send_bad_events.py`.
 2) ĐẾM MESSAGE trong topic `comments_scored` / `comments_dlq` bằng chênh lệch
    offset so với mốc ghi trước khi chạy (`--record-baseline`).
 3) GHÉP `data/processed/eval_labels.parquet` theo `comment_id` -> macro-F1,
    accuracy, P/R/F1 từng lớp TRÊN LUỒNG; so với offline hai mức:
      (a) offline trên TOÀN BỘ tập test (27.792 dòng) — con số của Task 7;
      (b) offline chạy lại chính PipelineModel trên ĐÚNG các comment_id xuất hiện
          trong luồng. Mức (b) tách bạch hai nguyên nhân lệch: do MẪU (1000 dòng
          so với 27.792) hay do ĐƯỜNG ỐNG streaming khác lúc huấn luyện.
 4) Độ trễ (latency_ms, kafka_latency_ms, queue_latency_ms) + cửa sổ + watermark.
 5) In 20 dòng mẫu và ghi kết quả ra outputs/tables/ + outputs/stream/<run>/.

Chỉ số dùng ĐÚNG hàm `confusion_matrix` / `metrics_from_cm` của Task 7 (import từ
src/training/train.py) để con số offline và trên luồng so sánh được với nhau.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from pyspark.ml import PipelineModel                                  # noqa: E402
from pyspark.sql import SparkSession, functions as F                  # noqa: E402

from src.common.utils import load_config                              # noqa: E402
from src.training.train import confusion_matrix, metrics_from_cm      # noqa: E402

# Tên topic Kafka chứa kết quả (đọc từ config, xem kafka/topics.yaml / config.yaml)
TOPIC_KEYS = ("topic_raw", "topic_scored", "topic_dlq")

# Bản ghi DLQ không đọc được comment_id thì được ghi rõ là "(khong-co-id)" chứ không để NULL
# (giữ nguyên quy ước của stream_job.py — nếu đổi bên đó thì đổi cả đây).
NO_ID_PLACEHOLDER = "(khong-co-id)"


def local_uri(p: Path | str) -> str:
    return "file://" + str(Path(p).resolve())


# ---------------------------------------------------------------------------
# 2) Đếm message trên Kafka (không cần cài javac — dùng kafka-python)
# ---------------------------------------------------------------------------
def end_offsets(cfg: dict) -> dict[str, dict[str, int]]:
    """Offset cuối (high watermark) của từng partition, từng topic kết quả."""
    from kafka import KafkaConsumer, TopicPartition

    cons = KafkaConsumer(bootstrap_servers=cfg["kafka"]["bootstrap_servers"],
                         group_id=None, request_timeout_ms=10000)
    out: dict[str, dict[str, int]] = {}
    try:
        for key in TOPIC_KEYS:
            topic = cfg["kafka"][key]
            parts = sorted(cons.partitions_for_topic(topic) or [])
            tps = [TopicPartition(topic, p) for p in parts]
            eo = cons.end_offsets(tps) if tps else {}
            out[topic] = {str(tp.partition): int(eo.get(tp, 0)) for tp in tps}
    finally:
        cons.close()
    return out


def sum_offsets(d: dict[str, int]) -> int:
    return int(sum(d.values()))


# ---------------------------------------------------------------------------
# Tiện ích đọc/ghi
# ---------------------------------------------------------------------------
def read_csv_rows(path: Path) -> list[dict]:
    import csv
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> int:
    ap = argparse.ArgumentParser(description="Kiểm chứng job streaming (Task 8)")
    ap.add_argument("--config", default=str(PROJECT_ROOT / "config.yaml"))
    ap.add_argument("--run-name", default="verify1")
    ap.add_argument("--sink-dir", default=None, help="mặc định outputs/stream/<run-name>")
    ap.add_argument("--model-path", default=None, help="mặc định outputs/models/sentiment_pipeline")
    ap.add_argument("--sent-labels", default=None,
                    help="file parquet do replay_producer --labels-out ghi (danh sách comment_id "
                         "đã phát); nhận cả .json {comment_id: ...}")
    ap.add_argument("--extra-valid", type=int, default=0,
                    help="số bản ghi HỢP LỆ gửi ngoài replay_producer (bad-11 + heartbeat + probe), "
                         "in ra ở cuối send_bad_events.py")
    ap.add_argument("--bad-injected", type=int, default=0,
                    help="số ca LỖI cố ý gửi (send_bad_events.py: 10)")
    ap.add_argument("--samples", type=int, default=20, help="số dòng mẫu in ra (mặc định 20)")
    ap.add_argument("--record-baseline", action="store_true",
                    help="chỉ ghi mốc offset Kafka của lần chạy rồi thoát")
    args = ap.parse_args()

    cfg = load_config(args.config)
    sink = Path(args.sink_dir) if args.sink_dir else PROJECT_ROOT / "outputs/stream" / args.run_name
    model_path = Path(args.model_path) if args.model_path else PROJECT_ROOT / "outputs/models/sentiment_pipeline"
    tables = PROJECT_ROOT / "outputs/tables"
    baseline_file = sink / "kafka_offsets_baseline.json"

    if args.record_baseline:
        sink.mkdir(parents=True, exist_ok=True)
        base = end_offsets(cfg)
        baseline_file.write_text(json.dumps(base, indent=2), encoding="utf-8")
        print(f"Đã ghi mốc offset Kafka vào {baseline_file}")
        for topic, parts in base.items():
            print(f"  {topic}: tổng {sum_offsets(parts)} {parts}")
        return 0

    spark = (SparkSession.builder.appName(f"verify-stream-{args.run_name}")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.ui.enabled", "false")
             .config("spark.sql.shuffle.partitions", "4")
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    log = lambda *a: print(*a, flush=True)  # noqa: E731

    labels_idx = {k: int(v) for k, v in cfg["labels"]["index"].items()}     # tên -> 0/1/2
    idx_label = {v: k for k, v in labels_idx.items()}
    class_order = [idx_label[i] for i in sorted(idx_label)]                 # theo chỉ số lớp

    # ------------------------------------------------------------------ đọc ra
    detail = spark.read.parquet(local_uri(sink / "scored_detail"))
    dlq = spark.read.parquet(local_uri(sink / "dlq"))
    n_detail, n_dlq = detail.count(), dlq.count()
    log(f"\n=== {args.run_name}: bảng chi tiết {n_detail} dòng | DLQ {n_dlq} dòng ===")

    # ------------------------------------------------- 1) đối chiếu số lượng
    rows_out: list[dict] = []

    def add(section: str, metric: str, value, note: str = "") -> None:
        rows_out.append({"section": section, "metric": metric, "value": value, "note": note})

    eq_note = "scored + dlq = đã gửi"
    dlq_ids = {r["comment_id"] for r in dlq.select("comment_id").distinct().collect()
               if r["comment_id"] is not None}
    detail_ids = {r["comment_id"] for r in detail.select("comment_id").distinct().collect()
                  if r["comment_id"] is not None}
    n_producer, dlq_from_producer = None, set()
    if args.sent_labels:
        p = Path(args.sent_labels)
        if p.suffix.lower() == ".json":
            obj = json.loads(p.read_text(encoding="utf-8"))
            sent_ids = set(obj) if isinstance(obj, dict) else {str(x) for x in obj}
        else:  # parquet do `replay_producer --labels-out` ghi (cột comment_id/label/rating)
            sent_ids = {r["comment_id"] for r in
                        spark.read.parquet(local_uri(p)).select("comment_id").distinct().collect()}
        n_producer = len(sent_ids)
        # Bản ghi của producer KHÔNG phải lúc nào cũng hợp lệ: replay_producer chỉ kiểm tra
        # có `comment_id` + `text`, còn luật làm sạch (rỗng / < min_chars / > max_chars) do
        # job streaming áp dụng -> phải trừ ra khỏi số kỳ vọng chấm điểm.
        dlq_from_producer = dlq_ids & sent_ids
    if n_producer is not None:
        expected_scored = n_producer - len(dlq_from_producer) + args.extra_valid
        expected_dlq = args.bad_injected + len(dlq_from_producer)
        sent_total = n_producer + args.extra_valid + args.bad_injected
        ok = (n_detail == expected_scored) and (n_dlq == expected_dlq)
        log(f"Đối chiếu: replay_producer phát {n_producer} bản ghi"
            f" | thêm {args.extra_valid} hợp lệ + {args.bad_injected} ca lỗi"
            f"  =>  đã gửi {sent_total}")
        log(f"           kỳ vọng: chấm điểm {expected_scored} (= {n_producer} - "
            f"{len(dlq_from_producer)} bản ghi của producer không qua được luật làm sạch"
            f" + {args.extra_valid}) | DLQ {expected_dlq}")
        log(f"           thực tế: chấm điểm {n_detail} | DLQ {n_dlq}"
            f"  ->  {'KHỚP' if ok else 'LỆCH!'}  ({n_detail} + {n_dlq} = {sent_total})")
        add("reconcile", "producer_sent", n_producer, "từ --sent-labels")
        add("reconcile", "extra_valid_sent", args.extra_valid, "bad-11 + heartbeat + probe")
        add("reconcile", "bad_injected", args.bad_injected)
        add("reconcile", "producer_records_into_dlq", len(dlq_from_producer),
            "bản ghi producer vướng luật làm sạch")
        add("reconcile", "sent_total", sent_total)
        add("reconcile", "scored_detail_rows", n_detail, eq_note)
        add("reconcile", "expected_scored_rows", expected_scored, eq_note)
        add("reconcile", "dlq_rows", n_dlq)
        add("reconcile", "expected_dlq_rows", expected_dlq)
        add("reconcile", "equation", "PASS" if ok else "FAIL",
            f"{n_detail} + {n_dlq} = {sent_total}")
    else:
        log(f"Chưa có --sent-labels: chỉ ghi nhận chấm điểm {n_detail} + DLQ {n_dlq} "
            f"= {n_detail + n_dlq} (không đối chiếu được với số đã gửi)")
        add("reconcile", "scored_detail_rows", n_detail, "chưa có số đã gửi để đối chiếu")
        add("reconcile", "dlq_rows", n_dlq)

    # --- kiểm tra các ca lỗi CỐ Ý (fixture của send_bad_events.py) nằm đúng chỗ ---
    injected = {
        "bad-04": "thieu_truong:text",
        "bad-06": "thieu_truong:event_ts",
        "bad-07": "event_ts_khong_doc_duoc",
        "bad-08": "van_ban_rong_sau_lam_sach",
        "bad-09": f"van_ban_qua_ngan_duoi_{int(cfg['cleaning']['min_chars'])}_ky_tu",
        "bad-10": f"van_ban_qua_dai_tren_{int(cfg['cleaning']['max_chars'])}_ky_tu",
    }
    dlq_map = {r["comment_id"]: r["reason"] for r in dlq.select("comment_id", "reason").collect()}
    n_ok = 0
    for cid, reason in injected.items():
        got = dlq_map.get(cid)
        hit = got == reason
        n_ok += hit
        log(f"  ca lỗi {cid:<8} -> DLQ lý do `{got}`  {'OK' if hit else 'LỆCH (kỳ vọng ' + reason + ')'}")
    add("dlq_cases", "injected_checked", len(injected))
    add("dlq_cases", "injected_matched", n_ok)
    if args.bad_injected == 10:
        # Cột comment_id trong DLQ không để NULL mà ghi rõ "(khong-co-id)" (xem stream_job.dlq_frame)
        n_null = dlq.filter(F.col("comment_id") == NO_ID_PLACEHOLDER).count()
        log(f"  ca lỗi không có comment_id (JSON hỏng x3 + thiếu comment_id): {n_null} dòng "
            f"-> {'OK' if n_null == 4 else 'LỆCH (kỳ vọng 4)'}")
        add("dlq_cases", "null_id_rows", n_null, "kỳ vọng 4 = 3 JSON hỏng + 1 thiếu comment_id")
    # bad-11 (hợp lệ, lạc hậu) + heartbeat + probe phải nằm ở bảng CHI TIẾT, không vào DLQ
    for cid in ("bad-11", "probe-late"):
        log(f"  {cid:<11} ở bảng chi tiết: {cid in detail_ids} | ở DLQ: {cid in dlq_ids}")
        add("dlq_cases", f"{cid}_in_detail", cid in detail_ids, "bản ghi hợp lệ, không vào DLQ")
        add("dlq_cases", f"{cid}_in_dlq", cid in dlq_ids, "kỳ vọng False")
    n_hb = len([c for c in detail_ids if c and c.startswith("hb-")])
    log(f"  heartbeat (hb-*) chấm điểm được: {n_hb}")
    add("dlq_cases", "heartbeat_scored", n_hb)

    # ---------------------------------------------------- 2) đếm trên Kafka
    if baseline_file.exists():
        base = json.loads(baseline_file.read_text(encoding="utf-8"))
        now = end_offsets(cfg)
        for key in ("topic_scored", "topic_dlq"):
            topic = cfg["kafka"][key]
            before, after = sum_offsets(base.get(topic, {})), sum_offsets(now.get(topic, {}))
            log(f"Kafka `{topic}`: offset cuối {before} -> {after} = +{after - before} message")
            add("kafka", f"{topic}_messages", after - before, "chênh lệch offset cuối so với mốc")
    else:
        log(f"Không thấy {baseline_file} — bỏ qua đếm message Kafka "
            f"(ghi mốc trước khi chạy bằng --record-baseline)")

    # ------------------------------------------- 3) DLQ theo lý do + từng ca
    log("\n--- DLQ theo lý do ---")
    dlq_reason = (dlq.groupBy("reason").count().orderBy(F.desc("count")).collect())
    for r in dlq_reason:
        log(f"  {r['reason']:<34} {r['count']}")
        add("dlq", f"reason:{r['reason']}", r["count"])
    dlq_rows = (dlq.select("comment_id", "reason", "kafka_partition", "kafka_offset", "event_ts")
                .orderBy("kafka_partition", "kafka_offset").collect())
    write_csv(tables / "stream_dlq_rows.csv",
              [{"comment_id": r["comment_id"], "reason": r["reason"],
                "kafka_partition": r["kafka_partition"], "kafka_offset": r["kafka_offset"],
                "event_ts": r["event_ts"]} for r in dlq_rows],
              ["comment_id", "reason", "kafka_partition", "kafka_offset", "event_ts"])
    log(f"(đã ghi {len(dlq_rows)} dòng DLQ vào outputs/tables/stream_dlq_rows.csv)")

    # ------------------------------------ 4) ghép nhãn thật -> chỉ số trên luồng
    labels = (spark.read.parquet(local_uri(PROJECT_ROOT / "data/processed/eval_labels.parquet"))
              .select("comment_id", F.col("label").alias("true_label")))
    joined = detail.join(labels, on="comment_id", how="inner")
    cols = ["comment_id", "stream_id", "pred_class", "pred_label", "confidence", "text_len",
            "latency_ms", "kafka_latency_ms", "queue_latency_ms", "event_time", "event_date",
            "event_hour", "kafka_partition", "kafka_offset", "true_label"]
    pdf = joined.select(*cols).toPandas()
    pdf["true_idx"] = pdf["true_label"].map(labels_idx).astype(int)
    pdf["pred_idx"] = pdf["pred_class"].astype(int)
    n_eval = len(pdf)
    log(f"\n--- Chỉ số trên luồng (ghép được nhãn thật cho {n_eval}/{n_detail} dòng) ---")
    cm_stream = confusion_matrix(pdf["true_idx"].values, pdf["pred_idx"].values, len(class_order))
    overall_s, per_class_s = metrics_from_cm(cm_stream, class_order)
    log(f"  accuracy {overall_s['accuracy']:.4f} | macro-F1 {overall_s['macro_f1']:.4f} | "
        f"weighted-F1 {overall_s['weighted_f1']:.4f} (n={overall_s['n']})")
    for lab in class_order:
        m = per_class_s[lab]
        log(f"    {lab:<9} P {m['precision']:.4f}  R {m['recall']:.4f}  F1 {m['f1']:.4f}  "
            f"support {m['support']}")
    add("stream_metrics", "n_eval", n_eval, "số dòng ghép được nhãn thật")
    for k in ("accuracy", "macro_f1", "weighted_f1"):
        add("stream_metrics", k, round(overall_s[k], 6))
    for lab in class_order:
        for k in ("precision", "recall", "f1", "support"):
            add("stream_metrics", f"{lab}_{k}", round(per_class_s[lab][k], 6))

    per_class_rows = []
    for lab in class_order:
        m = per_class_s[lab]
        per_class_rows.append({"scope": "stream", "label": lab,
                               **{k: round(m[k], 6) for k in ("precision", "recall", "f1")},
                               "support": m["support"]})
    # (a-bis) P/R/F1 từng lớp của offline trên toàn tập test — lấy nguyên từ Task 7
    for r in read_csv_rows(tables / "per_class_metrics.csv"):
        if r["model"] == "LogisticRegression" and r["split"] == "test":
            per_class_rows.append({"scope": "offline_full_test", "label": r["label"],
                                   "precision": float(r["precision"]), "recall": float(r["recall"]),
                                   "f1": float(r["f1"]), "support": int(r["support"])})

    # --------------------------------- 5) offline: toàn bộ test + đúng tập id
    mr = [r for r in read_csv_rows(tables / "model_results.csv")
          if r["model"] == "LogisticRegression" and r["split"] == "test"]
    if mr:
        r = mr[0]
        log(f"\n--- Offline (a) TOÀN BỘ tập test, {r['n']} dòng: accuracy {float(r['accuracy']):.4f} | "
            f"macro-F1 {float(r['macro_f1']):.4f} | weighted-F1 {float(r['weighted_f1']):.4f}")
        for k in ("accuracy", "macro_f1", "weighted_f1", "n"):
            add("offline_full_test", k, r[k], "outputs/tables/model_results.csv (Task 7)")
    else:
        log("CẢNH BÁO: không thấy dòng LogisticRegression/test trong model_results.csv")

    # (b) chạy lại chính PipelineModel trên đúng các comment_id có trong luồng:
    #     nếu chỉ số trùng khớp với luồng thì đường ống streaming = đường ống huấn luyện.
    # PHẢI có tiền tố file:// — mặc định của Spark ở máy này là HDFS (fs.defaultFS) nên
    # đường dẫn trần sẽ bị hiểu là hdfs://localhost:9000/home/hadoop/capstone/...
    model = PipelineModel.load(local_uri(model_path))
    test_df = (spark.read.parquet(local_uri(PROJECT_ROOT / "data/processed/test.parquet"))
               .select("comment_id", "text", "label"))
    same_ids = test_df.join(detail.select("comment_id").distinct(), on="comment_id", how="inner")
    off = (model.transform(same_ids)
           .select("comment_id", F.col("prediction").cast("int").alias("off_idx"))
           .toPandas())
    cmp_df = pdf.merge(off, on="comment_id", how="inner")
    agree = int((cmp_df["off_idx"] == cmp_df["pred_idx"]).sum())
    log(f"\n--- Offline (b) chạy lại PipelineModel trên ĐÚNG {len(cmp_df)} comment_id của luồng ---")
    log(f"  hai bên dự đoán GIỐNG nhau: {agree}/{len(cmp_df)} "
        f"({100.0 * agree / max(len(cmp_df), 1):.2f}%)")
    cm_off = confusion_matrix(cmp_df["true_idx"].values, cmp_df["off_idx"].values, len(class_order))
    overall_o, per_class_o = metrics_from_cm(cm_off, class_order)
    log(f"  accuracy {overall_o['accuracy']:.4f} | macro-F1 {overall_o['macro_f1']:.4f} | "
        f"weighted-F1 {overall_o['weighted_f1']:.4f} (n={overall_o['n']})")
    for lab in class_order:
        log(f"    {lab:<9} P {per_class_o[lab]['precision']:.4f}  R {per_class_o[lab]['recall']:.4f}"
            f"  F1 {per_class_o[lab]['f1']:.4f}  support {per_class_o[lab]['support']}")
        per_class_rows.append({"scope": "offline_same_ids", "label": lab,
                               **{k: round(per_class_o[lab][k], 6)
                                  for k in ("precision", "recall", "f1")},
                               "support": per_class_o[lab]["support"]})
    add("offline_same_ids", "n", overall_o["n"], "cùng comment_id với luồng")
    add("equivalence", "rows_compared", len(cmp_df))
    add("equivalence", "rows_agree", agree)
    add("equivalence", "agreement_pct", round(100.0 * agree / max(len(cmp_df), 1), 4))
    for k in ("accuracy", "macro_f1", "weighted_f1"):
        add("offline_same_ids", k, round(overall_o[k], 6))
    if n_eval:
        add("delta_vs_offline_same_ids", "macro_f1",
            round(overall_s["macro_f1"] - overall_o["macro_f1"], 6), "luồng - offline(cùng id)")
    add("delta_vs_offline_full_test", "macro_f1",
        round(overall_s["macro_f1"] - float(mr[0]["macro_f1"] if mr else 0.0), 6),
        "luồng - offline(toàn bộ test)")

    # --------------------------------------------------------- 6) độ trễ
    lat = detail.agg(
        F.min("latency_ms").alias("lat_min"),
        F.expr("percentile_approx(latency_ms, 0.5)").alias("lat_p50"),
        F.expr("percentile_approx(latency_ms, 0.95)").alias("lat_p95"),
        F.expr("percentile_approx(latency_ms, 0.99)").alias("lat_p99"),
        F.max("latency_ms").alias("lat_max"),
        F.expr("percentile_approx(kafka_latency_ms, 0.5)").alias("kl_p50"),
        F.max("kafka_latency_ms").alias("kl_max"),
        F.min("queue_latency_ms").alias("ql_min"),
        F.expr("percentile_approx(queue_latency_ms, 0.5)").alias("ql_p50"),
        F.expr("percentile_approx(queue_latency_ms, 0.95)").alias("ql_p95"),
        F.countDistinct("processing_ts").alias("n_processing_ts"),
    ).collect()[0]
    log("\n--- Độ trễ (mỗi dòng: latency_ms = lúc xử lý - event_time) ---")
    log(f"  latency_ms        p50 {lat['lat_p50']}  p95 {lat['lat_p95']}  p99 {lat['lat_p99']}  "
        f"max {lat['lat_max']}  min {lat['lat_min']}")
    log(f"  kafka_latency_ms  p50 {lat['kl_p50']}  max {lat['kl_max']}   "
        f"(producer -> broker, từ cột timestamp của Kafka)")
    log(f"  queue_latency_ms  min {lat['ql_min']}  p50 {lat['ql_p50']}  p95 {lat['ql_p95']}   "
        f"(broker -> xử lý xong)")
    log(f"  số giá trị processing_ts khác nhau: {lat['n_processing_ts']} "
        f"(= số micro-batch có ghi dữ liệu)")
    for k, v in lat.asDict().items():
        add("latency", k, v)

    # --------------------------------------------------- 7) cửa sổ + watermark
    for name in ("window_1min", "window_sliding_10s"):
        w = spark.read.parquet(local_uri(sink / name))
        n_w = w.count()
        log(f"\n--- {name}: {n_w} dòng ---")
        (w.orderBy(F.desc("n_comments")).show(6, truncate=False))
        add("windows", f"{name}_rows", n_w)
        if n_w:
            # In bằng date_format (UTC của session) — kiểu timestamp khi collect về Python bị
            # đổi sang múi giờ của máy, dễ gây nhầm với mốc UTC trong .show().
            s = w.agg(F.sum("n_comments").alias("n"),
                      F.date_format(F.min("window_start"), "yyyy-MM-dd HH:mm:ss").alias("ws"),
                      F.date_format(F.max("window_end"), "yyyy-MM-dd HH:mm:ss").alias("we")).collect()[0]
            log(f"  tổng n_comments {s['n']} | cửa sổ từ {s['ws']} đến {s['we']} (UTC)")
            add("windows", f"{name}_comments", s["n"], f"{s['ws']} .. {s['we']} UTC")

    # --- Watermark: hai bản ghi đến muộn có số phận KHÁC NHAU, kiểm bằng dữ liệu ---
    #   bad-11     đến trong batch đầu (lúc đó chưa có watermark)  -> PHẢI có cửa sổ
    #   probe-late đến sau khi watermark đã tiến 10 phút           -> PHẢI bị bỏ
    # Cột numRowsDroppedByWatermark của QueryProgress trong lần chạy này báo 0, nên kết luận
    # phải lấy từ đối chiếu dữ liệu, không lấy từ bộ đếm.
    late_detail = (detail.filter(F.col("comment_id").isin("bad-11", "probe-late"))
                   .select("comment_id", "stream_id",
                           F.date_trunc("minute", F.col("event_time")).alias("window_start")))
    w1 = spark.read.parquet(local_uri(sink / "window_1min"))
    hits = {r["comment_id"] for r in late_detail.join(
        w1.select("stream_id", "window_start"), ["stream_id", "window_start"], "left_semi").collect()}
    log("\n--- Watermark: số phận hai bản ghi đến muộn (đối chiếu trực tiếp) ---")
    for cid in ("bad-11", "probe-late"):
        log(f"  {cid:<11} có mặt trong cửa sổ 1 phút: {cid in hits}")
        add("watermark_late", f"{cid}_in_window_1min", cid in hits,
            "bad-11 đến cùng batch đầu; probe-late đến sau khi watermark đã tiến 10 phút")
    hb_min = (spark.read.parquet(local_uri(sink / "window_sliding_10s"))
              .filter(F.col("stream_id") == "heartbeat")
              .agg(F.date_format(F.min("window_start"), "yyyy-MM-dd HH:mm:ss")).collect()[0][0])
    log(f"  cửa sổ trượt sớm nhất của stream_id 'heartbeat' (chỉ chứa heartbeat + probe-late): "
        f"{hb_min} UTC  -> probe-late (18:03) không có cửa sổ nào")
    add("watermark_late", "heartbeat_sliding_min_start", hb_min)
    batch_csv = tables / "stream_batches.csv"
    if batch_csv.exists():
        rows = [r for r in read_csv_rows(batch_csv) if r["run_name"] == args.run_name]
        dropped: dict[str, int] = {}
        for r in rows:
            dropped[r["query_name"]] = dropped.get(r["query_name"], 0) + int(r["num_rows_dropped_by_watermark"])
        log("\n--- Watermark: số dòng bị bỏ vì đến muộn (theo query) ---")
        for q, v in sorted(dropped.items()):
            log(f"  {q:<18} {v}")
        add("watermark", "dropped_total", sum(dropped.values()), "numRowsDroppedByWatermark")
        for q, v in sorted(dropped.items()):
            add("watermark", f"dropped:{q}", v, "outputs/tables/stream_batches.csv")

    # ------------------------------------------------------- 8) 20 dòng mẫu
    log(f"\n--- {args.samples} dòng mẫu (không có văn bản gốc: privacy keep_text=false) ---")
    sample = pdf.head(args.samples).to_dict("records")   # list[dict] — duyệt DataFrame là duyệt TÊN CỘT
    log(f"{'comment_id':<12} {'true':<9} {'pred':<9} {'conf':>6} {'lat_ms':>8} "
        f"{'text_len':>8}  {'event_time':<20} stream_id")
    for r in sample:
        log(f"{r['comment_id']:<12} {r['true_label']:<9} {r['pred_label']:<9} "
            f"{float(r['confidence']):>6.3f} {int(r['latency_ms']):>8} "
            f"{int(r['text_len']):>8}  {str(r['event_time'])[:19]:<20} {r['stream_id']}")
    sample_cols = ["comment_id", "true_label", "pred_label", "confidence", "latency_ms",
                   "kafka_latency_ms", "queue_latency_ms", "text_len", "event_time", "stream_id",
                   "kafka_partition", "kafka_offset"]
    write_csv(tables / "stream_sample_rows.csv",
              [{k: r[k] for k in sample_cols} for r in sample], sample_cols)
    log("(đã ghi 20 dòng mẫu vào outputs/tables/stream_sample_rows.csv)")

    # -------------------------------------------------------------- ghi ra file
    write_csv(tables / "stream_verification.csv", rows_out,
              ["section", "metric", "value", "note"])
    write_csv(tables / "stream_per_class_metrics.csv", per_class_rows,
              ["scope", "label", "precision", "recall", "f1", "support"])
    summary = {
        "run_name": args.run_name,
        "sink_dir": str(sink),
        "n_scored": n_detail, "n_dlq": n_dlq,
        "n_eval_joined": int(n_eval),
        "stream": {k: overall_s[k] for k in ("n", "accuracy", "macro_f1", "weighted_f1")},
        "offline_same_ids": {k: overall_o[k] for k in ("n", "accuracy", "macro_f1", "weighted_f1")},
        "agreement_pct": round(100.0 * agree / max(len(cmp_df), 1), 4),
        "per_class_stream": {lab: {k: round(per_class_s[lab][k], 6)
                                   for k in ("precision", "recall", "f1", "support")}
                             for lab in class_order},
        "latency": {k: (int(v) if v is not None else None) for k, v in lat.asDict().items()},
        "tables": ["outputs/tables/stream_verification.csv",
                   "outputs/tables/stream_per_class_metrics.csv",
                   "outputs/tables/stream_sample_rows.csv",
                   "outputs/tables/stream_dlq_rows.csv"],
    }
    (sink / "verification.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    log(f"\nĐã ghi: outputs/tables/stream_verification.csv, stream_per_class_metrics.csv, "
        f"stream_sample_rows.csv, stream_dlq_rows.csv, {sink}/verification.json")
    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
