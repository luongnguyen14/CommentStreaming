# Báo cáo tiến độ — Nhóm 6 — ngày 19/10/2026

**Đề tài:** Mô hình phân loại cảm xúc dựa trên bình luận trực tuyến
(*Real-time Sentiment Classification of Online Comments using Kafka, Spark Structured Streaming and Spark ML*)

Tài liệu nội bộ, dùng để chuẩn bị nói với giảng viên. **Mọi con số đều dẫn về file thật trong `outputs/`** — không có số nào viết theo trí nhớ.

---

## 0. Mục tiêu buổi báo cáo tiến độ

Giáo viên cần nghe được 4 điều, theo đúng thứ tự:

1. **Đã làm đến đâu** so với kế hoạch (không phải kể lại toàn bộ lý thuyết).
2. **Làm như thế nào** — từng bước, đặc biệt là chuẩn bị dữ liệu, huấn luyện, kiểm thử.
3. **Kết quả đo được là gì** — số thật, nói cả mặt tốt và mặt yếu.
4. **Còn gì chưa làm** và kế hoạch tiếp theo.

> Nguyên tắc khi nói: **không giấu điểm yếu, không nhận những gì chưa kiểm chứng.**
> Giáo viên đánh giá cao việc biết giới hạn của mô hình hơn là con số đẹp.

---

## 1. Kịch bản 10 phút (bản ngắn gọn để nói)

| Thời gian | Nội dung | Mở gì trên màn hình |
|---|---|---|
| 0:00–0:45 | Chào, tên nhóm, đề tài, mục tiêu: cảnh báo sớm bùng nổ bình luận tiêu cực cho người làm livestream nhỏ | Slide tiêu đề |
| 0:45–2:00 | **Tiến độ tổng quan**: đã xong dữ liệu → làm sạch → huấn luyện → streaming → EDA → dashboard → chương trình thử nghiệm; còn báo cáo cuối và slide | Bảng tiến độ (§2) |
| 2:00–3:30 | **Dữ liệu**: IMDb CC0 1.010.293 review; dùng 201.074; làm sạch còn 185.286; chia 129.701 / 27.793 / 27.792 | `outputs/figures/06_class_distribution.png` |
| 3:30–5:30 | **Huấn luyện**: pipeline 7 bước; 4 mô hình + baseline; chọn trên validation; test dùng một lần | `outputs/figures/00_pipeline_architecture.png`, `03_model_comparison.png` |
| 5:30–6:30 | **Kết quả**: accuracy 0,7018; macro-F1 0,6233; từng lớp; nói ngay điểm yếu neutral 0,3783 | `01_confusion_matrix.png`, `02_per_class_prf1.png` |
| 6:30–7:45 | **Kiểm thử**: 77 test; kiểm rò rỉ 0/0/0; streaming 1.024 = 1.014 + 10; 1.000/1.000 dự đoán giống offline | `outputs/streaming_summary.md` |
| 7:45–8:45 | **Demo**: chạy `--examples`, chỉ câu `6/10` → neutral 99,3 % (mô hình đọc điểm số) | Terminal |
| 8:45–9:30 | **Hạn chế**: replay ≠ livestream; nhãn suy từ rating; neutral yếu; exactly-once chưa kiểm chứng; app hoàn chỉnh là việc tiếp theo; TRL 5 | Slide hạn chế |
| 9:30–10:00 | **Kế hoạch**: hoàn thiện Final Report, slide, ảnh dashboard, push GitHub; nếu có thời gian thì huấn luyện lại 64 % | Slide kế hoạch |

**Nếu chỉ có 3 phút:** bỏ phần EDA/dashboard, giữ: mục tiêu → dữ liệu → huấn luyện → kết quả → 3 hạn chế → kế hoạch.

**Câu mở đầu nên nói:**

> "Nhóm em đã hoàn thành phần kỹ thuật của prototype: từ dữ liệu thô đến mô hình, chạy theo luồng, có dashboard và có chương trình thử nghiệm mô hình. Hôm nay em xin báo cáo tiến độ, cách nhóm đã huấn luyện và kiểm thử, kết quả đo được, và những hạn chế nhóm xác định rõ."

---

## 2. Bảng tiến độ — nói trong 1 phút

| Nhóm việc | Trạng thái | Bằng chứng |
|---|---|---|
| Chọn đề tài, dữ liệu, quy ước | ✅ Xong | `docs/topic_decision.md`, `data/raw/SOURCE.md` |
| Action Plan, WBS, slide đề xuất | ✅ Xong | `deliverables/Action_Plan.docx`, `WBS.xlsx`, `Proposal_Slides.pptx` |
| Kafka + producer replay | ✅ Xong | `src/producer/`, kiểm chứng **1.000 gửi → 1.000 nhận, 0 lỗi** |
| Chuẩn bị dữ liệu + chia tập | ✅ Xong | `src/training/prepare.py`, `data/processed/` |
| Huấn luyện + đánh giá | ✅ Xong | `src/training/train.py`, `outputs/modeling_summary.md` |
| Streaming + DLQ + watermark | ✅ Xong | `src/streaming/stream_job.py`, `outputs/streaming_summary.md` |
| EDA + biểu đồ + insight | ✅ Xong | `src/eda/`, `outputs/figures/`, `outputs/insights.md` |
| Dashboard | ✅ Xong (demo) | `src/app/app.py`, `src/app/README.md` |
| Chương trình thử nghiệm mô hình | ✅ Xong | `src/app/model_trial.py`, `outputs/model_trial_report.md` |
| Kiểm thử tự động | ✅ **77 passed** | `tests/`, `tests/README.md` |
| Final Report + slide cuối | ⏳ **Chưa xong** | `deliverables/` chưa có `Final_Report.docx` |
| Ảnh chụp dashboard | ⏳ Chưa có | Máy ảo chặn snap browser; cần chụp từ máy thật |
| Push GitHub | ⏳ Còn 2 commit | Task 11b + Task 12 chưa push (lỗi SSH passphrase) |

