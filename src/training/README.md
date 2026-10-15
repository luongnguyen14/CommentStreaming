# src/training — Chuẩn bị dữ liệu và huấn luyện

- `prepare.py` — nạp dữ liệu thô, chuyển sang JSONL (**tập con theo `prepare.subsample_pct`**;
  hiện trên đĩa là tập 20% ~190 MB, config đã đổi sang 64%), chuẩn hóa
  nhãn 3 lớp từ `rating`, làm sạch bằng hàm dùng chung, **loại trùng (kể cả gần trùng)**,
  rồi mới chia train/val/test; ghi parquet + nhãn test + các bảng thống kê (Task 6)
- `train.py` — Spark ML Pipeline (RegexTokenizer -> StopWordsRemover -> NGram ->
  CountVectorizer -> IDF -> Normalizer -> bộ phân loại); huấn luyện 4 mô hình
  (NaiveBayes, LogisticRegression, LinearSVC one-vs-rest, RandomForest) + baseline đa số,
  chọn siêu tham số bằng `TrainValidationSplit` trong tập train, đánh giá trên
  validation, **đánh giá cuối cùng một lần trên test**; xuất hình + bảng + metadata (Task 7)

⚠️ TF-IDF nằm **trong Pipeline** để chỉ fit trên tập train. Tập test **chỉ dùng một lần** ở cuối.
⚠️ Nhãn **không bao giờ** đi vào luồng Kafka — producer chỉ đọc `eval_labels.parquet` khi cần.

## Cách chạy `prepare.py`

```bash
source scripts/env.sh
# chạy thử trước (quy ước CLAUDE.md §3)
PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \
    --driver-memory 2g --master 'local[2]' src/training/prepare.py --sample 20000
# bản đầy đủ
PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \
    --driver-memory 2g --master 'local[2]' src/training/prepare.py
```

| Tham số | Ý nghĩa |
|---|---|
| `--sample N` | dùng ~N bản ghi (chạy thử); bỏ trống = dùng cả tập con trong `prepare.subsample_pct`. ⚠️ Cờ này **vẫn ghi đè** `data/processed/*.parquet` bằng bản N dòng — chạy thử SAU khi chạy đầy đủ sẽ phá tập thật |
| `--method` | ghi đè `split.method` (`group_movie_balanced` hoặc `stratified`) |
| `--config`, `--seed` | như tên gọi (mặc định `config.yaml`, seed 42) |

## Cách chạy `train.py` (Task 7)

```bash
source scripts/env.sh
# chạy thử — TỰ ĐỘNG bỏ qua tập test (--sample luôn kèm --no-test)
PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \
    --driver-memory 2g --master 'local[2]' src/training/train.py --sample 20000
# bản đầy đủ (~13 phút ở 130k dòng): chọn mô hình trên val, đánh giá test MỘT LẦN, lưu model
# ⚠️ với `prepare.subsample_pct: 64` (~415k dòng train) nên nâng lên --driver-memory 4g:
#    log Task 7 cho thấy cache 912 MiB đã KHÔNG vừa ở 130k dòng (70 dòng
#    "Not enough space to cache" rải suốt quá trình huấn luyện, block bị đẩy ra đĩa).
PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \
    --driver-memory 4g --master 'local[2]' src/training/train.py
# vẽ lại hình từ bảng đã lưu (không huấn luyện lại, không chạm test)
$VENV_PY src/training/train.py --figures-only
```

| Tham số | Ý nghĩa |
|---|---|
| `--sample N` | chạy thử ~N dòng train (tất định theo `crc32`); **tự bật `--no-test`** |
| `--models nb,lr,svc,rf` | chọn tập mô hình cần chạy |
| `--no-test` | không đánh giá tập test (dùng khi thử nghiệm) |
| `--figures-only` | chỉ vẽ lại hình từ `outputs/tables/*.csv` |
| `--config`, `--seed` | như tên gọi |

## Những điểm dễ sai khi huấn luyện (Task 7)

1. **`array_position` trong PySpark chỉ nhận giá trị literal**, không nhận Column →
   phải viết biểu thức bằng `F.expr("array_position(...)")` (dùng để lấy argmax của
   `rawPrediction` cho LinearSVC).
2. **`prediction` của `OneVsRest` với LinearSVC**: OneVsRest dùng ngưỡng 0.5 áp lên
   điểm lề (margin) nên không đáng tin. Đã **đo thật**: trên 27.793 dòng val, cách của
   Spark khớp `argmax(rawPrediction)` **100,00%** — nhưng code vẫn dùng argmax tường
   minh để không phụ thuộc vào hành vi ngầm.
3. **Bộ stopword tiếng Anh của Spark chứa `not`, `no`, `never`, `n't`** — bỏ hết là
   mất tín hiệu phủ định; `training.keep_negations: true` giữ chúng lại.
4. **Spark 3.5 không có evaluator macro-F1** cho Python → `TrainValidationSplit` chọn
   theo weighted F1; **macro-F1 được tính riêng từ confusion matrix** và là chỉ số
   dùng để so sánh mô hình trên tập validation.
5. **`vector_to_array` + `element_at`** là cách lấy xác suất của lớp đúng (cột
   `probability` là Vector, không phải mảng).
6. **Chỉ số cao bất thường ⇒ dừng lại**: `training.leakage_threshold_macro_f1: 0.95`
   — vượt ngưỡng thì script **không lưu mô hình**, ghi `outputs/tables/leakage_alert.txt`
   và thoát mã 2.

## Những điểm dễ sai (đã gặp thật khi làm Task 6)

1. **`review_id` KHÔNG duy nhất trong nguồn**: đo trên file gốc — 1.010.293 bản ghi nhưng
   chỉ **994.692 id khác nhau**, tức **15.601 dòng (1,54%) lặp id**, gần như toàn bộ là bản
   sao y hệt. `prepare.py` phải loại trùng theo `comment_id` (giữ bản văn bản dài nhất) —
   vì job streaming và bảng nhãn đánh giá đều nối theo khóa này, id trùng làm phép nối
   nhập nhằng.
2. **HDFS là filesystem mặc định** của Spark ở máy này → mọi đường dẫn cục bộ phải ghi
   `file://`, nếu không Spark đi tìm trên HDFS và báo `PATH_NOT_FOUND`.
3. **`_manifest.json` phải bắt đầu bằng `_`** — file không có tiền tố đó nằm trong thư mục
   JSONL sẽ bị `spark.read.json(dir)` đọc thành một bản ghi rỗng (từng làm Spark đếm thừa 1 dòng).
4. **Chia tập: thiếu hụt phải lấy `argmax`** (chọn tập đang thiếu nhiều nhất), không phải
   `argmin` khoảng cách tới mục tiêu — bản đầu dồn hết dữ liệu vào val/test, train = 0 dòng.
5. **Tham lam chỉ cân theo số lượng**, không sửa được lệch tỷ lệ lớp → thêm bước hoán đổi
   cục bộ (`n_swap_try` lần, tất định): lệch giảm từ 1,64% xuống 0,01% trên bản mẫu.
6. **`--sample` phải lấy mẫu tất định theo `crc32`**, không dùng `sample().limit()` (mẫu dồn về đầu file).
7. `/tmp` là tmpfs ~3,6 GB → `scripts/env.sh` đã trỏ `SPARK_LOCAL_DIRS` sang ổ đĩa thật.
