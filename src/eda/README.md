# src/eda — Truy vấn, insight và trực quan hóa (Task 9, Day 9–10)

Hai bước tách rời, chạy độc lập:

| File | Việc | Ra |
|---|---|---|
| `queries.py` | Chạy 13 truy vấn **Spark SQL** trên Parquet dữ liệu huấn luyện + đầu ra streaming | `outputs/tables/eda_*.csv` |
| `plots.py` | Đọc lại chính các CSV đó, vẽ hình (không cần Spark) rồi **sinh** `outputs/insights.md` | `outputs/figures/06_…15_`, `outputs/tables/eda_model_quality.csv` |
| `sql/` | 13 file `.sql` nguyên văn để đưa vào báo cáo | — |

Tách hai bước để **sửa hình không phải chạy lại Spark**, và để mọi con số trên hình
truy vết được về một file CSV thật (CLAUDE.md §9).

> ⚠️ Biểu đồ: tiêu đề rõ, nhãn trục có đơn vị, chữ tiếng Anh, PNG 200 dpi, đánh số `06_`…
> `outputs/insights.md` được **sinh tự động** từ số đo — không sửa tay file đó;
> muốn đổi câu chữ thì sửa `plots.py` rồi chạy lại.

## Chạy lại từ đầu

```bash
source scripts/env.sh          # đặt VENV_PY, PYSPARK_PYTHON... (bắt buộc, nếu không pytest/spark lệch Python)

# 0) Phải có đầu ra streaming của Task 8 (đọc eda.streaming_run trong config.yaml)
$VENV_PY src/eda/queries.py --dry-run --check      # kiểm tra tham số + SQL, không cần Spark
$VENV_PY src/eda/queries.py --only class_distribution   # chạy thử 1 truy vấn
PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY \
  spark-submit --driver-memory 4g --master 'local[2]' src/eda/queries.py   # bản đầy đủ (~4 phút)

# 1) Vẽ hình + sinh insights (không cần Spark, ~5 giây)
$VENV_PY src/eda/plots.py
$VENV_PY src/eda/plots.py --only 12        # vẽ lại 1 hình (KHÔNG ghi đè insights.md)
```

`queries.py --sample N` ghi ra `*_sample.csv` để không ai nhầm số liệu chạy thử với
số liệu báo cáo; **xóa các file `*_sample.csv` sau khi thử.**

## Bảng tạm (temp view) mà SQL dùng

| View | Nguồn |
|---|---|
| `train` / `val` / `test` | `data/processed/*.parquet` |
| `stream_detail` | `outputs/stream/<run>/scored_detail` |
| `window_1min` / `window_sliding_10s` | `outputs/stream/<run>/window_*` |
| `stopwords` | danh sách của `src/training/train.py` (dùng chung, không chép lại) |

## Tham số

Mọi ngưỡng nằm trong `config.yaml` mục `eda` (không hard-code trong SQL):
`streaming_run`, `top_words_n/min_count`, `log_odds_prior`, `emoji_per_class_n`,
`length_bin_width/max`, `latency_bins_per_decade`, `alert.*` (ngưỡng cảnh báo +
số bình luận tối thiểu), `burst.sigma`.

## Vài cái bẫy đã gặp thật (giữ lại để lần sau khỏi mất thời gian)

- **Đường dẫn cục bộ phải có `file://`** — filesystem mặc định của Spark trên máy này là HDFS.
- **Múi giờ**: `spark.sql.session.timeZone=UTC`; máy ở +07 nên không ghim là lệch 7 tiếng.
- **`str.format` không dùng được** cho SQL (có `\x{1F000}`) → dùng chỗ giữ chỗ `{{tên}}`.
- **Chuỗi literal của Spark SQL**: `'don''t'` bị hiểu là phép nối chuỗi → ra `dont`.
  Vì vậy danh sách stopword phải đưa qua **temp view**, không nhúng vào SQL.
- **`\p{So}` bắt cả ký tự typography** (`°` U+00B0, `©`, `™`) → thống kê emoji phải
  lọc thêm dải tường minh `EMOJI_SYMBOL_RANGES` (xem `src/common/text_cleaning.py`).
- **Ô nhiệt hình 09**: cột `emoji_per_1000_comments` của q05 là mật độ của **cả lớp**
  (giống nhau mọi dòng cùng lớp) — muốn biết *emoji nào* đặc trưng cho lớp nào thì
  phải tính `1000 × n_emoji / n_comments_in_class` theo từng emoji.
- **Không nối đường qua chỗ trống**: cửa sổ 1 phút chỉ có 4 điểm, để matplotlib nối
  thẳng sẽ vẽ ra một hình nêm như thể có dữ liệu liên tục 10 phút → phải chèn `NaN`.
- **matplotlib không vẽ được emoji**: font DejaVu Sans thiếu glyph mặt cười (chỉ ra ô
  vuông) → nhãn dùng **tên Unicode tiếng Anh** ("face with tears of joy"), không dùng glyph.
- **`tight_layout` bỏ qua hình nhiều panel dùng chung trục x** (matplotlib 3.11 cảnh báo
  "Axes not compatible") → hình 09/10/14 đặt lề thủ công bằng `subplots_adjust` (`finish(..., manual=...)`).
