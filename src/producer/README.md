# src/producer — Kafka producer

- `replay_producer.py` — phát lại dữ liệu có nhãn qua Kafka để **mô phỏng** livestream
- `live_producer.py` — (tùy chọn) lấy bình luận livestream thật; **chỉ làm nếu điều khoản nền tảng cho phép**
- `test_consumer.py` — đọc topic và in mẫu để kiểm tra

⚠️ Message gửi lên Kafka **không chứa nhãn**. Nhãn đánh giá lưu riêng ở `data/processed/eval_labels.parquet`.
⚠️ `user_hash` là **băm có muối**, muối đọc từ biến môi trường — không hard-code.
