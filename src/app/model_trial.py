"""model_trial.py — Chương trình thử nghiệm mô hình (prototype, không cần Kafka/Streamlit).

Mục đích: chứng minh mô hình đã lưu hoạt động trên văn bản mới bằng ĐÚNG đường đi
của hệ thống thật:

    văn bản thô -> clean_text() (dùng chung) -> PipelineModel.transform() -> nhãn + xác suất

Đây là phần "thử nghiệm mô hình"; app hoàn chỉnh (dashboard) nằm ở `src/app/app.py`.
Chương trình này **KHÔNG** chứng minh mô hình tốt trên livestream thật — dữ liệu vẫn
là review IMDb, nhãn suy từ rating (xem `outputs/modeling_summary.md`).

Ba chế độ:

  1. Tương tác (mặc định) — nhập từng bình luận, gõ `:q` để thoát, `:sample` để xem ví dụ:
         bash scripts/run_model_trial.sh
  2. Chấm điểm vài câu / file:
         bash scripts/run_model_trial.sh --text "not bad at all"
         bash scripts/run_model_trial.sh --examples
         bash scripts/run_model_trial.sh --file comments.txt
  3. Đo trên một mẫu của tập test (có nhãn thật) và ghi báo cáo:
         bash scripts/run_model_trial.sh --test-sample 200
     Sinh ra `outputs/tables/model_trial_predictions.csv`,
     `outputs/tables/model_trial_summary.csv`, `outputs/model_trial_report.md`.

Quy ước (CLAUDE.md):
  - Dùng đúng `clean_text()` của lúc huấn luyện và streaming (§4) — không viết lại.
  - Quy tắc loại văn bản giống DLQ của streaming: rỗng / < min_chars / > max_chars.
  - Không hard-code đường dẫn/tham số: đọc `config.yaml` mục `model_trial`.
  - Không ghi văn bản vào CSV/report trừ khi có `--keep-text` (§7). Chỉ dùng
    `--keep-text` với dữ liệu công khai (IMDb CC0); KHÔNG dùng với bình luận thật.
  - Mọi con số trong report sinh từ chính lần chạy này, không viết tay (§9).
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Cho phép chạy từ bất kỳ thư mục nào: thêm gốc dự án (2 cấp trên file này).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pyspark.ml import PipelineModel                              # noqa: E402
from pyspark.sql import DataFrame, SparkSession, functions as F   # noqa: E402

from src.common.metrics import confusion_matrix, metrics_from_cm  # noqa: E402
from src.common.text_cleaning import clean_text                   # noqa: E402
from src.common.utils import PROJECT_ROOT as _PR, load_config     # noqa: E402

assert _PR == PROJECT_ROOT, "PROJECT_ROOT tính từ file này phải khớp src.common.utils"

LABELS = ["negative", "neutral", "positive"]
LABEL_VI = {"negative": "tiêu cực", "neutral": "trung lập", "positive": "tích cực"}


# ---------------------------------------------------------------------------
# Tiện ích chung
# ---------------------------------------------------------------------------
def resolve(path_str: str | Path) -> Path:
    """Đường dẫn tương đối tính từ gốc dự án (không hard-code /home/hadoop/...)."""
    p = Path(path_str)
    return p if p.is_absolute() else PROJECT_ROOT / p


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def one_line(text: str, width: int | None = None) -> str:
    """Gộp xuống dòng thành khoảng trắng để in bảng cho gọn."""
    s = " ".join((text or "").split())
    return s if width is None else (s[: width - 1] + "…" if len(s) > width else s)


def text_problem(text: str, cleaning: dict) -> str | None:
    """Trả về lý do loại văn bản (giống hệt quy tắc DLQ của streaming), hoặc None.

    Hàm thuần Python để test được không cần Spark. Thứ tự kiểm tra khớp
    `src/streaming/stream_job.py` (rỗng -> quá ngắn -> quá dài).
    """
    if not text or not text.strip():
        return "van_ban_rong_sau_lam_sach"
    n = len(text)
    min_chars = int(cleaning["min_chars"])
    max_chars = int(cleaning["max_chars"])
    if n < min_chars:
        return f"van_ban_qua_ngan_duoi_{min_chars}_ky_tu"
    if n > max_chars:
        return f"van_ban_qua_dai_tren_{max_chars}_ky_tu"
    return None


# ---------------------------------------------------------------------------
# Nạp mô hình + chấm điểm
# ---------------------------------------------------------------------------
def load_trial_model(spark: SparkSession, cfg: dict):
    """Nạp PipelineModel đã lưu + metadata. Trả về (model, meta, idx2lab)."""
    model_path = resolve(cfg["training"]["model_out"])
    meta_path = Path(str(model_path) + "_metadata.json")
    if not model_path.exists():
        raise FileNotFoundError(f"Không thấy mô hình: {model_path}")
    if not meta_path.exists():
        raise FileNotFoundError(f"Không thấy metadata: {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    # Thiếu tiền tố file:// thì Spark đi tìm trên HDFS (đã gặp thật ở Task 8).
    model = PipelineModel.load("file://" + str(model_path))
    # metadata ghi {"negative": 0, ...} -> đảo thành {0: "negative", ...}
    idx2lab = {int(v): k for k, v in meta["label_index"].items()}
    return model, meta, idx2lab


def cleaned_df(spark: SparkSession, rows: list[dict], abbreviations: dict) -> DataFrame:
    """Tạo DataFrame có cột `text` đã làm sạch bằng ĐÚNG hàm dùng lúc huấn luyện."""
    df = spark.createDataFrame(rows)
    return df.withColumn("text", clean_text(F.col("raw"), abbreviations))


def score_dataframe(model, df: DataFrame, idx2lab: dict) -> tuple[list[dict], float]:
    """Chấm điểm cả DataFrame, trả về (danh sách dự đoán, số giây)."""
    t0 = time.perf_counter()
    if "row_id" not in df.columns:
        # Dữ liệu đọc từ parquet không có row_id — thêm để giữ thứ tự khi in/ghi.
        df = df.withColumn("row_id", F.monotonically_increasing_id())
    out = model.transform(df)
    has_prob = "probability" in out.columns
    cols = ["row_id", "comment_id", "raw", "text", "label_true", "prediction"]
    cols = [c for c in cols if c in out.columns]
    if has_prob:
        cols.append("probability")
    collected = out.select(*cols).collect()
    elapsed = time.perf_counter() - t0

    rows: list[dict] = []
    for r in collected:
        d = r.asDict()
        pred_idx = int(d["prediction"])
        label_pred = idx2lab[pred_idx]
        if has_prob:
            probs = {idx2lab[i]: float(p) for i, p in enumerate(d["probability"])}
        else:
            probs = {lab: float("nan") for lab in idx2lab.values()}
        rows.append({
            "row_id": int(d["row_id"]),
            "comment_id": d.get("comment_id") or "",
            "raw": d.get("raw") or "",
            "text": d.get("text") or "",
            "label_true": d.get("label_true") or "",
            "pred_idx": pred_idx,
            "label_pred": label_pred,
            "probs": probs,
            "confidence": probs.get(label_pred, float("nan")),
        })
    return rows, elapsed


# ---------------------------------------------------------------------------
# In kết quả
# ---------------------------------------------------------------------------
def print_header(meta: dict) -> None:
    test = meta.get("metrics", {}).get("test", {})
    idx = ", ".join(f"{k}={v}" for k, v in meta["label_index"].items())
    print("=" * 78)
    print(" THỬ NGHIỆM MÔ HÌNH — PROTOTYPE (không cần Kafka/Streamlit)")
    print("=" * 78)
    print(f" Mô hình : {meta.get('model_name', '?')}")
    print(f" Lưu lúc : {meta.get('saved_at', '?')} (Spark {meta.get('spark_version', '?')})")
    print(f" Nhãn    : {idx}")
    if test:
        print(f" Khi huấn luyện, trên tập test: accuracy {test.get('accuracy', 0):.4f} | "
              f"macro-F1 {test.get('macro_f1', 0):.4f} | {test.get('n', 0):,} dòng")
    print(" Lưu ý   : đây là đánh giá trên review IMDb (nhãn SUY TỪ rating),")
    print("           KHÔNG phải bình luận livestream thật.")
    print("=" * 78)


def print_predictions(rows: list[dict], show_text: bool = True) -> None:
    if not rows:
        print("  (không có dòng hợp lệ)")
        return
    print(f"\n{'#':>2}  {'Bình luận':<50}  {'Dự đoán':<9}  "
          f"{'neg':>5} {'neu':>5} {'pos':>5}  {'Tin cậy':>8}")
    print("-" * 100)
    for i, r in enumerate(rows, 1):
        text = one_line(r["raw"] if show_text else r.get("comment_id", ""), 50)
        p = r["probs"]
        print(f"{i:>2}  {text:<50}  {r['label_pred']:<9}  "
              f"{p.get('negative', float('nan')):>5.2f} "
              f"{p.get('neutral', float('nan')):>5.2f} "
              f"{p.get('positive', float('nan')):>5.2f}  "
              f"{r['confidence']:>7.1%}")


def print_metrics(overall: dict, per_class: dict, cm: np.ndarray, labels: list[str]) -> None:
    print(f"\nĐO TRÊN MẪU TẬP TEST (N = {overall['n']:,})")
    print(f"  Accuracy    : {overall['accuracy']:.4f}")
    print(f"  Macro-F1    : {overall['macro_f1']:.4f}")
    print(f"  Weighted-F1 : {overall['weighted_f1']:.4f}")
    print(f"\n  {'Lớp':<10} {'Precision':>10} {'Recall':>8} {'F1':>8} "
          f"{'Support':>8} {'Share':>8}")
    print("  " + "-" * 60)
    for lab in labels:
        m = per_class[lab]
        print(f"  {lab:<10} {m['precision']:>10.4f} {m['recall']:>8.4f} "
              f"{m['f1']:>8.4f} {m['support']:>8,} {m['share']:>8.2%}")
    print("\n  Confusion matrix (hàng = nhãn thật, cột = dự đoán):")
    header = "  " + f"{'':>14}" + "".join(f"{'pred_' + lab:>14}" for lab in labels)
    print(header)
    for i, lab in enumerate(labels):
        print(f"  {'true_' + lab:>14}" + "".join(f"{int(cm[i, j]):>14}" for j in range(len(labels))))


# ---------------------------------------------------------------------------
# Ghi file kết quả
# ---------------------------------------------------------------------------
def prediction_records(rows: list[dict], run_at: str, mode: str, split: str,
                       keep_text: bool) -> list[dict]:
    recs = []
    for i, r in enumerate(rows, 1):
        true = r.get("label_true") or ""
        rec = {
            "run_at": run_at,
            "mode": mode,
            "split": split,
            "row": i,
            "comment_id": r.get("comment_id", ""),
            "label_true": true,
            "label_pred": r["label_pred"],
            "prob_negative": round(r["probs"].get("negative", float("nan")), 6),
            "prob_neutral": round(r["probs"].get("neutral", float("nan")), 6),
            "prob_positive": round(r["probs"].get("positive", float("nan")), 6),
            "confidence": round(r["confidence"], 6),
            "correct": (true == r["label_pred"]) if true else "",
        }
        if keep_text:
            rec["text_excerpt"] = one_line(r["text"], 200)
        recs.append(rec)
    return recs


def write_predictions(path: Path, recs: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(recs).to_csv(path, index=False, encoding="utf-8")


def append_summary(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([row])
    if path.exists():
        old = pd.read_csv(path)
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(path, index=False, encoding="utf-8")


def write_report(path: Path, ctx: dict) -> None:
    """Báo cáo tiếng Anh, mọi số sinh từ lần chạy này — dán được vào Final Report."""
    o, pc, cm, labels = ctx["overall"], ctx["per_class"], ctx["cm"], ctx["labels"]
    lines: list[str] = []
    lines += [
        "# Model Trial Report (prototype)",
        "",
        f"Generated at **{ctx['run_at']}** by `src/app/model_trial.py`.",
        "",
        f"- Command: `{ctx['command']}`",
        f"- Model: **{ctx['model_name']}** (saved {ctx['saved_at']}, Spark {ctx['spark_version']})",
        f"- Evaluation split: **{ctx['split']}** — deterministic sample ordered by `crc32(comment_id)`",
        f"- Sample size: **{o['n']:,}** comments",
        "",
        "> This program is a **model trial / prototype**, not the complete application.",
        "> It runs the same text-cleaning function and the same saved `PipelineModel`",
        "> used by the streaming job. It does not use Kafka or the dashboard.",
        "",
        "## 1. Metrics on the sample",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Accuracy | {o['accuracy']:.4f} |",
        f"| Macro-F1 | {o['macro_f1']:.4f} |",
        f"| Weighted-F1 | {o['weighted_f1']:.4f} |",
        "",
        "## 2. Per-class metrics",
        "",
        "| Label | Precision | Recall | F1 | Support | Share |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for lab in labels:
        m = pc[lab]
        lines.append(f"| {lab} | {m['precision']:.4f} | {m['recall']:.4f} | "
                     f"{m['f1']:.4f} | {m['support']:,} | {m['share']:.2%} |")

    lines += ["", "## 3. Confusion matrix (rows = true, columns = predicted)", "",
              "| true \\ predicted | " + " | ".join(labels) + " |",
              "|---|" + "---:|" * len(labels)]
    for i, lab in enumerate(labels):
        lines.append(f"| **{lab}** | " + " | ".join(str(int(cm[i, j])) for j in range(len(labels))) + " |")

    lines += ["", f"## 4. Example predictions (first {len(ctx['examples'])})", ""]
    if ctx["keep_text"]:
        lines += ["| # | Comment (cleaned, truncated) | True | Predicted | Confidence |",
                  "|---:|---|---|---|---:|"]
        for i, r in enumerate(ctx["examples"], 1):
            lines.append(f"| {i} | {one_line(r['text'], 110)} | "
                         f"{r.get('label_true') or '—'} | {r['label_pred']} | {r['confidence']:.1%} |")
    else:
        lines += ["_Text is not included (`--keep-text` was not passed). "
                  "Only aggregate results and label counts are stored._", ""]
        lines += ["| # | comment_id | True | Predicted | Confidence |",
                  "|---:|---|---|---|---:|"]
        for i, r in enumerate(ctx["examples"], 1):
            lines.append(f"| {i} | {r.get('comment_id') or '—'} | "
                         f"{r.get('label_true') or '—'} | {r['label_pred']} | {r['confidence']:.1%} |")

    lines += [
        "",
        "## 5. Caveats — read before citing these numbers",
        "",
        "1. **Labels are inferred from IMDb ratings** (1–4 negative, 5–6 neutral, 7–10 positive),",
        "   not human sentiment annotations. The `neutral` class is noisy; its F1 is the weakest.",
        "2. **The saved model was trained on the 20% deterministic subset** used in Task 7",
        f"   ({ctx['train_rows']:,} training rows). `config.yaml` now defaults to 64% for future",
        "   retraining, but the model used here was **not** retrained on 64%.",
        "3. **The test split was already used once** for the final evaluation",
        "   (`outputs/tables/test_eval_log.csv`). This run re-evaluates the frozen model on a",
        "   deterministic sample; it was **not** used to select or tune the model.",
        "4. **IMDb reviews are not live-stream comments.** The macro-F1 in this report must not",
        "   be promised for real livestream data. See `outputs/modeling_summary.md` §5.",
        f"5. The sample has {o['n']:,} rows, so sampling error applies; no confidence interval or",
        "   statistical significance test was computed.",
        "",
        "## 6. Reproduce",
        "",
        "```bash",
        ctx["command"],
        "```",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Các chế độ chạy
# ---------------------------------------------------------------------------
def collect_texts(args: argparse.Namespace, cfg: dict) -> list[str]:
    texts: list[str] = list(args.text or [])
    if args.file:
        path = Path(args.file)
        lines = path.read_text(encoding="utf-8").splitlines()
        texts += [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
    if args.examples:
        texts += list(cfg["dashboard"]["try_it_examples"])
    return texts


def run_batch(spark: SparkSession, model, meta: dict, idx2lab: dict, cfg: dict,
              texts: list[str], args: argparse.Namespace) -> int:
    cl = cfg["cleaning"]
    rows_in = [{"row_id": i, "comment_id": "", "raw": t, "label_true": ""}
               for i, t in enumerate(texts)]
    df = cleaned_df(spark, rows_in, cl["abbreviations"])
    scored, elapsed = score_dataframe(model, df, idx2lab)

    skipped = []
    valid = []
    for r in scored:
        reason = text_problem(r["text"], cl)
        if reason:
            skipped.append((r["raw"], reason))
        else:
            valid.append(r)
    for raw, reason in skipped:
        print(f"  ⚠ Bỏ qua ({reason}): {one_line(raw, 70)}")
    print_predictions(valid)
    n = max(len(scored), 1)
    print(f"\n  Thời gian chấm điểm: {elapsed:.2f} s cho {len(scored)} dòng "
          f"({elapsed * 1000 / n:.0f} ms/dòng)")

    if not args.no_write and valid:
        run_at = now_iso()
        out = resolve(cfg["model_trial"]["batch_predictions_out"])
        recs = prediction_records(valid, run_at, "batch", "-", args.keep_text)
        write_predictions(out, recs)
        print(f"  Đã ghi: {out}")
    return 0


def load_sample(spark: SparkSession, cfg: dict, split: str, n: int) -> DataFrame:
    """Lấy mẫu tất định: sắp theo crc32(comment_id) rồi lấy N dòng đầu.

    Tất định (chạy lại ra đúng mẫu cũ), trải đều theo id, không phụ thuộc thứ tự
    file — cùng nguyên tắc đã dùng ở Task 6/11.
    """
    path = resolve(cfg["paths"][split])
    if not path.exists():
        raise FileNotFoundError(f"Không thấy dữ liệu {split}: {path}")
    df = (spark.read.parquet("file://" + str(path))
          .select("comment_id", "text", "label")
          .withColumnRenamed("label", "label_true")
          .withColumn("raw", F.col("text")))
    if n > 0:
        df = df.orderBy(F.crc32("comment_id")).limit(n)
    return df


def run_test_sample(spark: SparkSession, model, meta: dict, idx2lab: dict, cfg: dict,
                    args: argparse.Namespace) -> int:
    mt = cfg["model_trial"]
    n = args.test_sample
    max_n = int(mt["max_sample_rows"])
    if n > max_n:
        print(f"LỖI: --test-sample {n} vượt trần {max_n:,} dòng (config model_trial.max_sample_rows).",
              file=sys.stderr)
        return 2

    split = args.split or mt["split"]
    cl = cfg["cleaning"]
    print(f"\nLấy mẫu tất định {n:,} dòng từ tập '{split}' ...", flush=True)
    df = load_sample(spark, cfg, split, n)
    df = df.withColumn("text", clean_text(F.col("text"), cl["abbreviations"]))
    scored, elapsed = score_dataframe(model, df, idx2lab)
    if not scored:
        print("LỖI: không có dòng nào trong mẫu.", file=sys.stderr)
        return 1

    # Quy tắc DLQ: văn bản không hợp lệ không được chấm điểm (giống streaming).
    valid = [r for r in scored if text_problem(r["text"], cl) is None]
    n_invalid = len(scored) - len(valid)
    if n_invalid:
        print(f"  ⚠ {n_invalid} dòng không hợp lệ theo quy tắc DLQ — loại khỏi chỉ số.")
    # Sắp theo comment_id để file kết quả tất định (row_id của Spark không đảm bảo thứ tự).
    valid.sort(key=lambda r: r["comment_id"])

    label_index = {lab: int(i) for lab, i in cfg["labels"]["index"].items()}
    y_true = np.array([label_index[r["label_true"]] for r in valid], dtype=int)
    y_pred = np.array([r["pred_idx"] for r in valid], dtype=int)
    cm = confusion_matrix(y_true, y_pred, len(LABELS))
    overall, per_class = metrics_from_cm(cm, LABELS)

    print_metrics(overall, per_class, cm, LABELS)
    print(f"\n  Thời gian chấm điểm: {elapsed:.2f} s cho {len(scored):,} dòng "
          f"({elapsed * 1000 / max(len(scored), 1):.0f} ms/dòng)")

    run_at = now_iso()
    command = shlex.join(["bash", "scripts/run_model_trial.sh"] + sys.argv[1:])
    if not args.no_write:
        pred_path = resolve(mt["predictions_out"])
        summary_path = resolve(mt["summary_out"])
        report_path = resolve(args.report) if args.report else resolve(mt["report_out"])
        write_predictions(pred_path, prediction_records(valid, run_at, "test_sample", split,
                                                        args.keep_text))
        append_summary(summary_path, {
            "run_at": run_at, "mode": "test_sample", "split": split,
            "model": meta.get("model_name", ""), "n": overall["n"],
            "accuracy": round(overall["accuracy"], 6),
            "macro_f1": round(overall["macro_f1"], 6),
            "weighted_f1": round(overall["weighted_f1"], 6),
            "f1_negative": round(per_class["negative"]["f1"], 6),
            "f1_neutral": round(per_class["neutral"]["f1"], 6),
            "f1_positive": round(per_class["positive"]["f1"], 6),
            "invalid_rows": n_invalid,
            "command": command,
        })
        examples_n = int(mt.get("examples_n", 8))
        write_report(report_path, {
            "run_at": run_at, "command": command,
            "model_name": meta.get("model_name", ""), "saved_at": meta.get("saved_at", ""),
            "spark_version": meta.get("spark_version", ""), "split": split,
            "overall": overall, "per_class": per_class, "cm": cm, "labels": LABELS,
            "examples": valid[:examples_n], "keep_text": args.keep_text,
            "train_rows": int(meta.get("sizes", {}).get("train", 0)),
        })
        print(f"  Đã ghi: {pred_path}")
        print(f"  Đã ghi: {summary_path} (thêm 1 dòng)")
        print(f"  Đã ghi: {report_path}")
    return 0


def interactive(spark: SparkSession, model, meta: dict, idx2lab: dict, cfg: dict,
                args: argparse.Namespace) -> int:
    cl = cfg["cleaning"]
    counter = 0
    print("\nNhập một bình luận rồi Enter. Lệnh: :q thoát · :sample lấy ví dụ từ tập test.")
    while True:
        try:
            line = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.lower() in (":q", ":quit", "quit", "exit"):
            break
        if not line:
            continue
        if line == ":sample":
            counter += 1
            try:
                # n=0: lấy toàn tập rồi tự sắp — để mỗi lần gọi ra một nhóm khác
                # (vẫn tất định theo counter, không phụ thuộc thứ tự file).
                df = load_sample(spark, cfg, "test", 0)
                df = df.orderBy(F.crc32("comment_id") + F.lit(counter * 7919)).limit(3)
                df = df.withColumn("text", clean_text(F.col("text"), cl["abbreviations"]))
                rows, _ = score_dataframe(model, df, idx2lab)
                print("\n  Ví dụ từ tập test (có nhãn thật):")
                print_predictions(rows)
            except Exception as exc:  # noqa: BLE001 - demo phải không chết vì lỗi đọc dữ liệu
                print(f"  ⚠ Không lấy được ví dụ: {type(exc).__name__}: {exc}")
            continue

        rows_in = [{"row_id": 0, "comment_id": "", "raw": line, "label_true": ""}]
        df = cleaned_df(spark, rows_in, cl["abbreviations"])
        cleaned = df.select("text").first()["text"]
        reason = text_problem(cleaned, cl)
        if reason:
            print(f"  ⚠ Không chấm điểm: {reason}")
            print("    (đây đúng là quy tắc đưa bản ghi vào DLQ của job streaming)")
            continue
        rows, elapsed = score_dataframe(model, df, idx2lab)
        r = rows[0]
        p = r["probs"]
        print(f"\n  Nhãn dự đoán : {r['label_pred']} ({LABEL_VI[r['label_pred']]})")
        print(f"  Xác suất     : negative {p['negative']:.3f} | "
              f"neutral {p['neutral']:.3f} | positive {p['positive']:.3f}")
        print(f"  Độ tin cậy   : {r['confidence']:.1%}")
        print(f"  Văn bản sạch : {cleaned[:160]!r}")
        print(f"  Thời gian    : {elapsed:.2f} s")
    return 0


# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Thử nghiệm mô hình cảm xúc đã lưu (không cần Kafka/Streamlit).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Ba chế độ:", 1)[1] if "Ba chế độ:" in __doc__ else None,
    )
    p.add_argument("--text", action="append", metavar="CÂU",
                   help="chấm điểm câu này (dùng nhiều lần được)")
    p.add_argument("--file", metavar="FILE", help="mỗi dòng một bình luận (bỏ dòng trống/#)")
    p.add_argument("--examples", action="store_true",
                   help="chấm điểm các câu ví dụ trong config.yaml (dashboard.try_it_examples)")
    p.add_argument("--test-sample", type=int, default=0, metavar="N",
                   help="đo trên N dòng lấy tất định từ tập test (có nhãn thật)")
    p.add_argument("--split", choices=["test", "val"], default=None,
                   help="tập dùng cho --test-sample (mặc định: config.yaml)")
    p.add_argument("--report", default="", metavar="FILE",
                   help="đường dẫn báo cáo Markdown (mặc định: config.yaml)")
    p.add_argument("--keep-text", action="store_true",
                   help="ghi văn bản (cắt ngắn) vào CSV/report — CHỈ dùng với dữ liệu công khai")
    p.add_argument("--no-write", action="store_true", help="không ghi file kết quả")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = load_config()
    for key in ("model_trial", "training", "cleaning", "paths", "labels"):
        if key not in cfg:
            print(f"LỖI: config.yaml thiếu mục '{key}'.", file=sys.stderr)
            return 2

    spark = (SparkSession.builder
             .appName("capstone-model-trial")
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    try:
        model, meta, idx2lab = load_trial_model(spark, cfg)
        print_header(meta)

        if args.test_sample:
            return run_test_sample(spark, model, meta, idx2lab, cfg, args)

        texts = collect_texts(args, cfg)
        max_batch = int(cfg["model_trial"].get("max_batch_rows", 10000))
        if len(texts) > max_batch:
            print(f"LỖI: {len(texts):,} câu vượt trần {max_batch:,} dòng cho chế độ batch.",
                  file=sys.stderr)
            return 2
        if texts:
            return run_batch(spark, model, meta, idx2lab, cfg, texts, args)
        return interactive(spark, model, meta, idx2lab, cfg, args)
    except FileNotFoundError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        print("Gợi ý: chạy `ls outputs/models/` và `ls data/processed/` để kiểm tra.",
              file=sys.stderr)
        return 1
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
