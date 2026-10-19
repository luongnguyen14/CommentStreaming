# Hướng dẫn chia sẻ dashboard Streamlit cho máy khác

Tài liệu này hướng dẫn cách cho **một máy khác** (máy thật, laptop của thành viên
khác, điện thoại trong cùng Wi‑Fi, hoặc người ở xa) mở dashboard Streamlit của dự án.

> Dashboard hiện tại: `src/app/app.py`, cổng mặc định **8501**.
> Dữ liệu trên dashboard là **replay từ review IMDb**, không phải bình luận livestream
> thật. Khi chia sẻ ra ngoài, luôn nói rõ điều này.

---

## 0. Chọn cách chia sẻ

| Tình huống | Cách | Máy kia cần cài gì? |
|---|---|---|
| Hai máy cùng mạng LAN / cùng Wi‑Fi phòng học | **Cách A — LAN** | Chỉ cần trình duyệt |
| Người ở xa, cần link gửi qua chat | **Cách B — ngrok** | Chỉ cần trình duyệt |
| Muốn máy kia tự chạy độc lập, không phụ thuộc máy ảo | **Cách C — clone repo** | Python 3.11, Java 8, Spark 3.5.9 |
| Chỉ cần xem giao diện, không cần tương tác | Ảnh chụp / video / PDF | Không |

**Không khuyến nghị Streamlit Community Cloud** cho app này: dịch vụ đó chỉ chạy
Python, **không có Java/Spark**, nên tab **Try It** sẽ lỗi; repo còn chứa 71 MB dữ liệu
`outputs/stream/`. Nếu chỉ muốn chia sẻ Live Monitor/About thì có thể thử, nhưng phải
sửa đường dẫn dữ liệu và chấp nhận mất Try It.

---

## 1. Chuẩn bị dashboard trên máy gốc

Mở terminal trên máy ảo:

```bash
cd /home/hadoop/capstone
source scripts/env.sh

# Kiểm tra xem dashboard có đang chạy sẵn không
pgrep -af 'streamlit run' || echo 'chưa chạy'
curl -s http://localhost:8501/_stcore/health || echo 'chưa trả lời'
```

Nếu chưa chạy:

```bash
$VENV_PY -m streamlit run src/app/app.py \
  --server.address 0.0.0.0 \
  --server.port 8501
```

Điều kiện quan trọng:

- Phải dùng `--server.address 0.0.0.0`, **không** để `127.0.0.1`. Nếu chỉ nghe
  localhost thì máy khác không vào được.
- Giữ terminal này mở trong suốt buổi demo. `Ctrl+C` để dừng.
- Nếu cổng 8501 bận, đổi `--server.port 8502` và dùng cổng đó ở mọi bước sau.
- Dashboard **không cần Kafka** khi chỉ xem dữ liệu có sẵn trong `outputs/stream/`.
- Tab **Try It** cần Java 8 + Spark 3.5.9 và model
  `outputs/models/sentiment_pipeline` (đã có trong repo). Lần chấm đầu mất
  khoảng 15–30 giây để dựng Spark.

Kiểm tra trên máy gốc:

```bash
curl -s http://localhost:8501/_stcore/health      # phải in ra: ok
ss -ltnp | grep 8501                               # phải thấy 0.0.0.0:8501
```

---

## 2. Cách A — Chia sẻ trong cùng mạng LAN

Đây là cách **an toàn và nhanh nhất** khi hai máy ở cùng phòng / cùng Wi‑Fi.

### 2.1. Lấy IP máy ảo

```bash
hostname -I
```

Máy ảo hiện tại có hai địa chỉ:

```text
172.16.99.138  172.16.99.139
```

Chọn địa chỉ **cùng dải mạng** với máy kia. Nếu không chắc, thử lần lượt cả hai.
Thông thường `172.16.99.138` là địa chỉ chính.

### 2.2. Mở từ máy khác

Trên máy khác, mở trình duyệt:

