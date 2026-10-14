# outputs/insights.md — Nhận xét gắn với từng biểu đồ

Mỗi mục ghi 1–2 câu nhận xét **dựa trên số liệu thật** trong `outputs/tables/`
(CLAUDE.md §8, §9).

---

## `00_pipeline_architecture.png` — Sơ đồ kiến trúc pipeline (Task 5)

- Sơ đồ mô tả luồng dữ liệu của hệ thống: producer phát lại dữ liệu IMDb có nhãn →
  Kafka (`comments_raw`) → Spark Structured Streaming → Spark ML → Parquet
  (`comments_scored`) → dashboard; bản ghi lỗi đi vào `comments_dlq`, còn **nhãn
  đánh giá nằm hoàn toàn ngoài luồng** (`data/processed/eval_labels.parquet`).
- Số liệu ghi trên hình là kết quả đo thật ngày 14/10/2026: producer đạt
  3.229–3.615 msg/s khi không giới hạn tốc độ và bám đúng mức đặt khi có giới hạn
  (100 → 100,0; 500 → 499,0 msg/s); kiểm chứng end-to-end gửi 1.000 message, đọc lại
  đủ 1.000, 0 lỗi (`logs/task5_1000msg_*.log`).
- **Lưu ý trung thực:** đây là sơ đồ kiến trúc (minh họa), chỉ các con số ở phần chú
  thích là số đo thật; luồng dữ liệu là **replay mô phỏng**, không phải livestream thật.

### Bảng số liệu nền

`outputs/tables/ingestion_report.csv` (thông lượng producer theo từng mức `--rate`).
