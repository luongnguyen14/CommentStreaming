# Hướng dẫn báo cáo dự án — Nhóm 6

**Dự án:** Mô hình phân loại cảm xúc dựa trên bình luận trực tuyến
(*Real-time Sentiment Classification of Online Comments using Kafka, Spark Structured Streaming and Spark ML*)

**Ngày kiểm tra trạng thái:** 19/10/2026 · **Tài liệu nội bộ** — không nộp cho giảng viên.
Mọi con số trong tài liệu này đều dẫn về file thật trong `outputs/` (CLAUDE.md §9).

---

## 0. Trạng thái dự án — đã kiểm tra lại

### 0.1 Những phần đã làm xong

| Task | Nội dung | Bằng chứng chính |
|---|---|---|
| 1 | Định khung đề tài, chọn dữ liệu, quy ước dự án | `docs/topic_decision.md`, `CLAUDE.md` |
| 2 | Action Plan + truy vết nguồn dữ liệu IMDb (CC0) | `deliverables/Action_Plan.docx`, `data/raw/SOURCE.md` |
| 3 | WBS 20 ngày, phân công 5 thành viên | `deliverables/WBS.xlsx` |
| 4 | Slide đề xuất 5 trang | `deliverables/Proposal_Slides.pptx` |
| 5 | Kafka 4.3.1 KRaft + producer replay + kiểm chứng 1.000 message | `src/producer/`, `outputs/tables/ingestion_report.csv` |
| 6 | Làm sạch văn bản dùng chung + chia tập + loại trùng | `src/common/text_cleaning.py`, `src/training/prepare.py`, `data/processed/` |
| 7 | Huấn luyện 4 mô hình + baseline, đánh giá test **một lần** | `src/training/train.py`, `outputs/modeling_summary.md`, `outputs/tables/test_eval_log.csv` |
| 8 | Spark Structured Streaming 6 query + DLQ + watermark | `src/streaming/stream_job.py`, `outputs/streaming_summary.md` |
| 9 | 13 truy vấn Spark SQL + 10 biểu đồ + insights | `src/eda/`, `outputs/figures/06–15_*`, `outputs/insights.md` |
| 10 | Dashboard Streamlit 3 tab + `run_demo.sh` | `src/app/app.py`, `outputs/stream/demo/` |
| 11 | Tăng dữ liệu lên 64 % + tài liệu tự huấn luyện lại | `scripts/make_training_guide.py`, `docs/huong_dan_huan_luyen.docx` |
| **12 (mới)** | **Chương trình thử nghiệm mô hình** — chạy được bằng một lệnh, không cần Kafka/Streamlit | `src/app/model_trial.py`, `scripts/run_model_trial.sh`, `outputs/model_trial_report.md` |

### 0.2 Đã đẩy lên GitHub chưa?

Kiểm tra ngày **19/10/2026**:

| Mục | Giá trị |
|---|---|
| Repository | `https://github.com/luongnguyen14/CommentStreaming` (public) |
| Commit mới nhất **trên GitHub** | `6fd6f49` — *Task 10b: cập nhật bằng chứng demo + log* |
| Commit mới nhất **ở máy** | `15a84da` — *Task 11b: hướng dẫn huấn luyện lại cho 3 nơi chạy* |
| Chênh lệch | **Máy đang hơn GitHub 1 commit** (Task 11b **chưa** đẩy lên) |
| Kích thước repo | ~47,8 MB trên GitHub; không có file nào > 50 MB trong git |

**Vì sao chưa đẩy được:** `git push` báo `Permission denied (publickey)`. Khóa `~/.ssh/id_rsa`
có passphrase và agent của GNOME từ chối ký khi chạy ngoài phiên đồ họa; khóa
`~/.ssh/id_ed25519` (không passphrase) **chưa được đăng ký** với GitHub.

**Cách xử lý (chọn một):**