```text
http://172.16.99.138:8501
```

Hoặc kiểm tra bằng dòng lệnh trước khi mở trình duyệt:

```bash
# Trên máy khác (Windows PowerShell / macOS / Linux)
curl http://172.16.99.138:8501/_stcore/health
# Kết quả mong đợi: ok
```

### 2.3. Nếu máy khác không vào được

Kiểm tra theo thứ tự:

1. **Máy ảo có nghe trên 0.0.0.0 không?**
   ```bash
   ss -ltnp | grep 8501
   ```
   Nếu thấy `127.0.0.1:8501` → thiếu `--server.address 0.0.0.0`.

2. **Firewall trên máy ảo có chặn không?**
   ```bash
   sudo ufw status
   # Nếu active:
   sudo ufw allow 8501/tcp
   ```

3. **Hai máy có cùng mạng không?**
   ```bash
   # Trên máy khác
   ping 172.16.99.138
   ```
   Nếu ping không được, hai máy không cùng mạng → dùng Cách B (ngrok) hoặc đổi
   kiểu mạng của VirtualBox.

4. **VirtualBox đang để NAT hay Bridged?**
   - **Bridged Adapter**: máy ảo có IP cùng dải với máy thật → mở trực tiếp
     `http://<IP-máy-ảo>:8501` như trên.
   - **NAT**: máy khác **không** vào được IP `10.0.2.x` / IP nội bộ của máy ảo.
     Phải tạo **Port Forwarding**:
     VirtualBox → Settings → Network → Adapter 1 → Advanced → Port Forwarding:

     | Name | Protocol | Host IP | Host Port | Guest IP | Guest Port |
     |---|---|---|---|---|---|
     | streamlit | TCP | *(trống)* | 8501 | *(trống)* | 8501 |

     Sau đó trên **máy thật** (máy host) mở `http://localhost:8501`; trên **máy khác
     trong LAN** mở `http://<IP-máy-thật>:8501` (ví dụ `http://192.168.1.10:8501`).

5. **Điện thoại trong cùng Wi‑Fi**: dùng IP máy ảo (nếu Bridged) hoặc IP máy thật
   (nếu NAT + port forwarding), không dùng `localhost`.

---

## 3. Cách B — Chia sẻ qua Internet bằng ngrok

Phù hợp khi người nhận **không cùng mạng** và chỉ cần xem trong thời gian ngắn.

Máy ảo hiện đã cài **ngrok 3.39.11** tại `/snap/bin/ngrok` và **đã có authtoken**
trong cấu hình. Không cần đăng ký lại.

### 3.1. Chạy dashboard

Làm theo Mục 1 (dashboard phải đang chạy ở cổng 8501).

### 3.2. Mở tunnel

Mở **terminal thứ hai** trên máy ảo:

```bash
ngrok http 8501
```

Kết quả có dạng:

```text
Session Status   online
Account          ...
Forwarding       https://abcd-1234-5678.ngrok-free.app -> http://localhost:8501
```

Gửi link `https://abcd-1234-5678.ngrok-free.app` cho người nhận. Họ mở bằng trình
duyệt, không cần cài gì.

### 3.3. Dừng tunnel

Quay lại terminal đang chạy ngrok, bấm `Ctrl+C`. Dashboard vẫn chạy; muốn tắt luôn
dashboard thì `Ctrl+C` ở terminal Streamlit.

### 3.4. Nếu ngrok báo lỗi authtoken

```bash
ngrok config add-authtoken <TOKEN>
```

Lấy token tại <https://dashboard.ngrok.com/get-started/your-authtoken> (đăng nhập
tài khoản ngrok). Sau đó chạy lại `ngrok http 8501`.

### 3.5. Lưu ý khi dùng ngrok

