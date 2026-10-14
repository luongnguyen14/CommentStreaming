# outputs/streaming_summary.md — Chạy streaming & kiểm chứng (Task 8)

Viết ngày **15/10/2026**. **Mọi con số dưới đây lấy từ file thật trong `outputs/`** —
chủ yếu `outputs/stream/verify1/verification.json`, `outputs/tables/stream_verification.csv`,
`stream_per_class_metrics.csv`, `stream_sample_rows.csv`, `stream_dlq_rows.csv`,
`stream_batches.csv` và log chạy `logs/task8_stream_verify1.log`,
`logs/task8_verify_verify1.log`.

---

## 1. Kết luận ngắn

Lần chạy chính thức **`verify1`** (15/10/2026, 18:08–18:14 UTC):

| Câu hỏi | Kết quả đo được |
|---|---|
| Bản ghi đã chấm điểm + bản ghi vào DLQ = bản ghi đã gửi? | **Đúng: 1.014 + 10 = 1.024** |
| Message ghi ra Kafka có khớp số dòng đã chấm? | **Khớp: `comments_scored` +1.014, `comments_dlq` +10** (theo chênh lệch offset) |
| Macro-F1 trên luồng so với offline? | **0,6311** (luồng, 1.000 dòng) vs **0,6233** (offline, 27.792 dòng) — xem §4 |
| Đường ống streaming có cho **cùng dự đoán** với lúc huấn luyện? | **Có: 1.000/1.000 dòng (100,00%)** giống nhau |
| Watermark có bỏ bản ghi đến muộn? | **Có** — bản ghi lạc hậu 10 phút gửi *sau khi* watermark đã tiến **không** có mặt trong cửa sổ nào (kiểm bằng đối chiếu dữ liệu, xem §6) |
| Có bảo đảm exactly-once? | **Chưa kiểm chứng** — chỉ dám nói **at-least-once** cho phần đã đo (§7) |

Điểm **quan trọng và trung thực nhất**: macro-F1 0,63 đạt được trên **dữ liệu IMDb phát
lại** (replay), nơi bình luận thường có câu "I rate it 7/10" — mô hình có thể đang đọc
con số thay vì hiểu cảm xúc (đã nêu ở `outputs/modeling_summary.md` §5). **Không được
hứa hẹn mức 0,63 cho bình luận livestream thật.**

## 2. Lần chạy chính thức

| Mục | Giá trị |
|---|---|
| Run name | `verify1` |
| Lệnh chạy | `bash scripts/run_stream.sh verify1 --sink-dir outputs/stream/verify1 --checkpoint-root checkpoints/streaming/verify1 --trigger-seconds 5` |
| Kafka | `comments_raw` (3 partition, `startingOffsets=latest`, `maxOffsetsPerTrigger=5000`) |
| Model | `outputs/models/sentiment_pipeline` (LogisticRegression của Task 7) |
| Watermark | 2 phút (event time) |
| Thời gian | 18:08:20 → 18:14:48 UTC (job READY lúc 18:08:32; dừng êm lúc 18:14:48) |
| Dữ liệu phát | 1.000 bình luận `--only-test --rate 50` + `send_bad_events.py --heartbeat 12 --heartbeat-interval 25 --late-probe` |
| Micro-batch | **110 batch** trên 6 query; mỗi query đọc đủ **1.024 bản ghi** |
| Thời gian trigger | trung bình 2,5–3,2 s/query, cao nhất 17,7 s (batch đầu của query cửa sổ, phải nạp state) |
| Dừng job | `bash scripts/stop_stream.sh verify1` → cả 6 query dừng sạch, "bỏ do watermark: 0" |

`comments_scored` có sẵn 71 message từ 2 lần chạy thử trước đó, nên mốc offset được ghi
lại **trước khi chạy** (`outputs/stream/verify1/kafka_offsets_baseline.json`) và mọi con
số Kafka dưới đây là **chênh lệch so với mốc đó**: `comments_scored` 71 → 1.085,
`comments_dlq` 22 → 32.

## 3. Đối chiếu số lượng — không có bản ghi nào bốc hơi

