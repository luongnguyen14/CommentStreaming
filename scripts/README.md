# scripts/ — Script điều khiển

- `run_demo.sh` — khởi động Kafka -> stream_job -> producer replay -> dashboard theo thứ tự
- `run_all.sh` — chạy toàn bộ pipeline với tham số `--sample`

Phải dừng sạch bằng một lệnh.

## Môi trường

- `env.sh` — biến môi trường dùng chung: Java 8, Spark 3.5.9, Python 3.11 cho PySpark.
  Các script khác `source scripts/env.sh` trước khi chạy.
- `check_env.sh` — kiểm tra nhanh Java/HDFS/Spark/pandas/streamlit; thêm `--smoke` để chạy thử SparkSession thật.

**Lưu ý vận hành:**

- HDFS **không tự chạy lại sau khi khởi động máy**: chạy `/usr/local/hadoop/sbin/start-dfs.sh` trước khi dùng Spark.
  Spark ghi event log lên `hdfs://localhost:9000/spark-logs`; HDFS tắt thì Spark báo lỗi kết nối `localhost:9000`.
- `start-dfs.sh` cần ssh không mật khẩu tới localhost. Khóa `~/.ssh/id_rsa` có passphrase nên không dùng được ở chế độ
  tự động — đã tạo thêm khóa `~/.ssh/id_ed25519` (không passphrase, 14/10/2026) và thêm vào `~/.ssh/authorized_keys`.

## Script tạo tài liệu nộp

Các script dưới đây **copy template của cô từ `TEMPLATES_DIR` sang `deliverables/` rồi mới điền**
(không bao giờ sửa file gốc). Chạy lại được nhiều lần, mỗi lần ghi đè bản trong `deliverables/`.

- `fill_action_plan.py` — điền Action Plan (Task 2)
- `fill_wbs.py` — điền WBS 20 ngày: ngày D1–D20, phân công, Gantt (Task 3)
- `install_template_fonts.py` — giải mã + cài font của template (chỉ cần chạy lại nếu đổi máy)

Sau khi chạy, **luôn kiểm tra bố cục** theo quy ước CLAUDE.md §11: chuyển PDF bằng
`soffice --headless --convert-to pdf` rồi soát trang trắng và render ảnh.
