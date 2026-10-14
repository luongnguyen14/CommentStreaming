# src/producer — Kafka producer (Task 5)

- `replay_producer.py` — phát lại dữ liệu có nhãn (IMDb) qua Kafka để **mô phỏng**
  một livestream: tốc độ thật, có đợt bùng nổ, có bản ghi đến muộn.
- `test_consumer.py` — đọc topic, in mẫu, đếm message, kiểm chứng "gửi N đọc đủ N".
- `live_producer.py` — **cố ý KHÔNG viết**: `docs/topic_decision.md` kết luận
  *không dùng livestream thật* (điều khoản YouTube/Twitch gần như không cho phép —
  xem mục "Nguồn bình luận livestream thật" trong tài liệu đó).

⚠️ Message gửi lên Kafka **không chứa nhãn** (comment_id, stream_id, user_hash,
text, event_ts). Nhãn đánh giá lưu riêng ở `data/processed/eval_labels.parquet`.
⚠️ `user_hash` là **băm có muối**, muối đọc từ biến môi trường — không hard-code.
⚠️ Đây là **dữ liệu replay mô phỏng**, không phải dữ liệu livestream thật —
luôn nói rõ khi báo cáo (CLAUDE.md §9).

## Chuẩn bị (một lần)

```bash
# Muối băm: sinh rồi cất vào file riêng, KHÔNG commit
python3 -c "import secrets;print('export COMMENT_HASH_SALT='+secrets.token_hex(16))" \
  >> ~/.capstone-secrets.sh && chmod 600 ~/.capstone-secrets.sh

source scripts/env.sh          # nạp biến môi trường + muối (nếu file tồn tại)
bash kafka/start_kafka.sh
bash kafka/create_topics.sh
```

## replay_producer.py

```bash
$VENV_PY src/producer/replay_producer.py --help

# Chạy thử nhỏ trước (quy ước CLAUDE.md §3)
$VENV_PY src/producer/replay_producer.py --sample 200 --rate 20

# Gửi 1000 message nhanh nhất có thể
$VENV_PY src/producer/replay_producer.py --max 1000 --rate 0

# Mô phỏng livestream: 50 bình luận/s, có bùng nổ, lặp lại vô hạn (Ctrl+C để dừng)
$VENV_PY src/producer/replay_producer.py --sample 500 --loop --rate 50 --burst 0.05

# Có ghi báo cáo thông lượng
$VENV_PY src/producer/replay_producer.py --max 2000 --rate 100 \
    --report outputs/tables/ingestion_report.csv
```

| Tham số | Ý nghĩa |
|---|---|
| `--rate R` | bình luận/giây (`0` = không giới hạn); mặc định lấy từ `config.yaml` |
| `--max N` | gửi tối đa N message rồi dừng |
| `--sample N` | lấy mẫu ngẫu nhiên N bản ghi trong file (seed 42) |
| `--loop` | gửi lặp lại khi hết dữ liệu |
| `--burst P` | xác suất bắt đầu đợt bùng nổ (tốc độ ×8 trong 2 s, theo config) |
| `--late-ratio P` | tỷ lệ bản ghi có `event_ts` bị đẩy trễ 5–30 s (để thử watermark) |
| `--topic/--config/--labels-out/--report/--seed/--log-every` | như tên gọi |

## test_consumer.py

```bash
$VENV_PY src/producer/test_consumer.py                  # đọc từ đầu topic, in 3 mẫu
$VENV_PY src/producer/test_consumer.py --expect 1000    # kiểm chứng đủ 1000 (exit 0/1)
```

Consumer kiểm tra luôn: đủ 5 trường bắt buộc và **không có trường nhãn**
(`label`/`rating`/`sentiment`) rò vào luồng.

## Kết quả đo được (14/10/2026, xem outputs/tables/ingestion_report.csv)

| Mức `--rate` | Thực đo |
|---|---|
| 100 | 100.0 msg/s |
| 500 | 499.0 msg/s |
| 2000 | 1973.7 msg/s |
| 0 (không giới hạn) | 3614.6 msg/s |
| 100 + `--burst 0.02` | 559.5 msg/s (trung bình, do bùng nổ vượt nhịp) |

Kiểm chứng end-to-end: gửi 1000 → nhận đủ 1000, 0 lỗi
(`logs/task5_1000msg_*.log`).

## Chạy lại từ đầu (máy mới)

1. `source scripts/env.sh` (cần `~/.capstone-secrets.sh` chứa `COMMENT_HASH_SALT`)
2. `bash kafka/start_kafka.sh && bash kafka/create_topics.sh`
3. `$VENV_PY src/producer/replay_producer.py --sample 200 --rate 20`
4. `$VENV_PY src/producer/test_consumer.py`
