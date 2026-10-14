# logs/ — Log chạy job

Log của `stream_job`, `replay_producer`, dashboard. Mặc định **không** commit lên git
(`.gitignore` loại `logs/*`).

**Ngoại lệ — log được commit vì là bằng chứng kiểm chứng** (đúng theo nguyên tắc
"mọi con số trong báo cáo phải truy vết được về file thật"): `task5_*`, `task6_*`,
`task7_*`, `task8_*` và `kafka_console_test.log`. Danh sách ngoại lệ nằm ở cuối mục
`.gitignore` (git lấy dòng khớp **cuối cùng**, nên các dòng `!` phải đặt sau `logs/*`).

| Nhóm file | Nội dung |
|---|---|
| `task5_*.log`, `task5_environment.txt` | Cài Kafka 4.3.1 KRaft, kiểm chứng 1000 gửi → 1000 nhận, đo thông lượng, đo RAM |
| `task6_*.log` | Làm sạch + chia tập (`prepare.py`) |
| `task7_*.log` | Huấn luyện + đánh giá 4 mô hình (`train.py`) |
| `task8_stream_<run>.log` | Log job streaming (Task 8): mỗi micro-batch một dòng + thông báo READY/dừng |
| `task8_verify_<run>.log` | Log `verify_stream.py`: đối chiếu số lượng, chỉ số trên luồng vs offline, 20 dòng mẫu |
| `task8_bad_events_<run>.log` | Log `send_bad_events.py` (10 ca lỗi + heartbeat + late-probe) |