```bash
# Cách A — nạp khóa có passphrase rồi push (nhập passphrase khi được hỏi)
ssh-add ~/.ssh/id_rsa
git push origin main

# Cách B — đăng ký khóa không passphrase với GitHub (một lần, sau đó push không cần nhập gì)
cat ~/.ssh/id_ed25519.pub
# Copy dòng vừa in → GitHub → Settings → SSH and GPG keys → New SSH key → dán → Add
git push origin main
```

> Sau khi làm xong Task 12 (tài liệu này + chương trình demo), máy sẽ hơn GitHub
> **2 commit** (Task 11b và Task 12). Hãy push cả hai.

### 0.3 Những việc còn thiếu trước khi nộp

| # | Việc | Ghi chú |
|---|---|---|
| 1 | **Điền Final Report** theo template của cô | `deliverables/` chưa có `Final_Report.docx`; xem bản đồ mục ở §3 |
| 2 | **Push GitHub** | Task 11b + Task 12 (xem §0.2) |
| 3 | **Ảnh chụp dashboard** | Không chụp được trong máy ảo (snap bị chặn); hướng dẫn port forwarding ở `src/app/README.md` |
| 4 | **Slide báo cáo cuối** | Dùng `deliverables/Proposal_Slides.pptx` làm gốc, cập nhật số liệu Task 7–10 |
| 5 | **Mục 5 Final Report** | Mỗi thành viên tự viết review + ảnh nhóm |
| 6 | **Rà WBS** | Cập nhật trạng thái thật trước khi nộp |

---

## 1. Chương trình thử nghiệm mô hình — nói gì khi báo cáo

### 1.1 Nó là gì

`src/app/model_trial.py` là **chương trình thử nghiệm mô hình** (prototype), tách khỏi
app hoàn chỉnh. Nó chạy **một lệnh**, không cần Kafka, không cần Streamlit, chỉ cần
model đã lưu trong `outputs/models/`. Đường đi đúng như hệ thống thật:

```
văn bản thô → clean_text() (dùng chung với lúc huấn luyện + streaming)
            → PipelineModel.transform()
            → nhãn (negative / neutral / positive) + xác suất từng lớp
```

### 1.2 Ba chế độ

```bash
# 1) Tương tác — nhập từng bình luận, gõ :q để thoát, :sample lấy ví dụ
bash scripts/run_model_trial.sh

# 2) Chấm điểm vài câu / file
bash scripts/run_model_trial.sh --examples
bash scripts/run_model_trial.sh --text "not bad at all actually, quite enjoyable"
bash scripts/run_model_trial.sh --file comments.txt

# 3) Đo trên mẫu tập test (có nhãn thật) + sinh báo cáo
bash scripts/run_model_trial.sh --test-sample 200
```

Chế độ 3 ghi ra:

| File | Nội dung |
|---|---|
| `outputs/model_trial_report.md` | Báo cáo tiếng Anh: chỉ số, P/R/F1 từng lớp, confusion matrix, ví dụ, **5 cảnh báo phải đọc** |
| `outputs/tables/model_trial_predictions.csv` | Từng dòng: nhãn thật, nhãn đoán, 3 xác suất, đúng/sai |
| `outputs/tables/model_trial_summary.csv` | Mỗi lần chạy một dòng — lịch sử kiểm chứng |

### 1.3 Kết quả chạy thật ngày 19/10/2026

Lấy **200 dòng tất định** (sắp theo `crc32(comment_id)`) từ tập test:

| Chỉ số | Trên mẫu 200 dòng | Trên **toàn tập test 27.792 dòng** (số chính thức) |
|---|---:|---:|
| Accuracy | 0,7200 | **0,7018** |
| Macro-F1 | 0,6317 | **0,6233** |
| Weighted-F1 | 0,7380 | **0,7213** |
| F1 negative | 0,6847 | **0,6723** |
| F1 neutral | 0,3750 | **0,3783** |
| F1 positive | 0,8356 | **0,8193** |

