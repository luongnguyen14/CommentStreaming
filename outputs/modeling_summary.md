# outputs/modeling_summary.md — Tóm tắt huấn luyện & đánh giá (Task 7)

Viết ngày **15/10/2026**. **Mọi con số dưới đây lấy từ file thật trong `outputs/`**
(`tables/model_results.csv`, `per_class_metrics.csv`, `confusion_matrix.csv`,
`top_features.csv`, `error_analysis.csv`, `test_eval_log.csv`, `leak_check.json`).
Tập test được dùng **đúng một lần** lúc 00:05:02 ngày 15/10/2026 (đã ghi log).

---

## 1. Kết luận ngắn

**Mô hình tốt nhất: Logistic Regression (multinomial, L2, `regParam=0.1`, 1-gram,
TF-IDF 20.000 đặc trưng, có trọng số lớp).**

| Chỉ số | Validation (27.793 dòng) | Test (27.792 dòng) |
|---|---|---|
| Accuracy | 0,7063 | 0,7018 |
| Weighted F1 | 0,7241 | 0,7213 |
| **Macro-F1** | **0,6291** | **0,6233** |

Với bối cảnh: **baseline đa số** (luôn đoán "positive") chỉ đạt accuracy 0,6108 /
macro-F1 0,2528. Như vậy mô hình **gấp ~2,5 lần baseline về macro-F1** nhưng **vẫn
còn xa mức "giải được bài toán"**: 30% bình luận bị đoán sai.

> Đây là **kết quả thật, không tô hồng**. Mức macro-F1 ~0,62 là hợp lý cho bài toán
> này vì (a) nhãn **suy từ rating 1–10** chứ không phải nhãn cảm xúc thật, (b) lớp
> `neutral` (rating 5–6) trộn lẫn "khen nhẹ" và "chê nhẹ" — xem §5.

## 2. So sánh 5 mô hình trên tập validation (KHÔNG dùng test để chọn)

| Mô hình | Acc | Weighted F1 | **Macro-F1** | Đặc trưng | Thời gian học | Dự đoán / 10.000 bình luận |
|---|---|---|---|---|---|---|
| MajorityBaseline | 0,6107 | 0,4631 | 0,2528 | 0 | 0 s | 0,00 s |
| **LogisticRegression** | **0,7063** | **0,7241** | **0,6291** | 20.000 | 245 s | 0,92 s |
| LinearSVC (One-vs-Rest) | 0,7000 | 0,7172 | 0,6218 | 20.000 | 116 s | 1,73 s |
| NaiveBayes | 0,6743 | 0,7013 | 0,6192 | 20.000 | 108 s | 1,07 s |
| RandomForest | 0,5878 | 0,6131 | 0,5343 | 5.000 | 282 s | 1,01 s |

- Ba mô hình tuyến tính (LR, SVC, NB) **xấp xỉ nhau** (macro-F1 0,619–0,629; chênh
  0,007–0,010). Chênh lệch này **chưa kiểm định ý nghĩa thống kê** — cần kiểm chứng
  nếu muốn khẳng định mô hình này hơn mô hình kia một cách chắc chắn.
- **RandomForest kém nhất** vì (a) chỉ dùng 5.000 đặc trưng (20.000 làm cây chậm
  không đáng), (b) cây chia theo ngưỡng nên kém phù hợp với vector TF-IDF thưa
  20.000 chiều, (c) chỉ 30 cây, sâu tối đa 12.
- Chọn LR (không phải SVC/NB) vì macro-F1 cao nhất **trên validation**, học nhanh,
  dự đoán nhanh và **có xác suất từng lớp** (SVC không có) — tiện cho dashboard.

## 3. Chọn siêu tham số — cách làm

- `TrainValidationSplit` chia **bên trong tập train** (80/20), chọn theo weighted F1,
  rồi **fit lại trên toàn bộ 129.701 dòng train**. Không nhìn validation/test.
- Lưới đã thử (config.yaml `training.grids`): NB 2 tổ hợp (1-gram/2-gram), LR 4
  (1-gram/2-gram × `regParam` 0,01/0,1), SVC 2 (`regParam` 0,01/0,1), RF 2 (độ sâu 8/12).
- **1-gram thắng 2-gram ở mọi mô hình** (LR: 0,1 + 1-gram; NB: 1-gram). 2-gram làm
  tăng số đặc trưng nhưng không giúp — hợp lý vì bình luận IMDb khá dài, 1-gram đã đủ.
- Xử lý mất cân bằng bằng `weightCol`: w = N/(k·n_c) tính **trên tập train**
  → negative 1,330 · neutral 2,404 · positive 0,546.
- Stopword: 162 từ (bộ tiếng Anh của Spark **trừ các từ phủ định** `not/no/never/n't...`
  — bỏ chúng là mất tín hiệu "not good"). Dữ liệu là tiếng Anh nên **không dùng**
  tách từ tiếng Việt (underthesea/pyvi); nếu đổi sang dữ liệu tiếng Việt thì phải thêm
  và **đo lại chi phí `pandas_udf`** (hiện chưa đo — cần kiểm chứng).

