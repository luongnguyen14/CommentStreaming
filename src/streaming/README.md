# src/streaming/ — Chấm điểm cảm xúc theo luồng (Task 8, Day 8–9)

Job Spark Structured Streaming đọc bình luận từ Kafka, làm sạch bằng **đúng hàm dùng
lúc huấn luyện**, chấm điểm bằng `PipelineModel` đã lưu ở Task 7, rồi ghi ra ba đích
(bảng chi tiết Parquet, topic Kafka, tổng hợp theo cửa sổ). Bản ghi lỗi/thiếu trường
đi vào **DLQ kèm lý do**.

```
                      ┌─ (a) detail  → outputs/stream/<run>/scored_detail  (Parquet, partition theo ngày/giờ)
comments_raw ──┐      ├─ (b) kafka   → topic comments_scored (JSON)
(Kafka)        │      ├─ (c) window  → outputs/stream/<run>/window_1min        (1 phút, nhảy)
   6 readStream ├─ parse from_json (schema tường minh) → clean_text (dùng chung) → model.transform()
   độc lập      │      └─ (c') sliding → outputs/stream/<run>/window_sliding_10s (10 giây, trượt 5 giây)
               └─ (d) DLQ: topic comments_dlq + outputs/stream/<run>/dlq  (kèm `reason`)
```

| File | Việc |
|---|---|
| `stream_job.py` | Job chính: 6 query streaming (bảng dưới), listener ghi log từng micro-batch |
| `verify_stream.py` | Kiểm chứng sau khi chạy: đối chiếu số lượng, ghép `eval_labels` tính macro-F1 trên luồng, so với offline |
| `../../scripts/run_stream.sh` | Khởi chạy nền + chờ tới khi `READY` mới cho phát dữ liệu |
| `../../scripts/stop_stream.sh` | Dừng **êm** (SIGTERM cho tiến trình Python của driver) |
| `../../scripts/send_bad_events.py` | Gửi 10 ca lỗi đã biết + heartbeat đẩy watermark + late-probe |

## 1. Sáu query — mỗi query một checkpoint riêng

Mỗi query là một `readStream` **độc lập** trên `comments_raw` (offset riêng), đúng quy
ước CLAUDE.md §5 — query này chậm không chặn query khác, và có thể chạy lại riêng một
query. Đổi lại: cùng một bản ghi được đọc 6 lần (mỗi query tự đọc), nên mọi phép đối
chiếu phải tính theo **từng đích**, không cộng dồn 6 query với nhau.

| Query | Nguồn | Đích | Checkpoint (`checkpoints/streaming/<run>/`) |
|---|---|---|---|
| `detail` | `comments_raw` | `outputs/stream/<run>/scored_detail` (Parquet) | `detail/` |
| `kafka` | `comments_raw` | topic `comments_scored` (JSON) | `kafka/` |
| `window` | `comments_raw` | `outputs/stream/<run>/window_1min` | `window/` |
| `sliding` | `comments_raw` | `outputs/stream/<run>/window_sliding_10s` | `sliding/` |
| `dlq_kafka` | `comments_raw` | topic `comments_dlq` (JSON + `reason`) | `dlq_kafka/` |
| `dlq_parquet` | `comments_raw` | `outputs/stream/<run>/dlq` | `dlq_parquet/` |

`--queries detail,kafka,window` để chỉ chạy một phần (tiện khi thử nhanh).

## 2. Chạy

```bash
source scripts/env.sh                       # Spark 3.5.9, Java 8, PYSPARK_PYTHON=python3.11
bash kafka/start_kafka.sh                   # nếu broker chưa chạy

# Cách 1 — script có kiểm tra trước khi chạy (khuyến nghị): chờ READY rồi mới phát dữ liệu
bash scripts/run_stream.sh verify1 --sink-dir outputs/stream/verify1 \
     --checkpoint-root checkpoints/streaming/verify1 --trigger-seconds 5

# Cách 2 — chạy trực tiếp
$SPARK_HOME/bin/spark-submit --master 'local[2]' --driver-memory 2g \
  --packages "$SPARK_KAFKA_PKG" \
  src/streaming/stream_job.py --run-name verify1
```

