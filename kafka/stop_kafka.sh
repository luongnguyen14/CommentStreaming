#!/usr/bin/env bash
# stop_kafka.sh — Dừng Kafka sạch sẽ (SIGTERM qua kafka-server-stop.sh),
# nếu sau 30 giây vẫn chạy thì báo rõ để người dùng tự quyết định (không kill -9 mặc định).
#
#   bash kafka/stop_kafka.sh

set -u
source "$(dirname "$0")/../scripts/env.sh"
export JAVA_HOME="$KAFKA_JAVA_HOME"

if ! "$KAFKA_HOME/bin/kafka-broker-api-versions.sh" --bootstrap-server "$KAFKA_BOOTSTRAP" >/dev/null 2>&1; then
  echo "Kafka không chạy trên $KAFKA_BOOTSTRAP — không có gì để dừng."
  exit 0
fi

echo "Dừng Kafka (SIGTERM) ..."
"$KAFKA_HOME/bin/kafka-server-stop.sh" 2>/dev/null || true

for i in $(seq 1 30); do
  if ! "$KAFKA_HOME/bin/kafka-broker-api-versions.sh" --bootstrap-server "$KAFKA_BOOTSTRAP" >/dev/null 2>&1; then
    echo "Kafka đã dừng (sau ${i}s)."
    exit 0
  fi
  sleep 1
done

echo "CẢNH BÁO: Kafka vẫn chạy sau 30s. Kiểm tra tiến trình java rồi quyết định:" >&2
pgrep -af "kafka.Kafka" >&2 || true
exit 1
