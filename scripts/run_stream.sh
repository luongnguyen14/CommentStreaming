#!/usr/bin/env bash
# run_stream.sh — Khởi chạy job streaming (Task 8) ở NỀN và chờ tới khi sẵn sàng.
#
#   bash scripts/run_stream.sh [tên-lần-chạy] [tham số thêm của stream_job.py ...]
#   ví dụ:
#     bash scripts/run_stream.sh main --starting-offsets latest
#     bash scripts/run_stream.sh verify --sink-dir outputs/stream/verify --duration-seconds 600
#
# Vì sao chạy nền: job streaming chạy liên tục; script này trả về ngay khi job báo
# READY (đã gắn offset nguồn) để bên phát dữ liệu không gửi sớm hơn mốc offset.
# Log: logs/task8_stream_<tên>.log | PID: logs/task8_stream_<tên>.pid
# Dừng: bash scripts/stop_stream.sh <tên>   (xem README để biết vì sao dừng phải êm)

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/env.sh"

RUN="${1:-main}"
shift || true
LOG="$PROJECT_ROOT/logs/task8_stream_${RUN}.log"
PID_FILE="$PROJECT_ROOT/logs/task8_stream_${RUN}.pid"

# --- kiểm tra nhanh trước khi chạy -------------------------------------------------
if pgrep -f "stream_job.py --run-name ${RUN}" >/dev/null 2>&1; then
  echo "LỖI: đã có job streaming với run-name '${RUN}' đang chạy (xem $PID_FILE)." >&2
  exit 1
fi
if ! (exec 3<>/dev/tcp/localhost/9092) 2>/dev/null; then
  echo "LỖI: không kết nối được Kafka ở localhost:9092 — chạy bash kafka/start_kafka.sh" >&2
  exit 1
fi
# HDFS chỉ dùng cho event log của Spark — sink và checkpoint đều nằm trên ổ đĩa cục bộ
# (config.yaml: `sink_root`, `checkpoint_root`). Nên HDFS tắt KHÔNG phải lý do để job
# không chạy: thay vì để SparkContext chết vì ConnectException tới localhost:9000 (đã
# gặp thật 15/10/2026, sau khi VM reboot), tắt event log cho riêng lần chạy này bằng
# --conf. Không sửa spark-defaults.conf vì file đó dùng chung cho mọi job Spark.
SPARK_CONF=()
hdfs_safemode_off() {
  # `hdfs dfs -ls` vẫn chạy được trong safe mode (chỉ đọc), nên phải hỏi riêng.
  # SLF4J cảnh báo nhiều binding in ra stderr -> lọc bằng 2>/dev/null.
  hdfs dfsadmin -safemode get 2>/dev/null | grep -q "Safe mode is OFF"
}
if ! hdfs dfs -ls / >/dev/null 2>&1; then
  echo "CẢNH BÁO: HDFS không phản hồi — chạy lần này với spark.eventLog.enabled=false" >&2
  echo "          (Spark History Server sẽ KHÔNG có lần chạy này; sink/checkpoint" >&2
  echo "          vẫn ghi bình thường vì nằm trên ổ đĩa cục bộ)." >&2
  echo "          Muốn có event log: /usr/local/hadoop/sbin/start-dfs.sh" >&2
  SPARK_CONF+=(--conf spark.eventLog.enabled=false)
elif ! hdfs_safemode_off; then
  # NameNode vừa khởi động còn ở safe mode vài giây; lúc đó tạo /spark-logs bị
  # SafeModeException (đã gặp thật 15/10/2026: start-dfs.sh rồi chạy job ngay).
  echo -n "HDFS đang ở safe mode — chờ tối đa 90 s "
  safe=0
  for _ in $(seq 1 90); do
    if hdfs_safemode_off; then safe=1; break; fi
    sleep 1; echo -n "."
  done
  echo
  if [ "$safe" -eq 1 ]; then
    echo "  HDFS đã ra khỏi safe mode — event log bật bình thường."
  else
    echo "CẢNH BÁO: HDFS vẫn ở safe mode sau 90 s — chạy lần này với" >&2
    echo "          spark.eventLog.enabled=false (thử: hdfs dfsadmin -safemode leave)." >&2
    SPARK_CONF+=(--conf spark.eventLog.enabled=false)
  fi
fi

echo "Khởi chạy job streaming: run='${RUN}' | log=${LOG#$PROJECT_ROOT/}"
: >"$LOG"
# Lưu ý: phải EXPORT biến môi trường TRƯỚC nohup — `nohup VAR=... cmd` bị nohup hiểu
# là tên chương trình cần chạy (nohup không xử lý phép gán biến), job sẽ thoát ngay.
export PYSPARK_DRIVER_PYTHON="$VENV_PY" PYSPARK_PYTHON="$VENV_PY"
nohup "$SPARK_HOME/bin/spark-submit" \
  --master 'local[2]' --driver-memory 2g \
  --packages "$SPARK_KAFKA_PKG" \
  "${SPARK_CONF[@]}" \
  "$PROJECT_ROOT/src/streaming/stream_job.py" --run-name "$RUN" "$@" \
  >>"$LOG" 2>&1 &
PID=$!
echo "$PID" >"$PID_FILE"

echo -n "Chờ job sẵn sàng (tối đa 240 s) "
for _ in $(seq 1 240); do
  if grep -q "^\[.*\] READY" "$LOG" 2>/dev/null; then
    echo; echo "READY — job đang chạy (PID ${PID}). Log: ${LOG#$PROJECT_ROOT/}"
    grep -E "READY|query \`|Spark 3|nguồn:|sink:" "$LOG" | tail -12
    exit 0
  fi
  if ! kill -0 "$PID" 2>/dev/null; then
    echo; echo "LỖI: job đã thoát. 40 dòng cuối log:" >&2
    tail -40 "$LOG" >&2
    exit 1
  fi
  sleep 1
  echo -n "."
done
echo; echo "HẾT THỜI GIAN chờ READY — 40 dòng cuối log:" >&2
tail -40 "$LOG" >&2
exit 1
