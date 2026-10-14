#!/usr/bin/env python3
"""replay_producer.py — Phát lại dữ liệu IMDb qua Kafka để MÔ PHỎNG một livestream.

Đây là **dữ liệu replay**, KHÔNG phải bình luận livestream thật (xem
docs/topic_decision.md và CLAUDE.md §9) — mọi tài liệu nộp phải nói rõ điều này.

Message gửi lên topic `comments_raw` (JSON, UTF-8):
    {comment_id, stream_id, user_hash, text, event_ts}
    - KHÔNG chứa nhãn (nhãn chỉ để đánh giá, không được rò vào luồng — CLAUDE.md §6)
    - user_hash = băm SHA-256 có muối của mã người dùng; muối đọc từ biến môi
      trường COMMENT_HASH_SALT (không hard-code — CLAUDE.md §7)

Nhãn đánh giá lưu RIÊNG ở data/processed/eval_labels.parquet theo comment_id
(nhãn suy từ cột `rating`; ánh xạ chính thức ở config.yaml mục `labels.mapping`).
File đó do src/training/prepare.py tạo cho tập test — producer chỉ ĐỌC, không ghi
đè (muốn ghi nhãn của đợt phát thì truyền --labels-out <file mới>).

Nguồn phát mặc định là bản JSONL đã xử lý (~200 MB) ở data/processed/imdb_jsonl;
`--source raw` để đọc thẳng file gốc 1,1 GB (chậm hơn).

Ví dụ:
    # phát đúng tập test (nhãn đã có sẵn trong eval_labels.parquet)
    .venv/bin/python src/producer/replay_producer.py --only-test --sample 500 --rate 50
    .venv/bin/python src/producer/replay_producer.py --sample 200 --rate 20
    .venv/bin/python src/producer/replay_producer.py --max 1000 --rate 0        # nhanh nhất có thể
    .venv/bin/python src/producer/replay_producer.py --sample 500 --loop --rate 50 --burst 0.05
    .venv/bin/python src/producer/replay_producer.py --max 2000 --rate 100 \
        --report outputs/tables/ingestion_report.csv
"""

from __future__ import annotations

import argparse
import json
import random
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.common.utils import get_salt, iter_json_array, load_config, salted_hash  # noqa: E402

try:
    from kafka import KafkaProducer
except ImportError:  # pragma: no cover
    sys.exit("Thiếu thư viện kafka-python — chạy: .venv/bin/pip install kafka-python")

STOP = False


def _on_sigint(signum, frame):  # Ctrl+C: dừng êm — vẫn ghi nhãn + báo cáo
    global STOP
    STOP = True


def iso_utc(ts: float) -> str:
    """epoch giây -> ISO-8601 UTC có mili giây, ví dụ 2026-10-14T14:42:45.123Z."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def build_label_map(cfg: dict) -> dict[str, str]:
    """{rating(str): nhãn} từ config.yaml — mục `labels.mapping` (ánh xạ chính
    thức chốt ở Task 6, dùng chung với src/training/prepare.py)."""
    return {str(r): label
            for label, ratings in cfg["labels"]["mapping"].items()
            for r in ratings}


def iter_jsonl(path: Path):
    """Đọc file JSONL (mỗi dòng một object) — dùng cho bản đã xử lý ở
    data/processed/imdb_jsonl (tập con ~200 MB thay vì file gốc 1,1 GB)."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def reservoir_sample(path: Path, n: int, seed: int, reader=iter_json_array) -> list[dict]:
    """Mẫu ngẫu nhiên đều trên toàn file (reservoir sampling, không nạp cả file)."""
    rng = random.Random(seed)
    sample: list[dict] = []
    for i, rec in enumerate(reader(path)):
        if i < n:
            sample.append(rec)
        elif rng.randint(0, i) < n:
            sample[rng.randint(0, n - 1)] = rec
    return sample


def record_to_message(rec: dict, cfg: dict, salt: bytes, label_map: dict):
    """Bản ghi thô -> (message, nhãn, rating). (None, None, None) nếu thiếu trường bắt buộc."""
    r = cfg["replay"]
    comment_id = rec.get(r["id_field"])
    text = rec.get(r["text_field"])
    if not comment_id or text is None:
        return None, None, None
    rating = str(rec.get("rating", "")).strip()
    msg = {
        "comment_id": comment_id,
        "stream_id": rec.get(r["stream_field"], "unknown"),
        "user_hash": salted_hash(str(rec.get(r["user_field"], "")), salt=salt),
        "text": text,
        "event_ts": iso_utc(time.time()),      # sẽ được ghi lại ngay trước khi gửi
    }
    return msg, label_map.get(rating), rating


