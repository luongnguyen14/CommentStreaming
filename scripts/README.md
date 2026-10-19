# scripts/ — Script điều khiển

## Demo toàn hệ thống (Task 10)

- `run_demo.sh` — khởi động **cả hệ thống** theo đúng thứ tự bắt buộc và dừng sạch bằng một lệnh:

  ```bash
  bash scripts/run_demo.sh                    # Kafka → topic → job streaming → producer replay → dashboard
  bash scripts/run_demo.sh --duration 600     # tự dừng sạch sau 10 phút
  bash scripts/run_demo.sh --sample 5000 --rate 30
  bash scripts/run_demo.sh --stop             # dừng sạch mọi thứ (kể cả Kafka)
  bash scripts/run_demo.sh --stop --keep-kafka
  bash scripts/run_demo.sh --help
  ```

  - **Thứ tự quan trọng**: Kafka phải sống trước; job streaming phải in `READY` trước khi
    producer gửi bản ghi đầu (job đọc `startingOffsets=latest`, bản ghi gửi sớm hơn mốc gắn
    offset sẽ bị bỏ qua); dashboard lên sau cùng (không cần Spark — chỉ đọc Parquet).
  - Job demo chạy kèm `--keep-text` để dashboard có khung "bình luận mới nhất" — **chỉ hợp lệ
    vì dữ liệu demo là review IMDb công khai**. Khi thu bình luận thật thì KHÔNG dùng cờ này
    (CLAUDE.md §7).
  - Dừng theo thứ tự ngược lại (dashboard → producer → job → Kafka) để không còn ai ghi vào
    sink sau khi job tắt; SIGTERM cho job để nốt micro-batch và ghi checkpoint.
  - PID/log: `logs/task10_dashboard_demo.{pid,log}`, `logs/task10_producer_demo.{pid,log}`,
    `logs/task8_stream_demo.{pid,log}`. `Ctrl+C` ở tiền cảnh cũng dừng sạch (có trap).
  - Chạy lại **cùng tên** sẽ tiếp tục từ checkpoint cũ và cộng dồn vào `outputs/stream/<tên>`;
    muốn bắt đầu lại từ đầu thì xoá `outputs/stream/<tên>` + `checkpoints/streaming/<tên>`.

  Hướng dẫn mở dashboard từ máy thật (port forwarding VirtualBox) và cách chụp ảnh/quay
  màn hình cho báo cáo: xem `src/app/README.md`.

## Môi trường

- `env.sh` — biến môi trường dùng chung: Java 8, Spark 3.5.9, Python 3.11 cho PySpark.
  Các script khác `source scripts/env.sh` trước khi chạy.
- `check_env.sh` — kiểm tra nhanh Java/HDFS/Spark/pandas/streamlit; thêm `--smoke` để chạy thử SparkSession thật.

**Lưu ý vận hành:**

- HDFS **không tự chạy lại sau khi khởi động máy**: chạy `/usr/local/hadoop/sbin/start-dfs.sh` trước khi dùng Spark.
  Spark ghi event log lên `hdfs://localhost:9000/spark-logs`; HDFS tắt thì Spark báo lỗi kết nối `localhost:9000`
  (đã gặp thật 15/10/2026 sau khi VM reboot).
- **`run_stream.sh` tự xử lý hai ca HDFS, không cần làm gì thêm** (sửa 15/10/2026):
  - **HDFS tắt** → chạy job với `--conf spark.eventLog.enabled=false` **cho riêng lần đó** (không sửa
    `spark-defaults.conf` vì file đó dùng chung). Job **vẫn chạy bình thường**: sink và checkpoint đều
    nằm trên **ổ đĩa cục bộ** (`config.yaml`: `sink_root`, `checkpoint_root`) — HDFS **chỉ** dùng cho
    event log. Đổi lại, Spark History Server (cổng 18080) **không có** lần chạy đó.
  - **HDFS vừa `start-dfs.sh` còn ở safe mode** → `hdfs dfs -ls` **vẫn chạy được** (chỉ đọc) nhưng tạo
    `/spark-logs` sẽ ném `SafeModeException`, nên script **chờ tối đa 90 s** cho safe mode tắt
    (`hdfs dfsadmin -safemode get`), rồi chạy với event log bật bình thường.