`--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.9` **phải khớp** phiên bản
Spark/Scala đã ghi ở `kafka/README.md` (Task 5); gói đã có sẵn trong `~/.ivy2/jars` nên
chạy được cả khi không có mạng.

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--run-name` | `main` | Tên lần chạy: tách sink + checkpoint + log + dòng trong `stream_batches.csv` |
| `--trigger-seconds` | `streaming.trigger_seconds` (10) | Chu kỳ micro-batch |
| `--max-offsets` | `streaming.max_offsets_per_trigger` (5000) | Trần số bản ghi mỗi micro-batch |
| `--starting-offsets` | `streaming.starting_offsets` (`latest`) | `latest`/`earliest`/chuỗi offset JSON |
| `--model-path` | `outputs/models/sentiment_pipeline` | PipelineModel của Task 7 |
| `--sink-dir` | `outputs/stream/<run-name>` | Thư mục ghi Parquet |
| `--checkpoint-root` | `checkpoints/streaming/<run-name>` | Gốc checkpoint (mỗi query một thư mục con) |
| `--watermark` | `streaming.watermark` (`2 minutes`) | Ngưỡng event-time chấp nhận đến muộn |
| `--queries` | `all` | Danh sách query muốn chạy |
| `--duration-seconds` | `0` (chạy mãi) | Tự dừng sau N giây |

Khi chạy với `--starting-offsets latest`, phải đợi job in `READY` **rồi mới phát dữ
liệu** — nếu không, bản ghi gửi trước mốc offset sẽ bị bỏ qua (đây chính là lý do
`run_stream.sh` tồn tại).

## 3. Dừng an toàn

```bash
bash scripts/stop_stream.sh verify1
```

Script gửi **SIGTERM cho tiến trình Python của driver** (con của JVM `spark-submit`),
handler trong `stream_job.py` gọi `query.stop()` cho từng query: micro-batch đang chạy
được làm nốt, Parquet + offset của batch đó được ghi trọn vẹn rồi mới thoát.

- **Không dùng `kill -9`**: có thể cắt ngang lúc đang ghi file/kafka send() và để lại
  batch dở. Structured Streaming vẫn an toàn về offset (offset chỉ được commit khi
  batch hoàn tất), nhưng kết quả có thể bị **trùng một phần** khi chạy lại — đúng bản
  chất at-least-once (xem §11).
- Chạy lại **cùng `--run-name`** ⇒ theo cơ chế của checkpoint, job tiếp tục từ offset đã
  commit (không xử lý lại dữ liệu cũ) — **cơ chế này chưa được thí nghiệm lại** ở Task 8,
  muốn khẳng định thì phải chạy thử rồi đếm bản ghi trùng. Chạy `--run-name` mới ⇒ bắt đầu
  lại theo `starting_offsets`.
- Muốn dừng sau một khoảng thời gian định trước: `--duration-seconds N`.

## 4. Làm sạch & chấm điểm — dùng chung với huấn luyện

- Làm sạch bằng đúng hàm `clean_text()` ở `src/common/text_cleaning.py` (viết một lần,
  Task 6 dùng cho train/val/test, Task 8 dùng cho luồng) — **không** viết lại logic.
- Không dùng Python UDF ở khâu làm sạch: toàn bộ là hàm Spark SQL (`lower`,
  `regexp_replace`, `trim`, `split`...) nên Catalyst tối ưu được. UDF chỉ xuất hiện
  trong `PipelineModel` (RegexTokenizer) do chính Spark cung cấp.
- Các ngưỡng lấy từ `config.yaml` mục `cleaning` (`min_chars` 20, `max_chars` 5000) —
  giống hệt lúc chuẩn bị dữ liệu, nên bản ghi vào luồng cũng chịu đúng luật đó.
- `PipelineModel` nạp từ `outputs/models/sentiment_pipeline`; chỉ số lớp 0/1/2 dịch
  sang tên lớp theo `config.yaml → labels.index` (cùng nguồn với Task 7).

## 5. Schema, event time và watermark

- `from_json` với **schema khai báo tường minh** (`RAW_SCHEMA`) — không suy luận từ
  dữ liệu. Schema có sẵn cột `_corrupt` vì **đã đo được**: Spark 3.5.9 *không* tự thêm
  cột `columnNameOfCorruptRecord` vào kết quả `from_json` như tài liệu mô tả; nếu không
  khai báo, cột `_corrupt` không tồn tại và JSON hỏng chỉ hiện ra dưới dạng toàn null.
- `event_ts` (ISO-8601 UTC, `yyyy-MM-dd'T'HH:mm:ss.SSSXXX`) → `event_time`; toàn bộ job
  chạy `spark.sql.session.timeZone=UTC` nên mốc cửa sổ, `event_date`, `event_hour` đều
  là UTC.
- **Watermark 2 phút** — chọn bằng số đo: `replay.late_max_s = 30` giây là mức trễ tối
  đa mà producer mô phỏng, watermark 2 phút = 4× mức đó (chịu được cả khi mức trễ bị đẩy
  lên 4 lần, đổi lại kết quả cửa sổ ra muộn hơn). Hệ quả **cần nói rõ**: một cửa sổ chỉ
  được ghi ra khi watermark vượt qua mốc kết thúc cửa sổ ⇒ kết quả ra sau `window_end`
  + ~2 phút, và watermark chỉ tiến khi có bản ghi mới. Vì vậy sau khi ngừng phát dữ
  liệu, các cửa sổ cuối **vẫn nằm trong state** (không sai — đúng ngữ nghĩa), muốn đẩy
  nốt thì phải phát thêm bản ghi mới (xem `send_bad_events.py --heartbeat`).
- Số bản ghi bị bỏ vì đến muộn được ghi lại theo từng batch ở cột
  `num_rows_dropped_by_watermark` (`outputs/tables/stream_batches.csv`) — đây là bằng
  chứng watermark có tác dụng, không phải suy đoán.

## 6. Đo độ trễ — định nghĩa chính xác

```
latency_ms        = unix_millis(current_timestamp()) − unix_millis(event_time)
kafka_latency_ms  = (timestamp của Kafka)              − unix_millis(event_time)
queue_latency_ms  = latency_ms − kafka_latency_ms
```

- `current_timestamp()` là **thời điểm micro-batch xử lý** (một giá trị cho cả batch —
  đã đo: số giá trị `processing_ts` khác nhau trong bảng chi tiết = số micro-batch có
  ghi dữ liệu). Vì vậy đây là độ trễ **theo batch**, không phải theo từng bản ghi.
- Độ trễ này bao gồm cả **thời gian chờ trigger** (tối đa `trigger_seconds`), thời gian
  chờ watermark/state và thời gian chấm điểm — tức là độ trễ end-to-end của đường ống,
  không phải độ trễ mạng.
- Khi phát lại dữ liệu (replay), `latency_ms` rất dễ lớn vì `event_time` do producer gán
  (có tỷ lệ bị đẩy trễ tới 30 giây) chứ **không phải** bình luận đến muộn ngoài đời. Vì
  vậy bảng chi tiết tách thêm `kafka_latency_ms` (producer → broker) để biết phần nào là
  do phía phát. Số đo thật nằm ở `outputs/streaming_summary.md`.

## 7. DLQ — mọi bản ghi bỏ đi đều có lý do

Bảng chi tiết chỉ chứa bản ghi **qua được** mọi kiểm tra; phần còn lại ghi vào
`comments_dlq` (JSON) và `outputs/stream/<run>/dlq` (Parquet) kèm cột `reason`.
Chuỗi kiểm tra theo thứ tự (lý do cuối cùng là lý do được ghi):

| `reason` | Khi nào |
|---|---|
| `json_khong_hop_le` | `from_json` báo lỗi (JSON hỏng, JSON mảng, JSON `null`…) |
| `thieu_truong:<tên>` | Thiếu `comment_id` / `stream_id` / `text` / `event_ts` |
| `event_ts_khong_doc_duoc` | Có `event_ts` nhưng không parse được theo định dạng ISO-8601 UTC |
| `van_ban_rong_sau_lam_sach` | `text` rỗng/toàn khoảng trắng sau làm sạch |
| `van_ban_qua_ngan_duoi_N_ky_tu` | Ngắn hơn `cleaning.min_chars` |
| `van_ban_qua_dai_tren_N_ky_tu` | Dài hơn `cleaning.max_chars` |

Mỗi bản ghi DLQ mang thêm `comment_id` (nếu đọc được), `json_raw`, `kafka_partition`,
`kafka_offset`, `event_ts`, `dlq_ts` để truy vết về đúng message trên Kafka. **Không có
nhánh nào âm thầm bỏ bản ghi**: mọi đường thoát đều gán `reason` hoặc đi vào bảng chi
tiết (điều kiện "hợp lệ" là `reason IS NULL`).

## 8. Riêng tư

- `streaming.privacy.keep_text: false` (mặc định) ⇒ bảng chi tiết **không** chứa văn
  bản gốc, chỉ có `text_len` và `text_hash` = md5 của bộ từ đã chuẩn hóa (`dedup_key`,
  cùng hàm với Task 6) — đủ để phát hiện copy-paste mà không lưu nội dung.
- `user_hash` do producer băm có muối (`COMMENT_HASH_SALT` đọc từ biến môi trường,
  không nằm trong repo) — job streaming chỉ chuyển tiếp, không giải ngược.
- Không có tên/ID thật/email/số điện thoại trong luồng dữ liệu.

## 9. Log micro-batch

`BatchLogListener` (StreamingQueryListener) ghi một dòng cho mỗi micro-batch của mỗi
query vào `outputs/tables/stream_batches.csv`:
`timestamp_utc, run_name, query_name, batch_id, num_input_rows, input_rows_per_second,
processed_rows_per_second, trigger_execution_ms, add_batch_ms,
num_rows_dropped_by_watermark, state_operators` — kèm in ra log của job. Đây là nguồn số
liệu thật cho phần kiểm chứng, không phải số viết tay.

## 10. Kiểm chứng

```bash
source scripts/env.sh
# (0) ghi mốc offset Kafka TRƯỚC khi chạy job để đếm được message ghi ra topic
$VENV_PY src/streaming/verify_stream.py --record-baseline --run-name verify1
# (1) chạy job, (2) phát dữ liệu, (3) dừng êm, rồi:
PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY \
$SPARK_HOME/bin/spark-submit --master 'local[2]' --driver-memory 2g \
  src/streaming/verify_stream.py --run-name verify1 \
  --sink-dir outputs/stream/verify1 --sent-labels outputs/stream/verify1/sent_labels.parquet \
  --extra-valid 14 --bad-injected 10