> ⚠️ **Khi báo cáo, dùng cột phải** (toàn tập test, từ `outputs/tables/model_results.csv`
> và `per_class_metrics.csv`). Cột trái chỉ để chứng minh chương trình chạy lại được và
> cho kết quả nhất quán — **không phải** kết quả chính thức. Chạy lại lần hai cho đúng
> cùng chỉ số (đã kiểm): mẫu là tất định.

Ví dụ đáng chú ý khi demo tương tác:

| Câu nhập | Kết quả thật | Điều cần nói |
|---|---|---|
| `it was okay, nothing special. 6/10` | **neutral 99,3 %** | Mô hình đọc **điểm số** `6/10`, không hiểu cảm xúc — đúng phát hiện Task 7 |
| `his "bad acting" had me crying with laughter, absolutely brilliant` | **positive 86,3 %** | Câu mỉa mai này **đoán đúng**; đừng nói "mô hình luôn sai với mỉa mai" |
| `Boring, badly acted, way too long.` | **negative 86,0 %** | Ca dễ, mô hình làm tốt |
| `short` | **không chấm điểm** | Quy tắc DLQ: dưới 20 ký tự → loại, giống hệt streaming |

### 1.4 Nó **không** phải là gì — phải nói rõ

- **Không phải app hoàn chỉnh.** Không có đăng nhập, không có phân quyền, không có quy
  trình xử lý cảnh báo cho moderator, không kết nối API nền tảng livestream.
- **Không phải dữ liệu livestream thật.** Vẫn là review IMDb phát lại; nhãn **suy từ
  rating** 1–10.
- **Không chứng minh** mô hình sẽ đạt macro-F1 0,62 trên bình luận livestream thật.
- **Không dùng** Kafka/Spark Streaming trong chương trình này — đó là phần của Task 8,
  đã kiểm chứng riêng.

### 1.5 Cách định vị trong báo cáo

Nói theo đúng thứ tự này:

1. **Vấn đề:** người làm livestream nhỏ không có đội kiểm duyệt, chat chạy quá nhanh.
2. **Giải pháp:** hệ thống phát hiện sớm **đợt bùng nổ tiêu cực** theo cửa sổ thời gian,
   không phải công cụ bán hàng.
3. **Đã làm được:** pipeline Kafka → Spark Structured Streaming → Spark ML → dashboard,
   chạy end-to-end trên dữ liệu **mô phỏng**; mô hình đạt **macro-F1 0,6233** trên tập test.
4. **Chương trình thử nghiệm:** chứng minh model đã lưu hoạt động trên văn bản mới bằng
   đúng đường đi của hệ thống.
5. **Chưa làm:** app hoàn chỉnh (production), dữ liệu livestream thật, kiểm chứng
   exactly-once. Đây là **future work**, không phải lỗi giấu đi.
6. **Mức trưởng thành:** **TRL 5** — hệ thống tích hợp, kiểm chứng trong môi trường mô phỏng.

---

## 2. Cách kể câu chuyện "Technology for Good"

### 2.1 Đoạn mở đầu tiếng Anh (dùng được trong report/slide)

> Small live-streamers often stream alone, without a moderation team. When a burst of
> harmful or negative comments arrives, the chat moves faster than a person can read;
> the streamer either ignores it or reacts too late, which contributes to stress and
> burnout. Existing moderation tools are built for large platforms and are priced for
> them. This project prototypes a low-cost **early-warning system** that monitors comment
> windows, estimates the share of negative comments, and raises an alert when the share
> crosses a threshold. It is built on Kafka and Spark Structured Streaming and validated
> in a simulated environment with public IMDb reviews (CC0). It is **not** a sales or
> engagement-optimisation tool, and it does **not** target individuals.

### 2.2 Ba điều tuyệt đối tránh

| Tránh | Vì sao |
|---|---|
| "Tăng doanh thu / tăng tương tác / giữ chân người xem" | Bị đọc là công cụ bán hàng — vi phạm Technology for Good |
| Chỉ trình bày Kafka/Spark/F1 | Bị đọc là "chỉ chứng minh kỹ thuật" — cô nói rõ trong Student's Guide |
| Ghép khuôn mặt / danh tính người bình luận | Xâm phạm riêng tư; đề tài chỉ dùng số liệu tổng hợp theo cửa sổ |

