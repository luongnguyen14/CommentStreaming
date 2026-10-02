# CLAUDE.md — Quy ước dự án Capstone (SIC Big Data)

File này áp dụng cho **mọi tác vụ** trong dự án. Đọc lại trước khi bắt đầu bất kỳ task nào.

---

## 0. Thông tin nhóm

| Mục | Giá trị |
|---|---|
| Khóa học | Samsung Innovation Campus — Big Data Course |
| Tên nhóm | Nhóm 6 |
| Nhóm trưởng | Vàng A Ký |
| Thành viên | Nguyễn Đình Bằng; Vàng Thị Dẳm; Dương Thị Hạnh; Ngô Lương Nguyên |
| Đề tài | Mô hình phân loại cảm xúc dựa trên bình luận trực tuyến |
| Day 1 | 15/09/2026 |

**PROJECT_ROOT = `/home/hadoop/capstone`** — mọi đường dẫn tương đối tính từ đây.
*(Thư mục `/home/hadoop/capstone/CommentStreaming` là thư mục trống, không dùng.)*

**TEMPLATES_DIR = `/home/hadoop/capstone/templates`** — các task sau đọc đường dẫn tài liệu của cô từ đây.

> ⚠️ **TUYỆT ĐỐI KHÔNG sửa, đổi tên, di chuyển hay xóa file trong `TEMPLATES_DIR`.**
> Muốn điền vào mẫu: **copy sang `deliverables/` rồi mới sửa bản copy.**
> Bỏ qua các file tạm bắt đầu bằng `~$` (file khóa của Office).

---

## 1. Quy ước của giảng viên (bắt buộc)

- **Technology for Good**: đề tài phải vì lợi ích cộng đồng.
  - ✅ Nên: phục vụ công chúng, giải quyết vấn đề thực tế.
  - ❌ Không: dự đoán giá chứng khoán, cờ bạc/đầu tư, dự đoán đua xe; đề tài mà giá trị chính là *giải trí*; đề tài **chỉ một cá nhân hoặc một công ty** hưởng lợi; đề tài **chỉ để chứng minh phương pháp/kỹ thuật** mà không giải quyết vấn đề thực.
- **Tài liệu nộp viết bằng tiếng Anh**, đúng theo template của cô (không tự đổi bố cục, font, màu).
- **Mốc nộp**: Day 5, Day 11, Day 18, Day 20 (xem `REQUIREMENTS.md`).
- **WBS được kiểm tra**: Day 9, Day 14, Day 19.
- Chia việc đều giữa các thành viên (tiêu chí Project Management trong Evaluation Sheet).

---

## 2. Cấu trúc thư mục

```
data/raw/         dữ liệu gốc — CHỈ ĐỌC, không sửa, không ghi đè
data/processed/   dữ liệu đã làm sạch, chia tập (parquet)
kafka/            script khởi động/dừng Kafka, tạo topic
src/producer/     Kafka producer (replay, live)
src/common/       hàm dùng chung (làm sạch văn bản, schema, tiện ích)
src/training/     chuẩn bị dữ liệu + huấn luyện Spark ML
src/streaming/    Spark Structured Streaming job
src/eda/          truy vấn Spark SQL + vẽ biểu đồ (+ src/eda/sql/)
src/app/          dashboard Streamlit
scripts/          script chạy toàn bộ / demo
checkpoints/      checkpointLocation của từng streaming query
logs/             log chạy job
outputs/figures/  biểu đồ PNG
outputs/tables/   bảng kết quả CSV
outputs/models/   PipelineModel đã lưu
docs/             tài liệu nội bộ (topic_decision, data_dictionary, scenario, qa_prep...)
deliverables/     sản phẩm nộp (copy từ TEMPLATES_DIR rồi điền)
```

- **Đặt tên file**: chữ thường, không dấu, không dấu cách, dùng `_`. Ví dụ `topic_decision.md`, `replay_producer.py`.
- **Biểu đồ đánh số thứ tự**: `01_`, `02_`, `03_`... (sơ đồ kiến trúc pipeline là `00_pipeline_architecture.png`).
- **Mỗi thư mục có một `README.md` ngắn** mô tả mục đích và cách chạy lại.

---

## 3. Quy ước code

