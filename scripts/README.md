# scripts/ — Script điều khiển

- `run_demo.sh` — khởi động Kafka -> stream_job -> producer replay -> dashboard theo thứ tự
- `run_all.sh` — chạy toàn bộ pipeline với tham số `--sample`

Phải dừng sạch bằng một lệnh.

## Script tạo tài liệu nộp

Các script dưới đây **copy template của cô từ `TEMPLATES_DIR` sang `deliverables/` rồi mới điền**
(không bao giờ sửa file gốc). Chạy lại được nhiều lần, mỗi lần ghi đè bản trong `deliverables/`.

- `fill_action_plan.py` — điền Action Plan (Task 2)
- `fill_wbs.py` — điền WBS 20 ngày: ngày D1–D20, phân công, Gantt (Task 3)
- `install_template_fonts.py` — giải mã + cài font của template (chỉ cần chạy lại nếu đổi máy)

Sau khi chạy, **luôn kiểm tra bố cục** theo quy ước CLAUDE.md §11: chuyển PDF bằng
`soffice --headless --convert-to pdf` rồi soát trang trắng và render ảnh.