def replay(args, cfg: dict, producer, salt: bytes, label_map: dict, raw_path: Path,
           only_ids: set[str] | None = None):
    """Vòng lặp gửi: điều tiết tốc độ, bùng nổ, bản ghi đến muộn, đếm đã xác nhận."""
    r = cfg["replay"]
    rate = args.rate if args.rate is not None else r["rate"]
    late_ratio = args.late_ratio if args.late_ratio is not None else r["late_ratio"]
    burst_prob = args.burst if args.burst is not None else r["burst_prob"]
    burst_factor = r["burst_factor"]
    burst_len_s = r["burst_len_s"]
    late_max_s = float(r["late_max_s"])

    rng = random.Random(args.seed)
    stats = {"delivered": 0, "failed": 0}

    # kafka-python gọi add_callback(metadata) khi THÀNH CÔNG và add_errback(exc)
    # khi lỗi — không phải kiểu callback(err, meta) của một số client khác.
    def on_success(_meta):
        stats["delivered"] += 1

    def on_error(exc):
        stats["failed"] += 1
        if stats["failed"] <= 3:
            print(f"  [LỖI GỬI] {type(exc).__name__}: {exc}", file=sys.stderr)

    def source():
        """Iterator bản ghi cho một vòng (sample là list, ngược lại đọc file theo dòng)."""
        return iter(args._sample) if args._sample else iter(args._reader(args._source_path))

    step = (1.0 / rate) if rate and rate > 0 else 0.0     # 0 = gửi nhanh nhất có thể
    labels: dict[str, dict] = {}
    sent = 0
    bytes_sent = 0
    skipped = 0
    filtered = 0
    t_start = None
    next_due = None
    burst_until = 0.0

    while not STOP:
        produced_any = False
        for rec in source():
            if STOP:
                break
            msg, label, rating = record_to_message(rec, cfg, salt, label_map)
            if msg is None:
                skipped += 1
                continue
            if only_ids is not None and msg["comment_id"] not in only_ids:
                filtered += 1          # --only-test: ngoài tập test thì không phát
                continue
            produced_any = True

            now = time.time()
            if t_start is None:
                t_start = now
                next_due = now

            # --- điều tiết tốc độ, có đợt bùng nổ ---
            if step:
                if now < burst_until:
                    cur_step = step / burst_factor
                else:
                    cur_step = step
                    if rng.random() < burst_prob:
                        burst_until = now + burst_len_s
                next_due += cur_step
                if next_due > now:
                    time.sleep(min(next_due - now, 1.0))

            # --- event_ts: đồng hồ gần thời gian thực; một tỷ lệ nhỏ bị đẩy trễ
            #     để bài toán watermark ở streaming có việc thật để xử lý ---
            event_ts = time.time()
            if rng.random() < late_ratio:
                event_ts -= rng.uniform(5.0, late_max_s)
            msg["event_ts"] = iso_utc(event_ts)

            payload = json.dumps(msg, ensure_ascii=False).encode("utf-8")
            bytes_sent += len(payload)
            producer.send(args.topic, key=msg["comment_id"].encode("utf-8"),
                          value=payload).add_callback(on_success).add_errback(on_error)

            if label is not None:
                labels[msg["comment_id"]] = {"label": label, "rating": rating}

            sent += 1
            if args.log_every and sent % args.log_every == 0:
                el = time.time() - t_start
                print(f"  ... {sent} message ({sent / el:.0f} msg/s đặt lịch, "
                      f"{stats['delivered']} đã xác nhận)", flush=True)
            if args.max and sent >= args.max:
                break

        if not args.loop or STOP or not produced_any:
            break

    print("Đang chờ Kafka xác nhận hết message còn lại ...", flush=True)
    producer.flush(timeout=120)
    elapsed = (time.time() - t_start) if t_start else 0.0
    return (sent, stats["delivered"], stats["failed"], labels, skipped, filtered,
            elapsed, bytes_sent)