- Ngôn ngữ: **Python 3 và PySpark**. Mỗi bước một script riêng, chạy được độc lập.
- **Tham số và đường dẫn để trong `config.yaml`** — không hard-code trong script.
- **Random seed = 42** cho mọi bước có yếu tố ngẫu nhiên.
- **Không để key, token, mật khẩu trong code** — đọc từ biến môi trường (ví dụ `os.environ["YT_API_KEY"]`).
- Mỗi thư mục có `README.md` ngắn: mục đích + cách chạy lại từ đầu.
- Trước khi chạy bản đầy đủ, luôn chạy thử bản `--sample N` nếu script hỗ trợ.

---

## 4. Nhất quán giữa huấn luyện và triển khai (quan trọng)

- Hàm làm sạch văn bản viết **một lần duy nhất** ở `src/common/text_cleaning.py`.
- **Dùng chung cho cả huấn luyện lẫn streaming** — không viết lại logic làm sạch ở chỗ khác.
- Ưu tiên **hàm Spark SQL** (`lower`, `regexp_replace`, `trim`...). **Tránh Python UDF** khi có thể (UDF chậm và chặn tối ưu hóa). Nếu buộc phải dùng (ví dụ tách từ tiếng Việt) thì phải đo và ghi rõ chi phí hiệu năng.
- Có test nhỏ cho các hàm làm sạch.

---

## 5. Quy ước streaming

- **Schema khai báo tường minh** khi `from_json` — không suy luận schema từ dữ liệu.
- Dùng **event time** kèm **watermark**; không dùng processing time thay cho event time.
- **Mỗi streaming query có `checkpointLocation` riêng** trong `checkpoints/` — không dùng chung.
- Bản ghi lỗi hoặc thiếu trường chuyển vào **hàng đợi lỗi (DLQ)** kèm lý do, không âm thầm bỏ qua.
- **Không khẳng định exactly-once nếu chưa kiểm chứng bằng thực nghiệm.** Chỉ nói điều đã đo được; phần chưa đo ghi rõ "chưa kiểm chứng".

---

## 6. Quy ước dữ liệu và mô hình

- **Loại trùng trước khi chia tập**, gồm cả **gần trùng sau khi chuẩn hóa** (bình luận livestream có rất nhiều bản copy-paste → nếu để lẫn sẽ gây điểm cao giả tạo).
- **Chia train/validation/test cố định**. **Tập test chỉ dùng một lần duy nhất vào cuối cùng.**
- **TF-IDF chỉ được học (fit) trên tập train** và phải **nằm trong Spark ML Pipeline** để đảm bảo điều đó.
- **Không đưa nhãn vào luồng streaming.** Nhãn chỉ dùng để đánh giá, lưu riêng ở `data/processed/eval_labels.parquet`, ghép lại theo `comment_id`.
- **Báo cáo macro-F1 và Precision/Recall/F1 từng lớp**, không chỉ Accuracy (dữ liệu mất cân bằng nên Accuracy gây hiểu nhầm).
- Nếu chỉ số cao bất thường → nghi ngờ rò rỉ dữ liệu, kiểm tra trùng lặp trước khi báo cáo.

---

## 7. Quyền riêng tư

- **Băm có muối (salted hash)** mã người dùng; muối đọc từ biến môi trường.
- **Không lưu thông tin cá nhân** (tên, ID thật, số điện thoại, email...).
- **Chỉ hiển thị kết quả tổng hợp** trên dashboard/báo cáo.
- Nếu thu bình luận thật: **kiểm tra điều khoản sử dụng của nền tảng trước**, tôn trọng hạn mức API.

---

## 8. Quy ước biểu đồ

- Tiêu đề rõ ràng; **nhãn trục có đơn vị**; **chữ tiếng Anh**.
- **Bảng màu nhất quán** giữa các biểu đồ (dùng xuyên suốt dự án).
- **PNG 200 dpi**, lưu vào `outputs/figures/`, đánh số `01_`, `02_`...
- **Mỗi biểu đồ kèm 1–2 câu insight dựa trên số liệu thật** (ghi vào `outputs/insights.md`).
- Xuất bảng số liệu nền của mỗi biểu đồ ra `outputs/tables/`.

---

## 9. Trung thực (nguyên tắc cao nhất)