### 2.3 Câu nhấn mạnh nên dùng

- "Giá trị của dự án là **an toàn tinh thần**, không phải giải trí."
- "Người hưởng lợi là người làm livestream **không có ngân sách** cho công cụ thương mại."
- "Điểm mới là **cảnh báo theo cửa sổ trượt** và **đo độ trễ phát hiện**, không phải
  phân loại từng bình luận rời rạc."

---

## 3. Bản đồ số liệu → từng mục của Final Report

Template Final Report nằm ở `templates/SIC_Big Data_Capstone Project_Final Report.docx`
(**không sửa file trong `templates/`**; copy sang `deliverables/` rồi điền).

> Quy tắc: mỗi con số dưới đây **chỉ được lấy từ file ghi ở cột nguồn**. Không chép số
> từ slide cũ hay từ trí nhớ.

### 3.1 Mục 1 — Introduction

| Mục | Nội dung | Nguồn |
|---|---|---|
| 1.1 Background Information | Vấn đề streamer nhỏ + bùng nổ bình luận tiêu cực; công cụ hiện có đắt/cho nền tảng lớn | `docs/topic_decision.md` §1 Cách A |
| 1.2 Motivation and Objective | Mục tiêu: cảnh báo sớm theo cửa sổ; **không** tối ưu doanh thu | `docs/topic_decision.md`, §2.1 ở trên |
| 1.3 Members and Role Assignments | 5 thành viên + vai trò | `CLAUDE.md` §0, WBS |
| 1.4 Schedule and Milestones | Tóm tắt D1–D20 + trạng thái thật | `deliverables/WBS.xlsx`, `REQUIREMENTS.md` §2 |

### 3.2 Mục 2 — Project Execution

| Mục | Nội dung | Số liệu / nguồn |
|---|---|---|
| 2.1 Simulated Scenario | Kafka replay review IMDb; **nói rõ không phải livestream thật**; producer gửi `comment_id`, `stream_id`, `user_hash`, `text`, `event_ts`; **không nhãn trong message** | `src/producer/replay_producer.py`, `docs/topic_decision.md`, `outputs/streaming_summary.md` §2 |
| 2.2 Datasets | IMDb Review Dataset - ebD, **CC0**; nguồn **1.010.293** review; dùng tập con **201.074** (19,9 %) ở Task 6/7; nhãn suy từ rating (1–4 / 5–6 / 7–10); chia **129.701 / 27.793 / 27.792** theo nhóm phim | `data/raw/SOURCE.md`, `docs/data_dictionary.md` §3, `outputs/tables/class_distribution.csv` |
| 2.3 Data Ingestion | Kafka 4.3.1 KRaft, 3 topic (`comments_raw` 3 partition, `comments_scored` 3, `comments_dlq` 1); producer băm có muối; kiểm chứng **1.000 gửi → 1.000 nhận, 0 lỗi** | `outputs/tables/ingestion_report.csv`, `logs/task5_1000msg_*.log` |
| 2.4 Data Transformation | Structured Streaming, **6 query**, schema tường minh, `clean_text()` dùng chung, watermark **2 phút**, cửa sổ **1 phút** + trượt **10 s/slide 5 s**, DLQ 6 nhánh lý do | `src/streaming/stream_job.py`, `outputs/streaming_summary.md` §2–§6 |
| 2.5 Data Query and Insight | **13 truy vấn Spark SQL**; 9 hình PNG + 1 HTML; insight sinh tự động | `src/eda/sql/q00–q12_*.sql`, `outputs/insights.md`, `outputs/figures/06–15_*` |

**Con số kiểm chứng end-to-end của 2.4** (lần chạy `verify1`, 15/10/2026):