**Nếu cô hỏi "vì sao chậm phần báo cáo":** trả lời thẳng — nhóm ưu tiên làm xong và kiểm chứng phần kỹ thuật trước; phần văn bản cuối đang được hoàn thiện, không có chỗ nào bị bỏ dở mà không ghi lại (`PROGRESS.md`).

---

## 3. Chi tiết từng bước đã làm — "các bước em thực hiện"

### Bước 1 — Chọn đề tài và dữ liệu (Task 1–2)

**Làm gì:**
- Xác định vấn đề: người làm livestream nhỏ không có đội kiểm duyệt; khi bùng nổ bình luận tiêu cực, chat chạy nhanh hơn người đọc.
- Chọn hướng "cảnh báo sớm theo cửa sổ thời gian", không phải phân loại từng câu rời rạc, không phải công cụ bán hàng.
- Chọn dữ liệu **IMDb Review Dataset - ebD**, giấy phép **CC0**, 1.010.293 review.

**Vì sao chọn IMDb:**
- Có sẵn, miễn phí, giấy phép rõ ràng.
- Có `rating` 1–10 để suy nhãn 3 lớp.
- Có `review_id` ổn định để nối nhãn và kiểm chứng streaming.
- Hạn chế phải nói ngay: **review phim không phải chat livestream** → có domain shift.

**Kết quả:** `docs/topic_decision.md`, `data/raw/SOURCE.md` (ghi md5, số bản ghi, phân bố rating).

---

### Bước 2 — Chuẩn bị dữ liệu (Task 6, `prepare.py`)

Đây là bước giáo viên hay hỏi nhất. Có **9 bước con**, số liệu thật trong `outputs/tables/cleaning_log.csv`:

| # | Bước | Số dòng vào | Bị loại | Còn lại | Làm gì / vì sao |
|---|---|---:|---:|---:|---|
| 1 | Nạp JSONL | 201.074 | 0 | 201.074 | Đọc tập con 20 % của nguồn (201.074 / 1.010.293 = 19,9 %) |
| 2 | Thiếu văn bản | 201.074 | 0 | 201.074 | Text rỗng sau làm sạch |
| 3 | Thiếu nhãn | 201.074 | **10.394** | 190.680 | `rating` thiếu hoặc ngoài 1–10 → không suy được nhãn |
| 4 | Quá ngắn | 190.680 | 10 | 190.670 | Dưới 20 ký tự → không đủ tín hiệu |
| 5 | Quá dài | 190.670 | **1.686** | 188.984 | Trên 5.000 ký tự → chặn chi phí và nhiễu |
| 6 | Trùng mã | 188.984 | **2.999** | 185.985 | Nguồn có `review_id` lặp; giữ bản văn bản dài nhất |
| 7 | Trùng chính xác | 185.985 | 636 | 185.349 | Cùng văn bản sau làm sạch |
| 8 | Trùng gần | 185.349 | 63 | **185.286** | Cùng bộ từ sau chuẩn hóa, khác thứ tự/dấu câu |
| 9 | Chia tập | 185.286 | 0 | 185.286 | Train 129.701 / Val 27.793 / Test 27.792 |

**Bốn điểm kỹ thuật phải nói:**

1. **Làm sạch viết một lần** ở `src/common/text_cleaning.py`, dùng chung cho cả huấn luyện và streaming. Không có bản sao logic thứ hai.
2. Làm sạch bằng **hàm Spark SQL** (`lower`, `regexp_replace`, `trim`, `split`…), **không dùng Python UDF** → Catalyst tối ưu được, chạy nhanh.
3. **Loại trùng trước khi chia tập**, gồm cả gần trùng. Nếu để bản copy-paste lẫn vào train/test thì điểm sẽ cao giả tạo.
4. **Chia theo nhóm phim**, không chia ngẫu nhiên từng dòng: một bộ phim chỉ nằm trong một tập. Mục đích là tránh rò rỉ nội dung (cùng một phim ở cả train và test).

**Thứ tự 9 bước làm sạch văn bản** (đúng thứ tự trong code — đổi thứ tự là đổi kết quả):

1. Chữ thường + trim.
2. Bỏ thẻ/entity HTML.
3. URL → `<url>`.
4. `@mention` → `<user>` (không giữ danh tính).
5. Chuẩn hóa dấu câu Unicode, bỏ ký tự vô hình.
6. Thay viết tắt/teencode theo từ điển (`pls` → `please`…).
7. Rút gọn ký tự lặp ≥ 3 → 2 (`soooo` → `soo`).
8. Tách emoji thành token riêng.
9. Gộp khoảng trắng + trim.

Hàm có tính **idempotent** (làm sạch hai lần cho cùng kết quả) — có test.

**Phân bố lớp sau khi chia** (`outputs/tables/class_distribution.csv`):

| Tập | negative | neutral | positive | Tổng |
|---|---:|---:|---:|---:|
| Train | 32.504 (25,06 %) | 17.983 (13,86 %) | 79.214 (61,07 %) | 129.701 |
| Val | 6.965 (25,06 %) | 3.854 (13,87 %) | 16.974 (61,07 %) | 27.793 |
| Test | 6.965 (25,06 %) | 3.853 (13,86 %) | 16.974 (61,08 %) | 27.792 |

