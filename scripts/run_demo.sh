#!/usr/bin/env bash
# run_demo.sh — Chạy TOÀN BỘ hệ thống demo (Task 10) bằng MỘT lệnh, dừng sạch bằng MỘT lệnh.
#
#   bash scripts/run_demo.sh                     # Kafka → topic → job streaming → producer → dashboard
#   bash scripts/run_demo.sh --duration 600      # tự dừng sạch sau 10 phút
#   bash scripts/run_demo.sh --sample 5000       # phát lại 5.000 bình luận rồi lặp
#   bash scripts/run_demo.sh --stop              # dừng sạch mọi thứ (kể cả Kafka)
#   bash scripts/run_demo.sh --stop --keep-kafka # dừng dashboard/job/producer, giữ Kafka
#   bash scripts/run_demo.sh --help
#
# THỨ TỰ có ý nghĩa, không phải cho đẹp:
#   1. Kafka phải sống trước (producer không có chỗ gửi);
#   2. job streaming phải READY trước khi producer gửi bản ghi đầu — job đọc
#      `starting_offsets: latest` (config.yaml) nên mọi bản ghi gửi trước khi job
#      gắn offset nguồn sẽ bị BỎ QUA (không phải lỗi, chỉ là mất dữ liệu demo);
#   3. dashboard lên sau cùng, và không cần Spark — nó chỉ đọc Parquet đã ghi.
#
# Job streaming chạy với `--keep-text`: giữ văn bản đã làm sạch để khung "bình luận
# mới nhất" của dashboard có nội dung. CHỈ hợp lệ vì dữ liệu demo là review IMDb
# CÔNG KHAI (CLAUDE.md §7) — khi thu bình luận thật thì KHÔNG dùng cờ này.
#
# Dừng êm: script dừng theo thứ tự ngược lại (dashboard → producer → job) để không
# còn ai ghi vào sink sau khi job đã tắt; SIGTERM cho job để nốt micro-batch hiện tại
# và ghi checkpoint (xem scripts/stop_stream.sh).

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$HERE/.." && pwd)"
# shellcheck disable=SC1091
source "$HERE/env.sh"

RUN="demo"
PORT=8501
RATE=""                 # rỗng = theo config.yaml (replay.rate)
SAMPLE=2000
DURATION=0              # 0 = chạy tới khi Ctrl+C / --stop
KEEP_KAFKA=0
DO_STOP=0
STREAM_EXTRA=()

usage() {
  sed -n '2,24p' "$HERE/run_demo.sh" | sed 's/^# \{0,1\}//'
  cat <<'EOF'

Tuỳ chọn:
  --run TÊN        tên lần chạy streaming (mặc định: demo) — cũng là tên thư mục
                   outputs/stream/<TÊN> và checkpoints/streaming/<TÊN>
  --port N         cổng dashboard (mặc định: 8501)
  --rate N         bình luận/giây của producer (mặc định: theo config.yaml = 50)
  --sample N       số bình luận lấy từ nguồn rồi phát lặp (mặc định: 2000)
  --duration N     tự dừng sạch sau N giây (mặc định: 0 = chạy tới khi dừng tay)
  --keep-kafka     khi dừng thì GIỮ Kafka chạy (mặc định: dừng cả Kafka)
  --stop           dừng sạch những gì script này khởi động rồi thoát
  -- <tham số...>  phần còn lại truyền thẳng cho src/streaming/stream_job.py
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --run) RUN="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --rate) RATE="$2"; shift 2 ;;
    --sample) SAMPLE="$2"; shift 2 ;;
    --duration) DURATION="$2"; shift 2 ;;
    --keep-kafka) KEEP_KAFKA=1; shift ;;
    --stop) DO_STOP=1; shift ;;
    --help|-h) usage; exit 0 ;;
    --) shift; STREAM_EXTRA=("$@"); break ;;
    *) echo "Tham số lạ: $1 (xem --help)" >&2; exit 2 ;;
  esac
done

DASH_PID_FILE="$PROJECT_ROOT/logs/task10_dashboard_${RUN}.pid"
DASH_LOG="$PROJECT_ROOT/logs/task10_dashboard_${RUN}.log"
PROD_PID_FILE="$PROJECT_ROOT/logs/task10_producer_${RUN}.pid"
PROD_LOG="$PROJECT_ROOT/logs/task10_producer_${RUN}.log"
mkdir -p "$PROJECT_ROOT/logs"

