#!/usr/bin/env bash
# stop_stream.sh — Dừng job streaming (Task 8) MỘT CÁCH ÊM ÁI.
#
#   bash scripts/stop_stream.sh [tên-lần-chạy]
#
# Vì sao phải dừng êm (không dùng `kill -9`):
#   - Job tự dừng từng query: nốt micro-batch đang chạy, ghi nốt file parquet +
#     commit offset vào checkpoint. `kill -9` có thể để lại một batch ghi dở.
#   - Lần chạy sau (cùng --run-name) sẽ TIẾP TỤC từ offset đã commit, không xử lý lại.
#
# Cách dừng: gửi SIGTERM cho TIẾN TRÌNH PYTHON của driver (con của JVM spark-submit)
# để handler trong stream_job.py chạy. Nếu không tìm thấy tiến trình Python (ví dụ
# job chạy ở chế độ khác), gửi SIGTERM cho JVM — kém êm hơn nhưng checkpoint của
# Structured Streaming vẫn an toàn vì offset chỉ được ghi khi batch đã hoàn tất.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/env.sh"

RUN="${1:-main}"
PID_FILE="$PROJECT_ROOT/logs/task8_stream_${RUN}.pid"
LOG="$PROJECT_ROOT/logs/task8_stream_${RUN}.log"

if [ ! -f "$PID_FILE" ]; then
  echo "LỖI: không thấy $PID_FILE — job chưa từng chạy qua run_stream.sh?" >&2
  exit 1
fi
JVM_PID="$(cat "$PID_FILE")"
if ! kill -0 "$JVM_PID" 2>/dev/null; then
  echo "Job (PID $JVM_PID) không còn chạy — không cần dừng."
  exit 0
fi

PY_PID="$(pgrep -P "$JVM_PID" -f 'stream_job.py' | head -1 || true)"
TARGET="${PY_PID:-$JVM_PID}"
if [ -n "$PY_PID" ]; then
  echo "Gửi SIGTERM cho tiến trình Python driver (PID ${PY_PID}, cha ${JVM_PID}) ..."
else
  echo "Không thấy tiến trình Python con — gửi SIGTERM cho JVM (PID ${JVM_PID}) ..."
fi
kill -TERM "$TARGET"

for i in $(seq 1 60); do
  if ! kill -0 "$JVM_PID" 2>/dev/null; then
    echo "Đã dừng sạch sau ${i}s. Các dòng log cuối:"
    grep -E "Nhận tín hiệu|đang dừng query|đã dừng sạch|Tổng số bản ghi|Đã dừng Spark" \
      "$LOG" | tail -12 || true
    rm -f "$PID_FILE"
    exit 0
  fi
  sleep 1
done

echo "CẢNH BÁO: sau 60 s job (PID $JVM_PID) vẫn chạy. 20 dòng cuối log:" >&2
tail -20 "$LOG" >&2
echo "Kiểm tra: ps -fp $JVM_PID | Có thể phải kill -TERM $JVM_PID lần nữa." >&2
exit 1
