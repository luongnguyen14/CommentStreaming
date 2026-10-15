# Từ điển dữ liệu — Capstone SIC Big Data (Nhóm 6)

> Tài liệu này mô tả **mọi cột** xuất hiện trong dự án: dữ liệu gốc, dữ liệu đã
> xử lý, nhãn đánh giá và các bảng thống kê. Cập nhật lần cuối: **15/10/2026** (Task 9).
>
> ⚠️ Nhắc lại nguyên tắc trung thực (CLAUDE.md §9): mọi con số trong báo cáo phải
> lấy từ file thật trong `outputs/`. Tài liệu này ghi **nguồn của từng con số**,
> không chép số từ trí nhớ.

---

## 1. Dữ liệu gốc — `data/raw/part-01.json`

Một shard của **IMDb Review Dataset - ebD** (giấy phép CC0, xem `data/raw/SOURCE.md`
để có đầy đủ nguồn, checksum, ngày tải). File là **một mảng JSON ~1,1 GB**, mỗi phần
tử là một review:

| Cột | Kiểu | Ý nghĩa | Ghi chú |
|---|---|---|---|
| `review_id` | string | Mã review | ⚠️ **KHÔNG duy nhất trong nguồn**: đo trên cả file có 994.692 id khác nhau / 1.010.293 dòng ⇒ **15.601 dòng (1,54%) lặp id** (gần như toàn bộ là bản sao y hệt). `prepare.py` loại trùng theo `comment_id` trước khi chia tập |
| `reviewer` | string | Mã/tên người viết | **Không đưa vào dữ liệu huấn luyện**; chỉ dùng để băm → `user_hash` |
| `movie` | string | Tên phim | Dùng làm `stream_id` (nhóm "phòng" thay cho livestream) |
| `rating` | **string** (1–10) | Điểm số | ~5–8% bản ghi **thiếu** → những dòng này không có nhãn |
| `review_summary` | string | Tiêu đề ngắn | **Không dùng** (dự án mô phỏng bình luận, không dùng tiêu đề) |
| `review_date` | string | Ngày viết | Giữ lại để tham chiếu; **không** dùng làm event time |
| `spoiler_tag` | string | Có tiết lộ nội dung | **Không dùng** |
| `review_detail` | string | Nội dung review | Nguồn của cột `text` |
| `helpful` | string | Số người thấy hữu ích | **Không dùng** (không có trong bản JSONL) |

**Đã đo lại ngày 14/10/2026:** file có **1.010.293** bản ghi (`grep -o '"review_id"' | wc -l`
= 1.010.293 = số dòng JSONL tạo ra, md5 file không đổi `e723d956b3b4a0dcd3e8d54ec1e9d4ca`).
Con số 1.010.296 ghi trước đó trong `SOURCE.md` là **sai 3 bản ghi** và đã được sửa.

---

## 2. `data/processed/imdb_jsonl/` — bản JSONL để Spark đọc song song

`src/training/prepare.py` chuyển mảng JSON gốc thành **JSONL** (mỗi dòng một object)
vì Spark đọc mảng JSON phải bật `multiLine=true` → dồn hết vào 1 task, rất chậm.

| Mục | Giá trị |
|---|---|
| File | `part-000.jsonl` |
| Số bản ghi | **201.074** / 1.010.293 (giữ **19,9%**) |
| Dung lượng | **~190 MB** (thay vì ~998 MB nếu giữ tất cả) |
| Cách chọn tập con | Giữ bản ghi có `crc32(review_id) % subsample_mod == 0` — bản sinh ra tập đang nằm trên đĩa dùng `subsample_mod: 5`. **Từ 15/10/2026** config đổi sang `prepare.subsample_pct` (dải tiền tố `crc32 % 1000 < pct * 10`) để chọn được mọi mốc phần trăm, xem `keep_record` trong `prepare.py` |
| Vì sao chọn theo `review_id` | **Tất định** (chạy lại ra đúng tập con cũ) và **không lệch theo thứ tự phim** trong file gốc (bộ dữ liệu xếp theo phim; cắt N dòng đầu sẽ chỉ lấy được một số phim) |
| Cột trong mỗi dòng | `review_id`, `reviewer`, `movie`, `rating`, `review_date`, `review_detail` (cắt ở `prepare.truncate_raw_detail` = 20.000 ký tự) |
| `_manifest.json` | Ghi nguồn + kích thước nguồn + tham số + số bản ghi để lần sau **bỏ qua bước chuyển đổi**. Tên **bắt đầu bằng `_`** để Spark bỏ qua khi đọc cả thư mục — đặt tên `manifest.json` sẽ bị đọc thành 1 bản ghi rỗng (đã từng xảy ra: Spark đếm 1.010.294 trong khi file có 1.010.293 dòng) |

