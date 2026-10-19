# SentimentGuard — Báo cáo kỹ thuật chi tiết (tiếng Việt)

> **Tài liệu đầy đủ:** [`bao_cao_ky_thuat_vi.docx`](bao_cao_ky_thuat_vi.docx) ·
> [`bao_cao_ky_thuat_vi.pdf`](bao_cao_ky_thuat_vi.pdf) (33 trang)
>
> **Bản nộp chính thức cho giảng viên:** [`../deliverables/Final_Report.docx`](../deliverables/Final_Report.docx)
> (tiếng Anh, theo template của cô).
>
> File Markdown này là **bản tóm tắt để đọc trên GitHub**. Nội dung chi tiết, bảng
> số liệu, hình ảnh và hướng dẫn chạy lại nằm trong file DOCX/PDF.

---

## 1. Tóm tắt

**SentimentGuard** là nguyên mẫu hệ thống phân loại cảm xúc bình luận trực tuyến theo
thời gian thực, nhằm **phát hiện sớm các đợt bùng phát bình luận tiêu cực** trong
livestream hoặc cộng đồng trực tuyến.

- **Đầu vào:** bình luận đã làm sạch (`comment_id`, `stream_id`, `user_hash`, `text`, `event_ts`).
- **Đầu ra:** nhãn `negative` / `neutral` / `positive` + xác suất, ghi ra Kafka và Parquet.
- **Tổng hợp:** cửa sổ 1 phút và cửa sổ trượt 10 giây/bước 5 giây.
- **Cảnh báo:** tỷ lệ tiêu cực > 30% **và** số bình luận ≥ 5.
- **Dashboard:** Streamlit, 3 tab (Live Monitor, Try It, About).

Điểm cốt lõi không phải là một mô hình “cao điểm”, mà là **một đường ống hoàn chỉnh
và trung thực**: làm sạch và loại trùng trước khi chia tập; TF-IDF chỉ fit trên train
và nằm trong Spark ML Pipeline; test chỉ dùng một lần; streaming dùng event time,
watermark và DLQ; mọi con số đều truy được về file thật trong `outputs/`.

---

## 2. Các con số then chốt

| Chỉ số | Giá trị | Nguồn |
|---|---|---|
| Bình luận sạch sau làm sạch + loại trùng | 185.286 | `outputs/tables/cleaning_log.csv` |
| Train / validation / test | 129.701 / 27.793 / 27.792 | `outputs/tables/class_distribution.csv` |
| Số đặc trưng TF-IDF | 20.000 | `outputs/tables/model_results.csv` |
| Mô hình được chọn | LogisticRegression | `outputs/tables/model_results.csv` |
| Accuracy trên test | 70,18% | `outputs/tables/model_results.csv` |
| Macro-F1 trên test | 62,33% | `outputs/tables/model_results.csv` |
| Weighted-F1 trên test | 72,13% | `outputs/tables/model_results.csv` |
| F1 negative / neutral / positive | 0,672 / 0,378 / 0,819 | `outputs/tables/per_class_metrics.csv` |
| Bản ghi streaming đã chấm / vào DLQ | 1.014 / 10 | `outputs/tables/stream_verification.csv` |
| Dự đoán luồng khớp offline | 1.000/1.000 (100%) | `outputs/tables/stream_verification.csv` |
| Độ trễ p50 / p95 / p99 | 2.413 / 9.663 / 27.091 ms | `outputs/tables/stream_verification.csv` |
| Số streaming query | 6 | `outputs/tables/stream_batches.csv` |
| Số test tự động | 77 passed | pytest, 15/10/2026 |

> **Cảnh báo:** baseline đoán “positive” đã đạt accuracy 61,07% và macro-F1 0,253.
> Mức cải thiện thật của mô hình nằm ở macro-F1 (+0,3705) và khả năng tách negative /
> neutral, không phải ở accuracy.

---

## 3. Kiến trúc

```
IMDb Review Dataset (CC0, 1.010.293 review)
        │  lấy mẫu tất định 201.074 (19,9%)
        ▼
prepare.py  ──►  data/processed/{train,val,test}.parquet
        │          185.286 bình luận sạch (70/15/15)
        ▼
train.py    ──►  Pipeline TF-IDF + LogisticRegression
        │          outputs/models/sentiment_pipeline
        ▼
replay_producer.py ──► Kafka comments_raw
        │
        ▼
Spark Structured Streaming (6 query)
   ├─ scored_detail (Parquet)
   ├─ comments_scored (Kafka)
   ├─ window_1min (Parquet)
   ├─ window_10s  (Parquet)
   ├─ comments_dlq (Kafka)
   └─ dlq (Parquet)
        │
        ▼
Streamlit dashboard + cảnh báo
```