- Bản miễn phí dùng **URL ngẫu nhiên**, đổi mỗi lần chạy lại; đừng in URL vào tài liệu.
- Người mở lần đầu có thể thấy trang cảnh báo của ngrok → bấm **Visit Site**.
- **Không có mật khẩu**: ai có link đều mở được dashboard, xem dữ liệu và bấm Try It
  (mỗi lần bấm sẽ khởi động Spark, tốn RAM/CPU). Chỉ chia sẻ với người tin cậy, dừng
  tunnel ngay sau buổi demo.
- Nếu cần bảo vệ bằng mật khẩu, xem Mục 5.

### 3.6. Phương án thay thế — Cloudflare Tunnel

Máy ảo chưa cài `cloudflared`. Nếu muốn dùng:

```bash
# Máy ảo là aarch64 → dùng gói linux-arm64
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared-linux-arm64.deb

# Mở tunnel, không cần tài khoản
cloudflared tunnel --url http://localhost:8501
```

Kết quả in ra một URL `https://random-words.trycloudflare.com`. Dừng bằng `Ctrl+C`.
Nếu máy là x86_64, đổi `linux-arm64` thành `linux-amd64`.

### 3.7. Phương án thay thế — SSH reverse tunnel

Nếu có một máy chủ công khai (VPS) và được phép mở cổng:

```bash
# Trên máy ảo
ssh -R 8501:localhost:8501 user@public-server
# Trên máy chủ, mở http://localhost:8501
# Máy khác mở http://<public-server>:8501 nếu GatewayPorts được bật
```

Cách này cần quyền trên máy chủ và cấu hình `GatewayPorts`; phức tạp hơn ngrok.

---

## 4. Cách C — Cài và chạy trên máy khác

Chọn cách này khi muốn máy kia **tự chạy độc lập**, không phụ thuộc máy ảo.

### 4.1. Yêu cầu

| Thành phần | Phiên bản | Ghi chú |
|---|---|---|
| Python | **3.11** | PySpark 3.5.9 không chạy với Python 3.14 |
| Java | 8 | Spark 3.5.9 cũng chạy với Java 11/17, nhưng dự án đã kiểm chứng với Java 8 |
| Spark | **3.5.9** | Bắt buộc khớp phiên bản model đã lưu |
| RAM | ≥ 2 GB trống | Try It dựng Spark local |
| Ổ đĩa | ~2 GB | Repo + venv + Spark |

### 4.2. Clone repo

Repo công khai:

```bash
git clone https://github.com/luongnguyen14/CommentStreaming.git
cd CommentStreaming
```

Repo đã chứa:

- `outputs/models/sentiment_pipeline` (~904 KB) — model để chấm điểm;
- `outputs/stream/demo` và `outputs/stream/verify1` (~71 MB) — dữ liệu cho Live Monitor.

**Không cần** dữ liệu thô `data/raw/part-01.json` (1,1 GB) hay `data/processed/*.parquet`
để mở dashboard. Chỉ cần chúng khi muốn huấn luyện lại / chạy lại prepare.

### 4.3. Tạo môi trường Python

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` đã có trên GitHub. Nếu bản clone cũ chưa có file này, cài trực tiếp:

```bash
pip install \
  pyspark==3.5.9 streamlit==1.65.0 pandas==3.0.6 numpy==2.4.6 \
  pyarrow==25.0.1 plotly==7.1.0 altair==6.3.0 watchdog==6.0.0 \
  PyYAML==6.0.3 kafka-python==3.0.11
```

### 4.4. Cài Java 8 và Spark 3.5.9

Kiểm tra Java:

```bash
java -version
```

Nếu chưa có Java 8, cài Temurin 8 (Ubuntu/Debian):

```bash
sudo apt update
sudo apt install -y wget apt-transport-https gpg
wget -qO - https://packages.adoptium.net/artifactory/api/gpg/key/public \
  | sudo gpg --dearmor -o /etc/apt/keyrings/adoptium.gpg
echo "deb [signed-by=/etc/apt/keyrings/adoptium.gpg] \
https://packages.adoptium.net/artifactory/deb $(. /etc/os-release; echo $VERSION_CODENAME) main" \
  | sudo tee /etc/apt/sources.list.d/adoptium.list