# --- dừng một tiến trình theo file PID (SIGTERM trước, -KILL chỉ khi cứng đầu) ---
stop_pidfile() {  # $1=file PID  $2=tên hiển thị
  local f="$1" name="$2" pid i
  [ -f "$f" ] || { echo "  • $name: không có file PID ($f) — bỏ qua"; return 0; }
  pid="$(cat "$f" 2>/dev/null || true)"
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    echo "  • $name: không còn chạy (PID ${pid:-?}) — xoá file PID"
    rm -f "$f"; return 0
  fi
  kill -TERM "$pid" 2>/dev/null || true
  for i in $(seq 1 20); do
    kill -0 "$pid" 2>/dev/null || { echo "  • $name: đã dừng sạch (PID $pid, ${i}s)"; rm -f "$f"; return 0; }
    sleep 1
  done
  echo "  • $name: không phản hồi SIGTERM sau 20s — kill -KILL $pid" >&2
  kill -KILL "$pid" 2>/dev/null || true
  rm -f "$f"
}

stop_all() {
  echo
  echo "== Dừng hệ thống demo (thứ tự ngược với lúc khởi động) =="
  stop_pidfile "$DASH_PID_FILE" "dashboard Streamlit"
  stop_pidfile "$PROD_PID_FILE" "producer replay"
  echo "  • job streaming: gửi SIGTERM (dừng êm, ghi nốt checkpoint) ..."
  bash "$HERE/stop_stream.sh" "$RUN" || true
  if [ "$KEEP_KAFKA" -eq 1 ]; then
    echo "  • Kafka: GIỮ chạy (--keep-kafka). Dừng sau bằng: bash kafka/stop_kafka.sh"
  else
    echo "  • Kafka: dừng (muốn giữ thì dùng --keep-kafka)"
    bash "$PROJECT_ROOT/kafka/stop_kafka.sh" || true
  fi
  echo "== Đã dừng. Log còn nguyên ở logs/task10_*_${RUN}.log và logs/task8_stream_${RUN}.log =="
}

if [ "$DO_STOP" -eq 1 ]; then
  stop_all
  exit 0
fi

# ---------------------------------------------------------------------------
# Kiểm tra trước khi tốn thời gian khởi động
# ---------------------------------------------------------------------------
[ -x "$VENV_PY" ] || { echo "LỖI: không thấy $VENV_PY — tạo venv theo README.md" >&2; exit 1; }
[ -d "$PROJECT_ROOT/outputs/models/sentiment_pipeline" ] || {
  echo "LỖI: chưa có mô hình outputs/models/sentiment_pipeline — chạy Task 7 trước." >&2; exit 1; }
if [ -z "${COMMENT_HASH_SALT:-}" ]; then
  echo "LỖI: chưa có COMMENT_HASH_SALT trong môi trường (producer cần để băm user_hash)." >&2
  echo "      Tạo một lần:  python3 -c \"import secrets;print('export COMMENT_HASH_SALT='+secrets.token_hex(16))\"" >&2
  echo "                    >> ~/.capstone-secrets.sh && chmod 600 ~/.capstone-secrets.sh" >&2
  exit 1
fi
if pgrep -f "stream_job.py --run-name ${RUN}" >/dev/null 2>&1; then
  echo "LỖI: đã có job streaming run-name='${RUN}' đang chạy. Dừng trước: bash scripts/run_demo.sh --stop" >&2
  exit 1
fi

trap 'echo; echo "Nhận Ctrl+C — dừng sạch ..."; stop_all; exit 130' INT TERM

echo "=============================================================="
echo " DEMO TASK 10 — lần chạy '${RUN}' | dashboard cổng ${PORT}"
echo " thời điểm bắt đầu: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "=============================================================="

# ---------------------------------------------------------------------------
# 1) Kafka + topic
# ---------------------------------------------------------------------------
echo
echo "[1/4] Kafka (bỏ qua nếu đang chạy sẵn) ..."
bash "$PROJECT_ROOT/kafka/start_kafka.sh"
bash "$PROJECT_ROOT/kafka/create_topics.sh" >/dev/null
echo "  3 topic sẵn sàng: comments_raw, comments_scored, comments_dlq"