## 4. Kết quả theo từng lớp (test, Logistic Regression)

| Lớp | Precision | Recall | F1 | Số mẫu | Tỷ lệ |
|---|---|---|---|---|---|
| negative | 0,6807 | 0,6642 | 0,6723 | 6.965 | 25,06% |
| **neutral** | **0,3036** | **0,5019** | **0,3783** | 3.853 | 13,86% |
| positive | 0,8851 | 0,7626 | 0,8193 | 16.974 | 61,08% |

Confusion matrix (test, hàng = nhãn thật): xem `tables/confusion_matrix.csv`.

- **`neutral` là điểm yếu rõ rệt** (F1 0,38). Nhìn ma trận nhầm lẫn: trong 3.853
  bình luận nhãn `neutral`, chỉ 50% được đoán đúng; 25% rơi sang `negative`, 25%
  sang `positive` — **sai về cả hai phía**, đúng như dự đoán về nhiễu nhãn.
- `positive` đoán khá tốt (F1 0,82) nhưng còn bỏ sót 17% (2.812 bình luận positive
  bị đoán thành neutral).
- Accuracy 0,7018 **không nên** dùng một mình để báo cáo: nó bị chi phối bởi lớp
  positive (61% dữ liệu) trong khi lớp neutral gần như không giải được.

## 5. ⚠️ Phát hiện quan trọng: mô hình "học" luôn cả điểm số trong văn bản

20 từ có trọng số lớn nhất mỗi lớp (`tables/top_features.csv`, hình `04_top_features.png`):

| Lớp | Vài đặc trưng đứng đầu (trọng số) |
|---|---|
| negative | turnout (5,37) · dir: (5,06) · escapes (4,39) · aimlessly (3,98) · uneventful (3,97) · **4/10 (3,92)** |
| neutral | ****spoilers** (8,74)** · **1/2 (6,04)** · **6/10 (5,62)** · **5/10 (5,62)** · ensue (4,89) · adrift (4,05) |
| positive | **7/10 (6,50)** · andrei (5,00) · **8/10 (4,74)** · satisfying (4,56) · adept (4,35) · well-directed (4,14) |

Đặc trưng mạnh nhất của lớp `neutral` **không phải từ ngữ cảm xúc** mà là **chính
điểm số người viết tự ghi trong bình luận** ("5/10", "6/10", "**1/2"). Điều này
**hợp lý về mặt dữ liệu** (nhãn được suy từ rating, mà người viết thường ghi lại
điểm đó trong bài), nhưng có **hai hệ quả phải nói rõ**:

1. Một phần độ chính xác đến từ việc **đọc lại con số** chứ không phải hiểu cảm xúc.
2. Khi chạy thật trên bình luận livestream (Task 8), **bình luận hiếm khi ghi "6/10"**
   → mô hình có thể **kém hơn con số 0,62** này. Đây là **giới hạn đã biết**, cần
   nêu trong báo cáo cuối, không được coi 0,62 là năng lực "hiểu cảm xúc".

Ngoài ra, do tách từ đơn giản theo khoảng trắng, dấu câu dính vào từ
("melodramatic,", "satisfying.") và một số đặc trưng là **tên riêng/tên phim**
(adams, andrei) — dấu hiệu mô hình còn dựa vào chủ đề, không chỉ cảm xúc.

## 6. Phân tích lỗi (30 bình luận đoán sai — `tables/error_analysis.csv`)

Cách lấy: 30 dòng sai đầu tiên theo thứ tự tất định (crc32 của `comment_id`), **đã ẩn
danh** (không có `user_hash`, không có tên người viết).

**Nhóm tự động (quy tắc trong code, tái lập được)** — hình `05_error_reasons.png`:

| Nhóm | Số dòng |
|---|---|
| phủ định (not/never…) | 14 |
| nhãn neutral nhiễu (suy từ rating 5–6) | 10 |
| khác (cần đọc tay) | 5 |
| quá ngắn, ít thông tin | 1 |

**Đọc tay cả 30 dòng** (phân tích của nhóm, có thể trùng nhóm):

| Nguyên nhân thật | Số dòng | Ví dụ thật (rút ngắn) |
|---|---|---|
| Ý trái chiều trong cùng bình luận (khen + chê) | ~9 | "the acting is good. the story is very much lacking" |
| Tóm tắt cốt truyện, gần như không nêu ý kiến | ~6 | đoạn tóm tắt phim dài, giọng trung tính |
| Mỉa mai / khen bằng từ ngữ tiêu cực | ~5 | "his 'bad acting' … had me crying" (thật ra là khen) |
| Phủ định & thành ngữ | ~5 | "i have never laughed more than this.. 10/10" |
| Nhãn không khớp văn bản | ~3 | văn bản rõ tiêu cực nhưng nhãn `neutral` (rating 5–6) |
| Bình luận dạng bảng điểm số ("1. animation: 4 out of 5…") | 2 | — |
| Quá ngắn / thiếu ngữ cảnh | 1 | "it is a painful lifetime punishment hating someone you should love instead." |