sudo apt update
sudo apt install -y temurin-8-jdk
```

Tải Spark 3.5.9:

```bash
wget https://archive.apache.org/dist/spark/spark-3.5.9/spark-3.5.9-bin-hadoop3.tgz
tar -xzf spark-3.5.9-bin-hadoop3.tgz -C "$HOME"
```

### 4.5. Đặt biến môi trường

**Không source nguyên `scripts/env.sh`** trên máy mới: file đó hard-code
`/home/hadoop/...` và đường dẫn Java `arm64` của máy ảo. Hãy export theo đường dẫn
thực tế:

```bash
export JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"
export SPARK_HOME="$HOME/spark-3.5.9"
export PYSPARK_PYTHON="$(command -v python3.11)"
export PYSPARK_DRIVER_PYTHON="$(command -v python3.11)"
export PATH="$SPARK_HOME/bin:$PATH"

java -version
python3.11 --version
```

### 4.6. Chạy dashboard

```bash
.venv/bin/python -m streamlit run src/app/app.py \
  --server.address 0.0.0.0 --server.port 8501
```

Mở `http://localhost:8501` trên chính máy đó, hoặc chia sẻ tiếp cho máy khác theo
Cách A/B.

### 4.7. Điều gì chạy được, điều gì cần thêm

| Tab | Cần gì | Ghi chú |
|---|---|---|
| Live Monitor | `outputs/stream/` (có trong repo) | Không cần Kafka, không cần Spark |
| Try It | Java 8 + Spark 3.5.9 + model | Lần đầu chậm 15–30 giây |
| About | `outputs/tables/` + model metadata | Có trong repo |

Nếu **Try It lỗi** nhưng Live Monitor/About vẫn chạy, kiểm tra theo thứ tự:
`java -version`, `echo $SPARK_HOME`, `python3.11 --version`, và sự tồn tại của
`outputs/models/sentiment_pipeline`.

### 4.8. Windows / macOS

- **Windows:** khuyến nghị dùng **WSL2** (Ubuntu) rồi làm đúng các bước trên. Chạy
  Spark native trên Windows cần `winutils.exe`/`hadoop.dll` và dễ lỗi; chưa kiểm chứng.
- **macOS:** cài Java 8 (Temurin), Spark 3.5.9 và Python 3.11 bằng Homebrew/pyenv;
  các lệnh `export` tương tự.

---

## 5. (Tuỳ chọn) Bảo vệ dashboard bằng mật khẩu

Streamlit **không có đăng nhập sẵn**. Khi chia sẻ qua Internet, có thể đặt Nginx phía
trước để hỏi mật khẩu.

```bash
sudo apt install -y nginx apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd demo
```

Tạo `/etc/nginx/sites-available/streamlit`:

```nginx
server {
    listen 8080;
    server_name _;

    auth_basic "Streamlit";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

Kích hoạt:

```bash
sudo ln -s /etc/nginx/sites-available/streamlit /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Sau đó chia sẻ `http://<IP>:8080` (LAN) hoặc `ngrok http 8080` (Internet). Người nhận
phải nhập mật khẩu. Đây là cấu hình tham khảo, **chưa chạy thử trên máy ảo này**.

---

## 6. Kiểm tra sau khi chia sẻ

- [ ] Trên máy gốc: `curl http://localhost:8501/_stcore/health` → `ok`.
- [ ] Trên máy nhận: `curl http://<IP>:8501/_stcore/health` → `ok` (hoặc mở trình duyệt).
- [ ] Mở đủ 3 tab: Live Monitor, Try It, About.
- [ ] Sidebar chọn đúng lần chạy (`demo` hoặc `verify1`) và thấy dữ liệu.
- [ ] Try It: bấm một câu ví dụ, thấy nhãn + xác suất.
- [ ] Dừng tunnel/dashboard sau khi demo xong.
- [ ] Không để lộ URL công khai trong nhóm chat/báo cáo.

