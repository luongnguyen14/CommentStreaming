#!/usr/bin/env bash
# create_topics.sh — Tạo 3 topic của dự án (chạy lại nhiều lần được, --if-not-exists).
#
#   bash kafka/create_topics.sh
#
#   comments_raw      3 partition — luồng bình luận thô từ producer
#   comments_scored   3 partition — kết quả chấm điểm từ Spark Structured Streaming
#   comments_dlq      1 partition  — bản ghi lỗi kèm lý do (dead-letter queue)

set -u
source "$(dirname "$0")/../scripts/env.sh"
export JAVA_HOME="$KAFKA_JAVA_HOME"

K="$KAFKA_HOME/bin/kafka-topics.sh --bootstrap-server $KAFKA_BOOTSTRAP"

create() {  # $1=tên topic  $2=số partition
  echo "== tạo topic $1 ($2 partition)"
  $K --create --if-not-exists --topic "$1" --partitions "$2" --replication-factor 1
}

create comments_raw     3
create comments_scored  3
create comments_dlq     1

echo
echo "== danh sách topic hiện có"
$K --list

echo
echo "== mô tả chi tiết"
$K --describe