Xem sơ đồ đầy đủ tại `outputs/figures/00_pipeline_architecture.png`.

---

## 4. Dữ liệu

- **Nguồn:** IMDb Review Dataset - ebD, Kaggle `ebiswas/imdb-review-dataset`, giấy phép
  **CC0**. File `part-01.json` có 1.010.293 review, 1,09 GB.
- **Tập con:** 201.074 bản ghi (19,9%), chọn tất định theo `crc32(review_id)`.
- **Nhãn:** suy từ rating — 1–4 negative, 5–6 neutral, 7–10 positive. Đây là **nhãn
  proxy**, không phải nhãn cảm xúc gán tay; neutral rất nhiễu.
- **Làm sạch:** 9 bước bằng Spark SQL (lower, bỏ HTML, URL → `<url>`, mention →
  `<user>`, chuẩn hóa dấu câu, viết tắt, rút gọn ký tự lặp, tách emoji, gộp khoảng
  trắng). Không dùng Python UDF; hàm idempotent; dùng chung cho train và streaming.
- **Loại trùng:** 2.999 trùng mã + 636 trùng chính xác + 63 gần trùng. Kiểm tra rò rỉ
  sau chia tập: **0** trùng văn bản giữa train↔val, train↔test, val↔test.
- **Chia tập:** 70/15/15, phân tầng theo nhóm phim, seed 42. Tập test dùng một lần.
- **Quyền riêng tư:** `user_hash = sha256(salt + reviewer)[:16]`; muối đọc từ
  `COMMENT_HASH_SALT`; không lưu PII; mặc định không ghi văn bản vào sink.

Chi tiết: [`data_dictionary.md`](data_dictionary.md) và chương 4 của báo cáo DOCX/PDF.

---

## 5. Mô hình

Pipeline 7 stage, tất cả nằm trong Spark ML Pipeline:

1. `RegexTokenizer` — tách theo khoảng trắng (văn bản đã lower).
2. `StopWordsRemover` — 162 stopword, **giữ từ phủ định** (not/no/never…).
3. `NGram` — n = 1 (n = 2 đã thử với NB và LR; lưới chọn n = 1).
4. `CountVectorizer` — tối đa 20.000 từ, `minDF = 3`.
5. `IDF` — giảm trọng số từ phổ biến.
6. `Normalizer` — chuẩn hóa L2.
7. Bộ phân loại — LogisticRegression (multinomial).

**Trọng số lớp** `w_c = N / (k × n_c)` tính trên train:

| Lớp | Số dòng train | Trọng số |
|---|---:|---:|
| Negative | 32.504 | 1,330 |
| Neutral | 17.983 | 2,404 |
| Positive | 79.214 | 0,546 |

**Chọn siêu tham số:** `TrainValidationSplit` 80/20 bên trong train, weighted F1;
sau đó so sánh 4 mô hình trên validation bằng macro-F1; test chỉ dùng một lần.

**Kết quả validation:**

| Mô hình | Accuracy | Weighted-F1 | Macro-F1 |
|---|---:|---:|---:|
| MajorityBaseline | 0,6107 | 0,4631 | 0,2528 |
| NaiveBayes | 0,6743 | 0,7013 | 0,6192 |
| **LogisticRegression** | **0,7063** | **0,7241** | **0,6291** |
| LinearSVC (OvR) | 0,7000 | 0,7172 | 0,6218 |
| RandomForest | 0,5878 | 0,6131 | 0,5343 |

**Kết quả test của LogisticRegression:** accuracy 0,7018; weighted-F1 0,7213;
macro-F1 0,6233. F1 từng lớp: negative 0,672; neutral 0,378; positive 0,819.

Chi tiết: chương 5–7 của báo cáo DOCX/PDF.

---

## 6. Streaming

- **Kafka 4.3.1 KRaft**, 3 topic: `comments_raw` (3 partition), `comments_scored` (3),
  `comments_dlq` (1).
- **Spark 3.5.9 Structured Streaming**, 6 query độc lập, mỗi query một checkpoint.
- **Schema tường minh** 6 trường, gồm `_corrupt`; message chỉ có 5 trường, **không có nhãn**.
- **Event time + watermark 2 phút**; cửa sổ nhảy 1 phút và cửa sổ trượt 10 giây/bước 5 giây.
- **DLQ** kèm lý do: JSON hỏng, thiếu trường, `event_ts` không đọc được, văn bản rỗng,
  quá ngắn, quá dài.