→ Dữ liệu **mất cân bằng**: positive chiếm 61 %, neutral chỉ 13,9 %. Đây là lý do **không được báo cáo accuracy một mình**.

---

### Bước 3 — Huấn luyện mô hình (Task 7, `train.py`)

**Đầu vào:** `train.parquet` (129.701 dòng), `val.parquet` (27.793 dòng), `test.parquet` (27.792 dòng).

**Pipeline Spark ML — 7 bước, tất cả nằm trong một `Pipeline`:**

```
text
 → RegexTokenizer          tách từ theo khoảng trắng
 → StopWordsRemover        bộ tiếng Anh của Spark, GIỮ từ phủ định (not/no/never/n't)
 → NGram                   n = 1 hoặc 2 (thử cả hai)
 → CountVectorizer         vocabSize = 20.000, minDF = 3
 → IDF                     nghịch đảo tần suất tài liệu
 → Normalizer              chuẩn hóa L2
 → Classifier              NaiveBayes / LogisticRegression / LinearSVC / RandomForest
```

**Vì sao TF-IDF nằm trong Pipeline:** để nó **chỉ được fit trên tập train**. Nếu fit trên toàn bộ dữ liệu trước khi chia thì thông tin của test đã rò vào vector hóa — điểm sẽ cao giả.

**4 mô hình + 1 baseline:**

| Mô hình | Lưới thử | Đặc điểm |
|---|---|---|
| MajorityBaseline | — | Luôn đoán "positive" — mốc so sánh |
| NaiveBayes | n-gram 1/2, smoothing 1.0 | Nhanh, xác suất |
| LogisticRegression | n-gram 1/2 × regParam 0.01/0.1 | Tuyến tính, có xác suất từng lớp |
| LinearSVC (One-vs-Rest) | n-gram 1, regParam 0.01/0.1 | Tuyến tính, không có xác suất |
| RandomForest | n-gram 1, 30 cây, sâu 8/12, 5.000 đặc trưng | Phi tuyến, chậm hơn |

**Cách chọn siêu tham số:**
- Dùng `TrainValidationSplit` **bên trong tập train** (80/20), chọn theo **weighted F1**.
  - Lý do dùng weighted F1: Spark 3.5 **không có evaluator macro-F1** cho Python.
- Sau khi chọn, **fit lại trên toàn bộ 129.701 dòng train**.
- So sánh các mô hình trên **tập validation** bằng macro-F1 (tính tay từ confusion matrix).
- **Tập test chỉ chạm đúng một lần** ở cuối, có ghi log `outputs/tables/test_eval_log.csv`.

**Xử lý mất cân bằng:** dùng `weightCol`, trọng số `w_c = N / (k · n_c)` tính **trên tập train**:
- negative 1,330 · neutral 2,404 · positive 0,546.

**Kết quả chọn mô hình trên validation** (không dùng test):

| Mô hình | Accuracy | Weighted F1 | **Macro-F1** | Thời gian học |
|---|---:|---:|---:|---:|
| MajorityBaseline | 0,6107 | 0,4631 | 0,2528 | 0 s |
| **LogisticRegression** | **0,7063** | **0,7241** | **0,6291** | **245 s** |
| LinearSVC | 0,7000 | 0,7172 | 0,6218 | 116 s |
| NaiveBayes | 0,6743 | 0,7013 | 0,6192 | 108 s |
| RandomForest | 0,5878 | 0,6131 | 0,5343 | 282 s |

→ Chọn **Logistic Regression**: macro-F1 cao nhất, học 245 s, dự đoán ~0,92 s/10.000 dòng, **có xác suất từng lớp** (SVC không có) nên dashboard hiển thị được độ tin cậy.

**Vì sao 1-gram thắng 2-gram:** 2-gram làm số đặc trưng tăng mạnh nhưng không cải thiện macro-F1; review IMDb khá dài nên 1-gram đã đủ tín hiệu.

---

### Bước 4 — Đánh giá mô hình (Task 7, cuối)

**Tập test 27.792 dòng, dùng đúng một lần:**

| Chỉ số | Giá trị |
|---|---:|
| Accuracy | **0,7018** |
| Weighted F1 | **0,7213** |
| **Macro-F1** | **0,6233** |
| Baseline đa số — macro-F1 | 0,2528 |

**Theo từng lớp (test):**

| Lớp | Precision | Recall | F1 | Số mẫu | Tỷ lệ |
|---|---:|---:|---:|---:|---:|
| negative | 0,6807 | 0,6642 | 0,6723 | 6.965 | 25,06 % |
| **neutral** | **0,3036** | **0,5019** | **0,3783** | 3.853 | 13,86 % |
| positive | 0,8851 | 0,7626 | 0,8193 | 16.974 | 61,08 % |

**Confusion matrix (test, hàng = nhãn thật):**

| Thật \ Đoán | negative | neutral | positive |
|---|---:|---:|---:|
| negative | **4.626** | 1.625 | 714 |
| neutral | 952 | **1.934** | 967 |
| positive | 1.218 | 2.812 | **12.944** |

