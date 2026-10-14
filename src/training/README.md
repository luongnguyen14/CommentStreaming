# src/training — Chuẩn bị dữ liệu và huấn luyện

- `prepare.py` — nạp dữ liệu thô, chuyển sang JSONL (**tập con ~200 MB**), chuẩn hóa
  nhãn 3 lớp từ `rating`, làm sạch bằng hàm dùng chung, **loại trùng (kể cả gần trùng)**,
  rồi mới chia train/val/test; ghi parquet + nhãn test + các bảng thống kê (Task 6)
- `train.py` — Spark ML Pipeline (RegexTokenizer -> StopWordsRemover -> n-gram ->
  CountVectorizer -> IDF -> classifier) *(Task 7)*

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
| `--sample N` | dùng ~N bản ghi (chạy thử); bỏ trống = dùng cả tập con trong `prepare.subsample_mod` |
| `--method` | ghi đè `split.method` (`group_movie_balanced` hoặc `stratified`) |
| `--config`, `--seed` | như tên gọi (mặc định `config.yaml`, seed 42) |

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