| Nguồn phát | Số bản ghi |
|---|---|
| `replay_producer --only-test --max 1000` (Kafka xác nhận 1.000, lỗi 0) | 1.000 |
| `send_bad_events.py`: ca 11 (hợp lệ, lạc hậu 10 phút) + 12 heartbeat + 1 late-probe | 14 |
| `send_bad_events.py`: 10 ca lỗi cố ý | 10 |
| **Tổng đã gửi** | **1.024** |

| Đích | Số bản ghi | Kiểm chứng chéo |
|---|---|---|
| Bảng chi tiết `scored_detail` | **1.014** | topic `comments_scored` +1.014 |
| DLQ `dlq` (Parquet) | **10** | topic `comments_dlq` +10 |
| **Tổng** | **1.024 = 1.024** ✔ | |

- **0 bản ghi của `replay_producer` rơi vào DLQ** trong lần này: cả 1.000 bản ghi đều
  qua được luật làm sạch. (Ở lần chạy thử với 30 bình luận **có** 1 bình luận thật bị
  đưa vào DLQ vì dài quá `max_chars` 5.000 — nghĩa là nhánh DLQ bắt được cả dữ liệu
  thật, không chỉ 10 ca do nhóm cố ý gửi.)
- DLQ phân bố đúng theo 10 ca đã gửi, tra được **từng ca** (`stream_dlq_rows.csv`):

| Lý do | Số bản ghi | Ca tương ứng |
|---|---|---|
| `json_khong_hop_le` | 3 | 01 JSON hỏng · 02 JSON mảng · 03 JSON `null` |
| `thieu_truong:text` | 1 | 04 |
| `thieu_truong:comment_id` | 1 | 05 |
| `thieu_truong:event_ts` | 1 | 06 |
| `event_ts_khong_doc_duoc` | 1 | 07 `2026-13-45T99:99:99Z` |
| `van_ban_rong_sau_lam_sach` | 1 | 08 toàn khoảng trắng |
| `van_ban_qua_ngan_duoi_20_ky_tu` | 1 | 09 `"ok"` |
| `van_ban_qua_dai_tren_5000_ky_tu` | 1 | 10 |

- 4 bản ghi JSON hỏng/thiếu `comment_id` được ghi rõ `(khong-co-id)` thay vì để trống —
  vẫn truy vết được về đúng `kafka_partition` + `kafka_offset`.
- Ca hợp lệ nhưng lạc hậu (`bad-11`, `probe-late`) **có** trong bảng chi tiết và
  **không** vào DLQ — đúng thiết kế (DLQ là để bắt bản ghi hỏng, không phải bản ghi trễ).

## 4. Chỉ số trên luồng so với offline

Ghép `data/processed/eval_labels.parquet` theo `comment_id`: **1.000/1.014** dòng chi tiết
có nhãn thật (14 dòng còn lại là heartbeat/probe/bad-11 do nhóm tự phát, không nằm trong
tập test nên bị loại khỏi phép đo — không được đưa chúng vào để "làm đẹp" chỉ số).

| Chỉ số | **Trên luồng** (1.000 dòng test) | Offline, **đúng 1.000 id đó** | Offline, toàn tập test (27.792 dòng) |
|---|---|---|---|
| Accuracy | **0,7030** | 0,7030 | 0,7018 |
| Weighted F1 | **0,7230** | 0,7230 | 0,7213 |
| **Macro-F1** | **0,6311** | 0,6311 | 0,6233 |
| F1 `negative` (support) | 0,6875 (230) | 0,6875 | 0,6723 (6.965) |
| F1 `neutral` (support) | 0,3958 (142) | 0,3958 | 0,3783 (3.853) |
| F1 `positive` (support) | 0,8099 (628) | 0,8099 | 0,8193 (16.974) |

**Cách tách nguyên nhân lệch:** chạy lại **chính `PipelineModel`** offline trên **đúng
1.000 `comment_id`** mà luồng đã chấm:

- **1.000/1.000 dự đoán trùng nhau (100,00%)** ⇒ đường ống streaming (schema → làm sạch →
  model) **cho kết quả y hệt** lúc huấn luyện. Đây là phép kiểm quan trọng nhất: nó loại
  trừ khả năng "sai vì streaming dùng hàm làm sạch khác".