Đọc 3 điều từ bảng này:
1. Neutral chỉ đúng **50,2 %**; sai **24,7 %** sang negative và **25,1 %** sang positive — sai về cả hai phía, đúng dấu hiệu **nhãn nhiễu** (rating 5–6 trộn "khen nhẹ" và "chê nhẹ").
2. Positive khá tốt (F1 0,8193) nhưng **2.812/16.974 (16,6 %)** bị đoán thành neutral.
3. Accuracy 0,7018 **không nên** dùng một mình: baseline đoán bừa "positive" đã được 0,6108.

**Kiểm tra rò rỉ dữ liệu:**
- Trùng văn bản sau chuẩn hóa: train↔val **0**, train↔test **0**, val↔test **0**.
- Ngưỡng cảnh báo macro-F1 0,95: kết quả 0,6233 → không có dấu hiệu rò rỉ.
- Nhật ký chạm test: **1 lần**.

**Phát hiện quan trọng — mô hình đọc cả điểm số:**
- `7/10` là đặc trưng mạnh **nhất** của lớp positive (trọng số 6,50).
- `6/10`, `5/10` nằm trong top 6 của neutral; `4/10` trong top 10 của negative.
- Hệ quả: một phần độ chính xác đến từ **đọc con số người viết tự ghi**, không phải hiểu cảm xúc. Trên livestream thật (hiếm khi ghi "6/10"), kết quả **có thể thấp hơn 0,62**. Đây là hạn chế đã biết, phải nói.

**Thời gian:** toàn bộ quá trình huấn luyện + đánh giá + vẽ hình khoảng **13 phút** trên máy ảo 4 nhân, `local[2]`, 2 GB driver.

---

### Bước 5 — Chạy theo luồng (Task 8, `stream_job.py`)

**Kiến trúc:**

```
Producer replay ──► Kafka comments_raw (3 partition)
                         │
                         ▼
        Spark Structured Streaming — 6 query độc lập
        ├─ detail    → Parquet scored_detail
        ├─ kafka     → topic comments_scored
        ├─ window    → Parquet window_1min
        ├─ sliding   → Parquet window_sliding_10s (10 s, trượt 5 s)
        ├─ dlq_kafka → topic comments_dlq
        └─ dlq_parquet → Parquet dlq
```

**Mỗi query có `checkpointLocation` riêng** — query này chậm không chặn query khác; chạy lại đúng tên thì tiếp tục từ offset đã commit.

**Các quyết định kỹ thuật:**
- Schema `from_json` **khai báo tường minh** — không suy luận từ dữ liệu.
- Dùng **event time** (`event_ts`), **watermark 2 phút**; cửa sổ 1 phút và cửa sổ trượt 10 giây / slide 5 giây.
- **Nhãn không đi vào Kafka.** Message chỉ có 5 trường: `comment_id`, `stream_id`, `user_hash`, `text`, `event_ts`.
- `user_hash` là **băm có muối** (muối từ biến môi trường), không gửi tên người dùng.
- Bản ghi lỗi vào **DLQ kèm lý do**, không âm thầm bỏ qua.
- Mặc định **không lưu văn bản** (`keep_text: false`); chỉ demo mới bật vì dữ liệu IMDb công khai.

**Kết quả kiểm chứng lần chạy `verify1`:**

| Câu hỏi | Kết quả |
|---|---|
| Gửi bao nhiêu? | **1.024** (1.000 replay + 14 kiểm chứng + 10 ca lỗi) |
| Chấm điểm + DLQ có khớp? | **1.014 + 10 = 1.024** ✔ |
| Kafka nhận đúng? | `comments_scored` +1.014, `comments_dlq` +10 |
| Streaming có cho cùng dự đoán với offline? | **1.000/1.000 (100,00 %)** |
| Macro-F1 trên luồng | **0,6311** (1.000 dòng) vs 0,6233 offline toàn tập |
| Watermark có bỏ bản ghi muộn? | **Có** — bản ghi lạc hậu 10 phút không có mặt trong cửa sổ |
| Exactly-once? | **Chưa kiểm chứng** — chỉ nói **at-least-once** |

**DLQ bắt đúng 10/10 ca:** JSON hỏng (3), thiếu `text` (1), thiếu `comment_id` (1), thiếu `event_ts` (1), `event_ts` không đọc được (1), văn bản rỗng (1), quá ngắn (1), quá dài (1).

---

### Bước 6 — Phân tích dữ liệu (Task 9, EDA)

- **13 truy vấn Spark SQL** trong `src/eda/sql/q00–q12_*.sql`.
- **15 hình** trong `outputs/figures/`, insight sinh tự động trong `outputs/insights.md`.

**5 con số đáng nhớ:**

| Phát hiện | Số thật |
|---|---|
| Dữ liệu mất cân bằng | positive 61,1 %, negative 25,1 %, neutral 13,9 % |
| Bình luận neutral dài nhất | trung vị **131 token**, gấp 1,6× positive (83 token) |
| Tốc độ phát | **969/1.014 bình luận trong 27 giây**; đỉnh **384 msg/s = 96 % trần thiết kế** (50 × 8 = 400) |
| Cảnh báo tiêu cực | bắn **đúng 1 lần**: 38,5 % với 13 bình luận; nếu bỏ điều kiện ≥5 bình luận thì có thêm **13 báo động giả** |
| Độ trễ end-to-end | p50 **2.413 ms**, p95 **9.663 ms**, p99 **27.091 ms**; 81 % bình luận được chấm trong 1–4 giây |

**Một phát hiện về chất lượng dữ liệu:** **11,2 % token có dấu câu dính ở hai đầu** ("movie." khác "movie"), làm từ vựng tăng từ 318.980 lên 524.107 từ (+64 %). Chưa sửa vì sửa phải huấn luyện lại mô hình mới so sánh được — ghi làm việc tiếp theo.

