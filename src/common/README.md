# src/common — Hàm dùng chung

- `utils.py` — đọc `config.yaml`, **băm có muối** mã người dùng (`salted_hash`,
  muối từ biến môi trường `COMMENT_HASH_SALT`), đọc file JSON lớn theo từng bản ghi
  (`iter_json_array` — dùng cho `data/raw/part-01.json` 1,1 GB).
- `plotting.py` — bảng màu + thiết lập chung cho mọi biểu đồ (PNG 200 dpi,
  chữ tiếng Anh, cùng bộ màu 3 lớp cảm xúc ở mọi hình — CLAUDE.md §8).
- `text_cleaning.py` — làm sạch văn bản bằng **hàm Spark SQL** (Task 6): chữ thường,
  URL → `<url>`, @mention → `<user>`, viết tắt/teencode theo từ điển trong
  `config.yaml`, rút gọn ký tự lặp ("haaaay" → "haay"), tách emoji thành token riêng
  (đếm được tần suất), gộp khoảng trắng; kèm `dedup_key` (khoá chống trùng) và
  `emoji_frequency`. Hàm **idempotent** (làm sạch hai lần vẫn ra cùng kết quả).
  Không dùng Python UDF; test ở `tests/test_text_cleaning.py`.

⚠️ **`text_cleaning.py` là nguồn duy nhất** cho logic làm sạch văn bản.
Cả huấn luyện (`src/training`) và streaming (`src/streaming`) **phải import từ đây**
để tránh lệch phân phối giữa lúc train và lúc chạy thật.

## Muối băm hoạt động thế nào

`COMMENT_HASH_SALT` **không** nằm trong repo. File `~/.capstone-secrets.sh`
(quyền 600, chỉ trên máy này) chứa biến đó và được `scripts/env.sh` nạp tự động.
Thiếu muối thì các script báo lỗi rõ ràng kèm lệnh sinh muối, **không đoán giá trị**.