- **Tuyệt đối không bịa số liệu.**
- **Mọi con số trong báo cáo/slide phải lấy từ file kết quả thật trong `outputs/`.**
- Không chắc thì ghi rõ **"cần kiểm chứng"**, không đoán.
- **Dữ liệu replay không được gọi là dữ liệu livestream thật.** Luôn nói rõ phần nào là mô phỏng.
- Ghi lại kết quả thật **kể cả khi mô hình không tốt như mong đợi**.

---

## 10. Quy trình làm việc

- Sau **mỗi tác vụ**: ghi **một dòng** vào `PROGRESS.md` (ngày, task, việc đã làm, file tạo ra, việc còn lại).
- **Commit git với thông điệp rõ ràng** sau mỗi task.
- Nếu một task bị dừng giữa chừng: đọc `PROGRESS.md` để biết đã làm gì rồi làm tiếp.

---

## 11. Soạn tài liệu nộp (bài học từ Task 2)

Áp dụng cho mọi task tạo file `.docx`/`.pptx`/`.xlsx` từ template của cô (Task 2, 3, 4, 11, 14, 15).

- **Không bao giờ sửa file trong `TEMPLATES_DIR`.** Luôn `shutil.copyfile` sang `deliverables/` rồi mới mở và điền.
- **Điền nội dung bằng cách nhân bản paragraph gốc của template** (`copy.deepcopy` của `w:p`) rồi chỉ đổi text — giữ nguyên font, cỡ chữ, giãn dòng của cô.
- **Xoá `w:spacing` trong `w:rPr` của các run do mình tạo.** Template của cô đặt letter-spacing co `-12` (0.6pt); khi in bằng LibreOffice nó làm **mất hết dấu cách** trên dòng dài ("Vàng A Ký (Team Leader)" → "VàngAKý(TeamLeader)"). Đây là lỗi của LibreOffice gặp template này, không phải do mình — bản gốc cũng bị. Xoá `w:spacing` chỉ đổi 0.6pt typography nhưng chữ hiện đúng.
- **Màu chữ: ép `w:val="000000"` và xoá `w:themeColor`/`w:themeShade`/`w:themeTint`.** Chữ mẫu màu xám là do theme shade, không phải do `w:val`, nên chỉ so sánh `w:val` sẽ không thay được.
- **Mỗi bảng của template bắt đầu bằng một page break cứng và mỗi dòng có `trHeight` tối thiểu.** Nội dung dài hơn mức tối thiểu sẽ làm bảng tràn trang và sinh **trang trắng** ở giữa. Sau khi điền **luôn** kiểm tra:
  ```bash
  soffice --headless --convert-to pdf --outdir /tmp/pdfcheck deliverables/<file>.docx
  pdfinfo /tmp/pdfcheck/<file>.pdf | grep Pages
  for p in $(seq 1 N); do pdftotext -f $p -l $p /tmp/pdfcheck/<file>.pdf - | tr -d '[:space:]' | wc -c; done
  ```
  Trang nào ra ~0 ký tự là trang trắng → phải rút gọn nội dung (giữ đúng 3–6 câu theo yêu cầu) rồi chạy lại.
- **Kiểm tra bố cục bằng ảnh, không chỉ bằng text:** `pdftoppm -r 100 -png <file>.pdf pg` rồi mở từng ảnh. Text có thể đúng mà bố cục vẫn vỡ.
- **Font nhúng của template là font làm mờ (obfuscated)**; script giải mã nằm ở `/tmp/pdfcheck/install_fonts.py`, font đã cài vào `~/.local/share/fonts/course-templates/`.

---

## 12. Tài liệu tham chiếu

| File | Nội dung |
|---|---|
| `REQUIREMENTS.md` | Sản phẩm phải nộp, mốc Day 1–20, rubric, TRL, hạn chế đề tài, cấu trúc Final Report |
| `PROGRESS.md` | Nhật ký tiến độ |
| `docs/topic_decision.md` | Quyết định định khung đề tài và chiến lược dữ liệu (Task 1) |
| `docs/data_dictionary.md` | Từ điển dữ liệu (tạo ở Task 6) |
| `TEMPLATES_DIR` | `/home/hadoop/capstone/templates` — tài liệu gốc của cô (chỉ đọc) |
