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

# Thêm vào PATH (không thêm trùng nếu đã có).
case ":$PATH:" in
  *":$SPARK_HOME/bin:"*) ;;
  *) export PATH="$SPARK_HOME/bin:$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$PATH" ;;
esac
