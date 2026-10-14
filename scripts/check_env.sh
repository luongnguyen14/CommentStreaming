#!/usr/bin/env bash
# check_env.sh — Kiểm tra nhanh môi trường đã sẵn sàng chưa.
#
#   bash scripts/check_env.sh           # kiểm tra nhanh (~5 giây)
#   bash scripts/check_env.sh --smoke   # thêm smoke test SparkSession thật (~30-60 giây)
#
# Trả mã thoát 0 nếu mọi thứ OK, 1 nếu có mục FAIL.

set -u
cd "$(dirname "$0")/.."          # PROJECT_ROOT
# shellcheck source=scripts/env.sh
source scripts/env.sh

fail=0
ok()  { echo "  [OK]   $1"; }
bad() { echo "  [FAIL] $1"; fail=1; }

echo "== Java =="
if java -version >/dev/null 2>&1; then
  ok "java: $(java -version 2>&1 | head -1)"
else
  bad "không chạy được java (JAVA_HOME=$JAVA_HOME)"
fi

echo "== HDFS =="
if jps 2>/dev/null | grep -q NameNode; then
  ok "NameNode đang chạy"
else
  bad "NameNode CHƯA chạy → /usr/local/hadoop/sbin/start-dfs.sh"
fi
if hdfs dfs -ls -d /spark-logs >/dev/null 2>&1; then
  ok "/spark-logs có trên HDFS (chỗ ghi event log của Spark)"
else
  bad "/spark-logs thiếu trên HDFS → hdfs dfs -mkdir -p /spark-logs"
fi

echo "== Spark =="
if [ -x "$SPARK_HOME/bin/spark-submit" ]; then
  ok "spark-submit: $SPARK_HOME"
else
  bad "không thấy $SPARK_HOME/bin/spark-submit"
fi
if python3.11 -c "import pandas" >/dev/null 2>&1; then
  ok "pandas cho Python 3.11 (driver Spark)"
else
  bad "thiếu pandas cho Python 3.11 → python3.11 -m pip install --user --break-system-packages pandas numpy"
fi
if python3 -c "import streamlit" >/dev/null 2>&1; then
  ok "streamlit cho Python 3.x mặc định (dashboard)"
else
  bad "thiếu streamlit → python3 -m pip install --user --break-system-packages streamlit"
fi

echo "== Smoke test SparkSession =="
if [ "${1:-}" = "--smoke" ]; then
  smoke=$(mktemp /tmp/spark_smoke_XXXXXX.py)
  cat > "$smoke" <<'PY'
from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("check-env").getOrCreate()
print("SPARK_OK", spark.version, "count=", spark.range(5).count())
spark.stop()
PY
  if spark-submit --master "local[2]" "$smoke" 2>&1 | grep -q "SPARK_OK"; then
    ok "SparkSession khởi động và chạy được"
  else
    bad "SparkSession lỗi (chạy lại không lọc log để xem chi tiết)"
  fi
  rm -f "$smoke"
else
  echo "  (bỏ qua — thêm --smoke để chạy thử SparkSession thật)"
fi

echo
if [ "$fail" -eq 0 ]; then
  echo "MÔI TRƯỜNG OK"
else
  echo "CÓ MỤC FAIL — xem danh sách [FAIL] ở trên"
fi
exit "$fail"
