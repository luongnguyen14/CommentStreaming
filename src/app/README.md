# src/app — Dashboard gần thời gian thực (Task 10, Day 10)

`app.py` là dashboard Streamlit 3 tab cho luồng chấm điểm cảm xúc:
**Live Monitor** (đọc Parquet cửa sổ do job streaming ghi) · **Try It** (chấm điểm
một câu nhập tay bằng `PipelineModel`) · **About** (pipeline, dữ liệu replay, hạn
chế mô hình, quyền riêng tư).

Dashboard **không dùng Spark ở tab Live Monitor** — nó chỉ đọc file Parquet mà job
streaming (Task 8) đã ghi. Nhờ vậy xem dashboard không làm chậm job và ngược lại.
Spark chỉ được dựng ở tab Try It, và chỉ khi người dùng thực sự bấm "Phân tích".

## Chương trình thử nghiệm mô hình — `model_trial.py`

Đây là phần **"thử nghiệm mô hình"** (prototype), tách khỏi app hoàn chỉnh: chạy
được bằng một lệnh, **không cần Kafka, không cần Streamlit**, chỉ cần model đã lưu
trong `outputs/models/`. Nó đi đúng đường của hệ thống thật:
`văn bản thô → clean_text() → PipelineModel → nhãn + xác suất`.

```bash
bash scripts/run_model_trial.sh                     # nhập bình luận tương tác (:q thoát, :sample ví dụ)
bash scripts/run_model_trial.sh --examples          # 4 câu ví dụ trong config.yaml
bash scripts/run_model_trial.sh --text "not bad"    # chấm một câu
bash scripts/run_model_trial.sh --test-sample 200   # đo trên 200 dòng tập test (có nhãn thật)
```

Chế độ `--test-sample` sinh báo cáo tiếng Anh `outputs/model_trial_report.md` + hai
bảng trong `outputs/tables/`; mọi số lấy từ chính lần chạy. Quy tắc loại văn bản
(rỗng / quá ngắn / quá dài) giống hệt DLQ của streaming. Mặc định **không ghi văn
bản** vào file; chỉ dùng `--keep-text` với dữ liệu công khai.

> Đây vẫn là **review IMDb phát lại**, không phải bình luận livestream thật. Báo cáo
> phải nói rõ (xem `docs/huong_dan_bao_cao.md`).

## App terminal — xem toàn bộ quy trình ngay trong terminal

`terminal_app.py` là bản **walkthrough 8 giai đoạn** chạy thẳng trong terminal Ubuntu,
dùng đúng code của hệ thống (không viết lại logic): lấy mẫu review → đóng gói message
→ `from_json` + DLQ → `clean_text()` → `PipelineModel` → cửa sổ event time → sink
Parquet → tổng kết. Mỗi giai đoạn in ra dữ liệu thật của chính lần chạy đó.

```bash
bash scripts/run_terminal_app.sh                     # từng giai đoạn, nhấn Enter
bash scripts/run_terminal_app.sh --auto              # tự chạy liên tục
bash scripts/run_terminal_app.sh --fast --limit 20   # nhanh, 20 bình luận
bash scripts/run_terminal_app.sh --stage 5           # chỉ giai đoạn chấm điểm
bash scripts/run_terminal_app.sh --text "not bad at all actually"   # chấm một câu
bash scripts/run_terminal_app.sh --interactive       # nhập nhiều câu để chấm
bash scripts/run_terminal_app.sh --live --duration 60  # theo dõi 3 topic Kafka
```

- **Không cần Kafka** ở chế độ walkthrough (mặc định): chỉ cần model đã lưu và
  `outputs/tables/clean_sample.csv`. Chế độ `--live` mới cần broker đang chạy.
- Không chạy lại job streaming; app **mô phỏng** phần thu thập bằng replay và dùng
  đúng `parse_stream`, `add_cleaning_and_reason`, `clean_text`, `PipelineModel`,
  `windows_from_detail`, `eval_alerts` của hệ thống.
