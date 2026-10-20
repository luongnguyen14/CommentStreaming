#!/usr/bin/env python3
"""terminal_app.py — Quy trình chạy của dự án, hiển thị trong terminal Ubuntu.

Quy trình 8 bước:

    Thu thập → Đóng gói → Parse/DLQ → Làm sạch
    → Phân tích → Cửa sổ → Ghi → Tổng kết

Cách chạy:

    bash scripts/run_terminal_app.sh                 # từng bước, nhấn Enter
    bash scripts/run_terminal_app.sh --auto          # tự chạy
    bash scripts/run_comment_stream.sh               # từng comment, kết quả ngay
    bash scripts/run_terminal_app.sh --stage 5       # chỉ một bước
    bash scripts/run_terminal_app.sh --text "..."    # chấm một câu
    bash scripts/run_terminal_app.sh --live --duration 60

Dùng đúng code của hệ thống: parse_stream, add_cleaning_and_reason, clean_text,
PipelineModel, windows_from_detail, eval_alerts. Dữ liệu là replay IMDb, không
phải livestream thật; exactly-once chưa kiểm chứng (chỉ at-least-once).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# Cho phép chạy từ bất kỳ thư mục nào: thêm gốc dự án (2 cấp trên file này).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.utils import load_config  # noqa: E402

LABELS = ["negative", "neutral", "positive"]
LABEL_VI = {"negative": "tiêu cực", "neutral": "trung lập", "positive": "tích cực"}
STAGE_TOTAL = 8
PIPELINE = ["Thu thập", "Đóng gói", "Parse/DLQ", "Làm sạch",
            "Phân tích", "Cửa sổ", "Ghi", "Tổng kết"]

RESET = "\033[0m"


# ---------------------------------------------------------------------------
# 0) Trình bày terminal — màu, khung, bảng, tạm dừng
# ---------------------------------------------------------------------------
class Colors:
    """Mã ANSI tối giản; tắt hoàn toàn khi `enabled=False` (--no-color / pipe)."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}{RESET}" if self.enabled else str(text)

    def bold(self, t):    return self._wrap("1", t)
    def dim(self, t):     return self._wrap("2", t)
    def red(self, t):     return self._wrap("31", t)
    def green(self, t):   return self._wrap("32", t)
    def yellow(self, t):  return self._wrap("33", t)
    def blue(self, t):    return self._wrap("34", t)
    def magenta(self, t): return self._wrap("35", t)
    def cyan(self, t):    return self._wrap("36", t)
    def gray(self, t):    return self._wrap("90", t)


def one_line(text: str, width: int | None = None) -> str:
    """Gộp mọi khoảng trắng/xuống dòng thành một dòng, cắt bớt nếu cần."""
    s = " ".join(str(text or "").split())
    if width is None or len(s) <= width:
        return s
    return s[: max(0, width - 1)] + "…"


def trunc(s: str, width: int) -> str:
    s = str(s)
    return s if len(s) <= width else s[: max(0, width - 1)] + "…"


def fmt_int(n) -> str:
    return f"{int(n):,}"


def human_size(path: Path) -> str:
    """Kích thước file -> chuỗi dễ đọc; '—' nếu file không tồn tại."""
    try:
        n = float(Path(path).stat().st_size)
    except OSError:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def fmt_pct(x, digits: int = 1) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{float(x) * 100:.{digits}f}%"