| Câu hỏi | Kết quả đo |
|---|---|
| Đã gửi | **1.024** bản ghi (1.000 replay + 14 kiểm chứng + 10 ca lỗi) |
| Đã chấm điểm + vào DLQ | **1.014 + 10 = 1.024** (khớp tuyệt đối) |
| Message Kafka | `comments_scored` +1.014, `comments_dlq` +10 (theo chênh lệch offset) |
| Dự đoán streaming vs offline trên đúng 1.000 `comment_id` | **1.000/1.000 giống nhau (100,00 %)** |
| Macro-F1 trên luồng (1.000 dòng) | **0,6311** |
| Watermark có bỏ bản ghi lạc hậu 10 phút? | **Có** (kiểm bằng đối chiếu dữ liệu) |
| Exactly-once? | **Chưa kiểm chứng** — chỉ nói **at-least-once** cho phần đã đo |

Nguồn: `outputs/streaming_summary.md` §1–§7, `outputs/tables/stream_verification.csv`,
`outputs/stream/verify1/verification.json`.

### 3.3 Mục 3 — Results

| Mục | Nội dung | Số liệu / nguồn |
|---|---|---|
| 3.1 Ingestion Scripts and Code | Producer, consumer kiểm thử, script Kafka | `src/producer/`, `kafka/`, `scripts/run_demo.sh` |
| 3.2 Transformation Scripts and Code | Làm sạch, chuẩn bị dữ liệu, huấn luyện, streaming, **model trial** | `src/common/text_cleaning.py`, `src/training/`, `src/streaming/`, `src/app/model_trial.py` |
| 3.3 Transformed Datasets | Schema 9 cột của train/val/test; `eval_labels` tách riêng; bảng Parquet của streaming | `docs/data_dictionary.md`, `outputs/tables/stream_sample_rows.csv`, `outputs/tables/stream_dlq_rows.csv` |
| 3.4 Visualization | 15 hình + 1 biểu đồ tương tác | `outputs/figures/`, `outputs/insights.md` |

**Số liệu mô hình chính thức** (dùng ở 3.2 và 4.1):

| Chỉ số | Giá trị | File |
|---|---:|---|
| Accuracy (test) | **0,7018** | `outputs/tables/model_results.csv` |
| Macro-F1 (test) | **0,6233** | `outputs/tables/model_results.csv` |
| Weighted-F1 (test) | **0,7213** | `outputs/tables/model_results.csv` |
| Baseline đa số — macro-F1 | 0,2528 | `outputs/tables/model_results.csv` |
| F1 negative / neutral / positive | **0,6723 / 0,3783 / 0,8193** | `outputs/tables/per_class_metrics.csv` |
| Số văn bản trùng giữa các tập | **0 / 0 / 0** | `outputs/tables/leak_check.json` |
| Thời gian học LR | 245 s | `outputs/tables/model_results.csv` |
| Dự đoán | 0,92–1,73 s / 10.000 bình luận | `outputs/tables/model_results.csv` |

**Điểm yếu phải nói thẳng:**

- `neutral` F1 chỉ **0,3783**; 25 % bình luận neutral bị đoán sang negative, 25 % sang
  positive — do nhãn suy từ rating 5–6 vốn nhiễu.
- Trong **top 20 từ của cả ba lớp đều có token điểm số tự ghi**: `6/10`, `5/10` nằm
  trong top 6 của neutral; `7/10` đứng **đầu** positive; `4/10` ở top 10 negative —
  mô hình có thể đang đọc con số thay vì hiểu cảm xúc (`outputs/tables/top_features.csv`).
- **11.427 người dùng** xuất hiện ở >1 tập là rủi ro rò rỉ **còn lại** (đã đo, chưa xử lý).

### 3.4 Mục 4 — Projected Impact

