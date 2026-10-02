# data/processed — Dữ liệu đã xử lý

Sinh ra bởi `src/training/prepare.py`. Gồm:
- `train.parquet`, `val.parquet`, `test.parquet` — chia cố định sau khi loại trùng
- `eval_labels.parquet` — nhãn của tập test, ghép theo `comment_id`, **dùng riêng cho đánh giá**

Có thể xóa và tạo lại từ `data/raw/` + config. Không commit lên git.