def write_labels(labels: dict[str, dict], labels_out: Path) -> int:
    """Ghi (và trộn với file cũ) nhãn đánh giá: CHỈ comment_id + label + rating."""
    import pandas as pd

    rows = [{"comment_id": cid, "label": v["label"], "rating": v["rating"]}
            for cid, v in labels.items()]
    new = pd.DataFrame(rows)
    labels_out.parent.mkdir(parents=True, exist_ok=True)
    if labels_out.exists():
        new = pd.concat([pd.read_parquet(labels_out), new], ignore_index=True)
    new = new.drop_duplicates(subset="comment_id", keep="last").sort_values("comment_id")
    new.to_parquet(labels_out, index=False)
    return len(new)


def append_report(rep_path: Path, args, cfg, sent, delivered, failed, elapsed, bytes_sent):
    import csv

    new_file = not rep_path.exists()
    rep_path.parent.mkdir(parents=True, exist_ok=True)
    with open(rep_path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp_utc", "topic", "rate_target", "burst_prob", "late_ratio",
                        "sent", "delivered", "errors", "seconds", "msgs_per_sec", "bytes", "note"])
        w.writerow([iso_utc(time.time()), args.topic,
                    args.rate if args.rate is not None else cfg["replay"]["rate"],
                    args.burst if args.burst is not None else cfg["replay"]["burst_prob"],
                    args.late_ratio if args.late_ratio is not None else cfg["replay"]["late_ratio"],
                    sent, delivered, failed, f"{elapsed:.2f}",
                    f"{delivered / elapsed:.1f}" if elapsed > 0 else "0",
                    bytes_sent,
                    f"sample={args.sample} max={args.max} loop={args.loop} seed={args.seed}"])