- Chênh lệch so với con số 0,6233 của Task 7 (**+0,0078**) **không** do đường ống mà do
  **mẫu**: 1.000 bình luận (3,6% tập test) rút ngẫu nhiên nên phân bố lớp hơi khác
  (`neutral` chiếm 14,2% ở mẫu vs 13,9% ở toàn tập; `negative` 23,0% vs 25,1%).
  Chênh lệch này **chưa kiểm định ý nghĩa thống kê** — chỉ dám nói là "cùng mức".

## 5. Độ trễ — đo thế nào và số thật

`latency_ms = unix_millis(current_timestamp()) − unix_millis(event_time)`, trong đó
`current_timestamp()` là **đồng hồ của micro-batch** (một giá trị dùng chung cho cả batch —
đo được: bảng chi tiết có **13 giá trị `processing_ts` khác nhau = 13 micro-batch có ghi
dữ liệu**). Vì vậy đây là độ trễ **theo batch**, bao gồm cả thời gian chờ trigger (5 s) —
không phải độ trễ mạng.

| Chỉ số (ms) | min | p50 | p95 | p99 | max |
|---|---|---|---|---|---|
| `latency_ms` (event_time → xử lý) | 40 | **2.413** | 9.663 | 27.091 | **603.608** |
| trong đó `kafka_latency_ms` (producer → broker) | — | **0** | — | — | 600.206 |
| trong đó `queue_latency_ms` (broker → xử lý xong) | 40 | **2.355** | 9.136 | — | — |

- `max` 603.608 ms = **9,9 phút**, chính là 2 bản ghi do nhóm **cố ý** gán `event_ts` lùi
  10 phút (`bad-11`, `probe-late`) — không phải bình luận đến muộn ngoài đời.
- `kafka_latency_ms` p50 = **0 ms**: producer và broker cùng một máy, gửi xong là broker
  nhận ngay — đây là hệ quả của việc chạy replay trên một máy ảo, **không** đại diện cho
  một hệ thống thật. Con số đáng nhìn là `queue_latency_ms` (min 40 ms · p50 2.355 ms ·
  p95 9.136 ms, gồm cả thời gian chờ trigger 5 s).

## 6. Cửa sổ & watermark

| Query | Số dòng | Tổng `n_comments` trong các cửa sổ | Khoảng thời gian (UTC) |
|---|---|---|---|
| `window_1min` (1 phút, nhảy) | 710 | 1.007 | 17:58:00 → 18:11:00 |
| `window_sliding_10s` (10 giây, trượt 5 giây) | 1.466 | 2.015 (cửa sổ chồng nhau nên > 1.014) | 17:58:45 → 18:11:25 |

Mỗi dòng là (**cửa sổ**, `stream_id`) với `n_negative` / `n_neutral` / `n_positive`,
`share_negative` / `share_neutral` / `share_positive`, `avg_confidence`, `avg_latency_ms`.
Ví dụ thật (cửa sổ 18:08–18:09, `window_1min`):

| `stream_id` (tên phim) | n | neg | neu | pos | `share_negative` |
|---|---|---|---|---|---|
| Mrs. Serial Killer (2020) | 126 | 12 | 20 | 94 | 0,0952 |
| Hunters (2020– ) | 12 | 7 | 2 | 3 | 0,5833 |
| I Am Not Okay with This (2020) | 9 | 5 | 1 | 3 | 0,5556 |
| Knives Out (2019) | 8 | 2 | 0 | 6 | 0,25 |

**Vì sao 1.007 chứ không phải 1.014 bản ghi nằm trong cửa sổ đã ghi ra** (giải thích trọn vẹn,
không có phần nào "không rõ"):

1. **6 bản ghi heartbeat cuối cùng còn nằm trong state** (3 cửa sổ: 18:11, 18:12, 18:13).
   Watermark chỉ tiến khi có **bản ghi mới**, mà cửa sổ chỉ được ghi ra khi watermark vượt
   mốc kết thúc cửa sổ ⇒ dừng phát dữ liệu đột ngột thì các cửa sổ cuối **phải** nằm lại.
   Đây đúng là trạng thái cuối của query: `state_operators = 3`.