# ---------------------------------------------------------------------------
# 2) Job streaming (chờ tới READY — PHẢI xong trước khi producer gửi)
# ---------------------------------------------------------------------------
echo
echo "[2/4] Job streaming (run='${RUN}', --keep-text cho demo dữ liệu công khai) ..."
# Lần chạy lại CÙNG tên sẽ tiếp tục từ checkpoint cũ (offset đã commit) — dữ liệu
# demo cộng dồn vào outputs/stream/<RUN>. Muốn bắt đầu lại từ đầu: xoá 2 thư mục
# outputs/stream/<RUN> và checkpoints/streaming/<RUN> rồi chạy lại.
bash "$HERE/run_stream.sh" "$RUN" --keep-text ${STREAM_EXTRA[@]+"${STREAM_EXTRA[@]}"}

# ---------------------------------------------------------------------------
# 3) Producer (replay) — chạy nền
# ---------------------------------------------------------------------------
echo
echo "[3/4] Producer replay (sample=${SAMPLE}, loop, rate=${RATE:-theo config}) ..."
RATE_ARG=()
if [ -n "$RATE" ]; then RATE_ARG=(--rate "$RATE"); fi
: >"$PROD_LOG"
nohup "$VENV_PY" "$PROJECT_ROOT/src/producer/replay_producer.py" \
  --sample "$SAMPLE" --loop "${RATE_ARG[@]}" \
  >>"$PROD_LOG" 2>&1 &
PROD_PID=$!
echo "$PROD_PID" >"$PROD_PID_FILE"
sleep 2
if ! kill -0 "$PROD_PID" 2>/dev/null; then
  echo "LỖI: producer thoát ngay. 20 dòng cuối log:" >&2; tail -20 "$PROD_LOG" >&2; exit 1
fi
echo "  producer PID $PROD_PID | log logs/task10_producer_${RUN}.log"

# ---------------------------------------------------------------------------
# 4) Dashboard — chạy nền, chờ tới khi trả lời HTTP
# ---------------------------------------------------------------------------
echo
echo "[4/4] Dashboard Streamlit (0.0.0.0:${PORT}) ..."
: >"$DASH_LOG"
nohup "$VENV_PY" -m streamlit run "$PROJECT_ROOT/src/app/app.py" \
  --server.address 0.0.0.0 --server.port "$PORT" \
  --server.headless true --browser.gatherUsageStats false \
  >>"$DASH_LOG" 2>&1 &
DASH_PID=$!
echo "$DASH_PID" >"$DASH_PID_FILE"

ready=0
for i in $(seq 1 60); do
  if ! kill -0 "$DASH_PID" 2>/dev/null; then
    echo "LỖI: dashboard thoát. 30 dòng cuối log:" >&2; tail -30 "$DASH_LOG" >&2; exit 1
  fi
  if (exec 3<>/dev/tcp/127.0.0.1/"$PORT") 2>/dev/null; then ready=1; break; fi
  sleep 1
done
[ "$ready" -eq 1 ] && echo "  dashboard sẵn sàng sau ${i}s (PID $DASH_PID)" \
  || { echo "CẢNH BÁO: cổng $PORT chưa mở sau 60s — xem $DASH_LOG" >&2; }

HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
cat <<EOF

==============================================================
 HỆ THỐNG ĐANG CHẠY
   Dashboard (trên máy ảo) : http://localhost:${PORT}
   Dashboard (máy thật)    : http://localhost:${PORT}   <- sau khi port-forward
   IP máy ảo               : ${HOST_IP:-?}
   Dữ liệu đang ghi vào    : outputs/stream/${RUN}/
   Mở xem khi chưa có dữ liệu: cửa sổ đầu tiên xuất hiện sau ~1–3 phút
                              (watermark 2 phút — dashboard tự ghi rõ lý do)

 DỪNG SẠCH (một lệnh):  bash scripts/run_demo.sh --stop
==============================================================
EOF

if [ "$DURATION" -gt 0 ]; then
  echo "Sẽ tự dừng sau ${DURATION}s (--duration). Ctrl+C để dừng sớm."
  sleep "$DURATION"
  stop_all
  exit 0
fi

echo "Ctrl+C để dừng toàn bộ."
# Giữ script ở tiền cảnh để Ctrl+C còn bắt được; trap INT ở trên lo phần dọn dẹp.
while kill -0 "$DASH_PID" 2>/dev/null; do sleep 2; done
echo "Dashboard đã thoát — dừng phần còn lại."
stop_all
