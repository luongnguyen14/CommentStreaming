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
| 14/10/2026 | 4 | Dựng slide đề xuất 5 trang (EN) từ Slide Template của cô: giữ nguyên master/layout/màu/font, sửa tên dự án trong footer của layout; cover (tên dự án + 5 thành viên), Problem & Technology for Good, Data & Architecture (sơ đồ Kafka → Spark Structured Streaming → Spark ML → Dashboard vẽ bằng shape), Expected Outcome & Novelty (nêu rõ dữ liệu replay + hạn chế), Roles & Schedule (3 giai đoạn); ghi chú thuyết trình ~3 phút/slide; xuất PDF, render ảnh từng slide và tự kiểm không tràn khung (sửa lỗi width=0 của placeholder và lỗi glyph ☒ của font template) | `deliverables/Proposal_Slides.pptx`, `deliverables/Proposal_Slides.pdf`, `scripts/fill_proposal_slides.py` | Nhóm duyệt nội dung + tập thuyết trình; cập nhật slide 5 nếu mốc Day thay đổi |
| 14/10/2026 | 5 | Cài **Kafka 4.3.1 KRaft** (`/home/hadoop/kafka`, không ZooKeeper; dùng JDK 17 Temurin bản người dùng vì Kafka 4.x bắt buộc Java 17, không có `sudo`); viết 3 script vận hành + tạo 3 topic (`comments_raw` 3 partition, `comments_scored` 3, `comments_dlq` 1, heap 512 MB); viết `replay_producer.py` (rate/burst/late-ratio/loop/sample, băm có muối, **không nhãn trong message**, nhãn lưu riêng `eval_labels.parquet`) và `test_consumer.py`; **kiểm chứng 1000 gửi → 1000 nhận, 0 lỗi**; đo thông lượng 5 mức `--rate`; xác nhận gói `spark-sql-kafka-0-10_2.12:3.5.9` chạy được (Spark đọc đủ 7000 message từ topic); đo RAM khi Kafka+Spark chạy đồng thời; vẽ sơ đồ kiến trúc `00_pipeline_architecture.png` | `kafka/*.sh` + `kafka/README.md`, `src/producer/*.py` + `README.md`, `src/common/utils.py`, `src/common/plotting.py`, `config.yaml`, `scripts/make_pipeline_diagram.py`, `outputs/figures/00_pipeline_architecture.png`, `outputs/tables/ingestion_report.csv`, `logs/task5_*.log` | Task 6: chốt ánh xạ rating→nhãn 3 lớp; `docs/topic_decision.md` còn số liệu cũ (CSV 18.408 dòng) cần cập nhật theo IMDb; `live_producer.py` **cố ý không làm** (điều khoản nền tảng — xem topic_decision §(b)) |

---

## ⚠️ Việc còn lại / chặn tiến độ

| # | Việc | Chặn task nào | Ghi chú |
|---|---|---|---|
| 1 | **Lịch thực tế vs mốc Day 20** | Toàn bộ | Day 1 = 15/09/2026 đã chốt ⇒ hôm nay 14/10 là **Day 30**, mọi hạn Day 5–20 đều đã qua. Cần thống nhất với cô hướng nộp bù / điều chỉnh mốc. |
| 2 | ~~Đo RAM khi chạy đồng thời Kafka + Spark~~ **ĐÃ ĐO 14/10/2026** | Task 8 (streaming) | Kafka (heap 512 MB) + Spark `local[2]` chạy đồng thời được; khả dụng thấp nhất ~1,9 GB (có dùng swap). Chốt cấu hình streaming: driver ~1g, `local[2]`, heap Kafka 512 MB. Số đo: `logs/task5_spark_kafka_memory.log`. |
| 3 | **Xác minh vài `review_id` với trang Kaggle** | Trước Final Report | Xem `data/raw/SOURCE.md` (mục "Việc còn lại"). |
| 4 | **Nhóm rà lại WBS** (phân công, trạng thái) trước khi nộp | Task 3 | Bản trong `deliverables/WBS.xlsx`. |
| 5 | ~~Chốt cấu hình Kafka~~ **XONG ở Task 5** | — | Dùng **Kafka 4.3.1 KRaft** tại `/home/hadoop/kafka`, dữ liệu ở `/home/hadoop/kafka-data` (ổ đĩa thật, không mất khi reboot như `/tmp`); bản 2.8.1 cũ giữ ở `/home/hadoop/kafka-2.8.1-old` nhưng không dùng. |

✔️ **Đã gỡ chặn:** (1) LibreOffice đã cài (02/10/2026). (2) **Nguồn dữ liệu đã truy vết** — dùng IMDb Review Dataset (CC0), loại CSV không rõ nguồn (14/10/2026). (3) **Day 1 đã chốt** = 15/09/2026 (14/10/2026). (4) **pandas + streamlit đã cài** (14/10/2026). (5) **Cách chạy Spark đã chốt**: `spark-submit` 3.5.9 + Python 3.11 qua `scripts/env.sh`; bản `pyspark` pip 4.2.0 không dùng được (cần Java 17, máy chỉ có Java 8/11). (6) **HDFS + Spark đã chạy thông** — smoke test 14/10/2026, event log ghi lên `hdfs://localhost:9000/spark-logs`. (7) **Kafka đã cài và chạy được** (4.3.1 KRaft + JDK 17 người dùng), producer/consumer + Spark đọc Kafka đều thông (14/10/2026).