- **At-least-once** đã kiểm chứng; **exactly-once chưa kiểm chứng**.

**Lần chạy `verify1` (15/10/2026):**

| Hạng mục | Kết quả |
|---|---|
| Tổng gửi | 1.024 bản ghi |
| Đã chấm điểm | 1.014 |
| Vào DLQ | 10 |
| Cân bằng | 1.014 + 10 = 1.024 (PASS) |
| Dự đoán luồng khớp offline | 1.000/1.000 (100%) |
| Macro-F1 trên 1.000 dòng | 0,6311 |
| Accuracy trên 1.000 dòng | 0,7030 |
| Độ trễ p50 / p95 / p99 | 2.413 / 9.663 / 27.091 ms |
| Số micro-batch | 110 |

Chi tiết: [`../outputs/streaming_summary.md`](../outputs/streaming_summary.md) và chương 8–9
của báo cáo DOCX/PDF.

---

## 7. Chạy lại

```bash
cd /home/hadoop/capstone
source scripts/env.sh

# Kiểm tra môi trường
bash scripts/check_env.sh

# Test tự động (cần HDFS đang bật và đã ra safe mode)
.venv/bin/python -m pytest tests/ -q

# Thử nghiệm mô hình (không cần Kafka)
bash scripts/run_model_trial.sh --examples
bash scripts/run_model_trial.sh --text "not bad at all"
bash scripts/run_model_trial.sh --test-sample 200

# Chạy toàn bộ demo (Kafka → streaming → producer → dashboard)
bash scripts/run_demo.sh --duration 600

# Dừng sạch
bash scripts/run_demo.sh --stop
```

Hướng dẫn chi tiết — gồm cách lấy file Word về máy, mở bằng Word/LibreOffice và chạy
trên máy gốc — nằm trong [`huong_dan_lay_file_word.md`](huong_dan_lay_file_word.md).

---

## 8. Hạn chế — đọc trước khi báo cáo

1. **Nhãn proxy từ rating IMDb**, không phải nhãn cảm xúc gán tay; neutral rất nhiễu
   (F1 chỉ 0,378).
2. **Khác miền dữ liệu:** review IMDb dài, có điểm số; livestream ngắn, teencode,
   không có “6/10”. Chỉ số 0,6233 là **mức trần lạc quan**.
3. **Mô hình túi từ** không hiểu phủ định/mỉa mai; 14/30 lỗi phân tích là do phủ định.
4. **Chồng lấn người dùng:** 11.427/111.087 người dùng ở hơn một tập; 75.939 dòng
   (41,0%). Đã ghi rõ, chưa loại bỏ hoàn toàn.
5. **Dữ liệu streaming là replay**, không phải bình luận livestream thật.
6. **Exactly-once chưa kiểm chứng**; chỉ khẳng định at-least-once.
7. **Độ trễ p95 9,7 giây**, quá chậm cho phản hồi tức thì; nút thắt là hàng đợi xử lý.
8. **Chưa có ảnh nhóm** trong repo; báo cáo tiếng Anh đang để chỗ trống.

Danh sách đầy đủ và hướng xử lý: chương 13 của báo cáo DOCX/PDF.

---

## 9. Tài liệu liên quan

| File | Nội dung |
|---|---|
| [`bao_cao_ky_thuat_vi.docx`](bao_cao_ky_thuat_vi.docx) | Báo cáo kỹ thuật đầy đủ (33 trang) |
| [`bao_cao_ky_thuat_vi.pdf`](bao_cao_ky_thuat_vi.pdf) | Bản PDF để đọc/in |
| [`../deliverables/Final_Report.docx`](../deliverables/Final_Report.docx) | Báo cáo cuối kỳ tiếng Anh (bản nộp) |
| [`../deliverables/Final_Report.pdf`](../deliverables/Final_Report.pdf) | Bản PDF của báo cáo tiếng Anh |
| [`data_dictionary.md`](data_dictionary.md) | Từ điển dữ liệu |
| [`bao_cao_tien_do.md`](bao_cao_tien_do.md) | Kịch bản báo cáo tiến độ + 30 câu Q&A |
| [`huong_dan_bao_cao.md`](huong_dan_bao_cao.md) | Hướng dẫn báo cáo trước hội đồng |
| [`../outputs/insights.md`](../outputs/insights.md) | Toàn bộ insight EDA kèm số liệu |
| [`../outputs/streaming_summary.md`](../outputs/streaming_summary.md) | Kiểm chứng streaming chi tiết |