> ⚠️ **Đây là tập con do nhóm tự chọn, không phải toàn bộ bộ dữ liệu.** Báo cáo phải
> nói rõ: nhóm dùng 201.074 review (1 shard, lấy mẫu 20%) chứ không phải 5.571.499
> review của bộ Kaggle đầy đủ.

> 📌 **Số liệu ở mục này mô tả tập đang nằm trên đĩa (sinh 14/10/2026 với `subsample_mod: 5`).**
> Config đã đổi sang `prepare.subsample_pct: 64` nhưng **chưa chạy lại** `prepare.py`, nên
> 201.074 vẫn là con số đúng. Chạy lại với 64% **đã đo được** 646.249 bản ghi / 608,8 MB —
> khi đó **mục này phải cập nhật**, cùng `data/processed/README.md` và `src/training/README.md`.
> Kế hoạch huấn luyện lại: `docs/huong_dan_huan_luyen.docx`.

---

## 3. Nhãn — suy từ `rating`, KHÔNG phải nhãn gốc

Bộ dữ liệu **không có nhãn cảm xúc**. Nhóm quy ước ánh xạ 3 lớp từ điểm số
(`config.yaml`, mục `labels.mapping` — dùng chung cho cả `prepare.py` lẫn producer):

| Nhãn | `rating` | Ý nghĩa |
|---|---|---|
| `negative` | 1, 2, 3, 4 | Tiêu cực |
| `neutral` | 5, 6 | Trung tính |
| `positive` | 7, 8, 9, 10 | Tích cực |

Quy ước này **là thiết kế của nhóm** (IMDb không công bố ngưỡng chính thức). Căn cứ:
thang 10 điểm thường được đọc thành 1–4 "chê", 5–6 "trung bình", 7–10 "khen"; dữ liệu
đo được cũng lệch mạnh về phía điểm cao (xem `outputs/tables/class_distribution.csv`).

**Hạn chế phải nói trong báo cáo:**
- Điểm số không đồng nghĩa cảm xúc: một review 8★ vẫn có thể mỉa mai, chê đạo diễn.
  Nhãn ở đây là **"sắc thái theo điểm số"**, không phải cảm xúc được gán nhãn thủ công.
- Lớp `neutral` (5–6) **không** đồng nghĩa văn bản trung tính — nhiều review 5–6★ dùng
  từ ngữ rất mạnh. Vì vậy chỉ số của lớp này sẽ thấp hơn và **không được** đọc là "mô
  hình kém" mà là "nhãn nhiễu" (nói rõ khi báo cáo).
- Bản ghi **thiếu `rating`** (rating NULL hoặc ngoài 1–10) **bị loại** và được đếm ở
  bước `03_thieu_nhan` trong `outputs/tables/cleaning_log.csv`.

---

## 4. `data/processed/train.parquet`, `val.parquet`, `test.parquet`

Ba tập **cố định** (chia một lần, `split.ratios` = 0,70 / 0,15 / 0,15, seed 42).
Cột giống nhau ở cả ba tập:

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `comment_id` | string | `review_id` của bản ghi gốc — khoá nối với nhãn đánh giá và với Kafka |
| `stream_id` | string | Tên phim (đóng vai "phòng/livestream"); **dùng để chia nhóm khi chia tập** |
| `user_hash` | string(16) | `sha256(muối + reviewer)` hex, cắt 16 ký tự đầu. Muối đọc từ biến môi trường `COMMENT_HASH_SALT` — **không** lưu bản gốc người dùng (CLAUDE.md §7). Giá trị **giống hệt** giá trị producer tạo khi replay (có test đối chiếu: `tests/test_utils.py::test_bam_spark_khop_python`) |
| `label` | string | `negative` / `neutral` / `positive` — xem §3 |
| `rating` | string | Điểm gốc 1–10 (giữ lại để truy vết, **không** dùng làm đặc trưng) |
| `text` | string | Văn bản **đã làm sạch** (§6) — đây là đầu vào của mô hình |
| `review_date` | string | Ngày viết gốc (chỉ để tham chiếu) |
| `n_chars` | int | Số ký tự của `text` (dùng để lọc `min_chars`/`max_chars`) |
| `n_tokens` | int | Số token tách theo khoảng trắng (khớp `RegexTokenizer` ở Task 7) |