def rel(path: Path) -> str:
    """Đường dẫn tương đối so với gốc dự án (để in cho gọn)."""
    try:
        return str(Path(path).relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


class UI:
    """In khung/bảng nhất quán. Không phụ thuộc thư viện ngoài."""

    ICONS = {"ok": "✔", "warn": "!", "err": "✘", "info": "i", "run": "▸"}

    def __init__(self, color: bool = True):
        self.c = Colors(color)
        cols = shutil.get_terminal_size(fallback=(100, 24)).columns
        self.width = max(80, min(int(cols), 108))
        self.inner = self.width - 2

    # -- khung -------------------------------------------------------------
    def banner(self, kicker: str, title: str, desc: str = "") -> None:
        c = self.c
        inner = self.inner
        print(c.cyan("╔" + "═" * inner + "╗"))
        head = f"{kicker} — {title}"
        print(c.cyan("║ ") + c.bold(c.yellow(trunc(head, inner - 2).ljust(inner - 2))) + c.cyan(" ║"))
        if desc:
            for chunk in textwrap.wrap(desc, width=inner - 4) or [""]:
                print(c.cyan("║ ") + c.dim(chunk.ljust(inner - 2)) + c.cyan(" ║"))
        print(c.cyan("╚" + "═" * inner + "╝"))

    def stage(self, n: int, title: str, desc: str = "") -> None:
        print()
        line = self.c.gray(" → ").join(
            (self.c.bold(self.c.yellow(name)) if i == n else self.c.gray(name))
            for i, name in enumerate(PIPELINE, 1)
        )
        print("  " + line)
        self.banner(f"GIAI ĐOẠN {n}/{STAGE_TOTAL}", title, desc)

    def section(self, title: str) -> None:
        print()
        print(self.c.bold(self.c.blue(f"▌ {title}")))
        print(self.c.gray("  " + "─" * (self.width - 4)))

    # -- ghi chú -----------------------------------------------------------
    def note(self, kind: str, text: str) -> None:
        c = self.c
        color = {"ok": c.green, "warn": c.yellow, "err": c.red,
                 "info": c.cyan, "run": c.blue}.get(kind, c.gray)
        icon = self.ICONS.get(kind, "·")
        lines = textwrap.wrap(str(text), width=self.width - 6) or [""]
        print("  " + color(icon) + " " + lines[0])
        for line in lines[1:]:
            print("    " + line)

    def kv(self, key: str, value: str) -> None:
        print(f"  {self.c.gray(trunc(key, 36).ljust(36))} {value}")

    # -- bảng --------------------------------------------------------------
    def table(self, headers: list[str], rows: list[list], aligns: list[str] | None = None,
              max_widths: list[int] | None = None) -> None:
        n = len(headers)
        if not rows:
            print(self.c.gray("  (không có dòng nào)"))
            return
        aligns = aligns or ["<"] * n
        cells = [[one_line(str(v)) for v in r] for r in rows]
        widths = [len(h) for h in headers]
        for r in cells:
            for i, v in enumerate(r[:n]):
                widths[i] = max(widths[i], len(v))
        if max_widths:
            widths = [min(w, m) for w, m in zip(widths, max_widths)]
        avail = self.width - 2 - 3 * (n - 1)
        while sum(widths) > avail:
            i = widths.index(max(widths))
            if widths[i] <= 4:
                break
            widths[i] -= 1
        fmt = "  " + " | ".join("{:" + a + str(w) + "}" for a, w in zip(aligns, widths))
        print(self.c.bold(fmt.format(*[trunc(h, w) for h, w in zip(headers, widths)])))
        print("  " + "-+-".join("-" * w for w in widths))
        for r in cells:
            print(fmt.format(*[trunc(v, w) for v, w in zip(r, widths)]))

    # -- thẻ bình luận ------------------------------------------------------
    def card(self, title: str, lines: list[str | tuple[str, object]]) -> None:
        """In một thẻ. Mỗi dòng có thể là str hoặc (str, hàm tô màu)."""
        c = self.c
        inner = self.width - 2
        body_w = inner - 2
        title = trunc(title, inner - 4)
        print(c.gray("┌─ ") + c.bold(title) + c.gray(" " + "─" * max(0, inner - len(title) - 3) + "┐"))
        for item in lines:
            text, color = (item if isinstance(item, tuple) else (item, None))
            for chunk in (textwrap.wrap(str(text), width=body_w) or [""]):
                padded = chunk.ljust(body_w)
                print(c.gray("│ ") + (color(padded) if color else padded) + c.gray(" │"))
        print(c.gray("└" + "─" * inner + "┘"))

    # -- tạm dừng -----------------------------------------------------------
    def pause(self, auto: bool, delay: float, label: str) -> None:
        if auto:
            if delay > 0:
                time.sleep(delay)
            return
        try:
            input(self.c.dim(f"  ⏎ {label}… "))
        except (EOFError, KeyboardInterrupt):
            print()


# ---------------------------------------------------------------------------
# 1) Dữ liệu mẫu + message (phần không cần Spark)
# ---------------------------------------------------------------------------
def _iso_utc(ts: float) -> str:
    """epoch giây -> ISO-8601 UTC có mili giây (cùng định dạng producer dùng)."""
    from src.producer.replay_producer import iso_utc
    return iso_utc(ts)


def topic_partitions() -> dict[str, int]:
    """Đọc số partition từ kafka/create_topics.sh — không hard-code trong app."""
    out: dict[str, int] = {}
    path = PROJECT_ROOT / "kafka" / "create_topics.sh"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*create\s+(\S+)\s+(\d+)", line)
            if m:
                out[m.group(1)] = int(m.group(2))
    return out


class Walkthrough:
    def __init__(self, cfg: dict, args: argparse.Namespace, ui: UI):
        self.cfg = cfg
        self.args = args
        self.ui = ui
        self.seed = int(args.seed if args.seed is not None else cfg.get("seed", 42))
        self.limit = max(1, int(args.limit))

        self.sample: pd.DataFrame | None = None
        self.true_lut: dict[str, tuple[str, str]] = {}
        self.offline_clean: dict[str, str] = {}
        self.messages: list[dict] | None = None
        self.bad: list[tuple[str, str, str]] | None = None
        self.bad_by_offset: dict[int, str] = {}

        self.spark = None
        self.checked = None
        self.parsed_rows: list[dict] | None = None
        self.model = None
        self.meta: dict | None = None
        self.idx2lab: dict[int, str] | None = None
        self.scored_rows: list[dict] | None = None
        self.score_elapsed = 0.0
        self.vocab_coef = None

        self.sample_agg: pd.DataFrame | None = None
        self.sample_state: dict | None = None
        self.real_agg_1min: pd.DataFrame | None = None
        self.real_state_1min: dict | None = None
        self.real_agg_slide: pd.DataFrame | None = None
        self.real_state_slide: dict | None = None
        self.real_latency: dict[str, float] = {}
        self.real_counts: dict[str, int | None] = {}
        self.run_dir: Path | None = None

    # -- dựng dữ liệu theo nhu cầu -----------------------------------------
    def ensure_sample(self) -> pd.DataFrame:
        if self.sample is not None:
            return self.sample
        split = str(self.cfg.get("model_trial", {}).get("split", "test"))
        path = PROJECT_ROOT / "outputs" / "tables" / "clean_sample.csv"
        if path.exists():
            df = pd.read_csv(path)
            if "split" in df.columns:
                part = df[df["split"].astype(str) == split].copy()
            else:
                part = df.copy()
            part = part.dropna(subset=["comment_id", "text_raw"])
            if part.empty:
                part = df.dropna(subset=["comment_id", "text_raw"]).copy()
            self.offline_clean = {
                str(r["comment_id"]): str(r.get("text", ""))
                for _, r in part.iterrows() if pd.notna(r.get("text", None))
            }
        else:
            # Dự phòng: chỉ có bản đã làm sạch, không có text_raw.
            self.ui.note("warn", "Không thấy outputs/tables/clean_sample.csv — dùng "
                                 "data/processed/test.parquet (không có văn bản thô).")
            part = pd.read_parquet(PROJECT_ROOT / self.cfg["paths"]["test"])
            part = part.rename(columns={"text": "text_raw"})
            part["user_hash"] = "khong-co-trong-ban-du-phong"
            part["rating"] = ""
            part["split"] = "test"

        n = min(self.limit, len(part))
        self.sample = (part.sample(n=n, random_state=self.seed)
                       .sort_values("comment_id").reset_index(drop=True))
        self.true_lut = {
            str(r["comment_id"]): (str(r.get("label", "")), str(r.get("rating", "")))
            for _, r in self.sample.iterrows()
        }
        return self.sample

    def ensure_messages(self) -> list[dict]:
        if self.messages is not None:
            return self.messages
        df = self.ensure_sample()
        self.messages = [{
            "comment_id": str(r["comment_id"]),
            "stream_id": str(r["stream_id"]),
            "user_hash": str(r["user_hash"]),
            # Producer gửi văn bản THÔ (review_detail), không gửi bản đã làm sạch.
            "text": str(r["text_raw"]),
            "event_ts": _iso_utc(time.time()),
        } for _, r in df.iterrows()]
        return self.messages

    def ensure_spark(self):
        if self.spark is not None:
            return self.spark
        self.ui.note("run", "Khởi động Spark local[2] (dùng cho parse, clean_text và model)…")
        t0 = time.perf_counter()
        import os
        os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")   # tránh WARN hostname
        from pyspark.sql import SparkSession
        self.spark = (SparkSession.builder
                      .appName("capstone-terminal-walkthrough")
                      .master("local[2]")
                      .config("spark.sql.session.timeZone", "UTC")
                      .config("spark.ui.enabled", "false")
                      .config("spark.ui.showConsoleProgress", "false")
                      .config("spark.eventLog.enabled", "false")
                      .config("spark.sql.shuffle.partitions", "4")
                      .getOrCreate())
        self.spark.sparkContext.setLogLevel("ERROR")
        self.ui.note("ok", f"Spark sẵn sàng sau {time.perf_counter() - t0:.1f}s "
                           f"(phiên bản {self.spark.version})")
        return self.spark

    def _bad_messages(self) -> list[tuple[str, str, str]]:
        """4 message hỏng CỐ Ý — để thấy DLQ, không phải dữ liệu thật."""
        now = _iso_utc(time.time())
        base = {"stream_id": "demo-dlq", "user_hash": "0000000000000000"}
        return [
            ("bad-json", '{"comment_id": "bad-json",', "JSON hỏng (cố ý)"),
            ("bad-missing-text", json.dumps(
                {"comment_id": "bad-missing-text", **base, "event_ts": now},
                ensure_ascii=False), "thiếu trường text (cố ý)"),
            ("bad-event-ts", json.dumps(
                {"comment_id": "bad-event-ts", **base,
                 "text": "This message is long enough but its timestamp cannot be parsed.",
                 "event_ts": "hom-qua"}, ensure_ascii=False), "event_ts không đọc được (cố ý)"),
            ("bad-short", json.dumps(
                {"comment_id": "bad-short", **base, "text": "ok", "event_ts": now},
                ensure_ascii=False), "văn bản quá ngắn (cố ý)"),
        ]

    def ensure_parsed(self) -> list[dict]:
        """Chạy ĐÚNG đường parse + validate của streaming trên một batch nhỏ."""
        if self.parsed_rows is not None:
            return self.parsed_rows
        msgs = self.ensure_messages()
        spark = self.ensure_spark()
        from src.streaming.stream_job import add_cleaning_and_reason, parse_stream

        self.bad = self._bad_messages()
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        raw_rows = [(json.dumps(m, ensure_ascii=False), i % 3, i, now_naive)
                    for i, m in enumerate(msgs)]
        offset0 = len(msgs)
        for j, (_cid, raw_json, note) in enumerate(self.bad):
            raw_rows.append((raw_json, (offset0 + j) % 3, offset0 + j, now_naive))
            self.bad_by_offset[offset0 + j] = note

        schema = "json_raw string, kafka_partition int, kafka_offset long, kafka_ts timestamp"
        raw_df = spark.createDataFrame(raw_rows, schema)
        checked = add_cleaning_and_reason(parse_stream(raw_df), self.cfg).cache()
        self.parsed_rows = [r.asDict() for r in checked.collect()]
        self.checked = checked
        return self.parsed_rows

    def ensure_model(self):
        if self.model is not None:
            return self.model, self.meta, self.idx2lab
        from src.app.model_trial import load_trial_model
        spark = self.ensure_spark()
        self.ui.note("run", "Nạp PipelineModel đã lưu (lần đầu có thể mất vài giây)…")
        t0 = time.perf_counter()
        self.model, self.meta, self.idx2lab = load_trial_model(spark, self.cfg)
        self.ui.note("ok", f"Đã nạp {self.meta.get('model_name', '?')} sau "
                           f"{time.perf_counter() - t0:.1f}s")
        return self.model, self.meta, self.idx2lab

    def ensure_scored(self) -> list[dict]:
        if self.scored_rows is not None:
            return self.scored_rows
        from pyspark.sql import functions as F
        from src.app.model_trial import load_trial_model  # noqa: F401 (kiểm tra sớm)

        self.ensure_parsed()
        model, meta, idx2lab = self.ensure_model()
        valid = self.checked.filter(F.col("dlq_reason").isNull())
        # Giữ văn bản thô ở `text_raw`, đưa `text_clean` vào đúng cột `text` mà
        # Pipeline đã học — giống hệt src/streaming/stream_job.py::score_stream.
        prepared = valid.withColumn("text_raw", F.col("text")).withColumn(
            "text", F.col("text_clean"))

        self.ui.note("run", "Chấm điểm từng bình luận bằng model.transform()…")
        t0 = time.perf_counter()
        # Lấy `event_time` dưới dạng epoch mili giây: `collect()` của PySpark đổi
        # timestamp sang giờ ĐỊA PHƯƠNG, còn dự án quy ước mọi mốc là UTC. Đổi qua
        # epoch rồi dựng lại bằng timezone.utc để không lệch +07.
        collected = (model.transform(prepared)
                     .select("comment_id", "stream_id", "text_raw", "text_clean",
                             F.unix_millis(F.col("event_time")).alias("event_ms"),
                             "prediction", "probability", "features")
                     .collect())
        self.score_elapsed = time.perf_counter() - t0
        done_at = datetime.now(timezone.utc).replace(tzinfo=None)

        rows: list[dict] = []
        for r in collected:
            d = r.asDict()
            pred_idx = int(d["prediction"])
            label_pred = idx2lab.get(pred_idx, f"lớp #{pred_idx}")
            prob_vec = d.get("probability")
            if prob_vec is not None:
                probs = {idx2lab[i]: float(p) for i, p in enumerate(list(prob_vec))}
            else:
                probs = {lab: float("nan") for lab in idx2lab.values()}
            label_true, rating_true = self.true_lut.get(str(d.get("comment_id") or ""), ("", ""))
            event_dt = None
            latency_ms = None
            if d.get("event_ms") is not None:
                event_dt = datetime.fromtimestamp(d["event_ms"] / 1000.0, tz=timezone.utc
                                                  ).replace(tzinfo=None)
                latency_ms = max(0.0, (done_at - event_dt).total_seconds() * 1000.0)
            rows.append({
                "comment_id": str(d.get("comment_id") or ""),
                "stream_id": str(d.get("stream_id") or ""),
                "text_raw": str(d.get("text_raw") or ""),
                "text_clean": str(d.get("text_clean") or ""),
                "event_time": event_dt,
                "pred_idx": pred_idx,
                "label_pred": label_pred,
                "probs": probs,
                "confidence": probs.get(label_pred, float("nan")),
                "label_true": label_true,
                "rating_true": rating_true,
                "latency_ms": latency_ms,
                "features": d.get("features"),
            })
        rows.sort(key=lambda x: x["comment_id"])
        self.scored_rows = rows
        self.ui.note("ok", f"Đã chấm {len(rows)} bình luận trong {self.score_elapsed:.2f}s "
                           f"({self.score_elapsed / max(1, len(rows)) * 1000:.0f} ms/bình luận)")
        return rows

    # -- tiện ích -----------------------------------------------------------
    def clean_one(self, text: str) -> str:
        from pyspark.sql import functions as F
        from src.common.text_cleaning import clean_text
        spark = self.ensure_spark()
        df = spark.createDataFrame([(str(text),)], "text string")
        return df.select(clean_text(F.col("text"),
                                    self.cfg["cleaning"]["abbreviations"]).alias("clean")
                         ).first()["clean"]

    def corrections(self, raw: str, clean: str) -> list[str]:
        """Các quy tắc làm sạch đã thực sự đổi văn bản (để hiển thị)."""
        tags = []
        if raw != raw.lower():
            tags.append("lower")
        if re.search(r"<[^>]+>", raw):
            tags.append("HTML")
        if re.search(r"https?://|www\.", raw, re.I):
            tags.append("URL")
        if re.search(r"(?<!\w)@\w+", raw):
            tags.append("mention")
        if re.search(r"(.)\1{2,}", raw):
            tags.append("lặp ký tự")
        if re.search(r"[\U0001F300-\U0001FAFF☀-➿]", raw):
            tags.append("emoji")
        if "  " in raw or "\n" in raw or "\t" in raw:
            tags.append("khoảng trắng")
        abbrev = self.cfg["cleaning"].get("abbreviations", {})
        tokens = set(re.findall(r"[a-z]+", raw.lower()))
        hit = sorted(tokens & set(abbrev))
        if hit:
            tags.append("viết tắt: " + ", ".join(hit[:4]))
        return tags or ["chuẩn hoá dấu câu/khoảng trắng"]

    def contributions(self, row: dict, top: int = 5, bottom: int = 2) -> list[tuple[str, float]]:
        """Các token đóng góp nhiều nhất cho lớp DỰ ĐOÁN (mô hình tuyến tính)."""
        if self.vocab_coef is None:
            try:
                from src.app.app import linear_parts
                self.vocab_coef = linear_parts(self.model)
            except Exception:                       # noqa: BLE001 — không chặn cả app
                self.vocab_coef = (None, None)
        vocab, coef = self.vocab_coef
        feat = row.get("features")
        pred = row.get("pred_idx")
        if vocab is None or coef is None or feat is None:
            return []
        if pred is None or pred >= coef.shape[0]:
            return []
        pairs = []
        for k, idx in enumerate(feat.indices):
            if 0 <= idx < len(vocab):
                pairs.append((vocab[idx], float(feat.values[k] * coef[pred, idx])))
        if not pairs:
            return []
        pairs.sort(key=lambda t: -t[1])
        chosen = pairs[:top] + pairs[-bottom:] if bottom else pairs[:top]
        seen, out = set(), []
        for w, v in chosen:
            if w not in seen:
                seen.add(w)
                out.append((w, v))
        return out

    def close(self) -> None:
        try:
            if self.checked is not None:
                self.checked.unpersist()
        except Exception:                           # noqa: BLE001
            pass
        try:
            if self.spark is not None:
                self.spark.stop()
        except Exception:                           # noqa: BLE001
            pass

    # ======================================================================
    # Các giai đoạn
    # ======================================================================
    def stage_1(self) -> None:
        df = self.ensure_sample()
        raw_path = PROJECT_ROOT / self.cfg["paths"]["raw_comments"]
        jsonl_path = PROJECT_ROOT / self.cfg["paths"]["raw_jsonl"] / "part-000.jsonl"
        self.ui.section("Nguồn dữ liệu")
        self.ui.kv("Nguồn gốc", f"{rel(raw_path)} ({human_size(raw_path)}, review IMDb công khai)")
        self.ui.kv("Bản đã xử lý", f"{rel(jsonl_path)} ({human_size(jsonl_path)})")
        self.ui.kv("Mẫu đang dùng", "outputs/tables/clean_sample.csv")
        self.ui.kv("Tập được lấy", str(self.cfg.get("model_trial", {}).get("split", "test")))
        self.ui.kv("Số dòng lấy", f"{len(df)} (seed={self.seed})")

        self.ui.section("Bản ghi lấy được")
        rows = []
        for i, r in df.head(10).iterrows():
            rows.append([i + 1, r["comment_id"], one_line(r.get("stream_id", ""), 30),
                         r.get("rating", ""), one_line(r.get("text_raw", ""), 48)])
        self.ui.table(["#", "comment_id", "phim / phòng", "rating", "văn bản thô (rút gọn)"],
                      rows, aligns=[">", "<", "<", ">", "<"],
                      max_widths=[3, 14, 30, 6, 48])
        if len(df) > 10:
            self.ui.note("info", f"… và {len(df) - 10} bản ghi nữa (tổng {len(df)}).")

    def stage_2(self) -> None:
        msgs = self.ensure_messages()
        df = self.ensure_sample()
        first = msgs[0]
        cid = first["comment_id"]
        label, rating = self.true_lut.get(cid, ("", ""))
        parts = topic_partitions()
        raw_topic = self.cfg["kafka"]["topic_raw"]

        self.ui.section("Message gửi Kafka (5 trường)")
        shown = dict(first)
        shown["text"] = one_line(first["text"], 220)      # chỉ rút gọn khi in
        print(self.ui.c.cyan(json.dumps(shown, ensure_ascii=False, indent=2)))
        self.ui.kv("Topic", f"{raw_topic} · {parts.get(raw_topic, '?')} partition")
        self.ui.kv("Key", cid)
        self.ui.kv("user_hash", first["user_hash"] + "  (băm có muối)")
        self.ui.kv("event_ts", first["event_ts"] + "  (UTC)")

        self.ui.section("Nhãn đánh giá (sidecar)")
        side = {"comment_id": cid, "label": label, "rating": rating}
        print(self.ui.c.magenta(json.dumps(side, ensure_ascii=False, indent=2)))
        self.ui.table(["#", "comment_id", "phòng", "nhãn (sidecar)", "rating"],
                      [[i + 1, m["comment_id"], one_line(m["stream_id"], 28),
                        self.true_lut.get(m["comment_id"], ("", ""))[0],
                        self.true_lut.get(m["comment_id"], ("", ""))[1]]
                       for i, m in enumerate(msgs[:8])],
                      aligns=[">", "<", "<", "<", ">"], max_widths=[3, 14, 28, 14, 6])
        if len(msgs) > 8:
            self.ui.note("info", f"… và {len(msgs) - 8} message nữa.")

    def stage_3(self) -> None:
        rows = self.ensure_parsed()
        from src.streaming.stream_job import RAW_SCHEMA

        self.ui.section("Schema")
        schema_rows = [[f.name, f.dataType.simpleString(), "có" if f.nullable else "không"]
                       for f in RAW_SCHEMA.fields]
        self.ui.table(["trường", "kiểu", "nullable"], schema_rows, max_widths=[20, 22, 8])

        self.ui.section("Kiểm tra từng bản ghi")
        tbl = []
        for r in rows:
            off = int(r["kafka_offset"])
            cid = r.get("comment_id") or "(không đọc được)"
            reason = r.get("dlq_reason")
            note = self.bad_by_offset.get(off, "")
            tbl.append([off, cid, "DLQ" if reason else "OK", reason or "—", note or "—"])
        self.ui.table(["offset", "comment_id", "trạng thái", "lý do DLQ", "ghi chú"],
                      tbl, aligns=[">", "<", "<", "<", "<"],
                      max_widths=[6, 18, 11, 34, 24])

        n_ok = sum(1 for r in rows if not r.get("dlq_reason"))
        n_dlq = len(rows) - n_ok
        self.ui.section("Đối soát")
        self.ui.kv("Nhận vào", f"{len(rows)} message "
                               f"({len(self.messages)} thật + {len(self.bad)} lỗi cố ý)")
        self.ui.kv("Hợp lệ", f"{n_ok}")
        self.ui.kv("DLQ", f"{n_dlq}")
        self.ui.kv("Tổng kiểm tra", f"{n_ok} + {n_dlq} = {len(rows)} ✔")

    def stage_4(self) -> None:
        rows = self.ensure_parsed()
        valid = [r for r in rows if not r.get("dlq_reason")]

        self.ui.section("Hàm làm sạch")
        self.ui.kv("Hàm", "src/common/text_cleaning.py :: clean_text()")
        self.ui.kv("Quy tắc", "lowercase · bỏ HTML · URL→<url> · @user→<user> · "
                              "dấu câu · viết tắt · ký tự lặp · emoji · khoảng trắng")

        self.ui.section("Làm sạch các bình luận")
        tbl = []
        for i, r in enumerate(valid):
            raw = str(r.get("text") or "")
            clean = str(r.get("text_clean") or "")
            offline = self.offline_clean.get(str(r.get("comment_id") or ""))
            match = "—" if not offline else ("✔" if offline == clean else "✘")
            tbl.append([i + 1, r.get("comment_id") or "", len(raw), len(clean), match,
                        ", ".join(self.corrections(raw, clean))])
        self.ui.table(["#", "comment_id", "thô", "sạch", "khớp", "quy tắc đã đổi"],
                      tbl, aligns=[">", "<", ">", ">", "<", "<"],
                      max_widths=[3, 14, 7, 7, 6, 52])
        for i, r in enumerate(valid[:2]):
            self.ui.card(f"Ví dụ {i + 1} — {r.get('comment_id')}", [
                ("RAW   : " + one_line(r.get("text"), 240), self.ui.c.dim),
                ("CLEAN : " + one_line(r.get("text_clean"), 240), self.ui.c.green),
            ])

    def stage_5(self) -> None:
        rows = self.ensure_scored()
        meta = self.meta or {}
        test = meta.get("metrics", {}).get("test", {})
        self.ui.section("Model")
        self.ui.kv("Tên", str(meta.get("model_name", "?")))
        self.ui.kv("Lưu lúc", str(meta.get("saved_at", "?")) + f" (Spark {meta.get('spark_version', '?')})")
        self.ui.kv("Pipeline", " → ".join(meta.get("pipeline_stages", [])) or "?")
        if test:
            self.ui.kv("Test lúc huấn luyện", f"accuracy {test.get('accuracy', 0):.4f} · "
                                              f"macro-F1 {test.get('macro_f1', 0):.4f} · "
                                              f"{fmt_int(test.get('n', 0))} dòng")

        self.ui.section("Từng bình luận")
        n_cards = max(0, min(int(self.args.cards), len(rows)))
        color_of = {"negative": self.ui.c.red, "neutral": self.ui.c.yellow,
                    "positive": self.ui.c.green}
        for i, r in enumerate(rows[:n_cards]):
            p = r["probs"]
            true_txt = "—"
            if r["label_true"]:
                ok = r["label_true"] == r["label_pred"]
                true_txt = (f"{r['label_true']} (rating {r['rating_true']}) "
                            f"{'✔' if ok else '✘'}")
            lines: list = [
                ("RAW   : " + one_line(r["text_raw"], 220), self.ui.c.dim),
                ("CLEAN : " + one_line(r["text_clean"], 220), self.ui.c.dim),
                (f"NHÃN  : {r['label_pred'].upper()}  "
                 f"(neg {p.get('negative', float('nan')):.3f} | "
                 f"neu {p.get('neutral', float('nan')):.3f} | "
                 f"pos {p.get('positive', float('nan')):.3f})  "
                 f"tin cậy {fmt_pct(r['confidence'])}",
                 color_of.get(r["label_pred"], self.ui.c.bold)),
                ("THẬT  : " + true_txt, self.ui.c.magenta),
            ]
            contrib = self.contributions(r)
            if contrib:
                lines.append(("TỪ    : " + " · ".join(f"“{w}” {v:+.2f}" for w, v in contrib),
                              self.ui.c.cyan))
            if r["latency_ms"] is not None:
                lines.append((f"ĐỘ TRỄ: {r['latency_ms'] / 1000:.2f}s (mô phỏng)", self.ui.c.gray))
            self.ui.card(f"[{i + 1}/{len(rows)}] {r['comment_id']} · "
                         f"{trunc(r['stream_id'], 40)}", lines)

        self.ui.section("Bảng kết quả")
        tbl = []
        for i, r in enumerate(rows):
            correct = "—" if not r["label_true"] else ("✔" if r["label_true"] == r["label_pred"] else "✘")
            tbl.append([i + 1, r["comment_id"], r["label_true"] or "—", r["label_pred"],
                        fmt_pct(r["confidence"]), correct])
        self.ui.table(["#", "comment_id", "nhãn thật", "dự đoán", "tin cậy", "đúng?"],
                      tbl, aligns=[">", "<", "<", "<", ">", "<"],
                      max_widths=[3, 16, 12, 12, 9, 6])

        labelled = [r for r in rows if r["label_true"]]
        if labelled:
            hit = sum(1 for r in labelled if r["label_true"] == r["label_pred"])
            self.ui.note("ok" if hit == len(labelled) else "warn",
                         f"Mẫu {len(labelled)} dòng: đúng {hit}/{len(labelled)} "
                         f"({hit / len(labelled):.1%})")

    def stage_6(self) -> None:
        rows = self.ensure_scored()
        try:
            from src.app.app import aggregate_windows, eval_alerts, windows_from_detail
        except Exception as e:                       # noqa: BLE001
            self.ui.note("err", f"Không import được hàm gộp cửa sổ của dashboard: {e}")
            return

        thr = float(self.cfg["eda"]["alert"]["negative_share_threshold"])
        min_c = int(self.cfg["eda"]["alert"]["min_comments"])

        self.ui.section("Cửa sổ 1 phút trên mẫu")
        detail = pd.DataFrame([{
            "comment_id": r["comment_id"],
            "event_time": r["event_time"],
            "pred_label": r["label_pred"],
            "latency_ms": r["latency_ms"] if r["latency_ms"] is not None else 0.0,
        } for r in rows])
        self.sample_agg = windows_from_detail(detail, 60)
        self.sample_state = eval_alerts(self.sample_agg, thr, min_c, recent_s=10 ** 9)
        self._print_windows(self.sample_agg, self.sample_state, title="mẫu thử")

        self.ui.section("Cửa sổ thật · verify1")
        base = PROJECT_ROOT / "outputs" / "stream" / "verify1"
        w1_path = base / "window_1min"
        ws_path = base / "window_sliding_10s"
        detail_path = base / "scored_detail"
        dlq_path = base / "dlq"
        if not w1_path.exists() and not ws_path.exists():
            self.ui.note("warn", "Không thấy outputs/stream/verify1/window_* — "
                                 "bỏ qua phần dữ liệu thật.")
            return

        # --- 1 phút: nhìn toàn cảnh -------------------------------------
        if w1_path.exists():
            raw1 = pd.read_parquet(w1_path)
            self.real_agg_1min = aggregate_windows(raw1)
            self.real_state_1min = eval_alerts(self.real_agg_1min, thr, min_c, recent_s=10 ** 9)
            self._print_windows(
                self.real_agg_1min.tail(8), self.real_state_1min,
                title="verify1 · cửa sổ 1 phút")
            top = self.real_agg_1min.loc[self.real_agg_1min.n_comments.idxmax()]
            crossed = (float(top["share_negative"]) > thr
                       and int(top["n_comments"]) >= min_c)
            self.ui.note("info",
                         f"1 phút · cửa sổ lớn nhất {pd.to_datetime(top['window_start']):%H:%M}–"
                         f"{pd.to_datetime(top['window_end']):%H:%M} UTC · "
                         f"{fmt_int(top['n_comments'])} bình luận · "
                         f"{fmt_pct(top['share_negative'])} tiêu cực · cảnh báo "
                         f"{'CÓ' if crossed else 'KHÔNG'}")

        # --- 10 giây trượt: nơi phát hiện cảnh báo thật ------------------
        if ws_path.exists():
            raw_s = pd.read_parquet(ws_path)
            self.real_agg_slide = aggregate_windows(raw_s)
            self.real_state_slide = eval_alerts(self.real_agg_slide, thr, min_c, recent_s=10 ** 9)
            hits = self.real_agg_slide[(self.real_agg_slide.share_negative > thr)
                                       & (self.real_agg_slide.n_comments >= min_c)]
            self.ui.section("Cửa sổ trượt 10 giây · verify1")
            if not hits.empty:
                h = hits.iloc[-1]
                h_start = pd.to_datetime(h["window_start"])
                around = self.real_agg_slide[
                    (pd.to_datetime(self.real_agg_slide.window_start) >= h_start - pd.Timedelta(seconds=20))
                    & (pd.to_datetime(self.real_agg_slide.window_start) <= h_start + pd.Timedelta(seconds=20))]
                self._print_windows(around, self.real_state_slide,
                                    title="quanh cảnh báo", overlap=True)
                self.ui.note("warn",
                             f"CẢNH BÁO · {pd.to_datetime(h['window_start']):%H:%M:%S}–"
                             f"{pd.to_datetime(h['window_end']):%H:%M:%S} UTC · "
                             f"{int(h['n_negative'])}/{int(h['n_comments'])} = "
                             f"{fmt_pct(h['share_negative'])} tiêu cực")
            else:
                self._print_windows(self.real_agg_slide.tail(10), self.real_state_slide,
                                    title="10 cửa sổ cuối", overlap=True)
            self.ui.note("info", f"10 giây · {len(self.real_agg_slide)} cửa sổ · "
                                 f"{len(hits)} cảnh báo")

        # --- số dòng + độ trễ thật --------------------------------------
        self.real_counts = {
            "scored_detail": self._parquet_rows(detail_path, "comment_id"),
            "window_1min": self._parquet_rows(w1_path, "n_comments"),
            "window_1min_gop": len(self.real_agg_1min) if self.real_agg_1min is not None else None,
            "window_sliding_10s": self._parquet_rows(ws_path, "n_comments"),
            "window_sliding_gop": len(self.real_agg_slide) if self.real_agg_slide is not None else None,
            "dlq": self._parquet_rows(dlq_path, "comment_id"),
        }
        self.ui.section("Số dòng · độ trễ")
        self.ui.kv("scored_detail", fmt_int(self.real_counts["scored_detail"] or 0) + " dòng")
        self.ui.kv("window_1min",
                   fmt_int(self.real_counts["window_1min"] or 0) +
                   f" dòng → {self.real_counts['window_1min_gop']} cửa sổ")
        self.ui.kv("window_sliding_10s",
                   fmt_int(self.real_counts["window_sliding_10s"] or 0) +
                   f" dòng → {self.real_counts['window_sliding_gop']} cửa sổ")
        if detail_path.exists():
            lat = pd.read_parquet(detail_path, columns=["latency_ms"])["latency_ms"].dropna()
            if len(lat):
                q = lat.quantile([0.5, 0.95, 0.99])
                self.real_latency = {f"p{int(p * 100)}": float(v) for p, v in q.items()}
                self.ui.kv("Độ trễ thật",
                           f"p50 {self.real_latency['p50'] / 1000:.1f}s · "
                           f"p95 {self.real_latency['p95'] / 1000:.1f}s · "
                           f"p99 {self.real_latency['p99'] / 1000:.1f}s "
                           f"({fmt_int(len(lat))} bình luận)")

    def _print_windows(self, agg: pd.DataFrame, state: dict, title: str,
                       overlap: bool = False) -> None:
        if agg is None or agg.empty:
            self.ui.note("warn", f"Chưa có cửa sổ nào cho {title}.")
            return
        tbl = []
        for _, r in agg.iterrows():
            flagged = (float(r.get("share_negative", 0)) >
                       float(self.cfg["eda"]["alert"]["negative_share_threshold"])
                       and int(r.get("n_comments", 0)) >=
                       int(self.cfg["eda"]["alert"]["min_comments"]))
            tbl.append([
                f"{pd.to_datetime(r['window_start']):%H:%M:%S}–"
                f"{pd.to_datetime(r['window_end']):%H:%M:%S}",
                int(r["n_comments"]), int(r.get("n_negative", 0)),
                int(r.get("n_neutral", 0)), int(r.get("n_positive", 0)),
                fmt_pct(r.get("share_negative")), "⚠" if flagged else "",
            ])
        self.ui.table(["cửa sổ (UTC)", "n", "neg", "neu", "pos", "tỷ lệ neg", "cảnh báo"],
                      tbl, aligns=["<", ">", ">", ">", ">", ">", "<"],
                      max_widths=[19, 5, 6, 6, 6, 9, 8])
        if state and state.get("has_data"):
            unit = "lượt (chồng lấn)" if overlap else "bình luận"
            self.ui.note("info", f"{title} · {state['n_recent']} cửa sổ · "
                                 f"{fmt_int(state['n_comments'])} {unit} · "
                                 f"{fmt_pct(state.get('share_negative'))} tiêu cực · cảnh báo "
                                 f"{'CÓ' if state.get('alert') else 'KHÔNG'}")

    @staticmethod
    def _parquet_rows(path: Path, column: str) -> int | None:
        if not path.exists():
            return None
        try:
            return len(pd.read_parquet(path, columns=[column]))
        except Exception:                           # noqa: BLE001
            return None

    def stage_7(self) -> None:
        self.ensure_scored()
        self.ui.section("Sink Parquet · verify1")
        base = PROJECT_ROOT / "outputs" / "stream" / "verify1"
        items = [
            ("scored_detail/", "mỗi bình luận đã chấm: nhãn, xác suất, độ trễ", "comment_id"),
            ("window_1min/", "cửa sổ 1 phút theo từng phòng", "n_comments"),
            ("window_sliding_10s/", "cửa sổ trượt 10 giây, slide 5 giây", "n_comments"),
            ("dlq/", "bản ghi lỗi kèm lý do", "comment_id"),
        ]
        for name, desc, col in items:
            n = self._parquet_rows(base / name, col)
            self.ui.kv(name, f"{fmt_int(n) if n is not None else '—':>8} dòng · {desc}")

        self.ui.section("Kafka")
        if self.args.no_kafka_check:
            self.ui.note("info", "Đã tắt kiểm tra Kafka (--no-kafka-check).")
        else:
            self._kafka_status()

        self.ui.section("Ghi kết quả")
        if self.args.no_write:
            self.ui.note("info", "Đã tắt ghi file (--no-write).")
            return
        self.run_dir = (PROJECT_ROOT / "outputs" / "terminal_demo"
                        / f"run_{datetime.now():%Y%m%d_%H%M%S}")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        rows = self.ensure_scored()

        pred = []
        for r in rows:
            rec = {
                "comment_id": r["comment_id"],
                "stream_id": r["stream_id"],
                "label_true": r["label_true"],
                "rating_true": r["rating_true"],
                "label_pred": r["label_pred"],
                "prob_negative": round(r["probs"].get("negative", float("nan")), 6),
                "prob_neutral": round(r["probs"].get("neutral", float("nan")), 6),
                "prob_positive": round(r["probs"].get("positive", float("nan")), 6),
                "confidence": round(r["confidence"], 6),
                "correct": (r["label_true"] == r["label_pred"]) if r["label_true"] else "",
                "latency_ms": round(r["latency_ms"], 1) if r["latency_ms"] is not None else "",
            }
            if self.args.keep_text:
                rec["text_clean_excerpt"] = one_line(r["text_clean"], 200)
            pred.append(rec)
        pd.DataFrame(pred).to_csv(self.run_dir / "predictions.csv", index=False, encoding="utf-8")

        dlq = [{
            "kafka_offset": int(r["kafka_offset"]),
            "comment_id": r.get("comment_id") or "",
            "dlq_reason": r.get("dlq_reason") or "",
            "note": self.bad_by_offset.get(int(r["kafka_offset"]), ""),
        } for r in self.ensure_parsed() if r.get("dlq_reason")]
        pd.DataFrame(dlq).to_csv(self.run_dir / "dlq.csv", index=False, encoding="utf-8")

        if self.sample_agg is not None and not self.sample_agg.empty:
            self.sample_agg.to_csv(self.run_dir / "windows_sample.csv", index=False, encoding="utf-8")

        labelled = [r for r in rows if r["label_true"]]
        hit = sum(1 for r in labelled if r["label_true"] == r["label_pred"])
        test = (self.meta or {}).get("metrics", {}).get("test", {})
        summary = [
            "# Terminal walkthrough — kết quả lần chạy",
            "",
            f"- Thời điểm chạy: {datetime.now().astimezone().isoformat(timespec='seconds')}",
            "- Dữ liệu: replay review IMDb công khai — **không phải livestream thật**.",
            f"- Tập lấy mẫu: `{self.cfg.get('model_trial', {}).get('split', 'test')}` · "
            f"{len(self.ensure_sample())} dòng · seed {self.seed}.",
            f"- Message đóng gói: {len(self.messages)} thật + {len(self.bad)} lỗi cố ý.",
            f"- Hợp lệ: {sum(1 for r in self.ensure_parsed() if not r.get('dlq_reason'))}; "
            f"DLQ: {len(dlq)}.",
            f"- Đã chấm: {len(rows)} bình luận trong {self.score_elapsed:.2f}s.",
            f"- Mẫu: đúng {hit}/{len(labelled)}" + (f" (accuracy {hit / len(labelled):.1%})"
                                                    if labelled else "") +
            " — mẫu nhỏ, chỉ để minh hoạ.",
            f"- Model: {self.meta.get('model_name', '?')}; trên tập test lúc huấn luyện: "
            f"accuracy {test.get('accuracy', 0):.4f}, macro-F1 {test.get('macro_f1', 0):.4f} "
            f"({fmt_int(test.get('n', 0))} dòng).",
            "",
            "## Điều đã đo / chưa đo",
            "",
            "- Đã đo: luồng parse → clean → predict → cửa sổ trên đúng code của dự án.",
            "- Đã đo: DLQ nhận đúng 4 bản ghi lỗi cố ý, mỗi bản ghi có lý do.",
            "- `latency_ms` trong file này là độ trễ MÔ PHỎNG offline (gồm khởi động Spark và "
            "nạp model), không phải latency streaming thật.",
            ("- Latency THẬT đo trên verify1: "
             f"p50 {self.real_latency['p50'] / 1000:.1f}s · "
             f"p95 {self.real_latency['p95'] / 1000:.1f}s · "
             f"p99 {self.real_latency['p99'] / 1000:.1f}s."
             if self.real_latency else
             "- Latency thật của verify1: chưa nạp trong lần chạy này (chạy giai đoạn 6 để đo)."),
            "- CHƯA kiểm chứng: exactly-once. Hệ thống chỉ khẳng định at-least-once.",
            "- Mẫu nhỏ không dùng để kết luận chất lượng mô hình; dùng bảng test đầy đủ.",
        ]
        (self.run_dir / "run_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

        self.ui.note("ok", f"Đã ghi {rel(self.run_dir)}/")
        self.ui.kv("predictions.csv", f"{len(pred)} dòng (không có văn bản trừ khi --keep-text)")
        self.ui.kv("dlq.csv", f"{len(dlq)} dòng")
        self.ui.kv("windows_sample.csv", "cửa sổ 1 phút của mẫu")
        self.ui.kv("run_summary.md", "tóm tắt + điều đã đo/chưa đo")

    def _kafka_status(self) -> None:
        try:
            from kafka import KafkaConsumer, TopicPartition
            boot = self.cfg["kafka"]["bootstrap_servers"]
            topics = [self.cfg["kafka"]["topic_raw"], self.cfg["kafka"]["topic_scored"],
                      self.cfg["kafka"]["topic_dlq"]]
            consumer = KafkaConsumer(
                bootstrap_servers=boot,
                enable_auto_commit=False,
                consumer_timeout_ms=1200,
                request_timeout_ms=2000,
                bootstrap_timeout_ms=2000,   # kafka-python 3.x: thay api_version_auto_timeout_ms
            )
            for topic in topics:
                parts = consumer.partitions_for_topic(topic)
                if not parts:
                    self.ui.kv(topic, "chưa có topic")
                    continue
                tps = [TopicPartition(topic, p) for p in sorted(parts)]
                begin = consumer.beginning_offsets(tps)
                end = consumer.end_offsets(tps)
                n = sum(end[tp] - begin[tp] for tp in tps)
                self.ui.kv(topic, f"{len(parts)} partition · {fmt_int(n)} message đang lưu")
            consumer.close()
            self.ui.note("ok", f"Kafka đang chạy tại {boot}.")
        except Exception as e:                       # noqa: BLE001
            self.ui.note("info", f"Kafka không chạy/không truy cập được ({type(e).__name__}). "
                                 "Bỏ qua — walkthrough không cần Kafka. Muốn xem live: "
                                 "bash scripts/run_demo.sh ở terminal khác.")

    def stage_8(self) -> None:
        rows = self.ensure_scored()
        parsed = self.ensure_parsed()
        n_ok = sum(1 for r in parsed if not r.get("dlq_reason"))
        n_dlq = len(parsed) - n_ok
        labelled = [r for r in rows if r["label_true"]]
        hit = sum(1 for r in labelled if r["label_true"] == r["label_pred"])
        lat = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
        test = (self.meta or {}).get("metrics", {}).get("test", {})

        self.ui.section("Tóm tắt")
        tbl = [
            ["Bản ghi lấy từ tập " + str(self.cfg.get("model_trial", {}).get("split", "test")),
             fmt_int(len(self.ensure_sample()))],
            ["Message đóng gói (5 trường)", fmt_int(len(self.messages))],
            ["Bản ghi lỗi cố ý", fmt_int(len(self.bad))],
            ["Hợp lệ / DLQ", f"{fmt_int(n_ok)} / {fmt_int(n_dlq)}"],
            ["Đã chấm điểm", fmt_int(len(rows))],
            ["Đúng trên mẫu", f"{hit}/{len(labelled)}" +
             (f" ({hit / len(labelled):.1%})" if labelled else "")],
            ["Thời gian model.transform", f"{self.score_elapsed:.2f}s "
                                          f"({self.score_elapsed / max(1, len(rows)) * 1000:.0f} ms/bình luận)"],
            ["Độ trễ mẫu (mô phỏng, event_ts→chấm)", f"{np.mean(lat) / 1000:.2f}s" if lat else "—"],
            ["Cửa sổ mẫu", fmt_int(len(self.sample_agg)) if self.sample_agg is not None else "—"],
            ["Cảnh báo trên mẫu", "CÓ" if (self.sample_state or {}).get("alert") else "KHÔNG"],
            ["Cửa sổ 1 phút thật verify1 (gộp)",
             fmt_int(len(self.real_agg_1min)) if self.real_agg_1min is not None else "—"],
            ["Cảnh báo trên cửa sổ 1 phút",
             "CÓ" if (self.real_state_1min or {}).get("alert") else "KHÔNG"],
            ["Cửa sổ 10 giây thật verify1 (gộp)",
             fmt_int(len(self.real_agg_slide)) if self.real_agg_slide is not None else "—"],
            ["Cảnh báo trên cửa sổ 10 giây",
             "CÓ" if (self.real_state_slide or {}).get("alert") else "KHÔNG"],
            ["Độ trễ thật verify1 (p50/p95/p99)",
             (f"{self.real_latency['p50'] / 1000:.1f}s / "
              f"{self.real_latency['p95'] / 1000:.1f}s / "
              f"{self.real_latency['p99'] / 1000:.1f}s") if self.real_latency else "—"],
        ]
        self.ui.table(["hạng mục", "giá trị"], tbl, max_widths=[42, 34])
        if test:
            self.ui.section("Model trên tập test")
            self.ui.kv("Accuracy", f"{test.get('accuracy', 0):.4f}")
            self.ui.kv("Macro-F1", f"{test.get('macro_f1', 0):.4f}")
            self.ui.kv("Weighted-F1", f"{test.get('weighted_f1', 0):.4f}")
            self.ui.kv("Số dòng test", fmt_int(test.get("n", 0)))

        self.ui.note("warn", "Replay IMDb, không phải livestream thật · exactly-once chưa "
                             "kiểm chứng · nhãn suy từ rating, lớp neutral nhiễu.")

        self.ui.section("Chạy lại")
        for cmd, desc in [
            ("bash scripts/run_terminal_app.sh", "từng giai đoạn, nhấn Enter"),
            ("bash scripts/run_terminal_app.sh --auto", "tự chạy"),
            ("bash scripts/run_comment_stream.sh", "từng comment, phân tích ngay"),
            ("bash scripts/run_terminal_app.sh --stage 5", "chỉ giai đoạn phân tích"),
            ("bash scripts/run_terminal_app.sh --text \"not bad at all\"", "chấm một câu"),
            ("bash scripts/run_terminal_app.sh --live --duration 60", "theo dõi Kafka"),
            ("bash scripts/run_demo.sh", "Kafka → job → dashboard"),
        ]:
            print("  " + self.ui.c.cyan("▸ " + cmd))
            print("    " + self.ui.c.gray(desc))

    # ======================================================================
    # Chạy từng comment: comment đến -> parse -> clean -> model -> kết quả
    # ======================================================================
    def one_by_one(self) -> None:
        from pyspark.sql import functions as F
        from src.streaming.stream_job import parse_stream, add_cleaning_and_reason

        msgs = self.ensure_messages()
        bad = [] if self.args.no_bad else self._bad_messages()
        spark = self.ensure_spark()
        model, meta, idx2lab = self.ensure_model()
        interval = 0.0 if self.args.fast else max(0.0, float(self.args.interval))

        items = [("comment", m["comment_id"], json.dumps(m, ensure_ascii=False), "")
                 for m in msgs]
        items += [("error", cid, raw, note) for cid, raw, note in bad]

        self.ui.banner("SENTIMENTGUARD — NHÓM 6", "Phân tích từng comment",
                       f"{len(msgs)} comment · {len(bad)} bản ghi lỗi · "
                       "mỗi comment: parse → clean → model")
        self.ui.kv("Model", str(meta.get("model_name", "?")))
        self.ui.kv("Tốc độ", "nhanh (không nghỉ)" if interval == 0 else f"{interval:.1f}s/comment")

        color_of = {"negative": self.ui.c.red, "neutral": self.ui.c.yellow,
                    "positive": self.ui.c.green}
        results: list[dict] = []
        counts = {"ok": 0, "dlq": 0, "right": 0, "labelled": 0}
        n = len(items)

        for i, (_kind, cid, raw, note) in enumerate(items, 1):
            t0 = time.perf_counter()
            raw_df = spark.createDataFrame(
                [(raw, 0, i - 1, datetime.now())],
                "json_raw string, kafka_partition int, kafka_offset long, kafka_ts timestamp")
            # Một Spark action duy nhất cho mỗi comment: bản ghi lỗi vẫn đi qua
            # model với text rỗng để không phải chạy job thứ hai chỉ để lấy lý do DLQ.
            cleaned = (add_cleaning_and_reason(parse_stream(raw_df), self.cfg)
                       .withColumn("text_raw", F.col("text")))
            safe_text = (F.when(F.col("dlq_reason").isNull(), F.col("text_clean"))
                         .otherwise(F.lit("")))
            scored = model.transform(cleaned.withColumn("text", safe_text))
            sr = scored.select(
                "comment_id", "stream_id", "text_raw", "text_clean", "dlq_reason",
                "prediction", "probability", "features",
                F.unix_millis(F.col("event_time")).alias("event_ms"),
            ).first()
            reason = sr["dlq_reason"]

            if reason:
                counts["dlq"] += 1
                self.ui.card(f"[{i}/{n}] LỖI · {cid}", [
                    ("RAW   : " + one_line(raw, 180), self.ui.c.dim),
                    ("KẾT QUẢ: DLQ · " + reason, self.ui.c.red),
                    ("GHI CHÚ: " + (note or "—"), self.ui.c.gray),
                ])
            else:
                pred_idx = int(sr["prediction"])
                probs = {idx2lab[k]: float(p) for k, p in enumerate(list(sr["probability"]))}
                label = idx2lab.get(pred_idx, f"lớp #{pred_idx}")
                contrib = self.contributions({"pred_idx": pred_idx, "features": sr["features"]})
                true_label, rating = self.true_lut.get(cid, ("", ""))
                true_txt = ""
                if true_label:
                    ok = true_label == label
                    counts["labelled"] += 1
                    counts["right"] += int(ok)
                    true_txt = f"{true_label} (rating {rating}) {'✔' if ok else '✘'}"
                elapsed = time.perf_counter() - t0
                counts["ok"] += 1

                lines: list = [
                    ("RAW   : " + one_line(sr["text_raw"], 220), self.ui.c.dim),
                    ("CLEAN : " + one_line(sr["text_clean"], 220), self.ui.c.green),
                    (f"KẾT QUẢ: {label.upper()}  "
                     f"neg {probs.get('negative', float('nan')):.3f} | "
                     f"neu {probs.get('neutral', float('nan')):.3f} | "
                     f"pos {probs.get('positive', float('nan')):.3f}",
                     color_of.get(label, self.ui.c.bold)),
                ]
                if contrib:
                    lines.append(("TỪ    : " + " · ".join(f"“{w}” {v:+.2f}" for w, v in contrib),
                                  self.ui.c.cyan))
                if true_txt:
                    lines.append(("THẬT  : " + true_txt, self.ui.c.magenta))
                lines.append((f"XỬ LÝ : {elapsed * 1000:.0f} ms", self.ui.c.gray))
                self.ui.card(f"[{i}/{n}] {cid} · {trunc(sr['stream_id'], 36)}", lines)

                if sr["event_ms"] is not None:
                    event_dt = datetime.fromtimestamp(sr["event_ms"] / 1000.0, tz=timezone.utc
                                                      ).replace(tzinfo=None)
                    results.append({"comment_id": cid, "event_time": event_dt,
                                    "pred_label": label, "latency_ms": elapsed * 1000})

            if interval and i < n:
                time.sleep(interval)

        self.ui.section("Kết thúc")
        self.ui.kv("Comment đã phân tích", fmt_int(counts["ok"]))
        self.ui.kv("DLQ", fmt_int(counts["dlq"]))
        if counts["labelled"]:
            self.ui.kv("Đúng trên mẫu", f"{counts['right']}/{counts['labelled']} "
                                       f"({counts['right'] / counts['labelled']:.1%})")
        if results:
            try:
                from src.app.app import eval_alerts, windows_from_detail
                detail = pd.DataFrame(results)
                agg = windows_from_detail(detail, 60)
                thr = float(self.cfg["eda"]["alert"]["negative_share_threshold"])
                min_c = int(self.cfg["eda"]["alert"]["min_comments"])
                state = eval_alerts(agg, thr, min_c, recent_s=10 ** 9)
                self._print_windows(agg, state, title="phiên này")
                if int(state.get("n_comments", 0)) < min_c:
                    self.ui.note("warn", f"Cảnh báo chỉ bật khi cửa sổ có ≥ {min_c} "
                                         f"bình luận; phiên này mới "
                                         f"{int(state.get('n_comments', 0))}.")
            except Exception as e:                   # noqa: BLE001
                self.ui.note("err", f"Không gộp được cửa sổ: {e}")

    # ======================================================================
    # Chấm một câu nhập tay (dùng cùng model + cùng clean_text)
    # ======================================================================
    def score_text(self, text: str, title: str = "Bình luận nhập tay") -> None:
        from pyspark.sql import functions as F
        from src.common.text_cleaning import clean_text
        spark = self.ensure_spark()
        model, _meta, idx2lab = self.ensure_model()
        df = spark.createDataFrame([(text,)], "text string").withColumn(
            "clean", clean_text(F.col("text"), self.cfg["cleaning"]["abbreviations"]))
        cleaned = df.first()["clean"]
        row = (model.transform(df.withColumn("text", F.col("clean")))
               .select("prediction", "probability", "features").first())
        pred_idx = int(row["prediction"])
        probs = {idx2lab[i]: float(p) for i, p in enumerate(list(row["probability"]))}
        label = idx2lab.get(pred_idx, f"lớp #{pred_idx}")
        rec = {"pred_idx": pred_idx, "features": row["features"]}
        contrib = self.contributions(rec)
        color_of = {"negative": self.ui.c.red, "neutral": self.ui.c.yellow,
                    "positive": self.ui.c.green}
        lines: list = [
            ("RAW   : " + one_line(text, 300), self.ui.c.dim),
            ("CLEAN : " + one_line(cleaned, 300), self.ui.c.dim),
            (f"NHÃN  : {label.upper()}  (neg {probs.get('negative', float('nan')):.3f} | "
             f"neu {probs.get('neutral', float('nan')):.3f} | "
             f"pos {probs.get('positive', float('nan')):.3f})",
             color_of.get(label, self.ui.c.bold)),
        ]
        if contrib:
            lines.append(("TỪ    : " + " · ".join(f"“{w}” {v:+.2f}" for w, v in contrib),
                          self.ui.c.cyan))
        lines.append(("LƯU Ý  : mô hình túi từ học từ review IMDb tiếng Anh — câu tiếng Việt, "
                      "hoặc phủ định phức tạp như “not bad”, có thể bị đoán sai.",
                      self.ui.c.gray))
        self.ui.card(title, lines)

    def interactive(self) -> None:
        self.ui.banner("PHÂN TÍCH BÌNH LUẬN NHẬP TAY",
                       "Cùng clean_text + PipelineModel của hệ thống",
                       "Gõ một câu tiếng Anh (dữ liệu huấn luyện là tiếng Anh). "
                       "Enter trống hoặc Ctrl+C để thoát.")
        while True:
            try:
                text = input(self.ui.c.cyan("  > "))
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not text.strip():
                break
            self.score_text(text.strip(), title="Bình luận vừa nhập")

    # ======================================================================
    # Điều phối
    # ======================================================================
    def run(self) -> None:
        stages = [
            (1, "THU THẬP DỮ LIỆU GIẢ LẬP", ""),
            (2, "ĐÓNG GÓI MESSAGE", ""),
            (3, "PARSE SCHEMA + KIỂM TRA + DLQ", ""),
            (4, "LÀM SẠCH VĂN BẢN", ""),
            (5, "CHẤM ĐIỂM TỪNG BÌNH LUẬN", ""),
            (6, "GỘP CỬA SỔ + CẢNH BÁO", ""),
            (7, "GHI SINK + KIỂM TRA KAFKA", ""),
            (8, "TỔNG KẾT", ""),
        ]
        selected = [s for s in stages if self.args.stage in (None, s[0])]
        t_all = time.perf_counter()
        for n, title, desc in selected:
            self.ui.stage(n, title, desc)
            t0 = time.perf_counter()
            getattr(self, f"stage_{n}")()
            print(self.ui.c.gray(f"  ⏱ giai đoạn {n} xong sau {time.perf_counter() - t0:.2f}s"))
            if (not self.args.stage and n < STAGE_TOTAL
                    and not self.args.auto and not self.args.fast):
                self.ui.pause(False, 0, "Nhấn Enter để chạy giai đoạn tiếp theo")
        print()
        print(self.ui.c.gray(f"  Tổng thời gian: {time.perf_counter() - t_all:.1f}s"))
        if self.args.text:
            self.ui.section("Chấm câu nhập qua --text")
            self.score_text(self.args.text, title="Câu truyền qua --text")
        if self.args.interactive:
            self.interactive()


# ---------------------------------------------------------------------------
# 2) Chế độ theo dõi Kafka trực tiếp (không cần Spark)
# ---------------------------------------------------------------------------
def live_mode(cfg: dict, ui: UI, duration: int) -> int:
    try:
        from kafka import KafkaConsumer
    except ImportError:
        ui.note("err", "Thiếu kafka-python — chạy: .venv/bin/pip install kafka-python")
        return 2
    boot = cfg["kafka"]["bootstrap_servers"]
    topics = [cfg["kafka"]["topic_raw"], cfg["kafka"]["topic_scored"], cfg["kafka"]["topic_dlq"]]
    ui.banner("CHẾ ĐỘ LIVE", "Theo dõi Kafka đang chạy",
              f"Broker: {boot} · topic: {', '.join(topics)} · {duration}s · Ctrl+C để dừng. "
              "Cần một terminal khác chạy: bash scripts/run_demo.sh")
    try:
        consumer = KafkaConsumer(
            *topics,
            bootstrap_servers=boot,
            auto_offset_reset="latest",
            enable_auto_commit=False,
            consumer_timeout_ms=1200,
            request_timeout_ms=3000,
            bootstrap_timeout_ms=3000,   # kafka-python 3.x: thay api_version_auto_timeout_ms
            value_deserializer=lambda b: b.decode("utf-8", "replace"),
        )
    except Exception as e:                           # noqa: BLE001
        ui.note("err", f"Không kết nối được Kafka tại {boot}: {type(e).__name__}: {e}")
        ui.note("info", "Khởi động hệ thống trước: bash scripts/run_demo.sh")
        return 2

    deadline = time.time() + max(1, int(duration))
    counts = {t: 0 for t in topics}
    try:
        while time.time() < deadline:
            batches = consumer.poll(timeout_ms=1000)
            for _tp, records in batches.items():
                for msg in records:
                    topic = msg.topic
                    counts[topic] = counts.get(topic, 0) + 1
                    stamp = datetime.now().strftime("%H:%M:%S")
                    try:
                        data = json.loads(msg.value)
                    except Exception:                # noqa: BLE001
                        data = {"raw": msg.value}
                    if topic == cfg["kafka"]["topic_raw"]:
                        cid = data.get("comment_id", "?")
                        text = one_line(data.get("text", ""), 70)
                        print(ui.c.cyan(f"[{stamp}] RAW    p{msg.partition}@{msg.offset} "
                                        f"{cid} | {text}"))
                    elif topic == cfg["kafka"]["topic_scored"]:
                        lab = data.get("pred_label", "?")
                        color = {"negative": ui.c.red, "neutral": ui.c.yellow,
                                 "positive": ui.c.green}.get(lab, ui.c.bold)
                        conf = data.get("confidence", "")
                        lat = data.get("latency_ms", "")
                        print(color(f"[{stamp}] SCORED p{msg.partition}@{msg.offset} "
                                    f"{data.get('comment_id', '?')} | {lab} "
                                    f"conf={conf} latency={lat}ms"))
                    else:
                        print(ui.c.yellow(f"[{stamp}] DLQ    p{msg.partition}@{msg.offset} "
                                          f"{data.get('comment_id', '?')} | "
                                          f"{data.get('reason', '?')}"))
    except KeyboardInterrupt:
        print()
    finally:
        consumer.close()

    ui.section("Đã nhận trong phiên live")
    for t in topics:
        ui.kv(t, fmt_int(counts.get(t, 0)) + " message")
    ui.note("info", "Message lấy từ Kafka; nếu job đang xử lý backlog thì `latency` có thể "
                    "rất lớn — đó là độ trễ thật của job. Dữ liệu vẫn là replay IMDb, "
                    "không phải livestream thật.")
    return 0


# ---------------------------------------------------------------------------
# 3) main
# ---------------------------------------------------------------------------
def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Chạy toàn bộ quy trình của dự án ngay trong terminal Ubuntu.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Ví dụ:
              bash scripts/run_terminal_app.sh                    # từng giai đoạn
              bash scripts/run_terminal_app.sh --auto             # tự chạy
              bash scripts/run_comment_stream.sh                  # từng comment
              bash scripts/run_terminal_app.sh --stage 5          # chỉ chấm điểm
              bash scripts/run_terminal_app.sh --text "not bad"   # chấm một câu
              bash scripts/run_terminal_app.sh --live --duration 60
            """))
    ap.add_argument("--config", default=str(PROJECT_ROOT / "config.yaml"))
    ap.add_argument("--limit", type=int, default=12,
                    help="số bình luận thật lấy từ tập test (mặc định 12)")
    ap.add_argument("--cards", type=int, default=5,
                    help="số thẻ chi tiết in ra ở giai đoạn 5 (mặc định 5)")
    ap.add_argument("--seed", type=int, default=None, help="seed lấy mẫu (mặc định config)")
    ap.add_argument("--auto", action="store_true", help="không dừng chờ Enter")
    ap.add_argument("--fast", action="store_true", help="như --auto nhưng không chờ giữa các giai đoạn")
    ap.add_argument("--delay", type=float, default=0.8, help="giây chờ giữa các giai đoạn khi --auto")
    ap.add_argument("--stage", type=int, choices=range(1, STAGE_TOTAL + 1),
                    help="chỉ chạy một giai đoạn (1–8)")
    ap.add_argument("--text", default=None,
                    help="chấm một câu rồi thoát (thêm --auto nếu muốn chạy walkthrough trước)")
    ap.add_argument("--interactive", action="store_true",
                    help="nhập bình luận để chấm rồi thoát (thêm --auto nếu muốn chạy walkthrough trước)")
    ap.add_argument("--live", action="store_true", help="theo dõi Kafka trực tiếp (không chạy walkthrough)")
    ap.add_argument("--duration", type=int, default=60, help="số giây theo dõi ở chế độ --live")
    ap.add_argument("--no-color", action="store_true", help="tắt màu ANSI")
    ap.add_argument("--no-write", action="store_true", help="không ghi outputs/terminal_demo/")
    ap.add_argument("--keep-text", action="store_true",
                    help="ghi thêm đoạn văn bản đã làm sạch vào CSV (chỉ dùng với dữ liệu công khai)")
    ap.add_argument("--no-kafka-check", action="store_true", help="bỏ qua kiểm tra Kafka ở giai đoạn 7")
    ap.add_argument("--one-by-one", action="store_true",
                    help="chạy từng comment: đến đâu phân tích và trả kết quả ngay")
    ap.add_argument("--interval", type=float, default=1.0,
                    help="giây nghỉ giữa các comment ở chế độ --one-by-one (mặc định 1.0)")
    ap.add_argument("--no-bad", action="store_true",
                    help="không chèn 4 bản ghi lỗi cố ý ở chế độ --one-by-one")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config)
    color = (not args.no_color) and sys.stdout.isatty()
    ui = UI(color=color)
    walk_explicit = args.auto or args.fast      # người dùng CHỦ ĐỘNG xin chạy walkthrough
    if args.fast:
        args.auto = True
        args.delay = 0.0
    if not sys.stdin.isatty():
        # Chạy qua pipe/CI: không thể chờ Enter.
        args.auto = True

    if args.live:
        return live_mode(cfg, ui, args.duration)

    if args.one_by_one:
        wt = Walkthrough(cfg, args, ui)
        try:
            wt.one_by_one()
            return 0
        except KeyboardInterrupt:
            print()
            ui.note("warn", "Đã dừng bằng Ctrl+C.")
            return 130
        except FileNotFoundError as e:
            ui.note("err", str(e))
            return 2
        finally:
            wt.close()

    # --text / --interactive một mình = chỉ chấm câu, không chạy lại 8 giai đoạn.
    # Thêm --auto (hoặc --fast) để chạy walkthrough trước rồi mới chấm.
    score_only = (args.text or args.interactive) and args.stage is None and not walk_explicit
    if score_only:
        ui.banner("SENTIMENTGUARD — NHÓM 6",
                  "Chấm một câu bằng đúng model của hệ thống",
                  "Chỉ nạp PipelineModel, không chạy lại 8 giai đoạn. "
                  "Muốn xem toàn bộ quy trình: bash scripts/run_terminal_app.sh")
        wt = Walkthrough(cfg, args, ui)
        try:
            if args.text:
                ui.section("Chấm câu nhập qua --text")
                wt.score_text(args.text, title="Câu truyền qua --text")
            if args.interactive:
                wt.interactive()
            return 0
        except KeyboardInterrupt:
            print()
            ui.note("warn", "Đã dừng bằng Ctrl+C.")
            return 130
        except FileNotFoundError as e:
            ui.note("err", str(e))
            return 2
        finally:
            wt.close()

    ui.banner("SENTIMENTGUARD — NHÓM 6", "Quy trình chạy trong terminal",
              "Replay IMDb · LogisticRegression · at-least-once")
    print("  " + ui.c.bold("QUY TRÌNH"))
    print(ui.c.gray("    " + "   ".join(f"{i} {name}" for i, name in enumerate(PIPELINE[:4], 1))))
    print(ui.c.gray("    " + "   ".join(f"{i} {name}" for i, name in enumerate(PIPELINE[4:], 5))))
    print("  " + ui.c.bold("CÁCH CHẠY"))
    for cmd, desc in [
        ("bash scripts/run_terminal_app.sh", "từng giai đoạn, Enter"),
        ("bash scripts/run_comment_stream.sh", "từng comment, phân tích ngay"),
        ("bash scripts/run_terminal_app.sh --auto", "tự chạy"),
    ]:
        print("    " + ui.c.cyan("▸ " + cmd) + ui.c.gray("  " + desc))
    print()
    ui.kv("Gốc dự án", str(PROJECT_ROOT))
    ui.kv("Cấu hình", rel(Path(args.config)))
    ui.kv("Chế độ", "từng giai đoạn (Enter)" if not args.auto else
          ("nhanh (--fast)" if args.fast else "tự chạy (--auto)"))
    ui.kv("Mẫu", f"{args.limit} bình luận thật + 4 bản ghi lỗi cố ý")

    wt = Walkthrough(cfg, args, ui)
    try:
        wt.run()
        return 0
    except KeyboardInterrupt:
        print()
        ui.note("warn", "Đã dừng bằng Ctrl+C.")
        return 130
    except FileNotFoundError as e:
        ui.note("err", str(e))
        return 2
    finally:
        wt.close()


if __name__ == "__main__":
    raise SystemExit(main())