---

### Bước 7 — Dashboard (Task 10)

- Streamlit 3 tab: **Live Monitor** (đọc Parquet), **Try It** (chấm một câu), **About** (pipeline + hạn chế).
- Cảnh báo dùng đúng quy tắc đã đo: **tỷ lệ tiêu cực > 30 % và ≥ 5 bình luận**.
- Che từ nhạy cảm, email, số điện thoại; không hiện `user_hash`.
- **Đây là dashboard demo, không phải app production** — chưa có đăng nhập, phân quyền, quy trình xử lý cảnh báo.

---

### Bước 8 — Chương trình thử nghiệm mô hình (Task 12)

- `src/app/model_trial.py`: chạy một lệnh, **không cần Kafka/Streamlit**.
- Dùng **đúng** `clean_text()` và `PipelineModel` của hệ thống.
- Ba chế độ: tương tác, batch (`--text/--file/--examples`), đo mẫu (`--test-sample N`).
- Quy tắc loại văn bản giống hệt DLQ (rỗng / < 20 / > 5.000 ký tự).
- Kết quả 200 dòng test: accuracy **0,7200**, macro-F1 **0,6317**, ~**8 ms/dòng**; chạy hai lần cho cùng kết quả.
- **Đây chỉ là kiểm tra tái lập** — số chính thức vẫn là toàn tập test: 0,7018 / 0,6233.

**Ví dụ nói khi demo:**

| Câu | Kết quả | Ý nghĩa |
|---|---|---|
| `it was okay, nothing special. 6/10` | neutral **99,3 %** | Mô hình đọc token `6/10`, không hiểu cảm xúc |
| `his "bad acting" had me crying with laughter, absolutely brilliant` | positive **86,3 %** | Câu mỉa mai này lại đúng — đừng nói "mô hình luôn sai với mỉa mai" |
| `Boring, badly acted, way too long.` | negative **86,0 %** | Ca dễ |
| `short` | **không chấm** | Đúng luật DLQ: dưới 20 ký tự |

---

### Bước 9 — Kiểm thử tự động

**77 test, pass toàn bộ** (`tests/README.md`), chia 4 nhóm:

| Nhóm | Số test | Kiểm gì |
|---|---:|---|
| Test cũ (làm sạch, utils, schema) | 28 | Tính idempotent, băm khớp Spark↔Python, ánh xạ nhãn, config |
| Dashboard | 21 | Gộp cửa sổ, quy tắc cảnh báo, che dữ liệu, biểu đồ |
| Chuẩn bị dữ liệu | 15 | Lấy mẫu tất định, lồng nhau, biên ngưỡng, manifest |
| Model trial | 13 | Quy tắc DLQ, công thức P/R/F1, định dạng output |

Chạy:

```bash
source scripts/env.sh
/usr/local/hadoop/sbin/start-dfs.sh && hdfs dfsadmin -safemode wait   # test Spark cần HDFS
.venv/bin/python -m pytest tests/ -q
```

Lưu ý: 13 test model trial **không cần Spark**, chạy được cả khi HDFS tắt.

---

## 4. "Test như nào?" — trả lời theo 4 tầng

Giáo viên hỏi "em test thế nào" thường muốn biết cả **kiểm thử phần mềm** lẫn **đánh giá mô hình**. Trả lời theo 4 tầng:

### Tầng 1 — Unit test (kiểm thử phần mềm)

- 77 test tự động, chạy bằng pytest.
- Kiểm các hàm dùng chung: làm sạch văn bản, băm, ánh xạ nhãn, quy tắc DLQ, công thức metric.
- Mục đích: đảm bảo **train và streaming dùng cùng logic**; sửa một bên mà quên bên kia là test bắt được.

### Tầng 2 — Smoke test mô hình đã lưu

- `scripts/check_model.py`: nạp lại `PipelineModel`, chấm 5 câu cố định.
- Mục đích: chứng minh model lưu ra **load lại được** và cho kết quả như lúc huấn luyện.

### Tầng 3 — Đánh giá offline trên tập test

- Chỉ dùng **một lần**, 27.792 dòng.
- Tính accuracy, weighted F1, **macro-F1**, P/R/F1 từng lớp, confusion matrix.
- Kiểm rò rỉ: trùng văn bản giữa các tập = 0/0/0; nhật ký chạm test = 1 lần.
- Đây là nguồn của con số chính thức **0,7018 / 0,6233**.

### Tầng 4 — Kiểm chứng end-to-end trên luồng

- Phát 1.024 bản ghi qua Kafka; đối chiếu **1.014 chấm điểm + 10 DLQ = 1.024**.
- Chạy lại model offline trên đúng 1.000 `comment_id`: **1.000/1.000 dự đoán giống nhau**.
- Kiểm watermark bằng bản ghi lạc hậu 10 phút: bị bỏ đúng.
- Kiểm DLQ bằng 10 ca lỗi đã biết: bắt đúng 10/10 kèm lý do.
- **Chưa** kiểm exactly-once khi crash/kill giữa batch → không khẳng định.

**Câu chốt:**

> "Nhóm em kiểm theo 4 tầng: unit test cho hàm dùng chung, smoke test cho model đã lưu, đánh giá offline một lần trên test, và kiểm chứng end-to-end trên luồng. Tầng nào cũng có file kết quả thật; phần chưa kiểm là exactly-once, nhóm ghi rõ là chưa kiểm chứng."

---

## 5. Kết quả chạy — bảng tổng hợp để chiếu