- `start-dfs.sh` cần ssh không mật khẩu tới localhost. Khóa `~/.ssh/id_rsa` có passphrase nên không dùng được ở chế độ
  tự động — đã tạo thêm khóa `~/.ssh/id_ed25519` (không passphrase, 14/10/2026) và thêm vào `~/.ssh/authorized_keys`.
- **Push GitHub** (`git@github.com:luongnguyen14/CommentStreaming`) cần khóa `~/.ssh/id_rsa` — khóa này có passphrase,
  mà agent của GNOME keyring (`/run/user/1002/gcr/ssh`) từ chối ký khi lệnh chạy không có phiên đồ họa
  (`agent refused operation`). Cách chạy được: mở terminal user `hadoop`, `ssh-add ~/.ssh/id_rsa` (nhập passphrase),
  rồi `git push` từ đó; hoặc nạp khóa vào một `ssh-agent` thường và trỏ `SSH_AUTH_SOCK` vào socket của nó.
  Khóa `id_ed25519` **chưa** đăng ký với GitHub nên không thay thế được.

## Script tạo tài liệu nộp

Các script dưới đây **copy template của cô từ `TEMPLATES_DIR` sang `deliverables/` rồi mới điền**
(không bao giờ sửa file gốc). Chạy lại được nhiều lần, mỗi lần ghi đè bản trong `deliverables/`.

- `fill_action_plan.py` — điền Action Plan (Task 2)
- `fill_wbs.py` — điền WBS 20 ngày: ngày D1–D20, phân công, Gantt (Task 3)
- `fill_proposal_slides.py` — dựng slide đề xuất 5 trang từ Slide Template (Task 4);
  giữ nguyên master/layout/màu/font, vẽ sơ đồ kiến trúc bằng shape của PowerPoint,
  ghi chú thuyết trình ~3 phút/slide
- `install_template_fonts.py` — giải mã + cài font của template (chỉ cần chạy lại nếu đổi máy)

## Script streaming (Task 8)

- `env.sh` (đã có ở trên) chứa `SPARK_KAFKA_PKG=org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.9`
  — **phải khớp** phiên bản Spark/Scala; gói đã nằm trong `~/.ivy2/jars` nên chạy được khi không có mạng.
- `run_stream.sh <tên-lần-chạy> [tham số của stream_job.py ...]` — kiểm tra trước khi chạy
  (đã có job cùng tên? Kafka ở `localhost:9092`? HDFS sống? còn safe mode?), chạy `spark-submit`
  ở nền và **chờ tới khi job in `READY`** mới trả về (để bên phát dữ liệu không gửi sớm hơn mốc
  offset). HDFS tắt **không** làm job dừng — xem mục "Lưu ý vận hành" ở trên.
  Log `logs/task8_stream_<tên>.log`, PID `logs/task8_stream_<tên>.pid`.
- `stop_stream.sh <tên-lần-chạy>` — dừng **êm**: SIGTERM cho tiến trình Python của driver
  (con của JVM `spark-submit`) → handler gọi `query.stop()` cho từng query. Không dùng `kill -9`.
- `send_bad_events.py` — gửi 10 ca lỗi đã biết (`bad-01`…`bad-10`) để kiểm chứng nhánh DLQ,
  thêm `--heartbeat N --heartbeat-interval S` (bản ghi hợp lệ đẩy watermark tiến) và
  `--late-probe` (bản ghi hợp lệ lạc hậu 10 phút, phải bị watermark bỏ). `--dry-run` để xem trước.

Quy trình kiểm chứng đầy đủ (đã chạy thật, số liệu ở `outputs/streaming_summary.md`):

