# Hướng dẫn app terminal — xem toàn bộ quy trình trong terminal

Tài liệu này giải thích cách chạy `src/app/terminal_app.py`: một app chạy **ngay trong
terminal Ubuntu**, đi qua **8 giai đoạn** của dự án từ lúc lấy dữ liệu giả lập đến khi
chấm điểm từng bình luận và gộp cửa sổ cảnh báo. App dùng **đúng code của hệ thống**
(`parse_stream`, `add_cleaning_and_reason`, `clean_text`, `PipelineModel`,
`windows_from_detail`, `eval_alerts`) chứ không viết lại logic.

> Dữ liệu là **REPLAY từ review IMDb công khai**, không phải bình luận livestream thật.
> Exactly-once **chưa kiểm chứng**; hệ thống chỉ khẳng định at-least-once.

---

## 1. Chạy nhanh

```bash
cd /home/hadoop/capstone

bash scripts/run_terminal_app.sh                      # từng giai đoạn, nhấn Enter
bash scripts/run_terminal_app.sh --auto               # tự chạy, nghỉ 0.8s giữa giai đoạn
bash scripts/run_terminal_app.sh --fast --limit 20    # nhanh, 20 bình luận
bash scripts/run_comment_stream.sh                    # từng comment: đến đâu, kết quả ngay
bash scripts/run_terminal_app.sh --stage 5            # chỉ giai đoạn chấm điểm
bash scripts/run_terminal_app.sh --text "not bad at all actually"  # chấm một câu
bash scripts/run_terminal_app.sh --interactive        # nhập nhiều câu để chấm
bash scripts/run_terminal_app.sh --live --duration 60 # theo dõi Kafka đang chạy
bash scripts/run_terminal_app.sh --help
```

App in gọn: **quy trình 8 bước → cách chạy → kết quả từng bước**. Mỗi giai đoạn có
breadcrumb `Thu thập → Đóng gói → Parse/DLQ → …` để biết đang ở đâu; không in giải
thích dài.

| Chế độ | Cần Kafka? | Cần Spark? | Thời gian điển hình |
|---|---|---|---|
| Walkthrough (mặc định / `--auto` / `--fast`) | Không | Có (từ giai đoạn 3) | 25–35s với `--fast` |
| `run_comment_stream.sh` (`--one-by-one`) | Không | Có | ~1–2s/comment sau khi nạp model |
| `--stage 1` | Không | Không | < 1s |
| `--text`, `--interactive` | Không | Có (nạp model) | ~8–12s lần đầu |
| `--live` | **Có** | Không | đúng `--duration` giây |

`--fast` = `--auto` + không nghỉ giữa các giai đoạn. Khi stdout không phải terminal
(chạy qua pipe, ghi log), app tự bật `--auto` để không chờ Enter.

---

## 2. Bản đồ 8 giai đoạn

| # | Giai đoạn | In ra gì | Code thật đằng sau | Nguồn dữ liệu |
|---|---|---|---|---|
| 1 | Thu thập dữ liệu giả lập | Kích thước file nguồn, tập được lấy, N dòng mẫu + văn bản rút gọn | `ensure_sample()` đọc `outputs/tables/clean_sample.csv` | 1.000 dòng mẫu; lấy 145 dòng `split=test`, seed 42 |
| 2 | Đóng gói message & gửi Kafka | JSON đúng 5 trường, topic, key, `user_hash`, `event_ts`; bảng nhãn sidecar | `ensure_messages()`; producer thật: `src/producer/replay_producer.py` | Mẫu ở giai đoạn 1 |
| 3 | Parse schema + kiểm tra + DLQ | Schema tường minh, bảng từng bản ghi OK/DLQ kèm lý do, đối soát | `RAW_SCHEMA`, `parse_stream()`, `add_cleaning_and_reason()` từ `src/streaming/stream_job.py` | N bản ghi thật + **4 bản ghi lỗi cố ý** |
| 4 | Làm sạch văn bản | Quy tắc, câu tổng hợp trước/sau, bảng độ dài & quy tắc đã đổi, 2 thẻ ví dụ | `clean_text()` từ `src/common/text_cleaning.py` | Văn bản thô của mẫu |
| 5 | Chấm điểm từng bình luận | Thông tin model, thẻ RAW/CLEAN/NHÃN/THẬT/TỪ/ĐỘ TRỄ, bảng đủ mọi dòng | `PipelineModel.transform()` + `linear_parts()` | Mẫu sau làm sạch; nhãn thật ghép từ sidecar |
| 6 | Gộp cửa sổ + cảnh báo | Cửa sổ 1 phút trên mẫu; cửa sổ thật `verify1` (1 phút và 10 giây trượt); latency thật | `windows_from_detail()`, `aggregate_windows()`, `eval_alerts()` | Mẫu + `outputs/stream/verify1/` |
| 7 | Ghi sink + kiểm tra Kafka | Số dòng 4 sink Parquet; offset 3 topic nếu broker chạy; ghi kết quả lần chạy | `_kafka_status()`, `_write_run_artifacts()` | `outputs/stream/verify1/` |
| 8 | Tổng kết | Bảng số của lần chạy, chỉ số test đầy đủ, một dòng lưu ý trung thực, lệnh chạy lại | Tổng hợp state của các giai đoạn | Tất cả ở trên |

