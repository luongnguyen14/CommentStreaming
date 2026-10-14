# kafka/ — Vận hành Kafka (Task 5)

Cài đặt thật trên máy ảo này: **Apache Kafka 4.3.1, chế độ KRaft (không có ZooKeeper)**,
một tiến trình broker + controller gộp, chạy tại `/home/hadoop/kafka`, dữ liệu ở
`/home/hadoop/kafka-data`, bootstrap `localhost:9092`.

## Vì sao cần JDK 17 riêng

Broker Kafka 4.x **bắt buộc Java 17** (KIP-1013), trong khi Spark/Hadoop của dự án
chạy Java 8 và máy không có quyền `sudo` để cài đặt hệ thống. Vì vậy nhóm tải
**Temurin JDK 17 bản người dùng** về `/home/hadoop/jdk-17.0.20.1+1` (symlink
`/home/hadoop/jdk-17`) và **chỉ dùng cho Kafka** — Spark vẫn dùng Java 8 như cũ.
Các script dưới đây tự đặt `JAVA_HOME=$KAFKA_JAVA_HOME` trước khi gọi Kafka.

Bộ nhớ heap của broker được giới hạn trong `start_kafka.sh`
(`KAFKA_HEAP_OPTS="-Xmx512M -Xms256M"`) vì máy ảo chỉ có 7 GB RAM.

## Script

| File | Việc |
|---|---|
| `start_kafka.sh` | Khởi động broker (nền), chờ tối đa 60 s đến khi sẵn sàng |
| `stop_kafka.sh` | Dừng sạch (SIGTERM), cảnh báo nếu sau 30 s vẫn chạy |
| `create_topics.sh` | Tạo 3 topic: `comments_raw` (3 partition), `comments_scored` (3), `comments_dlq` (1) |

## Chạy lại từ đầu (máy mới)

```bash
# 0) Biến môi trường (JAVA_HOME của Kafka, KAFKA_HOME, bootstrap ...)
source scripts/env.sh

# 1) Nếu chưa có Kafka: tải bản ổn định mới nhất từ https://kafka.apache.org/downloads
#    (Kafka 4.x cần JDK 17 — xem mục trên), giải nén về /home/hadoop/kafka
#    Sửa config/server.properties:
#        process.roles=broker,controller
#        controller.quorum.bootstrap.servers=localhost:9093
#        log.dirs=/home/hadoop/kafka-data
#    Rồi định dạng storage (KRaft) một lần:
#        "$KAFKA_HOME/bin/kafka-storage.sh" random-uuid   # lấy UUID
#        "$KAFKA_HOME/bin/kafka-storage.sh" format -t <UUID> -c "$KAFKA_HOME/config/server.properties" --standalone

# 2) Khởi động + tạo topic
bash kafka/start_kafka.sh
bash kafka/create_topics.sh

# 3) Kiểm tra nhanh bằng console producer/consumer
"$KAFKA_HOME/bin/kafka-console-producer.sh" --bootstrap-server localhost:9092 --topic comments_raw
"$KAFKA_HOME/bin/kafka-console-consumer.sh" --bootstrap-server localhost:9092 --topic comments_raw --from-beginning

# 4) Dừng
bash kafka/stop_kafka.sh
```

## Bằng chứng đã kiểm chứng (14/10/2026)

- Console producer/consumer: gửi 3 message, đọc lại đủ 3, exit code 0 —
  `logs/kafka_console_test.log`.
- End-to-end bằng script Python: gửi **1000** message vào `comments_raw`,
  đọc lại đếm đủ **1000**, 0 lỗi — `logs/task5_1000msg_producer.log`,
  `logs/task5_1000msg_consumer.log`.
- Thông lượng theo mức `--rate`: `outputs/tables/ingestion_report.csv`.

## Ghi chú

- Log broker: `$KAFKA_HOME/logs/broker.log`; nếu broker không lên, xem file này trước.
- `kafka-server-stop.sh` của Kafka 4.x có thể không tìm thấy tiến trình nếu chạy
  khác `JAVA_HOME`; `stop_kafka.sh` đã đặt `JAVA_HOME` đúng nên dừng được bình thường.
- Bản Kafka 2.8.1 cũ trên máy vẫn giữ nguyên ở `/home/hadoop/kafka-2.8.1-old`
  (không dùng cho dự án).