**Không** có trong parquet: `reviewer`, `review_summary`, `spoiler_tag`, `helpful`
(không dùng hoặc là thông tin cá nhân).

---

## 5. `data/processed/eval_labels.parquet` — nhãn đánh giá

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `comment_id` | string | Khoá nối với luồng Kafka và với `test.parquet` |
| `label` | string | Nhãn thật của tập test |
| `rating` | string | Điểm gốc |

- **Chỉ chứa tập test** — đúng một lần dùng vào cuối dự án (CLAUDE.md §6).
- Do `src/training/prepare.py` tạo. Producer **chỉ đọc** file này (tuỳ chọn
  `--only-test`) và **không ghi đè**; muốn ghi nhãn của một đợt phát thì truyền
  `--labels-out <file khác>`.
- **Nhãn tuyệt đối không đi vào luồng Kafka** — message chỉ có 5 trường (§7).

---

## 6. Làm sạch văn bản — thứ tự cố định, dùng chung train + streaming

Một chỗ duy nhất: `src/common/text_cleaning.py` (CLAUDE.md §4). Thứ tự quan trọng —
đổi thứ tự là đổi kết quả:

| # | Bước | Ví dụ |
|---|---|---|
| 1 | Chữ thường + trim | `"  Great  "` → `"great"` |
| 2 | Bỏ thẻ/entity HTML | `"<br>"`, `"&amp;"` → bỏ |
| 3 | URL → `<url>` | `"https://a.bc"` → `<url>` |
| 4 | @mention → `<user>` | `"@john"` → `<user>` (không giữ danh tính) |
| 5 | Chuẩn hoá dấu câu unicode + bỏ ký tự vô hình | `’` → `'`, `—` → `-`, bỏ zero-width |
| 6 | Từ điển viết tắt/teencode (`cleaning.abbreviations` trong config) | `"pls"` → `"please"`, `"thx"` → `"thanks"` |
| 7 | Rút gọn ký tự lặp ≥3 → 2 | `"haaaay"` → `"haay"`, `"soooo"` → `"soo"` |
| 8 | Emoji tách thành token riêng | `"hay👍quá"` → `"hay 👍 quá"` |
| 9 | Gộp khoảng trắng + trim | `"a   b"` → `"a b"` |

Ghi chú kỹ thuật:
- **Toàn bộ là hàm Spark SQL** (`lower`, `regexp_replace`, `trim`, `size`, `split`),
  **không dùng Python UDF** → không chặn tối ưu hoá Catalyst/WSCG (CLAUDE.md §4).
- Hàm **idempotent**: làm sạch hai lần cho cùng kết quả (có test). Nhờ vậy nếu
  streaming vô tình làm sạch lại văn bản đã sạch thì kết quả không đổi — `<url>` và
  `<user>` không bị regex bắt thẻ HTML ăn mất (dùng negative lookahead).
- Emoji bị tách thành token nên **đếm được tần suất** → `outputs/tables/emoji_frequency.csv`.
  Hạn chế đã biết: emoji ghép bằng ZWJ (👨‍👩‍👧) bị tách thành từng mảnh — chấp nhận vì mục
  tiêu là giữ tín hiệu cảm xúc, không phải hiển thị.
- Lớp emoji **không** gồm `\p{Sk}` (modifier symbol): đo trên dữ liệu thật thấy ký tự
  `¨` (U+00A8) đứng đầu bảng "emoji" với 394 lần — đó là rác mã hoá, nên đã loại.
- **Hai mức lọc emoji, đừng lẫn (bổ sung ở Task 9).** Hằng số `EMOJI_CLASS` (dùng ở bước 8
  để **tách token**) có chứa `\p{So}` — lớp này bao gồm cả **ký tự typography không phải
  emoji**: đo trên train thấy `°` (U+00B0) xuất hiện 59 lần và lọt vào top-30 "emoji".
  Vì vậy khi **thống kê** emoji (Hình 09, `eda_emoji_by_class.csv`) phải lọc thêm dải
  tường minh `EMOJI_SYMBOL_RANGES` trong cùng file. Hệ quả: số emoji ở bảng Task 9
  (`eda_emoji_by_class.csv`) **nhỏ hơn hoặc bằng** `emoji_frequency.csv` của Task 6
  (bảng đó chỉ dùng điều kiện thứ nhất). Đây là **lỗi đã sửa**, không phải hai định nghĩa
  song song có chủ ý — khi báo cáo chỉ dùng số của Task 9.
