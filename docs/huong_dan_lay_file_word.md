# Hướng dẫn lấy file Word về máy và chạy trên máy gốc

Tài liệu này hướng dẫn:

1. **Lấy file Word** (`Final_Report.docx` và báo cáo kỹ thuật tiếng Việt) từ máy ảo
   hoặc GitHub về máy cá nhân.
2. **Mở file Word** đúng cách, cài font nếu cần, và xuất lại PDF.
3. **Chạy lại chương trình** trên máy gốc (máy ảo đã có đủ dữ liệu) và trên một máy
   mới (chỉ có repo GitHub).

> **Nguyên tắc:** file trong `templates/` là tài liệu gốc của giảng viên — **không
> sửa, không đổi tên, không di chuyển, không xóa**. Mọi bản đã điền nằm trong
> `deliverables/` và `docs/`.

---

## 1. File cần lấy

| File | Vị trí trong dự án | Dùng để |
|---|---|---|
| Báo cáo cuối kỳ tiếng Anh (bản nộp) | `deliverables/Final_Report.docx` | Nộp cho giảng viên |
| Bản PDF của báo cáo tiếng Anh | `deliverables/Final_Report.pdf` | Đọc/in, giữ đúng bố cục |
| Báo cáo kỹ thuật tiếng Việt | `docs/bao_cao_ky_thuat_vi.docx` | Giải thích chương trình/mô hình |
| Bản PDF tiếng Việt | `docs/bao_cao_ky_thuat_vi.pdf` | Đọc/in |
| Bản tóm tắt Markdown | `docs/bao_cao_ky_thuat_vi.md` | Đọc nhanh trên GitHub |

Đường dẫn đầy đủ trên máy ảo:

```
/home/hadoop/capstone/deliverables/Final_Report.docx
/home/hadoop/capstone/deliverables/Final_Report.pdf
/home/hadoop/capstone/docs/bao_cao_ky_thuat_vi.docx
/home/hadoop/capstone/docs/bao_cao_ky_thuat_vi.pdf
```

---

## 2. Cách lấy file về máy cá nhân

### Cách A — Tải từ GitHub (khuyến nghị nếu repo đã được đẩy lên)

1. Mở trình duyệt, vào repo:
   `https://github.com/luongnguyen14/CommentStreaming`
2. Vào thư mục `deliverables/` (hoặc `docs/`).
3. Bấm vào file `Final_Report.docx`.
4. GitHub không xem trước được `.docx`; bấm nút **Download** (biểu tượng tải xuống)
   ở góc phải, hoặc chuột phải → **Save link as…**.
5. Lặp lại với `Final_Report.pdf`, `docs/bao_cao_ky_thuat_vi.docx`,
   `docs/bao_cao_ky_thuat_vi.pdf` nếu cần.

> Nếu repo để **private**, phải đăng nhập GitHub bằng tài khoản có quyền truy cập.
> Nếu không thấy nút Download, dùng **Code → Download ZIP** rồi giải nén.

### Cách B — Chép từ máy ảo bằng `scp` (nhanh nhất nếu đang dùng máy ảo)

Trên **máy ảo**, mở terminal và lấy địa chỉ IP:

```bash
hostname -I
```

Ví dụ ra `192.168.1.23`. Trên **máy cá nhân** (Windows/macOS/Linux), mở terminal
(PowerShell trên Windows) và chạy:

```bash
scp hadoop@192.168.1.23:/home/hadoop/capstone/deliverables/Final_Report.docx .
scp hadoop@192.168.1.23:/home/hadoop/capstone/deliverables/Final_Report.pdf .
scp hadoop@192.168.1.23:/home/hadoop/capstone/docs/bao_cao_ky_thuat_vi.docx .
scp hadoop@192.168.1.23:/home/hadoop/capstone/docs/bao_cao_ky_thuat_vi.pdf .
```

Dấu `.` ở cuối nghĩa là “lưu vào thư mục hiện tại”. Nếu muốn lưu vào Downloads:

```bash
# Windows PowerShell
scp hadoop@192.168.1.23:/home/hadoop/capstone/deliverables/Final_Report.docx $HOME\Downloads\
# macOS / Linux
scp hadoop@192.168.1.23:/home/hadoop/capstone/deliverables/Final_Report.docx ~/Downloads/
```

Nếu `scp` báo `Permission denied`, kiểm tra lại tên đăng nhập (`hadoop`) và mật khẩu
của máy ảo. Nếu báo `Connection refused`, bật SSH trong máy ảo:

