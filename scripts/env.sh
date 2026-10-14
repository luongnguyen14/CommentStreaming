#!/usr/bin/env bash
# env.sh — Biến môi trường của dự án. Source trước khi chạy bất kỳ script nào:
#     source scripts/env.sh
#
# Vì sao có file này thay vì chỉ dựa vào ~/.bashrc:
#  - chạy được cả khi không nạp bashrc (cron, terminal khác, script gọi nhau);
#  - ghi rõ một chỗ duy nhất: dùng Spark nào, Python nào, Java nào.

export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-arm64
export HADOOP_HOME=/usr/local/hadoop
export HADOOP_CONF_DIR="$HADOOP_HOME/etc/hadoop"
export SPARK_HOME=/home/hadoop/spark-3.5.9

# Spark 3.5.9 không chạy được với Python 3.14 (cloudpickle 2.2.1 lỗi RecursionError
# khi pickle). Máy có sẵn Python 3.11 — dùng cho cả driver lẫn executor của PySpark.
export PYSPARK_PYTHON=/usr/bin/python3.11
export PYSPARK_DRIVER_PYTHON=/usr/bin/python3.11

# ---------------------------------------------------------------------------
# Bí mật cục bộ (muối băm COMMENT_HASH_SALT ...). File KHÔNG nằm trong repo
# (quyền 600). Tạo một lần bằng:
#   python3 -c "import secrets;print('export COMMENT_HASH_SALT='+secrets.token_hex(16))" \
#     >> ~/.capstone-secrets.sh && chmod 600 ~/.capstone-secrets.sh
# ---------------------------------------------------------------------------
if [ -f "$HOME/.capstone-secrets.sh" ]; then
  # shellcheck disable=SC1091
  . "$HOME/.capstone-secrets.sh"
fi

# ---------------------------------------------------------------------------
# Kafka (Task 5)
# ---------------------------------------------------------------------------
# Kafka 4.3.1 chạy KRaft (không cần Zookeeper). Broker của Kafka 4.x bắt buộc
# Java 17 (KIP-1013) trong khi Spark ở đây chạy Java 8, nên Kafka dùng JDK riêng:
export KAFKA_HOME=/home/hadoop/kafka
export KAFKA_JAVA_HOME=/home/hadoop/jdk-17
export KAFKA_DATA_DIR=/home/hadoop/kafka-data
export KAFKA_BOOTSTRAP=localhost:9092

# Python venv của dự án (thư viện cho producer/consumer/EDA/dashboard).
# KHÔNG dùng cho spark-submit (Spark chạy bằng PYSPARK_PYTHON như trên).
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PROJECT_ROOT
export VENV_PY="$PROJECT_ROOT/.venv/bin/python"

# Thêm vào PATH (không thêm trùng nếu đã có).
case ":$PATH:" in
  *":$SPARK_HOME/bin:"*) ;;
  *) export PATH="$SPARK_HOME/bin:$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$PATH" ;;
esac
