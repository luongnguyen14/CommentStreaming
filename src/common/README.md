# src/common — Hàm dùng chung

- `utils.py` — đọc `config.yaml`, **băm có muối** mã người dùng (`salted_hash`,
  muối từ biến môi trường `COMMENT_HASH_SALT`), đọc file JSON lớn theo từng bản ghi
  (`iter_json_array` — dùng cho `data/raw/part-01.json` 1,1 GB).
- `plotting.py` — bảng màu + thiết lập chung cho mọi biểu đồ (PNG 200 dpi,
  chữ tiếng Anh, cùng bộ màu 3 lớp cảm xúc ở mọi hình — CLAUDE.md §8).
- `text_cleaning.py` — chuẩn hóa văn bản bằng **hàm Spark SQL** (không dùng Python UDF khi tránh được) *(Task 6/7)*

⚠️ **`text_cleaning.py` là nguồn duy nhất** cho logic làm sạch văn bản.
Cả huấn luyện (`src/training`) và streaming (`src/streaming`) **phải import từ đây**
để tránh lệch phân phối giữa lúc train và lúc chạy thật.

## Muối băm hoạt động thế nào

`COMMENT_HASH_SALT` **không** nằm trong repo. File `~/.capstone-secrets.sh`
(quyền 600, chỉ trên máy này) chứa biến đó và được `scripts/env.sh` nạp tự động.
Thiếu muối thì các script báo lỗi rõ ràng kèm lệnh sinh muối, **không đoán giá trị**.