2. **1 bản ghi bị watermark bỏ** — `probe-late`.

**Kiểm chứng watermark bằng dữ liệu (không suy đoán):** nhóm gửi 2 bản ghi hợp lệ nhưng
lạc hậu 10 phút ở 2 thời điểm khác nhau:

| Bản ghi | Gửi lúc | Số phận đo được |
|---|---|---|
| `bad-11` | cùng batch đầu tiên (chưa có watermark nào) | **có** cửa sổ `[17:58, 17:59)` với `n_comments=1` |
| `probe-late` | sau khi watermark đã tiến 10 phút (18:13) | **không** có mặt trong `window_1min` lẫn `window_sliding_10s` (cửa sổ trượt sớm nhất của `stream_id='heartbeat'` là 18:08:45, tức bản ghi 18:03 không có cửa sổ nào) |

⇒ **Watermark 2 phút thật sự bỏ được bản ghi đến muộn.**

⚠️ **Một chi tiết phải nói rõ:** cột `numRowsDroppedByWatermark` (lấy từ `QueryProgress`,
ghi ở `stream_batches.csv`) báo **0** ở cả 6 query, **dù** bằng chứng dữ liệu ở trên cho
thấy `probe-late` đã bị bỏ. Vậy bộ đếm này **không phản ánh** lần bỏ đó — kết luận phải
lấy từ đối chiếu dữ liệu. Không được viết trong báo cáo là "numRowsDroppedByWatermark
chứng minh watermark hoạt động".

## 7. Đảm bảo giao hàng — đã kiểm chứng gì, chưa kiểm chứng gì

| Mức bảo đảm | Kết luận |
|---|---|
| Kafka → file/Kafka, chạy liên tục không sự cố | **Quan sát được: không trùng, không mất** (1.014 + 10 = 1.024; topic nhận đúng +1.014 và +10) |
| Về mặt cơ chế (theo thiết kế của Structured Streaming) | **At-least-once**: offset chỉ được commit sau khi batch ghi xong; nếu job chết giữa lúc ghi và lúc commit thì batch đó sẽ chạy lại ⇒ **có thể trùng**, không mất |
| Exactly-once (kể cả khi có sự cố) | **CHƯA kiểm chứng** — chưa hề chạy thí nghiệm crash/kill -9/restart giữa batch, chưa bật `spark.task.maxFailures`/thử broker chết. **Không được khẳng định.** |
| Dừng êm | **Đã kiểm chứng 2 lần** (smoke + verify1): SIGTERM → 6 query dừng sạch, batch đang chạy làm nốt, không có file parquet dở |

## 8. Hạn chế & việc còn lại của Task 8

1. **Đây là dữ liệu replay, không phải livestream thật** (CLAUDE.md §9): `stream_id` là
   tên phim của IMDb, `event_ts` do nhóm tự gán. Mọi câu chữ trong báo cáo phải gọi đúng.
2. **Chưa kiểm chứng khả năng chịu lỗi** (crash/restart/broker chết) — xem §7.
3. **Chưa đo trên nhiều máy / dữ liệu lớn**: 1.024 bản ghi, một máy ảo, `local[2]`,
   trigger 5 s. Số liệu độ trễ **không** đại diện cho hệ thống thật.
4. **Bộ đếm `numRowsDroppedByWatermark` báo sai** (0 dù có bản ghi bị bỏ) — cần lưu ý khi
   viết báo cáo; muốn kết luận thì phải đối chiếu dữ liệu như §6.
5. **`neutral` vẫn gần như không giải được** trên luồng (F1 0,3958) — giống hệt offline
   (0,3783), tức không phải lỗi streaming mà là **nhiễu nhãn** (nhãn suy từ rating 5–6).
6. **Shortcut "điểm số trong bài"** (`7/10`, `5/10`) chưa được đo lại trên luồng: phép đo
   ở đây vẫn dùng chính dữ liệu IMDb, nên **chưa chứng minh được** mô hình không dựa vào
   con số khi gặp bình luận livestream.