- Kết quả mỗi lần chạy (trừ khi `--no-write`) ghi vào
  `outputs/terminal_demo/run_YYYYmmdd_HHMMSS/`: `predictions.csv`, `dlq.csv`,
  `windows_sample.csv`, `run_summary.md`.
- **Độ trễ trong app là độ trễ mô phỏng offline** (gồm khởi động Spark/nạp model),
  không phải latency streaming thật. Latency thật của `verify1` đo ở giai đoạn 6.
- Nhãn thật chỉ hiện ở giai đoạn 5/8 để đối chiếu, lấy từ sidecar — **không đi vào
  message, không đi vào model**.

Hướng dẫn chi tiết từng giai đoạn + kịch bản demo: `docs/huong_dan_terminal_app.md`.

## Cách chạy

### Cách 1 — cả hệ thống bằng một lệnh (khuyến nghị khi demo)

```bash
bash scripts/run_demo.sh                 # Kafka → topic → job streaming → producer → dashboard
bash scripts/run_demo.sh --duration 600  # tự dừng sạch sau 10 phút
bash scripts/run_demo.sh --stop          # dừng sạch mọi thứ (kể cả Kafka)
bash scripts/run_demo.sh --help
```

Script khởi động theo đúng thứ tự bắt buộc (Kafka trước, job phải READY trước khi
producer gửi bản ghi đầu, dashboard sau cùng) và dừng theo thứ tự ngược lại.
Log: `logs/task10_dashboard_demo.log`, `logs/task10_producer_demo.log`,
`logs/task8_stream_demo.log`.

### Cách 2 — chỉ chạy dashboard (dữ liệu đã có sẵn)

```bash
source scripts/env.sh
$VENV_PY -m streamlit run src/app/app.py --server.address 0.0.0.0 --server.port 8501
```

Mở `http://localhost:8501`. Sidebar cho chọn **lần chạy** trong `outputs/stream/`
(ví dụ `verify1` của Task 8 nếu chưa chạy demo), nhịp tự làm mới, ngưỡng cảnh báo.

> Lệnh trên chạy được từ **bất kỳ thư mục nào**: `app.py` tự thêm gốc dự án vào
> `sys.path` dựa trên vị trí file, và mọi đường dẫn suy ra từ `config.yaml`
> (`src.common.utils.PROJECT_ROOT`) — **không có đường dẫn tuyệt đối nào hard-code**.

## Ba tab

| Tab | Nội dung | Nguồn số liệu |
|---|---|---|
| **Live Monitor** | Biểu ngữ cảnh báo (ngưỡng chỉnh ở sidebar), 4 chỉ số (số bình luận cửa sổ hiện tại, tỷ lệ tiêu cực kèm so sánh với nền tập test 25,1 %, độ trễ trung bình + p95, bình luận/phút), 3 biểu đồ (cơ cấu cảm xúc cửa sổ mới nhất, cảm xúc theo phút, số bình luận theo phút), bảng 10 bình luận mới nhất **đã che** | `outputs/stream/<run>/window_sliding_10s`, `window_1min`, `scored_detail` |
| **Try It** | Nhãn dự đoán + xác suất từng lớp + các từ đóng góp nhiều nhất (mô hình tuyến tính) + văn bản sau khi làm sạch | `outputs/models/sentiment_pipeline` (nạp một lần nhờ `st.cache_resource`) |
| **About** | Sơ đồ pipeline, nói rõ phần nào là **replay**, bảng Precision/Recall/F1 từng lớp, 6 hạn chế đã biết, quy ước riêng tư | `outputs/tables/per_class_metrics.csv`, `outputs/models/sentiment_pipeline_metadata.json` |

Cảnh báo dùng **đúng quy tắc đã đo ở Task 9**: `share_negative > ngưỡng` **và**
`n_comments >= 5`. Điều kiện thứ hai bắt buộc — cửa sổ 1 bình luận luôn cho 0 % hoặc
100 %; đo trên `verify1` thấy bỏ điều kiện này sinh 13 báo động giả (xem
`outputs/insights.md` hình 12 và test `test_alert_tren_du_lieu_that_verify1`).

