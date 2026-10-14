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

---

## `01_confusion_matrix.png` — Ma trận nhầm lẫn (Task 7)

- Trên **test** (27.792 bình luận, Logistic Regression): lớp `positive` đoán đúng
  76%, `negative` 66%, còn **`neutral` chỉ 50%** — 25% rơi sang negative và 25% sang
  positive, tức sai về **cả hai phía**.
- Điều này khớp với giả thuyết **nhiễu nhãn**: nhãn `neutral` được suy từ rating 5–6,
  vốn trộn lẫn "khen nhẹ" và "chê nhẹ" nên bản thân văn bản không phân biệt được.

Bảng số liệu nền: `outputs/tables/confusion_matrix.csv`, `per_class_metrics.csv`.

## `02_per_class_prf1.png` — Precision/Recall/F1 từng lớp (Task 7)

- Precision lớp `neutral` chỉ **0,30** (3 trong 4 lần đoán "neutral" là sai) trong
  khi recall 0,50 — mô hình đoán neutral khá "hào phóng".
- Nếu chỉ báo cáo accuracy 0,70 sẽ che mất chuyện lớp `neutral` gần như **không giải
  được** (F1 0,38) — đúng lý do CLAUDE.md §6 yêu cầu báo cáo macro-F1 và chỉ số từng lớp.

Bảng số liệu nền: `outputs/tables/per_class_metrics.csv`.

## `03_model_comparison.png` — So sánh 5 mô hình trên validation (Task 7)

- Ba mô hình tuyến tính xấp xỉ nhau: LogisticRegression 0,629 > LinearSVC 0,622 >
  NaiveBayes 0,619 (macro-F1); RandomForest thấp nhất 0,534; baseline đa số 0,253.
- Khoảng cách giữa các mô hình tuyến tính chỉ **0,007–0,010** — chưa kiểm định ý
  nghĩa thống kê nên **không khẳng định** mô hình này hơn mô hình kia là chắc chắn.

Bảng số liệu nền: `outputs/tables/model_results.csv`.

## `04_top_features.png` — 20 từ trọng số lớn nhất mỗi lớp (Task 7)

- Đặc trưng mạnh nhất của lớp `neutral` là **điểm số người viết tự ghi** ("**1/2",
  "5/10", "6/10"), của `positive` là "7/10", "8/10", của `negative` là "4/10" —
  mô hình **đọc lại con số** trong bài thay vì hiểu cảm xúc.
- Hệ quả trung thực cần nêu: bình luận livestream (Task 8) hiếm khi ghi điểm số, nên
  **kết quả chạy thật có thể thấp hơn macro-F1 0,6233 đo trên dữ liệu test này**.

Bảng số liệu nền: `outputs/tables/top_features.csv`.

## `05_error_reasons.png` — Nhóm nguyên nhân của 30 bình luận đoán sai (Task 7)

- Nhóm tự động: **14/30 do phủ định** ("not/never"), **10/30 do nhãn neutral nhiễu**
  (rating 5–6), 5/30 cần đọc tay, 1/30 quá ngắn.
- Đọc tay 30 dòng thấy nguyên nhân thật thường là **ý trái chiều trong cùng bình luận
  (~9 dòng)** và **mỉa mai (~5 dòng)** — hai thứ mà đặc trưng túi-từ đơn giản không
  nắm được; xác suất trung bình mô hình gán cho lớp đúng chỉ **0,255**.

Bảng số liệu nền: `outputs/tables/error_analysis.csv`.
