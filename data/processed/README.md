# data/processed — Dữ liệu đã xử lý

Sinh ra bởi `src/training/prepare.py` (Task 6). Tạo lại được từ `data/raw/` + `config.yaml`,
**không commit lên git** (xem `.gitignore`).

| File / thư mục | Nội dung |
|---|---|
| `imdb_jsonl/part-000.jsonl` | Bản JSONL của nguồn để Spark đọc song song. **Tập con ~190 MB**: 201.074/1.010.293 bản ghi (giữ `crc32(review_id) % 5 == 0`, xem `prepare.subsample_mod`) |
| `imdb_jsonl/_manifest.json` | Nguồn + tham số + số bản ghi để lần chạy sau bỏ qua bước chuyển đổi. **Tên bắt đầu bằng `_`** để Spark không đọc nó thành một bản ghi rỗng |
| `train.parquet`, `val.parquet`, `test.parquet` | Chia cố định 70/15/15 **sau khi loại trùng**, theo nhóm phim (một phim không nằm ở hai tập), seed 42 |
| `eval_labels.parquet` | Nhãn của **tập test** (`comment_id`, `label`, `rating`) — nhãn không bao giờ đi vào luồng Kafka; producer chỉ đọc file này (`--only-test`) |

## Chạy lại từ đầu

```bash
source scripts/env.sh
# chạy thử trước
PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \
    --driver-memory 2g --master 'local[2]' src/training/prepare.py --sample 20000
# bản đầy đủ (tập con ~200 MB)
PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit \
    --driver-memory 2g --master 'local[2]' src/training/prepare.py
```

Xem `docs/data_dictionary.md` để biết ý nghĩa từng cột và lý do cách chia tập không rò rỉ.