```

`verify_stream.py` làm 5 việc: (1) đối chiếu `chấm điểm + DLQ = đã gửi`, (2) đếm message
trên `comments_scored`/`comments_dlq` theo chênh lệch offset, (3) ghép `eval_labels` theo
`comment_id` ⇒ macro-F1/accuracy/P-R-F1 từng lớp **trên luồng**, (4) chạy lại chính
`PipelineModel` offline trên **đúng** các `comment_id` đó để tách "lệch do mẫu" khỏi
"lệch do đường ống", (5) độ trễ, cửa sổ, watermark + in 20 dòng mẫu. Kết quả ghi vào
`outputs/tables/stream_verification.csv`, `stream_per_class_metrics.csv`,
`stream_sample_rows.csv`, `stream_dlq_rows.csv` và `outputs/stream/<run>/verification.json`.

**Kết quả lần chạy `verify1`** (1.000 bình luận test + 14 bản ghi hợp lệ thêm + 10 ca lỗi):
`1.014 + 10 = 1.024` khớp tuyệt đối, topic Kafka nhận đúng `+1.014` và `+10`, độ trễ
`latency_ms` p50 2.413 ms / p95 9.663 ms, macro-F1 trên luồng **0,6311** so với offline
**0,6233** (chạy lại model trên đúng 1.000 id đó: **1.000/1.000 dự đoán giống nhau**).
Toàn bộ số liệu, cách tách nguyên nhân lệch và các hạn chế: `outputs/streaming_summary.md`.

## 11. Đảm bảo giao hàng (delivery guarantee)

| Điều | Trạng thái |
|---|---|
| Cơ chế ghi | Offset Kafka **chỉ được commit khi micro-batch đã ghi xong** ra đích (ghi file Parquet đóng file, hoặc `send()` tới Kafka hoàn tất); checkpoint giữ offset theo từng batch |
| Vì thế về mặt thiết kế | **at-least-once**: job chết giữa lúc ghi và lúc commit ⇒ batch đó chạy lại ⇒ kết quả **có thể trùng**, không mất bản ghi |
| **Đã kiểm chứng bằng thực nghiệm** | (1) Chạy liên tục không sự cố (`verify1`): `1.014 + 10 = 1.024` đúng từng bản ghi, **không trùng, không mất**; topic `comments_scored`/`comments_dlq` nhận đúng số message đã chấm/đã loại. (2) Dừng êm: cả 6 query dừng sạch, batch đang chạy được làm nốt, không có file Parquet dở. (3) Mỗi query có thư mục checkpoint riêng và offset được commit theo từng batch (thấy trong `checkpoints/streaming/<run>/<query>/offsets/`) |
| **CHƯA kiểm chứng** | Exactly-once nói chung; hành vi khi **crash giữa batch** / `kill -9` / restart đột ngột (kể cả việc "chạy lại cùng `--run-name` thì tiếp tục từ offset đã commit" — mới là cơ chế, **chưa thí nghiệm**); khi **broker Kafka chết** hoặc đĩa đầy; khi ghi lỗi rồi retry (có sinh bản ghi trùng hay không). **Không được khẳng định exactly-once** trong báo cáo — muốn nói phải làm thí nghiệm bơm lỗi và đếm bản ghi trùng trước |

Chi tiết và số đo: `outputs/streaming_summary.md` §7.