- **Ghi chú về tiếng Việt:** bộ dữ liệu hiện tại là **tiếng Anh**, nên **không** cần
  `underthesea`/`pyvi`. Nếu sau này chuyển sang dữ liệu tiếng Việt thì **bắt buộc** thêm
  bước tách từ tiếng Việt; cách làm là `pandas_udf` (Arrow theo lô) vì Spark SQL không có
  tách từ tiếng Việt. **Chi phí hiệu năng: chưa đo trên máy này — cần kiểm chứng.** Ước
  lượng từ tài liệu Spark là chậm hơn hàm SQL khoảng 5–20 lần (UDF chặn tối ưu hoá và
  phải chuyển dữ liệu qua Arrow); **phải đo thật rồi ghi số đo** trước khi dùng, không
  được chép ước lượng này vào báo cáo như số liệu của nhóm.

---

## 7. Luồng Kafka — message chỉ có 5 trường, KHÔNG có nhãn

`src/producer/replay_producer.py` gửi JSON lên topic `comments_raw`:

| Trường | Ý nghĩa |
|---|---|
| `comment_id` | = `review_id` (khoá nối, cũng là khoá message) |
| `stream_id` | = `movie` (tên "phòng") |
| `user_hash` | Băm có muối, **giống hệt** cột `user_hash` trong parquet |
| `text` | **Văn bản gốc chưa làm sạch** — job streaming làm sạch bằng đúng hàm ở §6 |
| `event_ts` | ISO-8601 UTC (mili giây); một tỷ lệ nhỏ bị đẩy trễ (`replay.late_ratio`) để watermark có việc thật |

Không có `label`/`rating`/`sentiment`. `src/producer/test_consumer.py` kiểm tra cả
trường bắt buộc lẫn trường bị cấm và trả mã lỗi nếu phát hiện.

> ⚠️ **Đây là dữ liệu REPLAY (phát lại) để mô phỏng livestream, KHÔNG phải bình luận
> livestream thật.** Mọi slide/báo cáo phải ghi rõ (CLAUDE.md §9).

---

## 8. Các bảng trong `outputs/tables/`

| File | Cột | Nội dung |
|---|---|---|
| `cleaning_log.csv` | `step`, `rows_in`, `rows_removed`, `rows_out`, `note` | Số dòng bị loại ở **từng bước**: nạp → thiếu văn bản → thiếu nhãn → quá ngắn → quá dài → **trùng mã** → trùng chính xác → trùng gần → còn lại |
| `class_distribution.csv` | `split`, `label`, `count`, `share_in_split` | Phân bố lớp ở từng tập + dòng `ALL` (toàn bộ). `share_in_split` = tỷ lệ trong chính tập đó |
| `emoji_frequency.csv` | `emoji`, `count` | Top `prepare.emoji_top_n` emoji phổ biến nhất trên văn bản **đã làm sạch** |
| `clean_sample.csv` | `comment_id`, `stream_id`, `user_hash`, `label`, `rating`, `split`, `review_date`, `text`, `text_raw` | `prepare.sample_rows_out` dòng để **đối chiếu bằng mắt**: `text_raw` (gốc) cạnh `text` (đã sạch) |
| `ingestion_report.csv` | `timestamp_utc`, `topic`, `rate_target`, `burst_prob`, `late_ratio`, `sent`, `delivered`, `errors`, `seconds`, `msgs_per_sec`, `bytes`, `note` | Thông lượng producer (Task 5), ghi thêm một dòng mỗi lần chạy |
| `split_leak_check.csv` (nếu có) | — | Kết quả đo rò rỉ giữa các tập |

### Task 9 (EDA) — `outputs/tables/eda_*.csv`

Do `src/eda/queries.py` (Spark SQL) ghi ra; **bảng số liệu nền của từng hình**.
SQL nguyên văn ở `src/eda/sql/q00_…q12_*.sql`; sửa hình không phải chạy lại Spark
(`src/eda/plots.py` chỉ đọc lại các CSV này). Ghi chú chung:

- Phần lớn bảng «tĩnh» (tính từ parquet train/val/test) có cột `split`; ngoại lệ:
  `eda_length_quantiles.csv`, `eda_length_histogram.csv` và `eda_top_words_by_class.csv`
  **chỉ tính trên train** nên không có cột này — hình vẽ cũng dùng train.