| Hạng mục | Kết quả thật | Nguồn |
|---|---|---|
| Dữ liệu nguồn | 1.010.293 review IMDb (CC0) | `data/raw/SOURCE.md` |
| Tập con dùng | 201.074 (19,9 %) | `outputs/tables/cleaning_log.csv` |
| Sau làm sạch + loại trùng | 185.286 | `outputs/tables/cleaning_log.csv` |
| Chia tập | 129.701 / 27.793 / 27.792 | `outputs/tables/class_distribution.csv` |
| Mô hình tốt nhất | Logistic Regression | `outputs/tables/model_results.csv` |
| Test accuracy | **0,7018** | `outputs/tables/model_results.csv` |
| Test macro-F1 | **0,6233** | `outputs/tables/model_results.csv` |
| Baseline macro-F1 | 0,2528 | `outputs/tables/model_results.csv` |
| F1 negative / neutral / positive | **0,6723 / 0,3783 / 0,8193** | `outputs/tables/per_class_metrics.csv` |
| Trùng giữa các tập | 0 / 0 / 0 | `outputs/tables/leak_check.json` |
| Kafka ingestion | 1.000 gửi → 1.000 nhận, 0 lỗi | `outputs/tables/ingestion_report.csv` |
| Streaming | 1.014 chấm + 10 DLQ = 1.024 | `outputs/streaming_summary.md` |
| Streaming vs offline | 1.000/1.000 dự đoán giống | `outputs/streaming_summary.md` |
| Macro-F1 trên luồng | 0,6311 | `outputs/streaming_summary.md` |
| Test tự động | **77 passed** | `tests/README.md` |
| Model trial 200 dòng | 0,7200 / 0,6317 (kiểm tra tái lập) | `outputs/model_trial_report.md` |

---

## 6. Hạn chế — phải nói, không để giáo viên phát hiện trước

| # | Hạn chế | Cách nói trung thực |
|---|---|---|
| 1 | **Dữ liệu là replay IMDb**, không phải livestream thật | "Toàn bộ luồng là mô phỏng; nhóm không gọi đây là dữ liệu livestream." |
| 2 | **Nhãn suy từ rating** 1–4 / 5–6 / 7–10, không phải nhãn người gán | "Đây là quy ước của nhóm; lớp neutral nhiễu nhất." |
| 3 | **Neutral F1 0,3783** | "Điểm yếu đã biết; 50 % đoán đúng, sai 25 % về mỗi phía." |
| 4 | **Mô hình đọc điểm số** `6/10`, `7/10` | "Một phần điểm đến từ đọc con số; trên livestream thật có thể thấp hơn." |
| 5 | **11.427 người dùng xuất hiện ở >1 tập** | "Đã đo, chưa xử lý; chia theo phim nên cùng người xem có thể ở nhiều tập. Ảnh hưởng chưa định lượng." |
| 6 | **Chưa kiểm chứng exactly-once** | "Chỉ dám nói at-least-once cho phần đã chạy; chưa thử crash/kill." |
| 7 | **Chưa kiểm định ý nghĩa thống kê** giữa các mô hình | "Chênh lệch LR/SVC/NB 0,007–0,010, chưa chắc có ý nghĩa." |
| 8 | **Mô hình huấn luyện trên tập con 20 %** | "Vì giới hạn máy ảo; quy trình 64 % đã chuẩn bị nhưng chưa chạy để không phá tính so sánh." |
| 9 | **Chưa có app production** | "Prototype dừng ở TRL 5; app hoàn chỉnh là future work." |
| 10 | **Chưa có ảnh dashboard** | "Máy ảo chặn snap browser; sẽ chụp từ máy thật." |

**Câu chốt về TRL:**

> "Nhóm em tự đánh giá **TRL 5**: hệ thống tích hợp đầy đủ và kiểm chứng trong môi trường mô phỏng. Chưa lên TRL 6 vì chưa chạy với người dùng thật và dữ liệu thật."

---

## 7. Kế hoạch tiếp theo — nói trong 30 giây

1. **Hoàn thiện Final Report** theo template, dùng bản đồ số liệu trong `docs/huong_dan_bao_cao.md`.
2. **Slide báo cáo cuối** cập nhật số Task 7–10.
3. **Ảnh chụp dashboard** từ máy thật (port forwarding 8501).
4. **Push GitHub** 2 commit còn lại.
5. **Nếu còn thời gian:** huấn luyện lại trên 64 % dữ liệu theo `docs/huong_dan_huan_luyen.docx`; thu 200–300 bình luận livestream thật để đo lại.
6. **Hướng dài hạn:** app production (đăng nhập, quy trình moderator, API nền tảng, monitoring), kiểm chứng exactly-once.

---

## 8. Bộ câu hỏi–đáp án (25 câu)

### A. Về dữ liệu

**1. Vì sao dùng IMDb mà không dùng dữ liệu livestream thật?**
Vì cần dữ liệu có giấy phép rõ ràng, có nhãn để đánh giá, và có `id` ổn định để kiểm chứng luồng. IMDb là **CC0**, 1.010.293 review. Thu chat livestream thật vướng điều khoản nền tảng và quyền riêng tư; nhóm ghi rõ đây là **replay** và dừng ở TRL 5.

**2. Vì sao chỉ dùng 201.074 / 1.010.293 review?**
Máy ảo 7,2 GB RAM, 4 nhân. Tập 20 % đủ để huấn luyện và đánh giá, đồng thời giữ thời gian chạy trong khoảng 13 phút. Nhóm đã đo tập 64 %: **646.249 bản ghi / 608,8 MB**, nhưng chưa huấn luyện lại vì sẽ tạo tập test khác, không so sánh được với 0,6233 đã báo cáo.