## Ba điều phải biết trước khi demo (không phải lỗi)

1. **Cửa sổ ra chậm ~2–3 phút.** Job có watermark 2 phút: cửa sổ 1 phút chỉ được ghi
   sau khi watermark vượt mốc kết thúc cửa sổ. Trong vài phút đầu, `window_1min`
   còn rỗng trong khi `scored_detail` đã có dữ liệu — dashboard tự chuyển sang tính
   từ bảng chi tiết và **ghi rõ lý do** trên giao diện (dòng "Cửa sổ 1 phút đang
   chậm hơn bảng chi tiết **N giây**…"). Mốc thời gian luôn là **thời gian dữ liệu
   (UTC)**, không phải giờ hệ thống — dữ liệu replay không xảy ra "bây giờ".
2. **Khung "bình luận mới nhất" cần `--keep-text`.** Mặc định job **không lưu văn
   bản** (`streaming.privacy.keep_text: false`, CLAUDE.md §7). `run_demo.sh` bật
   `--keep-text` vì dữ liệu demo là review IMDb công khai; nếu chạy job không có cờ
   đó, dashboard vẫn chạy và hiện cảnh báo giải thích thay vì bảng rỗng khó hiểu.
3. **Không hiện mã người dùng.** `user_hash` không bao giờ được đưa lên giao diện;
   mã bình luận chỉ hiện khi tự bật ô "Hiện mã bình luận (truy vết)" ở sidebar. Từ
   nhạy cảm thay bằng `***`, email/số điện thoại bằng `[đã che]` (danh sách ở
   `config.yaml → dashboard.mask_words` / `mask_patterns`).

## Hướng dẫn mở dashboard từ MÁY THẬT (port forwarding VirtualBox)

> Muốn chia sẻ cho máy khác qua LAN, qua Internet (ngrok/Cloudflare) hoặc cài độc lập
> trên máy mới? Xem [`docs/huong_dan_share_streamlit.md`](../../docs/huong_dan_share_streamlit.md).

Máy ảo có IP riêng; trình duyệt trên máy thật không vào được `localhost:8501` của
máy ảo. Ba cách, chọn **một**:

### Cách A — NAT + Port Forwarding (mặc định của VirtualBox, không cần đổi mạng)

1. Trong VirtualBox, chọn máy ảo → **Settings** → **Network** → tab **Adapter 1**
   (đang để *Attached to: NAT*) → mở **Advanced** (nút tam giác) → **Port Forwarding**.
2. Bấm biểu tượng **+** (thêm rule) và điền:
   | Trường | Giá trị |
   |---|---|
   | Name | `streamlit` |
   | Protocol | `TCP` |
   | Host IP | *(để trống)* |
   | Host Port | `8501` |
   | Guest IP | *(để trống)* |
   | Guest Port | `8501` |
3. **OK** → **OK**. Rule có hiệu lực ngay, **không cần khởi động lại máy ảo**.
4. Trên máy thật mở: **http://localhost:8501**

Lưu ý: phải để `--server.address 0.0.0.0` (đúng như `run_demo.sh` chạy) để
Streamlit lắng nghe trên mọi card mạng; nếu chỉ nghe `127.0.0.1` thì port forwarding
không tới được.

### Cách B — Bridged Adapter (máy ảo có IP cùng dải mạng máy thật)

Settings → Network → Adapter 1 → *Attached to:* **Bridged Adapter** → chọn card mạng
thật (Wi‑Fi/Ethernet). Khởi động lại máy ảo, xem IP bằng `hostname -I` (script
`run_demo.sh` in ra IP này), rồi trên máy thật mở `http://<IP-máy-ảo>:8501`.
Dùng cách này khi muốn **điện thoại trong cùng Wi‑Fi** cũng mở được (hữu ích khi
quay video demo).

### Cách C — không cần forwarding: trình duyệt **trong** máy ảo

Mở Firefox/Chromium trong máy ảo → `http://localhost:8501`. Đơn giản nhất để chụp
ảnh, nhưng chụp xong thì ảnh có giao diện máy ảo.

### Kiểm tra nhanh khi không mở được

```bash
# Trong máy ảo: dashboard có trả lời không (chỉ kiểm tra, không cần trình duyệt)
curl -s http://localhost:8501/_stcore/health          # phải in ra: ok
ss -ltnp | grep 8501                                   # phải thấy 0.0.0.0:8501
```
- `127.0.0.1:8501` thay vì `0.0.0.0:8501` → thiếu `--server.address 0.0.0.0`.
- `ok` nhưng máy thật vẫn không vào → sai rule port forwarding (sai Guest Port) hoặc
  firewall trên máy thật chặn.

## Chụp ảnh / quay màn hình để đưa vào báo cáo

**Chụp ảnh (ảnh tĩnh đưa vào báo cáo/slide):**

1. Chuẩn bị **trước khi chụp**: chạy `bash scripts/run_demo.sh` và đợi **≥ 3 phút**
   để (a) có dữ liệu trong bảng chi tiết, (b) cửa sổ 1 phút đầu tiên đã ra sau
   watermark. Nhìn dòng "dữ liệu đến HH:MM:SS UTC" ở đầu tab Live Monitor — nếu số
   bình luận còn < 100 thì chưa nên chụp.
2. Ở sidebar, chọn ngưỡng cảnh báo để **có một lần biểu ngữ đỏ** đáng chụp (hạ
   ngưỡng xuống ~15–20 % trong lúc demo để thấy cơ chế hoạt động, rồi **nói rõ
   trong báo cáo** là ngưỡng lúc chụp khác mặc định) — hoặc chụp cả hai trạng thái:
   biểu ngữ xanh (không cảnh báo) và biểu ngữ đỏ (cảnh báo).
3. Chụp theo thứ tự gợi ý (3–5 ảnh là đủ cho báo cáo):
   - Ảnh 1: toàn trang Live Monitor (biểu ngữ + 4 chỉ số + biểu đồ).
   - Ảnh 2: khung 10 bình luận mới nhất (thấy rõ `***`/`[đã che]` và cột phòng).
   - Ảnh 3: tab Try It với **câu ví dụ số 2** (`it was okay, nothing special. 6/10`) — đây
     là ảnh đắt giá nhất: mô hình trả **trung lập 99 %** và từ đóng góp lớn nhất là chính
     token `6/10`, tức nó **đọc điểm số** thay vì hiểu cảm xúc (đúng phát hiện Task 7).
     (Câu ví dụ số 4 — câu mỉa mai — **đo ra lại đúng** (tích cực 86 %); đừng dùng nó để
     minh hoạ "mô hình sai", sẽ bị hỏi ngược.)
   - Ảnh 4: tab About (bảng Precision/Recall/F1 từng lớp).
   - Ảnh 5 (nếu báo cáo cần): `ls -la outputs/stream/demo/` hoặc biểu đồ trong
     `outputs/figures/` — số liệu tĩnh bổ trợ cho ảnh dashboard.
4. Cách chụp: trên máy thật dùng **`PrtScn`** (Windows, lưu vào
   `Pictures\Screenshots`), **`Cmd+Shift+4`** (macOS), hoặc trong Ubuntu/GNOME dùng
   `PrtScn` / `Shift+PrtScn` (chọn vùng). Muốn chụp **chỉ cửa sổ trình duyệt**:
   `Alt+PrtScn`. Ảnh nên ≥ 1280 px chiều rộng để chữ trong biểu đồ còn đọc được khi
   in; nếu chụp bằng điện thoại thì để ngang và tránh bóng màn hình.

**Quay màn hình (video demo 2–3 phút):**

1. Công cụ: **`Ctrl+Alt+Shift+R`** trên GNOME (GNOME Screen Recording) → xuất file
   `.webm` ở `~/Videos`; hoặc OBS (`sudo apt install obs-studio`) nếu cần thu cả
   tiếng nói. Trên máy thật: Windows `Win+G`, macOS `Cmd+Shift+5`.
2. Kịch bản gợi ý (quay **một mạch**, không cắt ghép — dễ bị coi là dàn dựng):
   - 0:00 — mở terminal máy ảo, chạy `bash scripts/run_demo.sh`, chỉ vào các bước
     Kafka → job → producer → dashboard đang lên.
   - 0:30 — mở dashboard trên máy thật qua `http://localhost:8501`, chỉ vào cột
     "dữ liệu đến … UTC" đang **tăng dần** (chứng minh là luồng, không phải ảnh).
   - 1:00 — để Live Monitor tự làm mới 2–3 nhịp; chỉ vào cảnh báo watermark (nếu có).
   - 1:30 — sang tab Try It, nhập 1 câu **tự nghĩ** (không dùng nút ví dụ) để thấy
     đúng độ trễ thật của lần chấm đầu (~15–30 s dựng Spark) rồi lần thứ hai nhanh.
   - 2:00 — lật tab About, nói rõ **"dữ liệu là replay, không phải livestream thật"**
     và nêu 1–2 hạn chế (mỉa mai, lớp trung lập yếu).
   - 2:30 — `Ctrl+C` ở terminal → chỉ vào log cho thấy các thứ dừng êm.
3. Trong báo cáo, **ghi rõ mọi con số hiện trên video đều là dữ liệu replay** và dẫn
   nguồn file (`outputs/stream/demo/`) — không trích số trong video như số của
   livestream thật (CLAUDE.md §9).

## Số đo thật của 4 câu ví dụ ở tab Try It (15/10/2026)

Bốn câu trong `config.yaml → dashboard.try_it_examples` đã được chạy qua
`PipelineModel` hiện tại; kết quả **tất định** (cùng mô hình ⇒ cùng kết quả):

| Câu ví dụ | Nhãn mô hình | Xác suất | Từ đóng góp mạnh nhất |
|---|---|---|---|
| `not bad at all actually, quite enjoyable` | neutral | 0,80 | `actually,` +0,73 · `enjoyable` +0,51 |
| `it was okay, nothing special. 6/10` | neutral | **0,99** | **`6/10` +3,27** · `special.` +0,64 |
| `the acting is good. the story is very much lacking` | neutral | 0,66 | `lacking` +0,97 · `good.` +0,21 |
| `his 'bad acting' had me crying with laughter, absolutely brilliant` | positive | 0,86 | `laughter,` +1,07 · `brilliant` +0,63 |

Hai điều đọc ra từ bảng này, dùng được luôn khi báo cáo:
- **Câu 2 chứng minh mô hình "đọc điểm số"**: token `6/10` đóng góp +3,27, lớn hơn mọi từ
  cảm xúc — đúng phát hiện ở `outputs/modeling_summary.md` §5 và `top_features.csv`.
- **Câu 4 (mỉa mai) lại ĐÚNG** — nên đừng lấy nó làm ví dụ "mô hình sai vì mỉa mai";
  hạn chế mỉa mai vẫn đúng về nguyên tắc (TF-IDF không có ngữ cảnh) nhưng phải nói là
  *hạn chế của phương pháp*, không phải kết quả đo được trên câu này.

## Kiểm thử

```bash
source scripts/env.sh
.venv/bin/python -m pytest tests/test_dashboard.py -q    # 21 test: gộp cửa sổ, cảnh báo, che dữ liệu, biểu đồ
```

Test dùng cả dữ liệu giả (ép các trường hợp biên) lẫn `outputs/stream/verify1` thật
(khoá lại con số Task 9: đúng 1 cửa sổ vượt ngưỡng 38,46 % / 13 bình luận).