- Các bảng «luồng» đọc từ `outputs/stream/<run>/` của **Task 8** — lần chạy
  `verify1`, **1.014 bình luận** (1.000 phát lại + 14 bản ghi kiểm chứng nhịp tim).
  ⚠️ REPLAY, không phải livestream thật. Bản ghi kiểm chứng sinh ra các cửa sổ
  1 bình luận — tỷ lệ ở đó **không có ý nghĩa thống kê**.

| File | Cột chính | Nội dung |
|---|---|---|
| `eda_overview.csv` | `n_train`, `n_val`, `n_test`, `n_streams_train`, `n_stream_comments`, `n_streams_streaming`, `stream_first/last_event_utc`, `n_windows_1min_rows`, `n_comments_in_windows`, `n_synthetic_comments`, `n_replay_comments` | Số kiểm tra quy mô (không vẽ hình) |
| `eda_class_distribution.csv` | `split`, `label`, `n_comments`, `share_in_split` | Phân bố lớp ở cả ba tập (Hình 06) |
| `eda_length_quantiles.csv` | `label`, `n_comments`, `mean_tokens`, `p25_tokens`, `p50_tokens`, `p75_tokens`, `p95_tokens`, `max_tokens`, `mean_chars`, `p50_chars` | Phân vị độ dài theo **token** (và ký tự) mỗi lớp (Hình 07) |
| `eda_length_histogram.csv` | `label`, `bin_lower_tokens`, `n_comments`, `share_in_class` | Histogram độ dài, bin rộng `eda.length_bin_width` (Hình 07). ⚠️ Bảng **không** có cột `split` — chỉ tính trên train |
| `eda_top_words_by_class.csv` | `label`, `rk`, `word`, `n_in_class`, `log_odds`, `z_score` | 20 từ đặc trưng nhất mỗi lớp, xếp theo log-odds có prior (Hình 08). `z_score` = điểm chuẩn hoá dùng để xếp hạng |
| `eda_emoji_by_class.csv` | `label`, `rk_in_class`, `rk_global`, `emoji`, `n_emoji`, `n_emoji_total`, `n_comments_in_class`, `n_comments_with_emoji`, `pct_comments_with_emoji`, `emoji_per_1000_comments`, `pct_of_class_emoji` | Emoji theo lớp (Hình 09). ⚠️ `emoji_per_1000_comments` là mật độ của **cả lớp** — giống nhau ở mọi dòng cùng lớp; suy ra mật độ **theo từng emoji** = `1000 × n_emoji / n_comments_in_class` |
| `eda_sentiment_per_minute.csv` | `window_start`, `window_end`, `n_comments`, `n_negative`, `n_neutral`, `n_positive`, `n_synthetic`, `n_replay`, `share_negative`, `share_neutral`, `share_positive` | Cửa sổ nhảy 1 phút của Task 8 (Hình 10) |
| `eda_sentiment_per_10s.csv` | như trên, **không có** `n_replay` | Cửa sổ trượt 10 giây (Hình 10) — dùng để thấy diễn biến **bên trong** phút |
| `eda_throughput_per_second.csv` | `second_utc`, `n_comments`, `mean_per_sec`, `sd_per_sec`, `burst_threshold`, `peak_per_sec`, `n_seconds_with_data`, `is_burst`, `configured_burst_ceiling` | Số bình luận mỗi giây; `burst_threshold` = `mean_per_sec + burst.sigma × sd_per_sec` (Hình 11). Các cột thống kê lặp lại trên mọi dòng (chỉ để vẽ) |
| `eda_negative_share_alert.csv` | `window_start`, `window_end`, `n_comments`, `n_negative`, `share_negative`, `alert_threshold`, `min_comments`, `has_enough_volume`, `is_alert` | Quy tắc cảnh báo: `is_alert = share_negative > alert_threshold AND n_comments >= min_comments` (Hình 12) |
| `eda_latency_quantiles.csv` | `label` (`all`/`injected_late`), `n_comments`, `min_ms`, `p50_ms`, `p90_ms`, `p95_ms`, `p99_ms`, `max_ms`, `mean_ms`, `kafka_p50_ms`, `kafka_p95_ms`, `queue_p50_ms`, `queue_p95_ms`, `queue_min_ms` | Phân vị độ trễ end-to-end và từng chặng (Hình 13). Đơn vị **mili giây** |
| `eda_latency_histogram.csv` | `bin_idx`, `bin_lower_ms`, `bin_upper_ms`, `n_comments`, `n_injected_late` | Histogram độ trễ, bin theo **bậc 10** (Hình 13); `n_injected_late` = số bản ghi cố tình đẩy trễ nằm trong bin |
| `eda_model_quality.csv` | `true_label`, `pred_label`, `count`, `row_share`, `model` | Ma trận nhầm lẫn của Task 7 ở **dạng dài** (mỗi ô một dòng) để vẽ Hình 14. F1/precision/recall từng lớp lấy từ `per_class_metrics.csv` — hình 14 dùng **cả ba** file |
| `eda_token_vocab.csv` | `n_token_occurrences`, `n_vocab_raw`, `n_vocab_stripped`, `n_occurrences_with_edge_punct`, `pct_occurrences_with_edge_punct` | Hạn chế bước tách từ: token còn dính dấu câu ở hai đầu (không vẽ hình) |