def main() -> int:
    ap = argparse.ArgumentParser(description="Replay dữ liệu IMDb qua Kafka (mô phỏng livestream)")
    ap.add_argument("--config", default=str(PROJECT_ROOT / "config.yaml"))
    ap.add_argument("--source", choices=["jsonl", "raw"], default="jsonl",
                    help="jsonl (mặc định): bản đã xử lý ~200 MB ở paths.raw_jsonl; "
                         "raw: file gốc paths.raw_comments (1,1 GB)")
    ap.add_argument("--topic", default=None, help="mặc định: kafka.topic_raw trong config")
    ap.add_argument("--rate", type=float, default=None, help="bình luận/giây (0 = không giới hạn)")
    ap.add_argument("--max", type=int, default=0, help="số message tối đa (0 = không giới hạn)")
    ap.add_argument("--sample", type=int, default=0,
                    help="chỉ dùng N bản ghi lấy mẫu ngẫu nhiên từ file (0 = cả file)")
    ap.add_argument("--loop", action="store_true", help="lặp lại dữ liệu khi hết")
    ap.add_argument("--burst", type=float, default=None,
                    help="xác suất bắt đầu đợt bùng nổ mỗi bước gửi (mặc định theo config)")
    ap.add_argument("--late-ratio", type=float, default=None,
                    help="tỷ lệ bản ghi có event_ts bị đẩy trễ (mặc định theo config)")
    ap.add_argument("--only-test", action="store_true",
                    help="chỉ phát các comment_id thuộc tập test (đọc paths.eval_labels) — "
                         "nhãn đã có sẵn ở đó nên KHÔNG cần --labels-out")
    ap.add_argument("--labels-out", default=None,
                    help="file parquet để ghi nhãn đánh giá; BỎ TRỐNG thì không ghi "
                         "(mặc định không ghi: data/processed/eval_labels.parquet do "
                         "src/training/prepare.py tạo, chỉ chứa tập test — tránh ghi đè)")
    ap.add_argument("--report", default=None, help="ghi 1 dòng thống kê thông lượng vào CSV (append)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--log-every", type=int, default=500)
    args = ap.parse_args()

    cfg = load_config(args.config)
    args.seed = args.seed if args.seed is not None else cfg["seed"]
    args.topic = args.topic or cfg["kafka"]["topic_raw"]
    raw_path = PROJECT_ROOT / cfg["paths"]["raw_comments"]
    eval_labels_path = PROJECT_ROOT / cfg["paths"]["eval_labels"]
    labels_out = None
    if args.labels_out:
        labels_out = Path(args.labels_out)
        if not labels_out.is_absolute():
            labels_out = PROJECT_ROOT / labels_out

    only_ids = None
    if args.only_test:
        import pandas as pd
        if not eval_labels_path.exists():
            print(f"LỖI: --only-test cần {eval_labels_path.relative_to(PROJECT_ROOT)} "
                  f"(chạy src/training/prepare.py trước)", file=sys.stderr)
            return 2
        only_ids = set(pd.read_parquet(eval_labels_path, columns=["comment_id"])["comment_id"])
        print(f"--only-test: chỉ phát {len(only_ids):,} comment_id của tập test")

    try:
        salt = get_salt()
    except Exception as e:
        print(f"LỖI: {e}", file=sys.stderr)
        return 2
    if not raw_path.exists():
        print(f"LỖI: không thấy dữ liệu nguồn {raw_path}", file=sys.stderr)
        return 2

    # Nguồn phát: mặc định bản JSONL đã xử lý (~200 MB, tập con của nguồn) cho
    # nhanh; --source raw để đọc thẳng file gốc 1,1 GB nếu cần.
    if args.source == "jsonl":
        src_path = PROJECT_ROOT / cfg["paths"]["raw_jsonl"] / "part-000.jsonl"
        if not src_path.exists():
            print(f"LỖI: chưa có {src_path.relative_to(PROJECT_ROOT)} — chạy "
                  f"src/training/prepare.py trước, hoặc dùng --source raw", file=sys.stderr)
            return 2
        args._reader = iter_jsonl
    else:
        src_path = raw_path
        args._reader = iter_json_array
    args._source_path = src_path

    args._sample = None
    if args.sample:
        t0 = time.time()
        args._sample = reservoir_sample(src_path, args.sample, args.seed, args._reader)
        print(f"Đã lấy mẫu {len(args._sample)} bản ghi trong {time.time() - t0:.1f}s (seed={args.seed})")

    print(f"Nguồn: {src_path.name} ({args.source}) | topic: {args.topic} | "
          f"rate={args.rate if args.rate is not None else cfg['replay']['rate']} | "
          f"max={args.max or '∞'} | loop={args.loop} | late_ratio="
          f"{args.late_ratio if args.late_ratio is not None else cfg['replay']['late_ratio']}",
          flush=True)

    producer = KafkaProducer(
        bootstrap_servers=cfg["kafka"]["bootstrap_servers"],
        acks=cfg["kafka"]["producer"].get("acks", "all"),
        linger_ms=cfg["kafka"]["producer"].get("linger_ms", 0),
        retries=5,
    )
    signal.signal(signal.SIGINT, _on_sigint)

    try:
        sent, delivered, failed, labels, skipped, filtered, elapsed, bytes_sent = replay(
            args, cfg, producer, salt, build_label_map(cfg), raw_path, only_ids)
    finally:
        producer.close(timeout=10)

    print(f"\nKết quả: đặt lịch {sent} message | Kafka xác nhận {delivered} | lỗi {failed} | "
          f"bỏ qua (thiếu trường) {skipped} | ngoài tập test {filtered:,}")
    print(f"Thời gian {elapsed:.2f}s -> {delivered / elapsed:.1f} msg/s | "
          f"{bytes_sent / 1024:.1f} KiB | {bytes_sent / max(len(labels), 1):.0f} B/label" if labels
          else f"Thời gian {elapsed:.2f}s -> {delivered / elapsed:.1f} msg/s | {bytes_sent / 1024:.1f} KiB")

    if labels and labels_out is not None:
        total = write_labels(labels, labels_out)
        print(f"Nhãn: {total} dòng -> {labels_out.relative_to(PROJECT_ROOT)} "
              f"(chỉ comment_id + label + rating — không có thông tin cá nhân)")
    elif labels:
        print(f"Nhãn: {len(labels)} comment_id đã phát (không ghi file — dùng --labels-out nếu muốn)")

    if args.report:
        rep = Path(args.report)
        if not rep.is_absolute():
            rep = PROJECT_ROOT / rep
        append_report(rep, args, cfg, sent, delivered, failed, elapsed, bytes_sent)
        print(f"Báo cáo thông lượng: +1 dòng -> {rep.relative_to(PROJECT_ROOT)}")

    return 0 if delivered > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