```bash
sudo apt install openssh-server
sudo systemctl enable --now ssh
```

### Cách C — Thư mục chia sẻ của VirtualBox

1. Trong cửa sổ máy ảo, chọn **Devices → Shared Folders → Shared Folders Settings**.
2. Bấm **Add** (biểu tượng dấu cộng):
   - Folder Path: chọn thư mục trên máy thật (ví dụ `D:\Capstone`).
   - Folder Name: `capstone`.
   - Tick **Auto-mount** và **Make Permanent**.
3. Trong máy ảo, cài Guest Additions nếu chưa có, rồi mount:

```bash
sudo mkdir -p /mnt/capstone
sudo mount -t vboxsf capstone /mnt/capstone
```

4. Chép file:

```bash
cp /home/hadoop/capstone/deliverables/Final_Report.docx /mnt/capstone/
cp /home/hadoop/capstone/deliverables/Final_Report.pdf  /mnt/capstone/
cp /home/hadoop/capstone/docs/bao_cao_ky_thuat_vi.docx  /mnt/capstone/
cp /home/hadoop/capstone/docs/bao_cao_ky_thuat_vi.pdf   /mnt/capstone/
```

5. Mở thư mục `D:\Capstone` trên máy thật để lấy file.

> Nếu mount báo `mount: unknown filesystem type 'vboxsf'`, cần cài **VirtualBox Guest
> Additions** trong máy ảo: Devices → Insert Guest Additions CD image → chạy installer.

### Cách D — USB hoặc dịch vụ lưu trữ

Chép file ra USB (nếu máy ảo nhận USB), hoặc upload lên Google Drive/OneDrive rồi tải
xuống máy thật. Không upload dữ liệu thô hay file template của giảng viên lên dịch vụ
công khai.

---

## 3. Mở file Word trên máy cá nhân

### 3.1. Microsoft Word

1. Mở Word → **File → Open** → chọn `Final_Report.docx`.
2. Nếu Word hiện **Protected View**, bấm **Enable Editing**.
3. Nếu Word hỏi “This document contains fields that may refer to other files”,
   bấm **Yes** để cập nhật số trang.
4. Kiểm tra nhanh:
   - Trang bìa có tiêu đề trong khung xám, ngày `19/10/26`, `Team 6`.
   - Mục 1–5 có nội dung; mục 6 để trống cho giảng viên.
   - Không có trang trắng ở giữa.
   - Bảng có header xanh, chữ trắng; biểu đồ rõ nét.

### 3.2. Font chữ

Báo cáo tiếng Anh dùng font **SamsungOne-400** (font nhúng trong template của cô).
Nếu máy chưa có font này, Word sẽ **tự thay thế** bằng font khác — nội dung vẫn đúng
nhưng bố cục có thể xê dịch vài dòng.

Có ba cách xử lý:

1. **Xem bản PDF** (`Final_Report.pdf`) — đây là bản giữ đúng bố cục nhất, không cần
   font.
2. **Cài font trên máy ảo Linux** (nơi có template):
   ```bash
   /usr/bin/python3 scripts/install_template_fonts.py
   fc-cache -f -v
   ```
   Font được giải mã vào `~/.local/share/fonts/course-templates/`.
3. **Cài font trên Windows/macOS:** chép các file `.ttf` trong
   `~/.local/share/fonts/course-templates/` từ máy ảo sang máy thật, rồi:
   - Windows: chuột phải file `.ttf` → **Install** (hoặc **Install for all users**).
   - macOS: mở file `.ttf` bằng **Font Book** → **Install Font**.

> Chỉ cài font để hiển thị. **Không chép file template gốc** ra ngoài hoặc đưa lên
> mạng — template thuộc bản quyền của giảng viên/Samsung.

### 3.3. LibreOffice (miễn phí)

1. Mở **LibreOffice Writer** → **File → Open** → chọn `.docx`.
2. Nếu LibreOffice hỏi giữ định dạng, chọn **Use Word 2007-365!** khi lưu.
3. Xuất PDF:
   ```bash
   soffice --headless --convert-to pdf --outdir . Final_Report.docx
   ```
4. Kiểm tra số trang:
   ```bash
   pdfinfo Final_Report.pdf | grep Pages
   ```
   Báo cáo tiếng Anh hiện có **22 trang**; báo cáo tiếng Việt có **33 trang**.

### 3.4. Xuất lại PDF từ Word