| Mục | Nội dung | Nguồn |
|---|---|---|
| 4.1 Accomplishments and Benefits | Pipeline end-to-end chạy được; 1.024 = 1.014 + 10; macro-F1 0,6233; cảnh báo theo cửa sổ; dashboard 3 tab; chi phí thấp | `outputs/modeling_summary.md`, `outputs/streaming_summary.md`, `outputs/insights.md` |
| 4.2 Future Improvements | Dữ liệu livestream thật + 200–300 bình luận gán tay; cải thiện neutral; kiểm chứng exactly-once/crash; **app production** (đăng nhập, quy trình moderator, API nền tảng, monitoring); kiểm định ý nghĩa thống kê | `PROGRESS.md` mục "Việc còn lại", §5 dưới đây |

### 3.5 Mục 5–6

- **Mục 5:** mỗi thành viên viết review/comment + ảnh nhóm.
- **Mục 6:** **để trống** cho giảng viên (IDEA /10, APPLICATION /30, RESULT /30,
  PROJECT MANAGEMENT /10, PRESENTATION & REPORT /20, TOTAL /100).

---

## 4. Kịch bản trình bày 5 phút (dùng chương trình thử nghiệm)

> Mục tiêu: hội đồng thấy **vấn đề → kiến trúc → kết quả đo → hạn chế**, không sa vào code.

| Thời lượng | Nói gì | Làm gì trên màn hình |
|---|---|---|
| 0:00–0:45 | Vấn đề streamer nhỏ; công cụ hiện có đắt; mục tiêu cảnh báo sớm **an toàn**, không bán hàng | Slide 1–2 |
| 0:45–1:30 | Kiến trúc: Producer → Kafka → Spark Structured Streaming → Parquet/Kafka → Dashboard; nói rõ **replay** | `outputs/figures/00_pipeline_architecture.png` |
| 1:30–2:30 | **Demo model trial**: nhập `it was okay, nothing special. 6/10` → neutral 99,3 %; giải thích mô hình đọc điểm số | `bash scripts/run_model_trial.sh` (chế độ tương tác) |
| 2:30–3:15 | Đo trên mẫu: **200 dòng → accuracy 0,7200 / macro-F1 0,6317**; nhấn mạnh số chính thức trên toàn test là **0,7018 / 0,6233** | `bash scripts/run_model_trial.sh --test-sample 200` |
| 3:15–4:00 | Kiểm chứng streaming: **1.024 = 1.014 + 10**; **1.000/1.000 dự đoán giống offline**; watermark bỏ bản ghi muộn | `outputs/streaming_summary.md` |
| 4:00–4:40 | Hạn chế: neutral F1 0,3783; nhãn suy từ rating; replay ≠ livestream; exactly-once chưa kiểm chứng; **app hoàn chỉnh là future work**; TRL 5 | Slide hạn chế |
| 4:40–5:00 | Kết luận: prototype chứng minh được kiến trúc + mô hình; bước tiếp theo là dữ liệu thật và app production | Slide kết luận |

**Mẹo an toàn khi demo:**

- Chạy trước một lần để Spark khởi động xong; lần đầu có thể chậm ~10–15 s.
- Nếu Spark/HDFS có sự cố, **vẫn còn** `outputs/model_trial_report.md` và các bảng CSV
  để trình bày — không phụ thuộc vào việc chạy live thành công.
- Không mở dashboard trong lúc chạy model trial trên máy ảo 7 GB RAM nếu không cần;
  dashboard không dùng Spark nhưng trình duyệt + Spark cùng lúc có thể chậm.

---

## 5. Được nói / Không được nói

| ✅ Được nói (có bằng chứng) | ❌ Không được nói |
|---|---|
| "Mô hình đạt **macro-F1 0,6233** trên **tập test IMDb** 27.792 dòng." | "Mô hình đạt 62 % trên **bình luận livestream thật**." |
| "Hệ thống chạy end-to-end trên **dữ liệu replay**." | "Hệ thống đang chạy **live** trên nền tảng." |
| "Nhãn được **suy từ rating** IMDb (1–4 / 5–6 / 7–10)." | "Nhãn cảm xúc do **người gán**." |
| "Đã kiểm chứng **at-least-once** cho phần chạy liên tục." | "Hệ thống bảo đảm **exactly-once**." |
| "Mức trưởng thành **TRL 5** — kiểm chứng trong môi trường mô phỏng." | "TRL 6/7/8" hoặc "sẵn sàng triển khai". |
| "`neutral` là điểm yếu: **F1 0,3783**." | "Mô hình hoạt động tốt ở cả 3 lớp." |
| "Đã đo **1.000/1.000** dự đoán streaming giống offline." | "Đã kiểm chứng mọi trường hợp lỗi/crash." |
| "Mẫu 200 dòng cho **0,6317** — chỉ để kiểm tra chương trình chạy lại được." | "Kết quả chính thức là 0,6317." |
| "Chương trình thử nghiệm **không cần Kafka/Streamlit**." | "Đây là **app hoàn chỉnh**." |

