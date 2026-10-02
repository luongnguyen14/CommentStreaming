# src/common — Hàm dùng chung

- `text_cleaning.py` — chuẩn hóa văn bản bằng **hàm Spark SQL** (không dùng Python UDF khi tránh được)

⚠️ **Đây là nguồn duy nhất** cho logic làm sạch văn bản.
Cả huấn luyện (`src/training`) và streaming (`src/streaming`) **phải import từ đây**
để tránh lệch phân phối giữa lúc train và lúc chạy thật.
