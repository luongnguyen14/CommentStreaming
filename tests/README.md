# tests — Test nhỏ cho các hàm dùng chung

Chạy:

```bash
source scripts/env.sh
.venv/bin/python -m pytest tests/ -q
```

Test chạy trên **SparkSession thật (`local[2]`)** với DataFrame nhỏ — đúng cách các
hàm được dùng trong pipeline, không test bằng chuỗi Python thuần.

| File | Kiểm tra gì |
|---|---|
| `test_text_cleaning.py` | Làm sạch văn bản: chữ thường, URL/`@mention` → token, bỏ HTML, rút gọn ký tự lặp, viết tắt theo ranh giới từ, tách emoji, đếm tần suất emoji, gộp khoảng trắng, **tính idempotent**, khoá chống trùng |
| `test_utils.py` | **Băm có muối của Spark khớp băm của Python** (train và streaming phải ra cùng `user_hash`), độ dài/hex của hash, người dùng thiếu mã, ánh xạ nhãn phủ đủ rating 1–10, đọc mảng JSON lớn theo dòng, các khoá bắt buộc trong `config.yaml` |

Kết quả lần chạy gần nhất (14/10/2026): **28 passed**.