**Câu chốt an toàn khi bị hỏi ngoài phạm vi:**

> "Phần đó chưa được kiểm chứng trong dự án này. Chúng em chỉ báo cáo những gì đã đo;
> nếu cần, đây là hướng kiểm chứng tiếp theo."

---

## 6. Q&A dự kiến

**1. Vì sao `neutral` thấp như vậy?**
Nhãn neutral là rating 5–6, trộn "khen nhẹ" và "chê nhẹ"; trong 3.853 mẫu neutral, chỉ 50 %
được đoán đúng, 25 % sang negative và 25 % sang positive — sai cả hai phía, đúng dấu hiệu
nhiễu nhãn. Đây là hạn chế của **nhãn suy từ rating**, không chỉ của mô hình.

**2. Vì sao dùng accuracy 70 % mà không phải 95 %?**
Vì dữ liệu mất cân bằng: đoán bừa "positive" đã đúng 61 %. Vì vậy nhóm báo cáo **macro-F1**
(0,6233) và F1 từng lớp, không dùng accuracy một mình. Baseline đa số chỉ đạt macro-F1 0,2528.

**3. Đây có phải dữ liệu livestream thật không?**
Không. Toàn bộ luồng là **replay review IMDb** qua Kafka. Nhóm nói rõ trong mọi tài liệu;
đây là lý do dự án dừng ở **TRL 5** (môi trường mô phỏng), không phải TRL 6.

**4. Làm sao biết streaming cho cùng kết quả với lúc huấn luyện?**
Chạy lại chính `PipelineModel` offline trên **đúng 1.000 `comment_id`** đã phát: **1.000/1.000
dự đoán trùng nhau (100,00 %)**. Chênh lệch macro-F1 0,6311 vs 0,6233 là do **mẫu** 1.000 dòng
(3,6 % tập test), chưa kiểm định ý nghĩa thống kê.

**5. Có bảo đảm exactly-once không?**
Không dám khẳng định. Những gì đã đo: chạy liên tục không mất/không trùng, dừng êm 2 lần,
checkpoint riêng từng query, chạy lại cùng `--run-name` tiếp tục từ offset đã commit.
**Chưa** bơm lỗi (kill giữa batch, broker chết) để đếm bản ghi trùng.

**6. Vì sao dùng Spark ML mà không dùng BERT/PhoBERT?**
Ràng buộc môi trường (máy ảo 7 GB RAM, 4 nhân, Spark 3.5.9) và mục tiêu của khóa là pipeline
Big Data. TF-IDF + Logistic Regression có thể giải thích được (xem từ đóng góp trong dashboard),
huấn luyện 245 s, dự đoán ~1 s/10.000 bình luận. BERT là **future work** khi có GPU/dữ liệu thật.

**7. Vì sao chọn IMDb?**
Giấy phép **CC0**, 1.010.293 review, tiếng Anh, có rating để suy nhãn. Hạn chế: miền dữ liệu
là **review phim**, không phải chat livestream → **domain shift**; nhóm nói rõ và không hứa
macro-F1 0,62 cho dữ liệu thật.