```bash
$VENV_PY src/streaming/verify_stream.py --record-baseline --run-name verify1   # ghi mốc offset
bash scripts/run_stream.sh verify1 --sink-dir outputs/stream/verify1 \
     --checkpoint-root checkpoints/streaming/verify1 --trigger-seconds 5
$VENV_PY src/producer/replay_producer.py --only-test --max 1000 --rate 50 \
     --labels-out outputs/stream/verify1/sent_labels.parquet
$VENV_PY scripts/send_bad_events.py --heartbeat 12 --heartbeat-interval 25 --late-probe
bash scripts/stop_stream.sh verify1
# rồi chạy verify_stream.py (không có --record-baseline) để đối chiếu + tính macro-F1
```

## Script kiểm tra mô hình

- `check_model.py` — nạp lại `outputs/models/sentiment_pipeline` bằng `PipelineModel.load`,
  chạy `clean_text()` rồi dự đoán 5 câu thử tiếng Anh, in lớp + xác suất. Dùng để xác nhận
  đường đi mà Task 8 (streaming) sẽ dùng:
  `PYSPARK_DRIVER_PYTHON=$VENV_PY PYSPARK_PYTHON=$VENV_PY spark-submit --driver-memory 2g --master 'local[2]' scripts/check_model.py`
- `run_model_trial.sh` — **chương trình thử nghiệm mô hình** dùng khi báo cáo/demo, không cần
  Kafka và không cần Streamlit. Chạy `src/app/model_trial.py` bằng Python của venv (không gọi
  thẳng `spark-submit` vì lệnh đó nuốt stdin, làm chế độ tương tác không nhận được câu nhập):
  ```bash
  bash scripts/run_model_trial.sh                     # nhập bình luận tương tác
  bash scripts/run_model_trial.sh --examples          # 4 câu ví dụ trong config.yaml
  bash scripts/run_model_trial.sh --text "not bad"    # chấm một câu
  bash scripts/run_model_trial.sh --test-sample 200   # đo trên 200 dòng tập test
  ```
  Chế độ `--test-sample` ghi `outputs/tables/model_trial_predictions.csv`,
  `model_trial_summary.csv` và `outputs/model_trial_report.md`. Script tự tắt event log
  (không cần HDFS) và dùng `conf/log4j2.properties` để bớt dòng INFO.

## Script vẽ biểu đồ

- `make_pipeline_diagram.py` — vẽ sơ đồ kiến trúc pipeline (Task 5) →
  `outputs/figures/00_pipeline_architecture.png` (200 dpi, chữ tiếng Anh, dùng chung
  bảng màu ở `src/common/plotting.py`). Số liệu in trên hình lấy từ
  `outputs/tables/ingestion_report.csv` và `logs/task5_1000msg_*.log`.

Sau khi chạy, **luôn kiểm tra bố cục** theo quy ước CLAUDE.md §11: chuyển PDF bằng
`soffice --headless --convert-to pdf` rồi soát trang trắng và render ảnh.

**Lỗi đã biết của template PPTX khi render bằng LibreOffice** (gặp ở Task 4):

1. Đặt `shape.height` cho placeholder **kế thừa vị trí từ layout** làm python-pptx ghi ra
   `<a:ext cx="0">` → chữ biến mất. Phải "materialize" `left/top/width` từ layout trước
   (xem `materialize_geometry` trong `fill_proposal_slides.py`).
2. Font thương hiệu (Samsung Sharp Sans) bị LibreOffice thay thế glyph sai ở ngữ cảnh
   *chữ thường + dấu cách + chữ số*: `Team 6` → `Tea 6` + ô vuông ☒, và lỗi này vào cả PDF.
   Cách chữa: tách cụm chữ số thành run riêng (`set_para_text_safe_digits`).
3. Xoá slide chỉ xoá quan hệ, part vẫn nằm trong gói → `add_slide` có thể ghi đè part đang
   dùng (2 slide trùng nội dung). Phải nhân bản slide trước, xoá sau.
