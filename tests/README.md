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
| `test_dashboard.py` | Dashboard Task 10 (pandas thuần, không cần Spark): đọc bảng thiếu/thư mục rỗng = **không phải lỗi**, gộp cửa sổ nhiều phòng **có trọng số** cho độ trễ, dựng lại cửa sổ từ bảng chi tiết, quy tắc cảnh báo (gồm ca **1 bình luận = 100 % không được báo** và ca khẳng định lại số Task 9 trên `verify1`: đúng 1 cửa sổ 38,46 %/13 bình luận), che từ nhạy cảm theo **ranh giới từ** + email/điện thoại, dựng được 4 loại biểu đồ và nhãn trục đúng đơn vị |
| `test_model_trial.py` | Chương trình thử nghiệm mô hình (13 test, **không cần Spark**): quy tắc loại văn bản giống DLQ (rỗng / dưới `min_chars` / trên `max_chars`), chỉ số từ confusion matrix (ca hoàn hảo, ca biết trước, lớp vắng mặt), định dạng/che văn bản khi ghi kết quả |

Kết quả lần chạy gần nhất (19/10/2026): **77 passed** (28 test cũ + 21 test dashboard +
15 test `prepare` + 13 test model_trial) — cần **HDFS bật** cho các test dùng
SparkSession, vì `spark-defaults.conf` trỏ event log lên `hdfs://localhost:9000`.
Riêng `tests/test_model_trial.py` là test thuần Python, chạy được cả khi HDFS tắt.