**3. Nhãn ở đâu ra?**
Không có nhãn cảm xúc gốc. Nhóm suy từ `rating`: 1–4 negative, 5–6 neutral, 7–10 positive. Đây là **quy ước thiết kế**, không phải nhãn chuẩn của IMDb.

**4. Vì sao neutral yếu?**
Rating 5–6 trộn "khen nhẹ" và "chê nhẹ"; văn bản có thể rất mạnh. Trong 3.853 mẫu neutral, chỉ **50,2 %** đoán đúng; **24,7 %** sang negative và **25,1 %** sang positive. Đây là **nhiễu nhãn**, không chỉ lỗi mô hình.

**5. Vì sao chia theo phim?**
Nếu chia ngẫu nhiên từng review, cùng một phim có thể nằm ở cả train và test → mô hình học đặc trưng của phim, điểm cao giả. Chia theo nhóm phim đảm bảo **một phim chỉ ở một tập**.

**6. 11.427 người dùng ở nhiều tập có phải rò rỉ không?**
Là **rủi ro còn lại**: cùng một reviewer có thể review nhiều phim ở các tập khác nhau. Nhóm đã đo nhưng **chưa xử lý** và **chưa định lượng ảnh hưởng**; khi báo cáo phải nói kèm điều kiện này, không được nói "không rò rỉ".

**7. Vì sao loại cả gần trùng?**
Bình luận livestream hay copy-paste; nếu bản gần trùng nằm ở cả train và test thì điểm cao giả tạo. Nhóm loại trùng chính xác **636** dòng và gần trùng **63** dòng trước khi chia.

### B. Về huấn luyện

**8. Pipeline gồm những gì?**
RegexTokenizer → StopWordsRemover → NGram → CountVectorizer (20.000 từ, minDF 3) → IDF → Normalizer L2 → classifier. Tất cả nằm trong một `Pipeline`.

**9. TF-IDF có fit trên test không?**
Không. Toàn bộ vector hóa nằm trong Pipeline, chỉ fit trên train. `TrainValidationSplit` cũng chia bên trong train. Test chỉ được transform, không được fit.

**10. Sao không dùng BERT/PhoBERT?**
Ràng buộc môi trường (7,2 GB RAM, 4 nhân, không GPU) và mục tiêu khóa là pipeline Big Data. TF-IDF + LR giải thích được (xem top features), huấn luyện 245 s, dự đoán ~1 s/10.000 dòng. BERT là future work.

**11. Vì sao chọn Logistic Regression?**
Macro-F1 validation cao nhất **0,6291**; học 245 s; dự đoán nhanh; **có xác suất từng lớp** để dashboard hiển thị. SVC 0,6218, NB 0,6192, RF 0,5343.

**12. Vì sao 1-gram thắng 2-gram?**
2-gram làm số đặc trưng tăng mạnh nhưng macro-F1 không cải thiện. Review IMDb dài, 1-gram đã đủ tín hiệu; 2-gram còn làm mô hình chậm và dễ nhiễu hơn.

**13. Xử lý mất cân bằng thế nào?**
`weightCol` với `w_c = N / (k · n_c)` tính trên train: negative 1,330; neutral 2,404; positive 0,546.

**14. Sao bỏ stopword mà vẫn giữ "not"?**
Bộ stopword tiếng Anh của Spark có `not`, `no`, `never`, `n't`. Với bài toán cảm xúc, bỏ chúng là mất tín hiệu phủ định ("not good" khác "good"), nên nhóm **giữ từ phủ định**, còn lại 162 stopword.

**15. Chọn siêu tham số thế nào? Có nhìn test không?**
`TrainValidationSplit` chia 80/20 **bên trong train**, chọn theo weighted F1 (Spark 3.5 không có evaluator macro-F1). Sau đó so sánh mô hình trên **validation** bằng macro-F1. Test chỉ chạm **một lần** ở cuối, có log.

**16. Mô hình có overfit không?**
Macro-F1 validation 0,6291 vs test 0,6233 — chênh **0,0058**, không có dấu hiệu overfit mạnh. LR có `regParam=0.1`.

**17. Huấn luyện mất bao lâu?**
LR 245 s; toàn bộ 4 mô hình + chọn tham số + đánh giá + vẽ hình khoảng **13 phút** trên máy ảo `local[2]`, 2 GB driver.

**18. Chạy lại huấn luyện bằng lệnh nào?**
```bash
source scripts/env.sh
PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \
  --driver-memory 2g --master 'local[2]' src/training/train.py
```
Chạy thử thêm `--sample 20000` (tự bỏ qua test). Với 64 % nên nâng `--driver-memory 4g`.

### C. Về đánh giá và kiểm thử

**19. Sao accuracy 70 % mà dám nói mô hình dùng được?**
Vì baseline đoán bừa "positive" đã được 61 %. Nhóm báo cáo **macro-F1 0,6233** (gấp 2,5 lần baseline 0,2528) và F1 từng lớp, không dùng accuracy một mình. 70 % vẫn là mức trung bình, nhóm không nói là giải xong bài toán.

**20. Làm sao biết không rò rỉ dữ liệu?**
Ba phép kiểm: (a) trùng văn bản sau chuẩn hóa giữa các tập = **0/0/0**; (b) macro-F1 0,6233 dưới ngưỡng cảnh báo 0,95; (c) `test_eval_log.csv` ghi đúng **1 lần** chạm test. Ngoài ra còn rủi ro 11.427 user ở nhiều tập — đã ghi rõ.