- **Word:** File → **Save As** → chọn **PDF (*.pdf)** → Save.
- **LibreOffice:** File → **Export as PDF** → Export.
- **Google Docs:** File → **Download** → **PDF Document (.pdf)** (chỉ dùng nếu đã
  upload; kiểm tra lại bố cục vì Google Docs có thể đổi font).

---

## 4. Chạy chương trình trên máy gốc (máy ảo đã có dữ liệu)

Máy gốc là máy ảo hiện tại, nơi đã có `data/raw/part-01.json`, dữ liệu đã xử lý và
model đã lưu. Chỉ cần mở terminal:

```bash
cd /home/hadoop/capstone
source scripts/env.sh
```

### 4.1. Kiểm tra môi trường

```bash
bash scripts/check_env.sh
```

Kết quả mong đợi: Java 8, Spark 3.5.9, Kafka 4.3.1, Python 3.11, các thư mục dữ liệu
tồn tại. Nếu HDFS chưa bật:

```bash
start-dfs.sh
hdfs dfsadmin -safemode wait
```

### 4.2. Chạy test tự động

```bash
.venv/bin/python -m pytest tests/ -q
```

Kết quả đã đo ngày 15/10/2026: **77 passed**. Nếu test lỗi hàng loạt, kiểm tra HDFS
đang bật và đã ra safe mode.

### 4.3. Thử nghiệm mô hình (không cần Kafka)

```bash
# 4 câu ví dụ
bash scripts/run_model_trial.sh --examples

# một câu tự nhập
bash scripts/run_model_trial.sh --text "not bad at all"

# đo trên 200 dòng test
bash scripts/run_model_trial.sh --test-sample 200
```

Kết quả `--test-sample 200` được ghi vào:
`outputs/tables/model_trial_summary.csv` và
`outputs/tables/model_trial_predictions.csv`.

### 4.4. Chạy toàn bộ demo (Kafka → streaming → dashboard)

```bash
# Chạy 10 phút rồi tự dừng sạch
bash scripts/run_demo.sh --duration 600

# Hoặc chạy tới khi Ctrl+C
bash scripts/run_demo.sh
```

Dashboard mở ở `http://localhost:8501`. Nếu chạy máy ảo không có giao diện, dùng
port forwarding của VirtualBox (Settings → Network → Advanced → Port Forwarding:
host 8501 → guest 8501) rồi mở `http://localhost:8501` trên máy thật.

Dừng sạch:

```bash
bash scripts/run_demo.sh --stop
```

### 4.5. Chạy streaming thủ công

```bash
# Khởi động Kafka + tạo topic
bash kafka/start_kafka.sh
bash kafka/create_topics.sh

# Job streaming ở nền, chờ READY
bash scripts/run_stream.sh verify1 --trigger-seconds 5

# Phát 1.000 bình luận từ tập test
$VENV_PY src/producer/replay_producer.py --only-test --max 1000 --rate 50

# Gửi các ca kiểm chứng (heartbeat, late, lỗi cố ý)
$VENV_PY scripts/send_bad_events.py --heartbeat 12 --heartbeat-interval 25 --late-probe

# Dừng êm
bash scripts/stop_stream.sh verify1
```

---

## 5. Chạy trên một máy mới (chỉ có repo GitHub)

### 5.1. Clone repo

```bash
git clone git@github.com:luongnguyen14/CommentStreaming.git
cd CommentStreaming
```

Nếu chưa cấu hình SSH cho GitHub, dùng HTTPS:

```bash
git clone https://github.com/luongnguyen14/CommentStreaming.git
```

### 5.2. Cài môi trường

