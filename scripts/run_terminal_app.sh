#!/usr/bin/env bash
# run_terminal_app.sh — Chạy app terminal (walkthrough toàn bộ quy trình) bằng MỘT lệnh.
#
#   bash scripts/run_terminal_app.sh                     # từng giai đoạn, nhấn Enter
#   bash scripts/run_terminal_app.sh --auto              # tự chạy liên tục
#   bash scripts/run_terminal_app.sh --fast --limit 20   # nhanh, 20 bình luận
#   bash scripts/run_terminal_app.sh --stage 5           # chỉ giai đoạn chấm điểm
#   bash scripts/run_terminal_app.sh --text "not bad"    # chấm một câu
#   bash scripts/run_terminal_app.sh --live --duration 60  # theo dõi Kafka
#   bash scripts/run_terminal_app.sh --help
#
# Vì sao chạy bằng Python của venv thay vì `spark-submit`: giống run_model_trial.sh —
# spark-submit ở client mode nuốt stdin, nên chế độ "nhấn Enter" sẽ không nhận được
# phím. Chạy $VENV_PY trực tiếp thì PySpark tự khởi động gateway, stdin vẫn của Python.
#
# Không cần Kafka cho chế độ walkthrough (mặc định). Chỉ cần model đã lưu trong
# outputs/models/ và dữ liệu mẫu outputs/tables/clean_sample.csv.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$HERE/.." && pwd)"
# shellcheck disable=SC1091
source "$HERE/env.sh"

export PYSPARK_DRIVER_PYTHON="$VENV_PY"
export PYSPARK_PYTHON="$VENV_PY"
export PYSPARK_SUBMIT_ARGS="--master local[2] --driver-memory 2g \
--conf spark.ui.enabled=false \
--conf spark.eventLog.enabled=false \
--conf spark.sql.shuffle.partitions=4 \
pyspark-shell"
export SPARK_SUBMIT_OPTS="-Dlog4j2.configurationFile=file://$PROJECT_ROOT/conf/log4j2.properties"

# -u: không đệm stdout khi bị pipe/redirect, để thứ tự dòng in đúng như khi xem terminal.
exec "$VENV_PY" -u "$PROJECT_ROOT/src/app/terminal_app.py" "$@"