**21. 77 test kiểm những gì?**
28 test cũ (làm sạch, băm, nhãn, config), 21 dashboard (cảnh báo, che dữ liệu, biểu đồ), 15 chuẩn bị dữ liệu (lấy mẫu tất định, manifest), 13 model trial (DLQ, metric). Chạy `pytest tests/ -q`; test Spark cần HDFS bật.

**22. Đã test mô hình trên câu mới chưa?**
Có. `scripts/check_model.py` chấm 5 câu cố định; `model_trial.py --examples` chấm 4 câu trong config. Ví dụ `6/10` → neutral 99,3 %, cho thấy mô hình đọc điểm số.

**23. Vì sao mẫu 200 dòng cho macro-F1 0,6317 khác 0,6233?**
Vì mẫu 200 dòng chỉ là 0,7 % tập test; chênh lệch do **lấy mẫu**, chưa kiểm định ý nghĩa. Số chính thức là toàn tập test 27.792 dòng: **0,6233**. Mẫu chỉ để chứng minh chương trình chạy lại được và tất định.

### D. Về streaming và hệ thống

**24. Vì sao dùng Kafka? Sao không đọc file trực tiếp?**
Kafka làm bộ đệm và tách nguồn phát khỏi nguồn xử lý; nhiều consumer độc lập; phát lại được; chịu được bùng nổ. File tĩnh không mô phỏng được luồng và offset.

**25. Watermark để làm gì? Vì sao 2 phút?**
Watermark chặn dữ liệu đến quá muộn và giới hạn state của cửa sổ. Producer mô phỏng trễ tối đa 30 giây, nên 2 phút = 4× biên an toàn. Hệ quả: cửa sổ chỉ được ghi sau khi đóng + watermark, nên kết quả ra chậm ~2–3 phút — đã kiểm chứng bằng bản ghi lạc hậu 10 phút.

**26. DLQ là gì?**
Hàng đợi bản ghi lỗi. Bản ghi hỏng/thiếu trường/ quá ngắn/ quá dài được ghi sang topic `comments_dlq` và Parquet kèm `reason`, không bị bỏ im lặng. Lần chạy `verify1` bắt đúng **10/10** ca.

**27. Có đảm bảo exactly-once không?**
**Không dám khẳng định.** Đã đo: chạy liên tục không mất/không trùng, dừng êm 2 lần, checkpoint riêng từng query. **Chưa** thử kill giữa batch, broker chết, hay đếm bản ghi trùng sau restart. Chỉ nói **at-least-once** cho phần đã đo.

**28. Dashboard có phải app hoàn chỉnh không?**
Không. Dashboard demo 3 tab, đọc Parquet; chưa có đăng nhập, phân quyền, quy trình xử lý cảnh báo, API nền tảng, monitoring. App production là future work.

**29. Vì sao chương trình demo không dùng Kafka?**
Vì mục đích là kiểm tra **mô hình** trên văn bản mới, không phải kiểm tra hạ tầng. Kafka/Streaming đã kiểm riêng ở Task 8 với 1.024 bản ghi. Tách ra giúp demo chạy được cả khi Kafka/HDFS tắt.

**30. Nếu chuyển sang bình luận tiếng Việt thì sao?**
Phải thêm tách từ tiếng Việt (ví dụ `underthesea`) dưới dạng `pandas_udf`, **đo chi phí** (UDF chậm hơn hàm SQL), gán nhãn tay, huấn luyện lại và đánh giá lại. **Chưa làm** — hiện tại dữ liệu là tiếng Anh nên không dùng tách từ tiếng Việt.

---

## 9. Checklist trước khi vào buổi báo cáo

- [ ] Mở sẵn 5 file: `00_pipeline_architecture.png`, `03_model_comparison.png`, `01_confusion_matrix.png`, `02_per_class_prf1.png`, `streaming_summary.md`.
- [ ] Mở terminal đã `cd /home/hadoop/capstone`; chạy thử `bash scripts/run_model_trial.sh --examples` một lần trước khi vào họp.
- [ ] Ghi ra giấy 6 số phải nhớ: **0,7018 · 0,6233 · 0,3783 · 1.024 = 1.014 + 10 · 1.000/1.000 · 77 passed**.
- [ ] Chuẩn bị câu nói về hạn chế (mục 6) — không để bị hỏi mới nói.
- [ ] Nếu cô hỏi "phần em làm gì": trả lời theo phân công trong WBS, không nhận phần người khác.
- [ ] Không mở dashboard + Spark cùng lúc trên máy ảo nếu không cần (7,2 GB RAM).

---

## 10. Một đoạn tiếng Anh dùng cho email/slide tiến độ

> We have completed the technical prototype: data preparation, model training and one-time test evaluation, a Kafka + Spark Structured Streaming pipeline with dead-letter handling and event-time watermarking, exploratory analysis, a Streamlit dashboard, and a standalone model-trial program. The best model is Logistic Regression with TF-IDF (20,000 features), achieving **accuracy 0.7018** and **macro-F1 0.6233** on a held-out test set of 27,792 IMDb reviews. End-to-end streaming verification shows **1,014 scored records + 10 dead-letter records = 1,024 sent**, and **1,000/1,000 predictions identical** to offline scoring. The system is at **TRL 5**: validated in a simulated environment. Remaining work: final report and slides, dashboard screenshots, repository push, and — as future work — validation on real livestream data and a production application.