**Ngưỡng/định nghĩa đọc từ `config.yaml` mục `eda`**, không hard-code trong SQL:
`streaming_run`, `top_words_n`/`min_count`, `log_odds_prior`, `emoji_per_class_n`,
`length_bin_width`/`max`, `latency_bins_per_decade`, `burst.sigma`, `alert.*`.

**Chạy thử** bằng `queries.py --sample N` ghi ra `*_sample.csv` (không ghi đè bảng thật)
để không ai nhầm số liệu chạy thử với số liệu báo cáo.

---

## 9. Chia tập và chống rò rỉ dữ liệu

Thứ tự bắt buộc (CLAUDE.md §6): **làm sạch → loại trùng → mới chia tập**.

1. **Loại trùng trước khi chia**, theo ba mức: (a) **trùng mã** — nguồn có `review_id` lặp
   (1,54% số dòng), giữ bản văn bản dài nhất, nhờ đó `comment_id` là khoá duy nhất nối
   được với luồng Kafka và bảng nhãn; (b) **trùng khít** văn bản đã làm sạch; (c) **gần
   trùng** (`dedup_key`: chữ thường, bỏ dấu câu, gộp khoảng trắng, **sắp xếp từ** rồi băm —
   hai câu cùng bộ từ khác thứ tự/dấu câu ra cùng khoá). Nếu để lẫn, bản copy ở tập train
   xuất hiện y hệt ở tập test → điểm cao giả tạo.
2. **Chia theo nhóm phim** (`split.method: group_movie_balanced`): một phim **không bao
   giờ** nằm ở hai tập, vì review cùng một phim chia sẻ bối cảnh rất mạnh. Chương trình
   **assert** điều này sau khi chia và in số đo ra log.
3. **Cân bằng nhãn** bằng tham lam nhiều lần thử (32 thứ tự, seed 42 + k, tất định),
   chọn phương án lệch ít nhất so với tỷ lệ mục tiêu.
4. **Kết quả đo được** (ghi trong log chạy, không phải suy đoán): phim nằm ở >1 tập = 0;
   số người dùng xuất hiện ở >1 tập được **in ra và báo cáo trung thực** — đây là rủi ro
   rò rỉ **còn lại** (cùng một người viết review cho nhiều phim khác nhau). Mức độ ảnh
   hưởng thấp vì các review đó là văn bản khác nhau và bản copy-paste đã bị bước 1 loại.
5. **Tập test chỉ dùng một lần** ở cuối dự án; nhãn test để riêng ở `eval_labels.parquet`.
6. **TF-IDF chỉ fit trên train** và nằm trong `Pipeline` của Spark ML (Task 7) — không
   fit trên val/test.

---

## 10. Tham chiếu nhanh

| Câu hỏi | Xem ở đâu |
|---|---|
| Nguồn, giấy phép, checksum dữ liệu gốc | `data/raw/SOURCE.md` |
| Vì sao chọn đề tài/dữ liệu này | `docs/topic_decision.md` |
| Tham số làm sạch, tỷ lệ chia, ánh xạ nhãn | `config.yaml` |
| Hàm làm sạch | `src/common/text_cleaning.py` + test `tests/test_text_cleaning.py` |
| Băm có muối | `src/common/utils.py` + test `tests/test_utils.py` |
| Tạo dữ liệu train/val/test | `src/training/prepare.py` |
| Số liệu thật để báo cáo | `outputs/tables/*.csv`, `outputs/figures/*.png`, `outputs/insights.md` |
