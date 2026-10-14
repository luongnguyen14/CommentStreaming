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
- **Push GitHub** (`git@github.com:luongnguyen14/CommentStreaming`) cần khóa `~/.ssh/id_rsa` — khóa này có passphrase,
  mà agent của GNOME keyring (`/run/user/1002/gcr/ssh`) từ chối ký khi lệnh chạy không có phiên đồ họa
  (`agent refused operation`). Cách chạy được: mở terminal user `hadoop`, `ssh-add ~/.ssh/id_rsa` (nhập passphrase),
  rồi `git push` từ đó; hoặc nạp khóa vào một `ssh-agent` thường và trỏ `SSH_AUTH_SOCK` vào socket của nó.
  Khóa `id_ed25519` **chưa** đăng ký với GitHub nên không thay thế được.

## Script tạo tài liệu nộp

Các script dưới đây **copy template của cô từ `TEMPLATES_DIR` sang `deliverables/` rồi mới điền**
(không bao giờ sửa file gốc). Chạy lại được nhiều lần, mỗi lần ghi đè bản trong `deliverables/`.

- `fill_action_plan.py` — điền Action Plan (Task 2)
- `fill_wbs.py` — điền WBS 20 ngày: ngày D1–D20, phân công, Gantt (Task 3)
- `fill_proposal_slides.py` — dựng slide đề xuất 5 trang từ Slide Template (Task 4);
  giữ nguyên master/layout/màu/font, vẽ sơ đồ kiến trúc bằng shape của PowerPoint,
  ghi chú thuyết trình ~3 phút/slide
- `install_template_fonts.py` — giải mã + cài font của template (chỉ cần chạy lại nếu đổi máy)

## Script vẽ biểu đồ

- `make_pipeline_diagram.py` — vẽ sơ đồ kiến trúc pipeline (Task 5) →
  `outputs/figures/00_pipeline_architecture.png` (200 dpi, chữ tiếng Anh, dùng chung
  bảng màu ở `src/common/plotting.py`). Số liệu in trên hình lấy từ
  `outputs/tables/ingestion_report.csv` và `logs/task5_1000msg_*.log`.

Sau khi chạy, **luôn kiểm tra bố cục** theo quy ước CLAUDE.md §11: chuyển PDF bằng
`soffice --headless --convert-to pdf` rồi soát trang trắng và render ảnh.

**Lỗi đã biết của template PPTX khi render bằng LibreOffice** (gặp ở Task 4):

1. Đặt `shape.height` cho placeholder **kế thừa vị trí từ layout** làm python-pptx ghi ra
   `<a:ext cx="0">` → chữ biến mất. Phải "materialize" `left/top/width` từ layout trước
   (xem `materialize_geometry` trong `fill_proposal_slides.py`).
2. Font thương hiệu (Samsung Sharp Sans) bị LibreOffice thay thế glyph sai ở ngữ cảnh
   *chữ thường + dấu cách + chữ số*: `Team 6` → `Tea 6` + ô vuông ☒, và lỗi này vào cả PDF.
   Cách chữa: tách cụm chữ số thành run riêng (`set_para_text_safe_digits`).
3. Xoá slide chỉ xoá quan hệ, part vẫn nằm trong gói → `add_slide` có thể ghi đè part đang
   dùng (2 slide trùng nội dung). Phải nhân bản slide trước, xoá sau.
