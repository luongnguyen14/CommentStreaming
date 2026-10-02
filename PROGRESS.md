# PROGRESS.md — Nhật ký tiến độ

Quy ước: sau **mỗi tác vụ** ghi **một dòng** theo mẫu:
`| Ngày | Task | Việc đã làm | File tạo ra | Việc còn lại |`

Ngày Day N tính từ Day 1 = 15/09/2026.

| Ngày | Task | Việc đã làm | File tạo ra | Việc còn lại |
|---|---|---|---|---|
| 02/10/2026 | 1 | Đọc toàn bộ tài liệu của cô trong `TEMPLATES_DIR` (Action Plan, Evaluation Sheet, Final Report, Slide Template, Student's Guide, WBS); bỏ qua file tạm `~$` | — | — |
| 02/10/2026 | 1 | Ghi quy ước dự án, tạo cấu trúc thư mục, `git init`, tạo README cho từng thư mục | `CLAUDE.md`, `REQUIREMENTS.md`, `PROGRESS.md`, `.gitignore`, 17 `README.md` | — |
| 02/10/2026 | 1 | Định khung đề tài, so sánh lựa chọn dữ liệu, chốt ngôn ngữ và kiến trúc | `docs/topic_decision.md` | Nhóm chốt phương án định khung; xác nhận lại mốc Day 1 và 5 câu hỏi cho cô |

---

## ⚠️ Việc còn lại / chặn tiến độ

| # | Việc | Chặn task nào | Ghi chú |
|---|---|---|---|
| 1 | **Cài LibreOffice** — máy chưa có `soffice`/`libreoffice`, mà Task 2, 3, 4, 11, 14, 15 đều yêu cầu "chuyển sang PDF bằng libreoffice" để tự kiểm tra bố cục | Task 2 trở đi | Gói `libreoffice-impress` **có sẵn trong kho** (bản 4:26.2.5.2). Cần chạy: `sudo apt install libreoffice-impress libreoffice-writer libreoffice-calc`. **Cần mật khẩu sudo** nên Claude không tự cài được — nhóm phải tự chạy. `pandoc` có sẵn nhưng **không thay thế được** (không đọc được `.pptx`). |
| 2 | **Truy vết nguồn `YoutubeCommentsDataSet.csv`** | Task 6 | Xem `data/raw/SOURCE.md`. Chưa có nguồn/giấy phép thì không được dùng trong báo cáo nộp. |
| 3 | **Xác nhận lại mốc Day 1 với cô** | Toàn bộ lịch | Xem `REQUIREMENTS.md` §2 |
| 4 | **Kiểm tra RAM trước khi chạy Kafka + Spark** | Task 5, 8 | Máy chỉ có 7 GB RAM, khuyến nghị của khóa là ≥ 8 GB |
