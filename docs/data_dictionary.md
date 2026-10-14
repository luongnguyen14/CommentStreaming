# Từ điển dữ liệu — Capstone SIC Big Data (Nhóm 6)

> Tài liệu này mô tả **mọi cột** xuất hiện trong dự án: dữ liệu gốc, dữ liệu đã
> xử lý, nhãn đánh giá và các bảng thống kê. Cập nhật lần cuối: **14/10/2026** (Task 6).
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
| `review_id` | string | Mã review | **Duy nhất**; dùng làm `comment_id` |
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
| Cách chọn tập con | `prepare.subsample_mod: 5` — giữ bản ghi có `crc32(review_id) % 5 == 0` |
| Vì sao chọn theo `review_id` | **Tất định** (chạy lại ra đúng tập con cũ) và **không lệch theo thứ tự phim** trong file gốc (bộ dữ liệu xếp theo phim; cắt N dòng đầu sẽ chỉ lấy được một số phim) |
| Cột trong mỗi dòng | `review_id`, `reviewer`, `movie`, `rating`, `review_date`, `review_detail` (cắt ở `prepare.truncate_raw_detail` = 20.000 ký tự) |
| `_manifest.json` | Ghi nguồn + kích thước nguồn + tham số + số bản ghi để lần sau **bỏ qua bước chuyển đổi**. Tên **bắt đầu bằng `_`** để Spark bỏ qua khi đọc cả thư mục — đặt tên `manifest.json` sẽ bị đọc thành 1 bản ghi rỗng (đã từng xảy ra: Spark đếm 1.010.294 trong khi file có 1.010.293 dòng) |

> ⚠️ **Đây là tập con do nhóm tự chọn, không phải toàn bộ bộ dữ liệu.** Báo cáo phải
> nói rõ: nhóm dùng 201.074 review (1 shard, lấy mẫu 20%) chứ không phải 5.571.499
> review của bộ Kaggle đầy đủ.

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
| `cleaning_log.csv` | `step`, `rows_in`, `rows_removed`, `rows_out`, `note` | Số dòng bị loại ở **từng bước**: nạp → thiếu văn bản → thiếu nhãn → quá ngắn → quá dài → trùng chính xác → trùng gần → còn lại |
| `class_distribution.csv` | `split`, `label`, `count`, `share_in_split` | Phân bố lớp ở từng tập + dòng `ALL` (toàn bộ). `share_in_split` = tỷ lệ trong chính tập đó |
| `emoji_frequency.csv` | `emoji`, `count` | Top `prepare.emoji_top_n` emoji phổ biến nhất trên văn bản **đã làm sạch** |
| `clean_sample.csv` | `comment_id`, `stream_id`, `user_hash`, `label`, `rating`, `split`, `review_date`, `text`, `text_raw` | `prepare.sample_rows_out` dòng để **đối chiếu bằng mắt**: `text_raw` (gốc) cạnh `text` (đã sạch) |
| `ingestion_report.csv` | `timestamp_utc`, `topic`, `rate_target`, `burst_prob`, `late_ratio`, `sent`, `delivered`, `errors`, `seconds`, `msgs_per_sec`, `bytes`, `note` | Thông lượng producer (Task 5), ghi thêm một dòng mỗi lần chạy |
| `split_leak_check.csv` (nếu có) | — | Kết quả đo rò rỉ giữa các tập |

---

## 9. Chia tập và chống rò rỉ dữ liệu

Thứ tự bắt buộc (CLAUDE.md §6): **làm sạch → loại trùng → mới chia tập**.

1. **Loại trùng trước khi chia** — cả trùng khít và gần trùng (`dedup_key`: chữ thường,
   bỏ dấu câu, gộp khoảng trắng, **sắp xếp từ** rồi băm). Hai câu cùng bộ từ chỉ khác thứ
   tự/dấu câu ra cùng khoá → bị coi là gần trùng. Nếu để lẫn, bản copy ở tập train sẽ
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
