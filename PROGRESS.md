# PROGRESS.md — Nhật ký tiến độ

Quy ước: sau **mỗi tác vụ** ghi **một dòng** theo mẫu:
`| Ngày | Task | Việc đã làm | File tạo ra | Việc còn lại |`

Ngày Day N tính từ Day 1 = 15/09/2026.

| Ngày | Task | Việc đã làm | File tạo ra | Việc còn lại |
|---|---|---|---|---|
| 02/10/2026 | 1 | Đọc toàn bộ tài liệu của cô trong `TEMPLATES_DIR` (Action Plan, Evaluation Sheet, Final Report, Slide Template, Student's Guide, WBS); bỏ qua file tạm `~$` | — | — |
| 02/10/2026 | 1 | Ghi quy ước dự án, tạo cấu trúc thư mục, `git init`, tạo README cho từng thư mục | `CLAUDE.md`, `REQUIREMENTS.md`, `PROGRESS.md`, `.gitignore`, 17 `README.md` | — |
| 02/10/2026 | 1 | Định khung đề tài, so sánh lựa chọn dữ liệu, chốt ngôn ngữ và kiến trúc | `docs/topic_decision.md` | Nhóm chốt phương án định khung; xác nhận lại mốc Day 1 và 5 câu hỏi cho cô |
| 02/10/2026 | 2 | Điền Action Plan (Team 6, đề tài, Goal, Abstract, Method, Data, Expected Outcome, phân vai, tóm tắt lịch); chuyển PDF và tự kiểm tra bố cục 5 trang, không còn trang trắng | `deliverables/Action_Plan.docx`, `deliverables/Action_Plan.pdf`, `scripts/fill_action_plan.py` | Nhóm tự kiểm tra lại tên/ngày tháng và vai trò từng thành viên trước khi nộp |

---

## ⚠️ Việc còn lại / chặn tiến độ

| # | Việc | Chặn task nào | Ghi chú |
|---|---|---|---|
| 1 | **Truy vết nguồn `YoutubeCommentsDataSet.csv`** | Task 6 | Xem `data/raw/SOURCE.md`. Chưa có nguồn/giấy phép thì không được dùng trong báo cáo nộp. |
| 2 | **Xác nhận lại mốc Day 1 với cô** | Toàn bộ lịch | Xem `REQUIREMENTS.md` §2 |
| 3 | **Kiểm tra RAM trước khi chạy Kafka + Spark** | Task 5, 8 | Máy chỉ có 7 GB RAM, khuyến nghị của khóa là ≥ 8 GB |

✔️ **Đã gỡ chặn:** LibreOffice đã được cài (02/10/2026) — Task 2, 3, 4, 11, 14, 15 dùng được để tự kiểm tra bố cục.
