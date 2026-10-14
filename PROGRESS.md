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
| 14/10/2026 | 2b | Truy vết được bộ dữ liệu: `part-01.json` là 1 shard của Kaggle **"IMDb Review Dataset - ebD"** (giấy phép **CC0**); chốt **IMDb là dữ liệu huấn luyện chính**, loại `YoutubeCommentsDataSet.csv` (không truy vết được nguồn); viết lại `SOURCE.md` bằng số liệu đo thật (1.010.296 review, md5, phân bố rating) | `data/raw/SOURCE.md` | Xác minh vài `review_id` với trang Kaggle trước Final Report; ghi ánh xạ rating→nhãn 3 lớp ở Task 6 |
| 14/10/2026 | 2c | Cập nhật Action Plan cho khớp dữ liệu mới (mục Data + Abstract: IMDb CC0, nhãn suy từ rating); xuất lại docx+pdf, tự kiểm 5 trang không trang trắng | `scripts/fill_action_plan.py`, `deliverables/Action_Plan.docx`, `deliverables/Action_Plan.pdf` | — |
| 14/10/2026 | 3 | Điền WBS: 7 nhóm việc / 32 dòng kế hoạch, ngày D1–D20 = 15/09–04/10/2026, phân công 5 thành viên, Gantt tô theo từng ngày, trạng thái ghi đúng thực tế ngày 14/10; tự kiểm bố cục PDF 2 trang, không trang trắng | `deliverables/WBS.xlsx`, `deliverables/WBS.pdf`, `scripts/fill_wbs.py` | Nhóm rà lại phân công + trạng thái; cập nhật khi tiến độ thay đổi |
| 14/10/2026 | Env | Dựng môi trường chạy được: cài pandas + streamlit (Python 3.14); bật HDFS (sửa `ssh localhost` bằng khóa `id_ed25519` mới vì `id_rsa` cũ có passphrase); tạo `/spark-logs`; phát hiện Spark 3.5.9 lỗi với Python 3.14 (cloudpickle → RecursionError) → **chốt chạy Spark bằng `spark-submit` + Python 3.11** và cài pandas/numpy cho 3.11; smoke test SparkSession chạy thật thành công, event log ghi lên HDFS | `scripts/env.sh`, `scripts/check_env.sh`, `scripts/README.md`, `~/.bashrc` | Đo RAM khi chạy đồng thời Kafka + Spark trước khi làm demo |

---

## ⚠️ Việc còn lại / chặn tiến độ

| # | Việc | Chặn task nào | Ghi chú |
|---|---|---|---|
| 1 | **Lịch thực tế vs mốc Day 20** | Toàn bộ | Day 1 = 15/09/2026 đã chốt ⇒ hôm nay 14/10 là **Day 30**, mọi hạn Day 5–20 đều đã qua. Cần thống nhất với cô hướng nộp bù / điều chỉnh mốc. |
| 2 | **Đo RAM khi chạy đồng thời Kafka + Spark** | Task 4, 5 | Máy 7 GB RAM. Đo 14/10 khi chỉ có HDFS: còn khả dụng 1,9 GB; cần đo lại khi Kafka + Spark cùng chạy để chốt cấu hình `local[N]`. |
| 3 | **Xác minh vài `review_id` với trang Kaggle** | Trước Final Report | Xem `data/raw/SOURCE.md` (mục "Việc còn lại"). |
| 4 | **Nhóm rà lại WBS** (phân công, trạng thái) trước khi nộp | Task 3 | Bản trong `deliverables/WBS.xlsx`. |
| 5 | **Chốt cấu hình Kafka ở Task 4** | Task 4 | Kafka 2.8.1 cài ở `/home/hadoop/kafka` (thư mục `kafka_2.12-2.8.1` chỉ còn `logs`, không dùng); `log.dirs=/tmp/kafka-logs` — cân nhắc đổi sang đường dẫn ổn định để không mất log khi reboot. |

✔️ **Đã gỡ chặn:** (1) LibreOffice đã cài (02/10/2026). (2) **Nguồn dữ liệu đã truy vết** — dùng IMDb Review Dataset (CC0), loại CSV không rõ nguồn (14/10/2026). (3) **Day 1 đã chốt** = 15/09/2026 (14/10/2026). (4) **pandas + streamlit đã cài** (14/10/2026). (5) **Cách chạy Spark đã chốt**: `spark-submit` 3.5.9 + Python 3.11 qua `scripts/env.sh`; bản `pyspark` pip 4.2.0 không dùng được (cần Java 17, máy chỉ có Java 8/11). (6) **HDFS + Spark đã chạy thông** — smoke test 14/10/2026, event log ghi lên `hdfs://localhost:9000/spark-logs`.
