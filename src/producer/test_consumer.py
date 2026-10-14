#!/usr/bin/env python3
"""test_consumer.py — Đọc topic Kafka để KIỂM TRA producer (không phải job streaming).

Đọc từ đầu topic (--from-beginning, mặc định) hoặc từ cuối, in vài mẫu JSON,
đếm số message và các trường thiếu, rồi thoát sau --idle-timeout giây không có
message mới. Dùng --expect N để kiểm chứng "gửi N, đọc đủ N" (exit code 0/1).

Ví dụ:
    .venv/bin/python src/producer/test_consumer.py --expect 1000
    .venv/bin/python src/producer/test_consumer.py --topic comments_raw --from-now --samples 3
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.common.utils import load_config  # noqa: E402

try:
    from kafka import KafkaConsumer, TopicPartition
except ImportError:  # pragma: no cover
    sys.exit("Thiếu thư viện kafka-python — chạy: .venv/bin/pip install kafka-python")

REQUIRED_FIELDS = ("comment_id", "stream_id", "user_hash", "text", "event_ts")
FORBIDDEN_FIELDS = ("label", "rating", "sentiment")   # nhãn không được rò vào luồng


def check_message(raw: bytes) -> tuple[dict | None, list[str]]:
    """Giải mã + kiểm tra trường bắt buộc/trường bị cấm. Trả (msg, danh sách lỗi)."""
    errs: list[str] = []
    try:
        msg = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return None, [f"JSON hỏng: {e}"]
    missing = [f for f in REQUIRED_FIELDS if not msg.get(f)]
    if missing:
        errs.append("thiếu trường: " + ",".join(missing))
    leaked = [f for f in FORBIDDEN_FIELDS if f in msg]
    if leaked:
        errs.append("rò nhãn vào luồng: " + ",".join(leaked))
    return msg, errs


def main() -> int:
    ap = argparse.ArgumentParser(description="Đọc và kiểm tra message trên topic Kafka")
    ap.add_argument("--config", default=str(PROJECT_ROOT / "config.yaml"))
    ap.add_argument("--topic", default=None, help="mặc định: kafka.topic_raw trong config")
    ap.add_argument("--from-now", action="store_true",
                    help="chỉ đọc message mới (mặc định: đọc từ đầu topic)")
    ap.add_argument("--expect", type=int, default=0, help="số message mong đợi (kiểm chứng)")
    ap.add_argument("--samples", type=int, default=3, help="số mẫu in ra đầu tiên")
    ap.add_argument("--idle-timeout", type=float, default=10.0,
                    help="dừng khi không có message mới trong bấy nhiêu giây")
    ap.add_argument("--max-seconds", type=float, default=0,
                    help="dừng cứng sau bấy nhiêu giây (0 = không giới hạn)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    topic = args.topic or cfg["kafka"]["topic_raw"]

    consumer = KafkaConsumer(
        bootstrap_servers=cfg["kafka"]["bootstrap_servers"],
        group_id=f"test-inspect-{int(time.time())}",
        auto_offset_reset="latest" if args.from_now else "earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=2000,
    )
    parts = consumer.partitions_for_topic(topic)
    if not parts:
        print(f"LỖI: topic '{topic}' không tồn tại. Tạo bằng: bash kafka/create_topics.sh",
              file=sys.stderr)
        return 2
    consumer.assign([TopicPartition(topic, p) for p in sorted(parts)])
    if args.from_now:
        consumer.seek_to_end()
    else:
        consumer.seek_to_beginning()

    t_start = time.time()
    last_msg_at = t_start
    count = 0
    bad = 0
    bytes_total = 0
    per_part: dict[int, int] = {}
    first_sample: list[dict] = []
    last_ts = None
    stop = False

    while not stop:
        got = consumer.poll(timeout_ms=1000)
        now = time.time()
        for tp, records in got.items():
            for rec in records:
                count += 1
                bytes_total += len(rec.value)
                per_part[tp.partition] = per_part.get(tp.partition, 0) + 1
                last_msg_at = now
                msg, errs = check_message(rec.value)
                if errs:
                    bad += 1
                    if bad <= 5:
                        print(f"  [LỖI] partition {tp.partition} offset {rec.offset}: {errs}")
                elif len(first_sample) < args.samples:
                    first_sample.append(msg)
                if msg:
                    last_ts = msg.get("event_ts")
        if count >= args.expect > 0:
            stop = True
        elif now - last_msg_at > args.idle_timeout:
            stop = True
        elif args.max_seconds and now - t_start > args.max_seconds:
            stop = True

    consumer.close()
    elapsed = time.time() - t_start

    print(f"\nTopic '{topic}': đọc {count} message trong {elapsed:.2f}s "
          f"({count / elapsed:.1f} msg/s) | {bytes_total / 1024:.1f} KiB")
    print(f"  theo partition: {dict(sorted(per_part.items()))}")
    print(f"  message lỗi: {bad}")

    print(f"\nMẫu ({len(first_sample)}):")
    for m in first_sample:
        text = (m.get("text") or "").replace("\n", " ")[:70]
        print(f"  comment_id={m.get('comment_id')} stream_id={m.get('stream_id')} "
              f"user_hash={m.get('user_hash')} event_ts={m.get('event_ts')}")
        print(f'    text: "{text}..."')

    if args.expect:
        ok = count == args.expect and bad == 0
        print(f"\nKIỂM CHỨNG: mong đợi {args.expect} message, đọc được {count} -> "
              f"{'ĐẠT' if ok else 'KHÔNG ĐẠT'}")
        if last_ts:
            print(f"  event_ts của message cuối: {last_ts}")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
