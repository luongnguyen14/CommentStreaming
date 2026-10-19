#!/usr/bin/env bash
# run_model_trial.sh — Chạy chương trình thử nghiệm mô hình bằng MỘT lệnh.
#
#   bash scripts/run_model_trial.sh                     # nhập bình luận tương tác
#   bash scripts/run_model_trial.sh --examples          # 4 câu ví dụ trong config.yaml
#   bash scripts/run_model_trial.sh --text "not bad"    # chấm một câu
#   bash scripts/run_model_trial.sh --test-sample 200   # đo trên 200 dòng tập test
#   bash scripts/run_model_trial.sh --help
#
# Vì sao chạy bằng Python của venv thay vì gọi thẳng `spark-submit`:
# `spark-submit` trong chế độ client nuốt stdin, nên chế độ TƯƠNG TÁC không nhận
# được câu người dùng gõ (đã gặp thật: chỉ hiện dấu nhắc rồi thoát). Chạy
# `$VENV_PY` trực tiếp thì PySpark tự khởi động gateway qua spark-submit, còn
# stdin vẫn thuộc về tiến trình Python. Venv đã có pyspark 3.5.9 (đúng phiên bản
# đã lưu model) nên không cần cài thêm.
#
# Vì sao tắt event log: máy này cấu hình Spark ghi event log lên HDFS; nếu HDFS
# chưa bật (hay gặp sau khi reboot máy ảo) thì SparkContext chết ngay. Demo không
# cần History Server nên tắt cho lần chạy này — KHÔNG sửa spark-defaults.conf
# (file đó dùng chung cho mọi job).
#
# Không cần Kafka, không cần Streamlit. Chỉ cần model đã lưu trong outputs/models/.

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
--conf spark.sql.shuffle.partitions=8 \
pyspark-shell"
export SPARK_SUBMIT_OPTS="-Dlog4j2.configurationFile=file://$PROJECT_ROOT/conf/log4j2.properties"

exec "$VENV_PY" "$PROJECT_ROOT/src/app/model_trial.py" "$@"
