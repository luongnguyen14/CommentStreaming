#!/usr/bin/env bash
# start_kafka.sh — Khởi động Kafka 4.3.1 (KRaft, không cần Zookeeper).
#
#   bash kafka/start_kafka.sh
#
# Chạy nền (nohup), log ở /home/hadoop/kafka/logs/broker.log.
# Chờ tới khi broker trả lời được trên localhost:9092 rồi mới thoát (mã thoát 0).
#
# Lưu ý về Java: broker của Kafka 4.x bắt buộc Java 17 (KIP-1013), trong khi
# Spark của dự án chạy Java 8 — nên script này đặt JAVA_HOME riêng cho Kafka,
# KHÔNG dùng JAVA_HOME mặc định của scripts/env.sh.

set -u
source "$(dirname "$0")/../scripts/env.sh"
export JAVA_HOME="$KAFKA_JAVA_HOME"

LOG_DIR="$KAFKA_HOME/logs"
LOG_FILE="$LOG_DIR/broker.log"
mkdir -p "$LOG_DIR" "$KAFKA_DATA_DIR"

if "$KAFKA_HOME/bin/kafka-broker-api-versions.sh" --bootstrap-server "$KAFKA_BOOTSTRAP" >/dev/null 2>&1; then
  echo "Kafka đang chạy sẵn trên $KAFKA_BOOTSTRAP — không khởi động lại."
  exit 0
fi

# Heap nhỏ cho phù hợp RAM máy ảo (~7 GB, dùng chung với HDFS/Spark).
export KAFKA_HEAP_OPTS="-Xmx512M -Xms256M"

echo "Khởi động Kafka 4.3.1 (KRaft) với JAVA_HOME=$JAVA_HOME ..."
nohup "$KAFKA_HOME/bin/kafka-server-start.sh" "$KAFKA_HOME/config/server.properties" \
  >> "$LOG_FILE" 2>&1 &
echo "  PID: $!  |  log: $LOG_FILE"

# Chờ broker sẵn sàng (tối đa 60 giây)
for i in $(seq 1 60); do
  if "$KAFKA_HOME/bin/kafka-broker-api-versions.sh" --bootstrap-server "$KAFKA_BOOTSTRAP" >/dev/null 2>&1; then
    echo "Kafka sẵn sàng trên $KAFKA_BOOTSTRAP (sau ${i}s)"
    exit 0
  fi
  sleep 1
done

echo "LỖI: Kafka không sẵn sàng sau 60s — xem $LOG_FILE" >&2
exit 1
