#!/usr/bin/env python3
"""send_bad_events.py — Gửi các BẢN GHI LỖI đã biết vào topic `comments_raw`.

`replay_producer.py` chỉ gửi bản ghi hợp lệ (bản thiếu trường bị nó bỏ qua), nên muốn
kiểm chứng nhánh DLQ của job streaming thì phải chủ động gửi bản ghi hỏng. Script này
gửi đúng 11 ca lỗi (mỗi ca 1 message), `comment_id` đặt trước dạng `bad-01...bad-11`
để đối chiếu được về sau:

    01 json hỏng hẳn            ("{not json")
    02 JSON mảng (không phải object)
    03 JSON `null`
    04 thiếu `text`
    05 thiếu `comment_id`
    06 thiếu `event_ts`
    07 `event_ts` sai định dạng
    08 `text` rỗng sau khi làm sạch (toàn khoảng trắng)
    09 `text` quá ngắn (< cleaning.min_chars)
    10 `text` quá dài  (> cleaning.max_chars)
    11 đủ trường nhưng lạc hậu 10 phút so với watermark (đến muộn quá hạn)

LƯU Ý về ca 11: bản ghi này **hợp lệ** nên KHÔNG vào DLQ — nó dùng để chứng minh
watermark: muộn hơn `streaming.watermark` thì bị phép gộp cửa sổ bỏ (đếm ở cột
`num_rows_dropped_by_watermark` trong `outputs/tables/stream_batches.csv`), nhưng
vẫn có mặt trong bảng chi tiết (query `detail` không dùng watermark).

    source scripts/env.sh
    $VENV_PY scripts/send_bad_events.py                 # gửi 11 ca vào comments_raw
    $VENV_PY scripts/send_bad_events.py --dry-run       # chỉ in ra, không gửi

--heartbeat và --late-probe (thêm ở Task 8, dùng cho lần kiểm chứng chính thức)
--------------------------------------------------------------------------------
Watermark chỉ tiến khi có bản ghi MỚI, và một cửa sổ chỉ được ghi ra khi
watermark vượt qua mốc kết thúc cửa sổ. Nếu ngừng gửi ngay sau 1000 bình luận
thì các cửa sổ cuối (kể cả cửa sổ chứa phần lớn dữ liệu) sẽ **nằm lại trong
state**, không bao giờ được ghi ra — đúng theo ngữ nghĩa của Structured Streaming,
nhưng làm việc kiểm chứng cửa sổ dang dở.

    --heartbeat N --heartbeat-interval S   gửi thêm N bản ghi HỢP LỆ (comment_id
                                           hb-001...) cách nhau S giây, đóng vai
                                           "nhịp tim" đẩy watermark tiến lên;
    --late-probe                           sau khi heartbeat xong mới gửi 1 bản ghi
                                           hợp lệ lạc hậu 10 phút -> lần này nó
                                           ĐẾN MUỘN SAU khi watermark đã tiến, nên
                                           bị phép gộp cửa sổ bỏ thật (đếm ở
                                           num_rows_dropped_by_watermark), trong khi
                                           vẫn có trong bảng chi tiết.
                                           (Ca 11 ở trên đến cùng batch đầu nên
                                           watermark lúc đó chưa có -> chưa bị bỏ.)

Ví dụ lần kiểm chứng chính thức:
    $VENV_PY scripts/send_bad_events.py --heartbeat 7 --heartbeat-interval 25 --late-probe
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.common.utils import load_config  # noqa: E402


def iso_utc(ts: float) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def build_cases(cfg: dict, now: float) -> list[tuple[str, str, str]]:
    """-> [(mã ca, mô tả, payload thô)]. Payload là CHUỖI đúng như gửi lên Kafka."""
    min_chars = int(cfg["cleaning"]["min_chars"])
    max_chars = int(cfg["cleaning"]["max_chars"])

    def ok(**kw) -> str:
        msg = {"comment_id": "bad", "stream_id": "stream-test", "user_hash": "deadbeef",
               "text": "a perfectly normal comment with enough characters",
               "event_ts": iso_utc(now)}
        msg.update(kw)
        return json.dumps(msg, ensure_ascii=False)

    return [
        ("01", "json_khong_hop_le: JSON hỏng hẳn", "{not json"),
        ("02", "json_khong_hop_le: JSON là mảng, không phải object", "[1, 2, 3]"),
        ("03", "json_khong_hop_le: JSON null", "null"),
        ("04", "thieu_truong:text",
         json.dumps({"comment_id": "bad-04", "stream_id": "stream-test",
                     "user_hash": "deadbeef", "event_ts": iso_utc(now)})),
        ("05", "thieu_truong:comment_id",
         json.dumps({"stream_id": "stream-test", "user_hash": "deadbeef",
                     "text": "a comment with no id at all but long enough",
                     "event_ts": iso_utc(now)})),
        ("06", "thieu_truong:event_ts",
         json.dumps({"comment_id": "bad-06", "stream_id": "stream-test",
                     "user_hash": "deadbeef",
                     "text": "a comment with no timestamp but long enough"})),
        ("07", "event_ts_khong_doc_duoc",
         json.dumps({"comment_id": "bad-07", "stream_id": "stream-test",
                     "user_hash": "deadbeef",
                     "text": "a comment with a broken timestamp value",
                     "event_ts": "2026-13-45T99:99:99Z"})),
        ("08", "van_ban_rong_sau_lam_sach",
         json.dumps({"comment_id": "bad-08", "stream_id": "stream-test",
                     "user_hash": "deadbeef", "text": "     ",
                     "event_ts": iso_utc(now)})),
        ("09", f"van_ban_qua_ngan (dưới {min_chars} ký tự)",
         json.dumps({"comment_id": "bad-09", "stream_id": "stream-test",
                     "user_hash": "deadbeef", "text": "ok",
                     "event_ts": iso_utc(now)})),
        ("10", f"van_ban_qua_dai (trên {max_chars} ký tự)",
         json.dumps({"comment_id": "bad-10", "stream_id": "stream-test",
                     "user_hash": "deadbeef", "text": "blah " * (max_chars // 5 + 10),
                     "event_ts": iso_utc(now)})),
        ("11", "HỢP LỆ nhưng lạc hậu 10 phút (quá hạn watermark) — dùng để thử watermark",
         ok(comment_id="bad-11", text="late arriving comment, valid on purpose",
            event_ts=iso_utc(now - 600))),
    ]


def heartbeat_payload(comment_id: str, now: float, stream_id: str) -> str:
    """Bản ghi HỢP LỆ để đẩy watermark (event_ts = thời điểm gửi thật)."""
    return json.dumps({
        "comment_id": comment_id,
        "stream_id": stream_id,
        "user_hash": "heartbeat",
        "text": "heartbeat message used to advance the event-time watermark",
        "event_ts": iso_utc(now),
    }, ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser(description="Gửi bản ghi lỗi đã biết vào comments_raw")
    ap.add_argument("--config", default=str(PROJECT_ROOT / "config.yaml"))
    ap.add_argument("--topic", default=None, help="mặc định: kafka.topic_raw")
    ap.add_argument("--dry-run", action="store_true", help="chỉ in ra, không gửi")
    ap.add_argument("--counts", default="1", help="số lần gửi mỗi ca (mặc định 1)")
    ap.add_argument("--skip-bad", action="store_true", help="không gửi 11 ca lỗi, chỉ heartbeat/probe")
    ap.add_argument("--heartbeat", type=int, default=0,
                    help="gửi thêm N bản ghi hợp lệ (hb-001...) để đẩy watermark")
    ap.add_argument("--heartbeat-interval", type=float, default=25.0,
                    help="khoảng cách giây giữa hai heartbeat (mặc định 25)")
    ap.add_argument("--late-probe", action="store_true",
                    help="sau heartbeat, gửi 1 bản ghi hợp lệ lạc hậu 10 phút (phải bị watermark bỏ)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    topic = args.topic or cfg["kafka"]["topic_raw"]
    cases = [] if args.skip_bad else build_cases(cfg, time.time())
    rep = int(args.counts)

    if cases:
        print(f"Chuẩn bị gửi {len(cases)} ca lỗi x {rep} lần vào topic `{topic}` "
              f"({cfg['kafka']['bootstrap_servers']})")
        for code, desc, payload in cases:
            print(f"  bad-{code}: {desc}  [{len(payload)} B]")
    n_heartbeat = max(0, args.heartbeat)
    if n_heartbeat:
        print(f"Sau đó: {n_heartbeat} heartbeat cách nhau {args.heartbeat_interval:g}s "
              f"(~{(n_heartbeat - 1) * args.heartbeat_interval:g}s) để đẩy watermark tiến.")
    if args.late_probe:
        print("Cuối cùng: 1 late-probe (hợp lệ, lạc hậu 10 phút) — phải bị watermark bỏ.")

    # Đếm để đối chiếu về sau: ca 11 là HỢP LỆ (không vào DLQ), 10 ca còn lại vào DLQ.
    valid_expected = rep * 1 + n_heartbeat + (1 if args.late_probe else 0)   # ca 11 + heartbeat + probe
    dlq_expected = rep * (len(cases) - 1) if cases else 0

    if args.dry_run:
        print("--dry-run: không gửi gì.")
        print(f"[dry-run] dự kiến: valid={valid_expected} dlq={dlq_expected}")
        return 0

    from kafka import KafkaProducer
    producer = KafkaProducer(bootstrap_servers=cfg["kafka"]["bootstrap_servers"],
                             acks=cfg["kafka"]["producer"].get("acks", "all"),
                             retries=5)
    sent = 0
    try:
        for _ in range(rep):
            for code, _desc, payload in cases:
                producer.send(topic, key=f"bad-{code}".encode("utf-8"),
                              value=payload.encode("utf-8"))
                sent += 1
        producer.flush(timeout=60)

        for i in range(n_heartbeat):
            if i:
                time.sleep(args.heartbeat_interval)
            payload = heartbeat_payload(f"hb-{i + 1:03d}", time.time(), "heartbeat")
            producer.send(topic, key=f"hb-{i + 1:03d}".encode("utf-8"),
                          value=payload.encode("utf-8"))
            sent += 1
            print(f"  [{time.strftime('%H:%M:%S')}] hb-{i + 1:03d} (event_ts=now)")

        if args.late_probe:
            payload = json.dumps({
                "comment_id": "probe-late", "stream_id": "heartbeat",
                "user_hash": "heartbeat",
                "text": "probe: valid but ten minutes late, must be dropped by the watermark",
                "event_ts": iso_utc(time.time() - 600),
            }, ensure_ascii=False)
            producer.send(topic, key=b"probe-late", value=payload.encode("utf-8"))
            sent += 1
            print(f"  [{time.strftime('%H:%M:%S')}] probe-late (event_ts=now-600s)")
    finally:
        producer.flush(timeout=60)
        producer.close(timeout=10)
    print(f"Đã gửi {sent} message vào `{topic}`: {valid_expected} HỢP LỆ "
          f"(ca 11 + heartbeat + probe) + {dlq_expected} vào DLQ.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