---

## 3. Chạy từng comment — comment đến, kết quả ra ngay

`scripts/run_comment_stream.sh` là chế độ `--one-by-one`: mỗi bình luận được đưa vào
**một mình**, chạy đủ `parse_stream → add_cleaning_and_reason → clean_text →
PipelineModel`, in kết quả, rồi mới sang bình luận tiếp theo — giống cách một consumer
xử lý từng message khi nó đến.

```bash
bash scripts/run_comment_stream.sh                     # 12 comment, nghỉ 1s/comment
bash scripts/run_comment_stream.sh --limit 20          # 20 comment
bash scripts/run_comment_stream.sh --fast              # không nghỉ
bash scripts/run_comment_stream.sh --no-bad            # bỏ 4 bản ghi lỗi cố ý
bash scripts/run_comment_stream.sh --interval 0.5      # nghỉ 0,5s/comment
```

Mỗi comment in một thẻ:

```
┌─ [2/7] rw5512669 · Pokémon: Mewtwo Strikes Back - Evol… ─────────────────┐
│ RAW   : Off the bat, it's almost a shot for shot remake of the original… │
│ CLEAN : off the bat, it's almost a shot for shot remake of the original… │
│ KẾT QUẢ: NEGATIVE  neg 0.493 | neu 0.453 | pos 0.054                     │
│ TỪ    : “padding” +0.42 · “poor” +0.27 · “instead.” +0.25 …              │
│ THẬT  : negative (rating 3) ✔                                            │
│ XỬ LÝ : 2020 ms                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

- Bản ghi lỗi vẫn vào **DLQ** kèm lý do, in thẻ `LỖI` thay vì kết quả.
- `XỬ LÝ` là thời gian **một lượt Spark job** (gồm cả khởi động job), không phải
  latency streaming thật; latency thật của `verify1` ở giai đoạn 6.
- Kết thúc in tổng: số comment, số DLQ, đúng/sai trên mẫu, và cửa sổ 1 phút của
  **phiên này**. Cảnh báo chỉ bật khi cửa sổ có ≥ `min_comments` bình luận
  (`config.yaml`, hiện là 5) — app nói rõ nếu phiên chưa đủ ngưỡng.
- Mỗi comment chỉ chạy **một Spark action**: bản ghi lỗi vẫn đi qua model với text
  rỗng để lấy luôn `dlq_reason`, tránh job thứ hai.

Đây vẫn là **replay**: app không mở Kafka consumer; nó mô phỏng đúng đường đi của
một message. Muốn xem consumer thật: `bash scripts/run_demo.sh` rồi
`bash scripts/run_terminal_app.sh --live --duration 60`.

---

## 4. Chi tiết từng giai đoạn — nhìn gì khi demo

### Giai đoạn 1 — Thu thập dữ liệu giả lập

App không gọi API và không phát lại Kafka ở bước này; nó lấy mẫu từ
`outputs/tables/clean_sample.csv` — bản mẫu 1.000 dòng đã chuẩn bị từ review IMDb.
Mẫu được giới hạn ở **tập test** (145 dòng) và lấy `--limit` dòng (mặc định 12) với
`seed=42`.

Điểm cần nói khi demo:

- Kích thước nguồn (`data/raw/part-01.json`, ~1,0 GB) và bản JSONL đã xử lý
  (`data/processed/imdb_jsonl/part-000.jsonl`, ~189,7 MB) được đọc bằng `human_size()`,
  không hard-code.
- `rating` 1–4 → negative, 5–6 → neutral, 7–10 → positive. Nhãn này **chưa** đi vào
  luồng; nó nằm ở sidecar và chỉ dùng để đối chiếu ở giai đoạn 5.

### Giai đoạn 2 — Đóng gói message & gửi Kafka

Mỗi message chỉ có **5 trường bắt buộc**:

```json
{
  "comment_id": "rw2868742",
  "stream_id": "The Evolution of Andrew Andrews (2012)",
  "user_hash": "1070e5749b700354",
  "text": "Oh My God...Major Spoiler alert. ...",
  "event_ts": "2026-10-20T02:58:54.852Z"
}
```

- `text` là **văn bản thô**; producer không làm sạch trước khi gửi.
- `event_ts` là ISO-8601 UTC, do producer ghi ngay trước khi gửi.
- `user_hash` đã băm có muối; không có tên/ID thật.
- **Không có `label`** trong message. Bảng nhãn in riêng bên dưới là sidecar.
- Topic `comments_raw` có 3 partition; key là `comment_id` để giữ thứ tự theo bình luận.

### Giai đoạn 3 — Parse schema + kiểm tra + DLQ

App khởi động Spark `local[2]` và dùng đúng `RAW_SCHEMA`, `parse_stream()`,
`add_cleaning_and_reason()` của job streaming:

- `from_json` chạy **PERMISSIVE** với `columnNameOfCorruptRecord = "_corrupt"`.
- Schema khai báo tường minh: `comment_id`, `stream_id`, `user_hash`, `text`,
  `event_ts`, `_corrupt` — tất cả `string`.
- 4 bản ghi lỗi **cố ý** được chèn sau N bản ghi thật:

| offset | Bản ghi | Lý do DLQ |
|---|---|---|
| N | JSON hỏng | `json_khong_hop_le` |
| N+1 | thiếu `text` | `thieu_truong:text` |
| N+2 | `event_ts = "hom-qua"` | `event_ts_khong_doc_duoc` |
| N+3 | `text = "ok"` | `van_ban_qua_ngan_duoi_20_ky_tu` |

- Bảng đối soát `N hợp lệ + 4 DLQ = N + 4` chứng minh **không bản ghi nào bị bỏ im
  lặng** (CLAUDE.md §5).

### Giai đoạn 4 — Làm sạch văn bản

Một hàm duy nhất `src/common/text_cleaning.py :: clean_text()`, viết bằng **Spark SQL
column** (không Python UDF), dùng chung cho huấn luyện và streaming. Các quy tắc:

`lowercase` · bỏ HTML · URL → `<url>` · `@user` → `<user>` · chuẩn hoá dấu câu ·
viết tắt · gộp ký tự lặp · tách emoji · gộp khoảng trắng.

App in một câu tổng hợp đủ mọi quy tắc, rồi áp lên từng bình luận thật và so
`text_clean` với cột `text` đã làm sạch từ trước trong `clean_sample.csv`. Cột `khớp`
phải toàn dấu ✔ — đó là bằng chứng **cùng một hàm, cùng một kết quả**.

### Giai đoạn 5 — Chấm điểm từng bình luận

App nạp `outputs/models/sentiment_pipeline` (Pipeline:
`RegexTokenizer → StopWordsRemover → NGram → CountVectorizerModel → IDFModel →
Normalizer → LogisticRegressionModel`) và gọi `model.transform()` trên từng bình luận.

Mỗi thẻ chi tiết in:

- **RAW** — văn bản gốc; **CLEAN** — sau `clean_text()`;
- **NHÃN** — nhãn dự đoán + xác suất 3 lớp + độ tin cậy;
- **THẬT** — nhãn suy từ rating, kèm ✔/✘; nhãn này **chỉ dùng để đối chiếu**, không
  đi qua luồng;
- **TỪ** — các từ đóng góp mạnh nhất, tính từ `feature × coefficient` của mô hình
  tuyến tính;
- **ĐỘ TRỄ** — từ `event_ts` đến lúc chấm xong. Đây là **độ trễ mô phỏng offline**,
  gồm cả thời gian khởi động Spark/nạp model, **không phải latency streaming thật**.

Bảng cuối in đủ mọi dòng. Accuracy trên mẫu nhỏ chỉ để minh hoạ; kết luận chất lượng
mô hình dùng bảng test đầy đủ ở giai đoạn 8.

### Giai đoạn 6 — Gộp cửa sổ + cảnh báo

Ba phần:

1. **Cửa sổ 1 phút trên mẫu nhỏ** — dùng `windows_from_detail(detail, 60)` và
   `eval_alerts()` đúng như job streaming. Vài bình luận thì một cửa sổ là bình thường.
2. **Cửa sổ THẬT của `verify1`**:
   - `window_1min`: 710 dòng theo phòng → gộp còn **4 cửa sổ**; cửa sổ lớn nhất có
     **1.001 bình luận, 21,9 % tiêu cực → KHÔNG vượt ngưỡng 30 %**.
   - `window_sliding_10s`: 1.466 dòng → gộp còn **23 cửa sổ**; đúng **1 cửa sổ vượt
     ngưỡng**: `18:08:30–18:08:40 UTC`, **5/13 = 38,5 % tiêu cực**.
   - Vì cửa sổ trượt chồng lấn, tổng số bình luận trong các cửa sổ là **số lượt đếm**
     (2.015), không phải số bình luận duy nhất (1.014). App ghi rõ điều này.
3. **Latency thật trên `verify1`**: p50 **2,4s**, p95 **9,6s**, p99 **27,1s** trên
   1.014 bình luận.

Bài học: cùng dữ liệu, cửa sổ 1 phút **san phẳng** đợt bùng phát ngắn; cửa sổ 10 giây
trượt mới bắt được. Đó là lý do dashboard dùng cửa sổ 10 giây cho trạng thái "hiện tại".

Mốc thời gian trong app là **giờ dữ liệu (UTC)**, không phải giờ hệ thống. Trong job
streaming thật, **watermark 2 phút** khiến cửa sổ ra chậm hơn bảng chi tiết vài phút —
đúng ngữ nghĩa event time, không phải lỗi.

### Giai đoạn 7 — Ghi sink + kiểm tra Kafka

In số dòng 4 sink của `verify1`:

| Sink | Số dòng | Nội dung |
|---|---|---|
| `scored_detail/` | 1.014 | mỗi bình luận đã chấm: nhãn, xác suất, độ trễ |
| `window_1min/` | 710 | cửa sổ 1 phút theo từng phòng |
| `window_sliding_10s/` | 1.466 | cửa sổ trượt 10 giây, slide 5 giây |
| `dlq/` | 10 | bản ghi lỗi kèm lý do |

Sau đó, nếu Kafka đang chạy, app đọc offset đầu/cuối của `comments_raw`,
`comments_scored`, `comments_dlq`. Nếu broker tắt, app báo rõ và gợi ý
`bash scripts/run_demo.sh` — không treo.

Cuối cùng app ghi kết quả lần chạy vào `outputs/terminal_demo/run_YYYYmmdd_HHMMSS/`
(trừ khi `--no-write`):

- `predictions.csv` — nhãn thật/dự đoán, xác suất, đúng/sai, latency;
- `dlq.csv` — offset, `comment_id`, lý do, ghi chú;
- `windows_sample.csv` — cửa sổ 1 phút trên mẫu;
- `run_summary.md` — tóm tắt + điều đã đo/chưa đo.

Mặc định **không ghi văn bản**; chỉ thêm cột trích đoạn khi có `--keep-text` (chỉ dùng
với dữ liệu công khai).

### Giai đoạn 8 — Tổng kết

Bảng số của chính lần chạy (số bản ghi, số DLQ, số đã chấm, accuracy trên mẫu, số cửa
sổ, cảnh báo, latency thật), chỉ số test đầy đủ lúc huấn luyện:

| Chỉ số | Giá trị |
|---|---|
| Accuracy | 0,7018 |
| Macro-F1 | 0,6233 |
| Weighted-F1 | 0,7213 |
| Số dòng test | 27.792 |

và **một dòng lưu ý trung thực** ở cuối:

> Replay IMDb, không phải livestream thật · exactly-once chưa kiểm chứng · nhãn suy
> từ rating, lớp neutral nhiễu.

Các điều đã đo / chưa kiểm chứng, giải thích đầy đủ (app chỉ in dòng ngắn ở trên):

- ✔ Đã đo: parse schema tường minh, DLQ có lý do, `clean_text` dùng chung,
  `model.transform` từng bình luận, cửa sổ theo event time.
- ✘ Dữ liệu là replay IMDb — không phải livestream thật.
- ✘ Exactly-once **chưa kiểm chứng**.
- ✘ Mẫu nhỏ không dùng để kết luận chất lượng mô hình.
- ✘ Nhãn suy từ rating IMDb, không phải nhãn cảm xúc gán tay; lớp neutral rất nhiễu.

---

## 5. Phần nào là thật, phần nào là mô phỏng

| Thành phần | Trong app | Thực tế |
|---|---|---|
| Dữ liệu | Lấy mẫu từ `clean_sample.csv` | Replay review IMDb; **không phải livestream** |
| Gửi Kafka | Chỉ in message, không gửi khi walkthrough | Producer thật: `src/producer/replay_producer.py` |
| Parse + DLQ | Chạy thật trên Spark local | Cùng hàm với job streaming |
| Làm sạch | Chạy thật | Cùng hàm với huấn luyện + streaming |
| Chấm điểm | Chạy thật bằng model đã lưu | Cùng PipelineModel |
| Cửa sổ trên mẫu | Chạy thật trên vài dòng | Cùng hàm gộp/cảnh báo |
| Cửa sổ `verify1` | Đọc file **đã đo thật** | Từ lần chạy Task 8 |
| Kafka ở giai đoạn 7 | Chỉ đọc offset nếu broker chạy | Không bắt buộc |
| Exactly-once | Không khẳng định | **Chưa kiểm chứng** |

---

## 6. Kịch bản demo 5 phút

1. **0:00** — `bash scripts/run_terminal_app.sh` (chế độ nhấn Enter).
2. **Giai đoạn 1** — chỉ vào nguồn ~1,0 GB và mẫu test; nói rõ "đây là replay".
3. **Giai đoạn 2** — mở message JSON, chỉ ra **không có `label`**.
4. **Giai đoạn 3** — chỉ bảng 4 bản ghi lỗi và dòng đối soát `N + 4`.
5. **Giai đoạn 4** — chỉ cột `khớp` toàn ✔.
6. **Giai đoạn 5** — mở 1–2 thẻ, chỉ xác suất 3 lớp và từ đóng góp; nói rõ nhãn thật
   chỉ để đối chiếu.
7. **Giai đoạn 6** — đây là điểm nhấn: cửa sổ 1 phút **không** cảnh báo, cửa sổ 10
   giây **có** cảnh báo thật 38,5 % (5/13). Giải thích watermark 2 phút và giờ UTC.
8. **Giai đoạn 7** — chỉ 4 sink và file kết quả vừa ghi.
9. **Giai đoạn 8** — đọc bảng test đầy đủ + dòng lưu ý trung thực.
10. **Kết thúc** — `bash scripts/run_comment_stream.sh --limit 5` để thấy đúng nhịp
    "comment đến → phân tích → kết quả", rồi
    `bash scripts/run_terminal_app.sh --text "not bad at all actually"` để thấy mô
    hình túi từ sai với phủ định phức tạp (neg 0,86) — một hạn chế thật, không phải
    lỗi che giấu.

Nếu muốn chạy không cần nhấn Enter khi quay video:
`bash scripts/run_terminal_app.sh --auto` (nghỉ 0,8s mỗi giai đoạn) hoặc
`--fast` (không nghỉ).

---

## 7. Tùy chọn đầy đủ

| Tùy chọn | Mặc định | Ý nghĩa |
|---|---|---|
| `--config` | `config.yaml` | file cấu hình |
| `--limit N` | 12 | số bình luận thật lấy từ tập test (tối đa 145) |
| `--cards N` | 5 | số thẻ chi tiết in ở giai đoạn 5 |
| `--seed N` | theo config (42) | seed lấy mẫu |
| `--auto` | tắt | không dừng chờ Enter |
| `--fast` | tắt | như `--auto`, không nghỉ giữa giai đoạn |
| `--delay S` | 0,8 | giây nghỉ giữa giai đoạn khi `--auto` |
| `--stage N` | tắt | chỉ chạy một giai đoạn 1–8 |
| `--one-by-one` | tắt | chạy từng comment, in kết quả ngay (dùng qua `run_comment_stream.sh`) |
| `--interval S` | 1,0 | giây nghỉ giữa các comment ở `--one-by-one` |
| `--no-bad` | tắt | không chèn 4 bản ghi lỗi cố ý ở `--one-by-one` |
| `--text "..."` | — | chỉ chấm một câu rồi thoát; thêm `--auto` để walkthrough trước |
| `--interactive` | tắt | nhập nhiều câu để chấm rồi thoát; thêm `--auto` để walkthrough trước |
| `--live` | tắt | theo dõi 3 topic Kafka (không chạy walkthrough) |
| `--duration S` | 60 | số giây theo dõi ở `--live` |
| `--no-color` | tắt | tắt màu ANSI |
| `--no-write` | tắt | không ghi `outputs/terminal_demo/` |
| `--keep-text` | tắt | ghi thêm trích đoạn văn bản vào CSV (chỉ dữ liệu công khai) |
| `--no-kafka-check` | tắt | bỏ qua kiểm tra Kafka ở giai đoạn 7 |

---

## 8. Lỗi thường gặp

| Hiện tượng | Nguyên nhân / cách xử lý |
|---|---|
| `ModuleNotFoundError: pyspark` | Chạy sai Python. Luôn dùng `bash scripts/run_terminal_app.sh` (script tự `source scripts/env.sh` và dùng `.venv/bin/python`). |
| Spark báo lỗi Java | Cần Java 8 cho Spark: `java -version`; xem `scripts/env.sh`. |
| `Không thấy outputs/models/sentiment_pipeline` | Chưa huấn luyện: chạy `bash scripts/run_training.sh` (hoặc lấy model từ máy gốc). |
| `Không thấy outputs/stream/verify1` | Chưa có lần chạy Task 8; giai đoạn 6 sẽ bỏ qua phần dữ liệu thật. |
| `--live` báo `Unable to bootstrap` | Kafka chưa chạy: mở terminal khác chạy `bash scripts/run_demo.sh`, hoặc dùng `--no-kafka-check` cho walkthrough. |
| Chữ bị cắt/không màu | Terminal hẹp hoặc đang pipe; dùng terminal ≥ 100 cột, bỏ `--no-color` khi xem trực tiếp. |
| Muốn xem lệnh không cần Enter | Thêm `--auto` hoặc `--fast`. |

---

## 9. Liên hệ với dashboard Streamlit

| | Streamlit (`src/app/app.py`) | Terminal (`src/app/terminal_app.py`) |
|---|---|---|
| Mục đích | Dashboard gần thời gian thực, 3 tab | Walkthrough từng bước của toàn bộ pipeline |
| Cần Kafka | Không (đọc Parquet) | Không (walkthrough); `--live` thì có |
| Cần trình duyệt | Có | Không |
| Dữ liệu | `outputs/stream/<run>/` | Mẫu test + `verify1` + 4 lỗi cố ý |
| Điểm mạnh khi báo cáo | Trực quan, biểu đồ, thao tác | Nhìn rõ từng bước, từng bản ghi, từng lý do DLQ |

Hai app dùng **cùng model, cùng hàm làm sạch, cùng quy tắc cảnh báo** — terminal app
không phải bản minh hoạ riêng.