| Thành phần | Phiên bản | Ghi chú |
|---|---|---|
| Java cho Spark | 8 | Bắt buộc với Spark 3.5.9 |
| Spark | 3.5.9 | Đặt `SPARK_HOME` |
| Kafka | 4.3.1 (KRaft) | Cần Java 17 |
| Python cho Spark | 3.11 | `PYSPARK_PYTHON` |
| Python cho venv | 3.11+ | Tạo `.venv` |

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
source scripts/env.sh
```

### 5.3. Dữ liệu — điểm cần chú ý

**Repo GitHub không chứa dữ liệu thô và dữ liệu đã xử lý** (xem `.gitignore`):
`data/raw/part-01.json` (1,1 GB) và `data/processed/*.parquet` không được commit.
Model đã lưu (`outputs/models/sentiment_pipeline`, ~916 KB) **có** trong repo, nên
chương trình thử nghiệm mô hình chạy được ngay.

Muốn chạy streaming trên máy mới, cần dữ liệu test:

1. Tải `part-01.json` từ Kaggle:
   `https://www.kaggle.com/datasets/ebiswas/imdb-review-dataset` (CC0).
2. Đặt vào `data/raw/part-01.json`.
3. Chạy:
   ```bash
   $VENV_PY src/training/prepare.py
   ```
4. **Lưu ý tái lập:** dữ liệu 201.074 bản ghi hiện có được tạo bằng code cũ
   (`crc32 % 5 == 0`). `config.yaml` hiện tại là `subsample_pct: 64` — chạy lại sẽ
   ra một tập khác. Muốn đúng số liệu báo cáo, chép `data/processed/` từ máy gốc
   hoặc dùng code cũ; nếu chỉ cần chạy demo, tập mới vẫn dùng được nhưng mọi chỉ số
   phải đo lại.

### 5.4. Chạy thử

```bash
bash scripts/check_env.sh
bash scripts/run_model_trial.sh --examples
bash scripts/run_model_trial.sh --test-sample 200
```

Nếu chưa có Kafka, chỉ chạy được phần thử nghiệm mô hình; streaming cần Kafka và
dữ liệu test.

---

## 6. Lỗi thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `ModuleNotFoundError: No module named 'pyspark'` | Dùng Python hệ thống thay vì venv | `source scripts/env.sh`, dùng `$VENV_PY` |
| Spark chết khi khởi động | HDFS tắt hoặc đang safe mode | `start-dfs.sh`, `hdfs dfsadmin -safemode wait` |
| `Connection refused` khi `scp` | SSH chưa bật | `sudo systemctl enable --now ssh` |
| Word thay font, chữ giãn cách lạ | Thiếu SamsungOne-400 | Xem PDF, hoặc cài font ở mục 3.2 |
| PDF có trang trắng | Nội dung tràn trang | Dùng bản PDF đã kiểm tra; nếu tự sửa DOCX, kiểm tra lại bằng `pdfinfo` + `pdftotext` |
| Dashboard không mở | Chưa chạy demo hoặc sai port | Kiểm tra `logs/task10_*.log`, mở đúng `http://localhost:8501` |
| Producer gửi nhưng không có kết quả | Job chưa READY, `startingOffsets=latest` | Chờ `run_stream.sh` báo READY rồi mới gửi |
| Test lỗi 26 trường hợp | HDFS chưa bật | Bật HDFS, chờ safe mode off |
| `git push` báo `Permission denied (publickey)` | Chưa thêm SSH key vào GitHub | Xem mục 7 |

---

## 7. Đẩy lên GitHub (nếu cần)

Kiểm tra remote:

```bash
git remote -v
```

Nếu dùng SSH và gặp `Permission denied (publickey)`:

```bash
# Xem public key
cat ~/.ssh/id_ed25519.pub
```

Copy toàn bộ dòng đó, vào **GitHub → Settings → SSH and GPG keys → New SSH key**,
dán và lưu. Kiểm tra:

```bash
ssh -T git@github.com
```

Nếu vẫn lỗi, thử dùng HTTPS với token cá nhân:

```bash
git remote set-url origin https://github.com/luongnguyen14/CommentStreaming.git
git push origin main
# Username: <tài khoản GitHub>
# Password: <personal access token, không phải mật khẩu>
```

Tạo token tại **GitHub → Settings → Developer settings → Personal access tokens**.

---

## 8. Checklist trước khi nộp

- [ ] Đã tải `deliverables/Final_Report.docx` và `.pdf`.
- [ ] Mở DOCX bằng Word/LibreOffice, kiểm tra không có trang trắng.
- [ ] Đã chèn **ảnh nhóm** vào mục 5 của báo cáo tiếng Anh (repo chưa có ảnh).
- [ ] Đã kiểm tra mục 6 để trống cho giảng viên.
- [ ] Đã tải `docs/bao_cao_ky_thuat_vi.docx`/`.pdf` nếu cần bản tiếng Việt.
- [ ] Đã chạy `bash scripts/run_model_trial.sh --examples` trên máy gốc.
- [ ] Đã nói rõ dữ liệu streaming là **replay**, không phải livestream thật.
- [ ] Đã nói rõ **exactly-once chưa kiểm chứng**.
- [ ] Đã kiểm tra GitHub đã có commit mới nhất (nếu nộp kèm link).