- Trong 30 lỗi, **10 dòng có nhãn thật là `neutral`** — đúng như kết luận §4.
- Xác suất mô hình gán cho **lớp đúng** ở 30 lỗi: trung bình **0,255**, cao nhất
  0,47; chỉ 3/30 dòng vượt 0,40. Nghĩa là: khi sai, mô hình **thường sai khá "tự
  tin"** (không phải lưỡng lự giữa hai lớp), chứ không phải "suýt đúng".
  *(Lưu ý toán học: với mọi dòng bị đoán sai, xác suất lớp đúng luôn ≤ 0,5 — nên chỉ
  so sánh mức 0,26 với mốc 0,5, không so với 1,0.)*
- Kiểm tra nhanh bằng mắt trên 5 câu tự viết (`logs/task7_check_model.log`):
  "not bad at all actually, quite enjoyable" bị đoán **neutral 0,80** — đúng kiểu lỗi
  phủ định ở trên; "it was okay, nothing special. 6/10" được **neutral 0,99** — đúng
  kiểu "đọc con số" ở §5.

## 7. Kiểm tra rò rỉ (task 7.6)

| Phép kiểm tra | Kết quả |
|---|---|
| Trùng văn bản (sau chuẩn hóa, `dedup_key`) train↔val / train↔test / val↔test | **0 / 0 / 0** (`tables/leak_check.json`) |
| Macro-F1 test so với ngưỡng cảnh báo 0,95 (`training.leakage_threshold_macro_f1`) | 0,6233 — **không có dấu hiệu rò rỉ** |
| Nhật ký số lần chạm tập test | 1 lần (`tables/test_eval_log.csv`) |

Vì `prepare.py` đã loại trùng 3 mức **trước khi chia** và chia theo **nhóm phim**,
con số 0 ở trên là đúng kỳ vọng. Chỉ số 0,62 cũng nằm trong khoảng bình thường của
bài toán (bình luận dài, nhiều nhiễu), **không** phải mức "quá cao" cần dừng lại.

## 8. Hạn chế & việc cần kiểm chứng

1. **Nhãn không phải nhãn cảm xúc thật** — suy từ rating 1–10 (quy ước của nhóm).
   Lớp `neutral` F1 0,38 phần lớn là do **nhiễu nhãn**, không hẳn do mô hình kém.
2. **Đặc trưng điểm số ("6/10")** — xem §5: kết quả trên dữ liệu livestream (không
   có điểm số) **có thể thấp hơn** mức 0,62 này. Cần đo lại khi chạy Task 8.
3. **Chưa kiểm định ý nghĩa thống kê** cho chênh lệch giữa LR / SVC / NB.
4. **Chưa thử mô hình ngôn ngữ** (embeddings, transformer) — ngoài phạm vi Spark ML
   của đề tài; nếu làm sẽ phải so lại với mức 0,6233 này.
5. **Chưa dùng 2-gram cho lớp neutral** một cách riêng biệt (lưới chung cho cả 3 lớp).
6. Thời gian dự đoán đo trên máy ảo 4 nhân chạy `local[2]`, **không** phải môi trường
   sản xuất — chỉ dùng để so sánh giữa các mô hình.

## 9. File sinh ra ở Task 7

| File | Nội dung |
|---|---|
| `src/training/train.py` | Script huấn luyện + đánh giá + vẽ hình (chạy lại được) |
| `outputs/models/sentiment_pipeline/` | PipelineModel tốt nhất (904 KB) |
| `outputs/models/sentiment_pipeline_metadata.json` | Ánh xạ nhãn, tham số, phiên bản Spark, kích thước tập, ngày huấn luyện, chỉ số |
| `outputs/tables/model_results.csv` | Chỉ số từng mô hình (val + test) |
| `outputs/tables/per_class_metrics.csv` | P/R/F1 từng lớp |
| `outputs/tables/confusion_matrix.csv` | Ma trận nhầm lẫn (số đếm + tỷ lệ theo hàng) |
| `outputs/tables/top_features.csv` | 20 từ trọng số lớn nhất mỗi lớp |
| `outputs/tables/error_analysis.csv` | 30 lỗi + nhóm nguyên nhân + văn bản (ẩn danh) |
| `outputs/tables/leak_check.json`, `test_eval_log.csv` | Kiểm tra rò rỉ + nhật ký dùng tập test |
| `outputs/figures/01…05_*.png` | Ma trận nhầm lẫn, P/R/F1 từng lớp, so sánh mô hình, từ khóa, nguyên nhân lỗi |
| `logs/task7_train_full.log`, `logs/task7_check_model.log` | Log chạy thật |

**Chạy lại:**

```bash
source scripts/env.sh
# chạy thử (không chạm tập test)
PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \
    --driver-memory 2g --master 'local[2]' src/training/train.py --sample 20000
# bản đầy đủ (đánh giá test 1 lần, lưu mô hình)
... src/training/train.py
# vẽ lại hình từ bảng đã lưu (không huấn luyện lại)
$VENV_PY src/training/train.py --figures-only
# kiểm chứng mô hình đã lưu (đường đi của Task 8)
PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \
    --driver-memory 2g --master 'local[2]' scripts/check_model.py
```