**8. Quyền riêng tư xử lý thế nào?**
Mã người dùng băm **có muối** (`COMMENT_HASH_SALT` từ biến môi trường); mặc định **không lưu
văn bản** trong bảng streaming (`keep_text: false`); dashboard chỉ hiện số liệu tổng hợp, che
từ nhạy cảm/email/số điện thoại, không hiện `user_hash`. Không thu dữ liệu thật.

**9. Điểm mới so với các case đã biết là gì?**
Không phải phân loại từng bình luận, mà **cảnh báo theo cửa sổ trượt** (10 s/slide 5 s),
kèm **độ trễ phát hiện** như một chỉ số đánh giá, trên thiết bị phổ thông — hướng tới người
làm livestream nhỏ không có ngân sách.

**10. Nếu có thêm một tháng thì làm gì?**
(1) Thu 200–300 bình luận livestream thật, gán tay, đo lại; (2) cải thiện neutral bằng nhãn
tay/active learning; (3) kiểm chứng exactly-once và crash; (4) xây app production: đăng nhập,
quy trình moderator, API nền tảng, monitoring; (5) kiểm định ý nghĩa thống kê giữa các mô hình.

**11. Vì sao chương trình demo không dùng Kafka?**
Vì mục đích của nó là kiểm tra **mô hình** trên văn bản mới, không phải kiểm tra hạ tầng.
Phần Kafka/Streaming đã được kiểm chứng riêng ở Task 8 với 1.024 bản ghi. Tách ra giúp demo
chạy được cả khi Kafka/HDFS tắt.

**12. Vì sao giữ mô hình cũ (20 % dữ liệu) thay vì huấn luyện lại 64 %?**
Vì mô hình đã được đánh giá **một lần** trên tập test và các số liệu báo cáo gắn với nó.
Huấn luyện lại 64 % sẽ tạo **tập test khác** (~89.000 dòng), không so sánh trực tiếp được với
macro-F1 0,6233. Nhóm đã có tài liệu `docs/huong_dan_huan_luyen.docx` để tự chạy lại nếu cần.

---

## 7. Checklist trước khi nộp

- [ ] **Push GitHub** Task 11b + Task 12 (`ssh-add ~/.ssh/id_rsa && git push origin main`)
- [ ] Chạy `bash scripts/run_model_trial.sh --test-sample 200` một lần cuối, giữ
      `outputs/model_trial_report.md` làm bằng chứng
- [ ] Chụp ảnh dashboard từ máy thật (port forwarding 8501 — xem `src/app/README.md`)
- [ ] Copy template Final Report sang `deliverables/` rồi điền theo bản đồ §3
- [ ] Cập nhật slide cuối bằng số Task 7–10 (không dùng số cũ trong slide đề xuất)
- [ ] Kiểm tra lại **từng con số** trong report/slide đối chiếu file nguồn
- [ ] Mục 5: review từng thành viên + ảnh nhóm; Mục 6 để trống
- [ ] Rà WBS, cập nhật trạng thái thật
- [ ] Tập nói 5 phút, thử demo một lần trước buổi báo cáo

---

## 8. Phụ lục — lệnh nhanh

```bash
# Trạng thái git / GitHub
git log --oneline -5
git status
git push origin main            # sau khi ssh-add ~/.ssh/id_rsa

# Chương trình thử nghiệm mô hình
bash scripts/run_model_trial.sh --examples
bash scripts/run_model_trial.sh --test-sample 200
cat outputs/model_trial_report.md

# Kiểm tra model bằng script cũ (5 câu cố định)
source scripts/env.sh
PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \
  --driver-memory 2g --master 'local[2]' scripts/check_model.py

# Chạy toàn bộ test (cần HDFS bật cho các test Spark)
/usr/local/hadoop/sbin/start-dfs.sh && hdfs dfsadmin -safemode wait
.venv/bin/python -m pytest tests/ -q
/usr/local/hadoop/sbin/stop-dfs.sh

# Số liệu chính thức
head -n 4 outputs/tables/model_results.csv
grep '^LogisticRegression,test' outputs/tables/per_class_metrics.csv
sed -n '1,40p' outputs/streaming_summary.md
```