---

## 7. Lỗi thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Máy khác báo `Connection refused` | Dashboard chỉ nghe `127.0.0.1` | Chạy lại với `--server.address 0.0.0.0` |
| Máy khác báo timeout | Firewall hoặc khác mạng | `sudo ufw allow 8501/tcp`; kiểm tra ping; dùng Bridged/NAT forwarding/ngrok |
| `curl` trên máy ảo ra `ok`, máy khác không vào được | NAT chưa port-forward | Tạo rule 8501 → 8501 trong VirtualBox |
| `ngrok` báo `ERR_NGROK_4018` | Thiếu authtoken | `ngrok config add-authtoken <TOKEN>` |
| Ngrok mở ra trang cảnh báo | Chặn của bản miễn phí | Bấm **Visit Site** |
| Streamlit báo lỗi websocket sau Nginx | Thiếu header `Upgrade` | Dùng đúng cấu hình ở Mục 5 |
| Try It báo `JAVA_HOME is not set` | Chưa export Java | `export JAVA_HOME=...`; kiểm tra `java -version` |
| Try It báo lỗi PySpark/cloudpickle | Dùng Python 3.14 | Dùng Python 3.11 cho cả driver và executor |
| `pip install` lỗi phiên bản | Python quá mới | Tạo venv bằng `python3.11` |
| Cổng 8501 bận | Dashboard cũ đang chạy | `--server.port 8502` hoặc dừng tiến trình cũ |
| Live Monitor trống | Chưa chọn đúng run, hoặc chưa có dữ liệu | Chọn `demo`/`verify1`; dữ liệu chỉ có sau khi job streaming ghi |
| Bảng “bình luận mới nhất” trống | Job streaming không bật `--keep-text` | Chạy `scripts/run_demo.sh` (đã bật sẵn) hoặc thêm `--keep-text` |

---

## 8. Lưu ý dữ liệu, quyền riêng tư và tài nguyên

1. **Đây là dữ liệu replay** từ review IMDb công khai, không phải bình luận livestream
   thật. Không được gọi là “dữ liệu livestream” trong báo cáo.
2. **Không có đăng nhập.** Khi dùng ngrok/Cloudflare, ai có URL đều xem được. Chỉ chia
   sẻ trong thời gian demo, với người tin cậy; dừng tunnel ngay sau đó.
3. **Không đưa bình luận thật của người dùng lên dashboard công khai.** App có che từ
   nhạy cảm nhưng không thay thế được việc kiểm soát quyền truy cập.
4. **Try It khởi động Spark** cho mỗi phiên; nhiều người bấm cùng lúc sẽ tốn RAM/CPU.
   Máy ảo cấu hình thấp chỉ nên phục vụ 1–3 người xem.
5. **Không chia sẻ file template của giảng viên** qua tunnel/cloud; chỉ chia sẻ dashboard.
6. Dừng sạch sau demo:
   ```bash
   # Dừng ngrok: Ctrl+C ở terminal ngrok
   # Dừng dashboard: Ctrl+C ở terminal Streamlit
   # Nếu chạy bằng run_demo.sh:
   bash scripts/run_demo.sh --stop
   ```

---

## 9. Tài liệu liên quan

| File | Nội dung |
|---|---|
| `src/app/README.md` | Cách chạy dashboard, 3 tab, port forwarding, chụp ảnh/quay video |
| `docs/huong_dan_lay_file_word.md` | Tải file Word về máy, chạy lại toàn bộ dự án trên máy gốc/máy mới |
| `scripts/run_demo.sh` | Chạy toàn bộ Kafka → streaming → dashboard bằng một lệnh |
| `requirements.txt` | Phiên bản Python package đã kiểm chứng |
| `outputs/stream/` | Dữ liệu dashboard đọc (đã có trong repo) |
| `outputs/models/sentiment_pipeline` | Model cho tab Try It (đã có trong repo) |
