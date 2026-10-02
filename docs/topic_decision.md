# Topic Framing and Data Strategy Decision
## Quyết định định khung đề tài và chiến lược dữ liệu

**Dự án:** Mô hình phân loại cảm xúc dựa trên bình luận trực tuyến
(Real-time Sentiment Classification of Online Comments using Kafka, Spark Structured Streaming and Spark ML)

**Nhóm:** Nhóm 6 — Nhóm trưởng: Vàng A Ký — Thành viên: Nguyễn Đình Bằng; Vàng Thị Dẳm; Dương Thị Hạnh; Ngô Lương Nguyên
**Task:** 1 (Day 1–2) · **Ngày soạn:** 02/10/2026 · **Trạng thái:** ⏳ *chờ nhóm chốt và hỏi cô*

---

## 0. Tóm tắt quyết định

| Hạng mục | Khuyến nghị | Trạng thái |
|---|---|---|
| **Cách định khung** | **(A) An toàn cộng đồng & sức khỏe tinh thần cho người làm livestream nhỏ** | Cần cô xác nhận |
| **Ngôn ngữ** | **Tiếng Anh** (tiếng Việt để ở phần hướng phát triển) | Cần cô xác nhận |
| **Dữ liệu huấn luyện** | Bộ dữ liệu bình luận YouTube 3 lớp đã có sẵn trên máy (`YoutubeCommentsDataSet.csv`, 18.408 dòng) — **phải truy vết nguồn gốc trước khi dùng** | ⚠️ Cần kiểm chứng nguồn |
| **Cách tạo luồng** | **Replay có nhãn qua Kafka** (phương án *c*), **không** thu livestream thật | — |
| **Kiến trúc** | Producer → Kafka `comments_raw` → Spark Structured Streaming → Parquet + Kafka `comments_scored` → Dashboard | — |

**Điểm cần lưu ý nhất:** đây là dự án **học thuật mô phỏng bằng dữ liệu replay**, không phải hệ thống thu thập
livestream thật. Điều này **phải được nói rõ** trong mọi tài liệu nộp, và **phù hợp với TRL 5**
("validated in a simulated environment") — xem `REQUIREMENTS.md` §4.

---

## 1. Ba cách định khung đề tài để có lợi ích cộng đồng rõ ràng

Cô yêu cầu đề tài thuộc **"Technology for Good"**: vì lợi ích công chúng, không chỉ một công ty hưởng lợi,
và **không chỉ chứng minh kỹ thuật** (FAQ Q2 trong Student's Guide).

> ⚠️ **Rủi ro chung của đề tài gốc:** "phân loại cảm xúc bình luận livestream" rất dễ bị hội đồng đọc thành
> **công cụ bán hàng** (tối ưu doanh thu) hoặc **bài tập kỹ thuật Kafka + Spark**.
> Cả ba cách dưới đây đều nhằm giải quyết rủi ro đó.

---

### Cách A — An toàn cộng đồng và sức khỏe tinh thần cho người làm livestream nhỏ

**Tên tiếng Anh gợi ý:** *Early-Warning System for Harmful Comment Spikes in Small-Streamer Live Chats*

| Mục | Nội dung |
|---|---|
| **Vấn đề thực tế** | Người làm livestream nhỏ (một mình, không có đội kiểm duyệt) thường xuyên hứng chịu các đợt bình luận tiêu cực, quấy rối hoặc "raid" có tổ chức. Chat chạy quá nhanh để đọc bằng mắt, nên họ hoặc là bỏ qua, hoặc là phản ứng muộn. Hệ quả là căng thẳng, kiệt sức và bỏ nghề. |
| **Ai hưởng lợi** | Người làm livestream nhỏ và cá nhân; người kiểm duyệt cộng đồng (moderator) tình nguyện; khán giả (chat an toàn hơn). Đây là nhóm **không có ngân sách** cho công cụ thương mại. |
| **Điểm mới** | Không phân loại từng bình luận một cách rời rạc, mà **phát hiện sớm đợt bùng nổ tiêu cực** theo cửa sổ thời gian trên **thiết bị phổ thông**. Kết hợp độ trễ phát hiện (detection latency) như một chỉ số đánh giá, không chỉ F1. |
| **Rủi ro bị coi là "thương mại thuần túy"** | Nếu báo cáo dùng từ ngữ như "tăng doanh thu", "tăng tương tác", "giữ chân người xem" thì sẽ bị đọc là công cụ bán hàng. → **Giảm rủi ro:** tuyệt đối không dùng chỉ số kinh doanh; chỉ dùng chỉ số an toàn (số đợt tiêu cực phát hiện được, độ trễ cảnh báo). Nhấn mạnh đối tượng là người **không có nguồn thu** từ livestream. |
| **Rủi ro bị coi là "chỉ chứng minh kỹ thuật"** | Nếu báo cáo chỉ trình bày Kafka/Spark/ML. → **Giảm rủi ro:** mở đầu bằng vấn đề an toàn tinh thần, có **quy trình ứng xử cụ thể** khi cảnh báo xuất hiện, có kịch bản người dùng và hướng dẫn vận hành. |
| **Rủi ro quyền riêng tư** | Người bình luận là **bên thứ ba**: suy luận cảm xúc của họ là xử lý dữ liệu cá nhân; cảnh báo có thể dẫn tới kiểm duyệt quá tay. → **Giảm rủi ro:** băm có muối mã người dùng; **không lưu văn bản gốc** trong đầu ra tổng hợp; chỉ hiển thị số liệu tổng hợp theo cửa sổ thời gian; **không nhắm mục tiêu vào cá nhân**; ghi rõ giới hạn trong báo cáo. |
| **Điểm yếu cần lưu ý** | Livestream gần với lĩnh vực **giải trí** — một trong các lĩnh vực bị cô "highly discouraged". Cần lập luận rằng giá trị ở đây là **an toàn**, không phải giải trí. **Đây là câu hỏi số 1 phải hỏi cô.** |

---

### Cách B — Phản hồi tức thời cho livestream giáo dục hoặc dịch vụ công

**Tên tiếng Anh gợi ý:** *Real-time Audience Confusion Detection for Educational and Public-Service Livestreams*

| Mục | Nội dung |
|---|---|
| **Vấn đề thực tế** | Lớp học trực tuyến và các buổi livestream giải đáp của cơ quan công quyền có rất nhiều bình luận nhưng người dẫn không đọc kịp. Họ không biết học viên/người dân đang **hiểu sai**, **bối rối** hay **bực bội** cho đến khi buổi học kết thúc — lúc đó đã muộn. |
| **Ai hưởng lợi** | Học viên (được giải đáp đúng lúc); giáo viên/người dẫn (điều chỉnh nhịp độ ngay); cơ quan dịch vụ công và người dân (livestream Q&A hiệu quả hơn). |
| **Điểm mới** | Chuyển mục tiêu từ "cảm xúc về sản phẩm" sang **tín hiệu bối rối / mất kết nối trong học tập**; cảnh báo theo cửa sổ trượt ngắn để kịp can thiệp; chỉ số quan tâm là **thời gian từ lúc bùng nổ đến lúc cảnh báo**. |
| **Rủi ro "thương mại"** | **Thấp nhất trong ba cách** — giáo dục và dịch vụ công mặc nhiên là lợi ích công, không ai "bán" được gì từ kết quả. |
| **Rủi ro "chỉ chứng minh kỹ thuật"** | Vẫn có, nếu thiếu kịch bản sử dụng. → **Giảm rủi ro:** mô tả rõ "khi cảnh báo bật thì giáo viên làm gì" (ví dụ: dừng lại, nhắc lại khái niệm, hỏi lại cả lớp) và đo hiệu quả của quy trình đó. |
| **Rủi ro quyền riêng tư** | **Cao nhất** — người bình luận có thể là **học sinh, sinh viên, có thể là trẻ vị thành niên**; dữ liệu gắn với lớp học. → **Giảm rủi ro:** **không theo dõi từng cá nhân dưới mọi hình thức**, chỉ số liệu tổng hợp theo lớp/cửa sổ; xin phép cơ sở giáo dục nếu thu dữ liệu thật; cân nhắc loại bỏ hoàn toàn phần nhận diện người dùng. |
| **Điểm yếu cần lưu ý** | Bộ dữ liệu huấn luyện sẵn có **không thuộc miền giáo dục** → phải trình bày trung thực về **lệch miền dữ liệu (domain shift)**, thậm chí biến nó thành một nội dung phân tích của đề tài. |

---

### Cách C — Công cụ mã nguồn mở chi phí thấp cho tổ chức nhỏ

**Tên tiếng Anh gợi ý:** *A Low-Cost, Self-Hosted Open-Source Comment Sentiment Toolkit for Small Nonprofits and Community Newsrooms*

| Mục | Nội dung |
|---|---|
| **Vấn đề thực tế** | Tổ chức phi lợi nhuận, tòa soạn cộng đồng, nhóm dân sự địa phương có nhu cầu theo dõi phản hồi công chúng nhưng **không đủ tiền** mua công cụ thương mại, và **không muốn đẩy dữ liệu người dân lên dịch vụ đám mây của bên thứ ba**. |
| **Ai hưởng lợi** | Tổ chức phi lợi nhuận, tòa soạn nhỏ, nhóm cộng đồng — và qua họ là công chúng. |
| **Điểm mới** | Đóng góp nằm ở **tính tái lập và chi phí**, không phải thuật toán mới: pipeline chạy được trên một máy ảo phổ thông, cấu hình công khai, tài liệu đầy đủ để tổ chức khác dựng lại. |
| **Rủi ro "thương mại"** | **Thấp** — đối tượng là tổ chức phi lợi nhuận. |
| **Rủi ro "chỉ chứng minh kỹ thuật"** | **Cao nhất trong ba cách** — "chúng em xây một pipeline chạy được" gần như đúng nguyên văn điều cô không khuyến khích. → **Giảm rủi ro:** bắt buộc phải có **kịch bản người dùng thật**, dashboard hướng tới người dùng cuối, và **quy trình vận hành bằng văn bản** mà một tổ chức nhỏ có thể làm theo. |
| **Rủi ro quyền riêng tư** | Tự lưu trữ (self-hosted) là **điểm cộng** vì dữ liệu không rời khỏi tổ chức. Vẫn cần băm/ẩn danh và chỉ hiển thị tổng hợp. |

---

### Bảng so sánh ba cách định khung

| Tiêu chí | A — An toàn streamer nhỏ | B — Giáo dục / dịch vụ công | C — Công cụ mã nguồn mở |
|---|---|---|---|
| Độ mạnh "lợi ích công" | Cao | **Rất cao** | Cao |
| Rủi ro bị coi là "giải trí" | ⚠️ **Có** | Không | Không |
| Rủi ro bị coi là "thương mại" | Trung bình | **Thấp** | Thấp |
| Rủi ro bị coi là "chỉ chứng minh kỹ thuật" | Trung bình | Trung bình | ⚠️ **Cao** |
| Điểm mới (novelty) | **Cao** | Cao | Thấp–Trung bình |
| Mức độ khớp với dữ liệu sẵn có | **Cao** (bình luận YouTube) | Thấp (lệch miền) | Trung bình |
| Rủi ro quyền riêng tư | Trung bình | **Cao** (có thể có trẻ vị thành niên) | Trung bình |
| Giữ được đề tài gốc (livestream + Kafka + Spark) | **Có** | Có | Có |

---

## 2. Chiến lược dữ liệu

### 2.1. Kiểm tra tài nguyên máy ảo (đã chạy thật, ngày 02/10/2026)

```
$ df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p2  262G   33G  219G  13% /          ← 219 GB trống

$ free -h
               total        used        free      shared  buff/cache   available
Mem:           7.0Gi       5.3Gi       178Mi       116Mi       1.6Gi       1.8Gi
Swap:          3.0Gi       163Mi       2.9Gi

$ nproc
4
```

**Đọc kết quả:**

| Tài nguyên | Đo được | Ngưỡng khuyến nghị của khóa | Kết luận |
|---|---|---|---|
| Ổ trống `/` | **219 GB** | ≥ 40 GB | ✅ Thoải mái |
| RAM | **7,0 GB** (chỉ còn **1,8 GB available**) | ≥ 8 GB | ⚠️ **Thiếu — rủi ro cao nhất của dự án** |
| CPU | 4 nhân | — | Đủ cho mức tải dự kiến |

> ⚠️ **Cảnh báo tài nguyên — cần xử lý trước Task 5.**
> Máy chỉ có **7 GB RAM** trong khi khóa khuyến nghị **≥ 8 GB**, và **5,3 GB đã bị chiếm** bởi môi trường
> đồ họa (nautilus 568 MB, firefox 564 MB, gnome-shell 516 MB, ptyxis 469 MB, các tiến trình `Isolated`...).
> Hiện **chưa có tiến trình Java/Kafka/Spark nào chạy**, nên khi bật đồng thời Kafka + Spark job sẽ
> **thiếu RAM nghiêm trọng** và tiến trình có thể bị OOM-kill.
> **Hành động đề xuất:** đóng Firefox/nautilus khi chạy pipeline; giới hạn heap Kafka (ví dụ `KAFKA_HEAP_OPTS=-Xmx512m`);
> đặt `spark.driver.memory` ≤ 2g; giảm số partition của `comments_raw` và tốc độ gửi trong Task 5; tận dụng 3 GB swap.
> Xem thêm `REQUIREMENTS.md` và Task 5 trong kế hoạch.

---

### 2.2. Ba lựa chọn nguồn dữ liệu

#### (a) Bộ dữ liệu cảm xúc có nhãn công khai để huấn luyện

| Bộ dữ liệu | Ngôn ngữ | Số dòng | Nhãn | Giấy phép | Rủi ro |
|---|---|---|---|---|---|
| **UIT-VSFC**<br>`uitnlp/vietnamese_students_feedback` | Tiếng Việt | **16.175**<br>(train 11.426 / val 1.583 / test 3.166) | **3 lớp**: `sentiment` 0=negative, 1=neutral, 2=positive<br>(+ cột `topic`) | **Unknown** (không rõ) | Miền dữ liệu là **phản hồi sinh viên về môn học**, không phải livestream. Giấy phép "Unknown" → **không chắc được phép dùng trong báo cáo học thuật** |
| **UIT-VSMEC**<br>`ura-hcmut/UIT-VSMEC`, `duwuonline/UIT-VSMEC` | Tiếng Việt | **6.927**<br>(5.548 / 686 / 693) | **7 cảm xúc**: Enjoyment, Sadness, Fear, Anger, Disgust, Surprise, Other | **Unknown** (không rõ) | 7 lớp lệch nhau, phải gộp về 3 lớp → mất thông tin và phải tự định nghĩa ánh xạ. Giấy phép cũng "Unknown" |
| **Sentiment140**<br>Kaggle `kazanova/sentiment140` | Tiếng Anh | ~1.600.000 (***cần kiểm chứng*** con số chính xác) | Thực chất **2 lớp** (+/−) sinh bằng **distant supervision** (dựa vào emoticon) — **không có lớp neutral thật** | Không nêu rõ ràng ở nguồn gốc | Nhãn **nhiễu** do gán tự động; thiếu lớp neutral nên **không khớp** bài toán 3 lớp của nhóm |
| **Bộ dữ liệu cục bộ**<br>`/home/hadoop/YoutubeCommentsDataSet.csv` | Tiếng Anh | **18.408** (đo được) | **3 lớp**: positive **11.432** / neutral **4.638** / negative **2.338** | **CẦN KIỂM CHỨNG** | Nguồn gốc **chưa xác định** — xem cảnh báo bên dưới |

**Cách kiểm chứng các con số trên (ngày 02/10/2026):** truy vấn API
`datasets-server.huggingface.co/size` và `/rows` cho từng dataset.
Con số Sentiment140 lấy từ mô tả công khai, **chưa tải về đếm trực tiếp** → ghi rõ *cần kiểm chứng*.

> ⚠️ **CẢNH BÁO VỀ BỘ DỮ LIỆU CỤC BỘ** — đây là ứng viên hấp dẫn nhất nhưng **chưa dùng được ngay**:
> - File có **18.408 dòng**, 2 cột `Comment,Sentiment`; phân bố **positive 11.432 (62,1%) / neutral 4.638 (25,2%) / negative 2.338 (12,7%)** → **mất cân bằng lớp rõ rệt**, phải dùng `weightCol` khi huấn luyện.
> - Đã đo được: **536 dòng trùng chính xác**, **569 dòng trùng sau khi chuẩn hóa**, **44 bình luận rỗng**, **5 văn bản có nhãn mâu thuẫn**. → Nhóm **phải loại trùng trước khi chia tập**, nếu không điểm sẽ cao giả tạo.
> - `md5 = dc4323696d2aac0cd2f9a10707b9a18a`
> - ❌ **Nguồn gốc và giấy phép CHƯA XÁC ĐỊNH.** Tìm kiếm cho thấy có bộ dữ liệu Kaggle mô tả **18.409 mục** với cột *Video ID, Comment, Likes, Sentiment* — **gần giống nhưng không khớp** (file của nhóm chỉ có 2 cột).
> - **Việc phải làm trước Task 6:** tìm lại trang Kaggle/Hugging Face gốc, lưu URL + giấy phép + ngày tải vào `data/raw/SOURCE.md`. **Nếu không truy vết được nguồn, không được dùng trong báo cáo nộp** — vì báo cáo bắt buộc ghi nguồn dữ liệu.

#### (b) Nguồn bình luận livestream thật

| Nguồn | Cách lấy | Điều khoản sử dụng | Quyền riêng tư | Chi phí / hạn mức |
|---|---|---|---|---|
| **YouTube Live chat**<br>(Data API v3, `liveChatMessages.list`) | REST polling hoặc gRPC `streamList`, cần API key / OAuth | Thuộc **YouTube API Services Terms of Service + Developer Policies**. **Cấm scraping.** Phần lớn dữ liệu API **phải xóa hoặc làm mới trong 30 ngày**; yêu cầu xóa của người dùng phải xử lý trong **7 ngày** | Bình luận gắn với kênh/tác giả → **là dữ liệu cá nhân** | Quota mặc định **10.000 units/ngày**. **Chi phí thực của `liveChatMessages.list` không được Google công bố chính thức** — ước tính cộng đồng ~5 units/lần gọi, nghĩa là polling 1 giây/lần **hết quota sau ~33 phút**. *(cần kiểm chứng trên tài liệu chính thức)* |
| **Twitch chat**<br>(IRC / WebSocket) | Kết nối IRC tới máy chủ chat | **Twitch Developer Services Agreement** quy định: chỉ được giữ chat log **trong thời gian cần thiết để vận hành dịch vụ**; **cấm tạo cơ sở dữ liệu công khai**; **cấm thu thập thông tin về người dùng cuối**; phải xử lý yêu cầu opt-out; nói chung **cấm lưu bản sao Twitch Content** (chỉ cho phép cache 24 giờ) | Tương tự YouTube — người bình luận là bên thứ ba | Miễn phí về tiền, nhưng **điều khoản gần như không cho phép dùng cho dự án này** |

> ❌ **Kết luận: KHÔNG dùng livestream thật làm nguồn dữ liệu chính.**
> Cả hai nền tảng đều **hạn chế rõ ràng** việc lưu trữ và tái sử dụng bình luận của người dùng cuối.
> Rủi ro vi phạm điều khoản **lớn hơn nhiều** so với lợi ích học thuật thu được.
> Nếu nhóm vẫn muốn có một mẫu nhỏ dữ liệu thật để đo **lệch miền dữ liệu**, phải: (1) hỏi ý kiến cô trước,
> (2) chỉ lấy mẫu rất nhỏ, (3) ẩn danh ngay khi thu, (4) không công bố văn bản gốc, (5) ghi rõ trong báo cáo.
> **Đây là việc tùy chọn, không nằm trong đường găng của dự án.**

#### (c) Phát lại (replay) dữ liệu có nhãn qua Kafka để mô phỏng livestream

Đọc dữ liệu đã có nhãn và **gửi lại qua Kafka theo tốc độ điều khiển được** (`--rate`, `--burst`, `--late-ratio`),
tạo ra một luồng bình luận liên tục giống livestream thật về mặt **vận tốc và tính liên tục**.

- ✅ Có nhãn sẵn → **đo được chất lượng trên luồng** và so sánh với kết quả offline.
- ✅ Điều khiển được tốc độ, độ trễ, bùng nổ, bản ghi lỗi → **kiểm thử được watermark, DLQ, chịu lỗi**.
- ✅ Lặp lại được → thí nghiệm có thể tái lập (rất quan trọng cho phần Result của rubric).
- ❌ **Không phải dữ liệu livestream thật** → bắt buộc phải ghi rõ trong mọi tài liệu nộp.

#### Bảng so sánh tổng hợp ba lựa chọn

| Tiêu chí | (a) Dataset công khai có nhãn | (b) Livestream thật | (c) Replay qua Kafka |
|---|---|---|---|
| Ngôn ngữ | Việt (UIT-VSFC, UIT-VSMEC) / Anh (Sentiment140, bộ cục bộ) | Tiếng Việt/Anh/đa ngữ | Theo bộ dữ liệu nguồn |
| Số dòng | 6.927 – 1.600.000 | Không giới hạn (theo phiên live) | 18.408 (bộ cục bộ) hoặc theo dataset |
| Có nhãn không | ✅ Có | ❌ **Không** | ✅ Có |
| Giấy phép | Phần lớn ghi **"Unknown"** → rủi ro | **Bị hạn chế bởi ToS** | Thừa hưởng từ dataset nguồn |
| Chi phí | Miễn phí | Tốn quota / phụ thuộc nền tảng | Miễn phí |
| Rủi ro chính | Lệch miền, giấy phép mơ hồ | **Vi phạm điều khoản**, quyền riêng tư, hết quota | Bị coi là "không phải dữ liệu thật" → **phải nói rõ** |
| Dùng được để **đánh giá** | ✅ | ❌ (không có nhãn) | ✅ |
| **Kết luận** | ✅ **Dùng làm nguồn huấn luyện** | ❌ **Loại** | ✅ **Dùng làm cách tạo luồng** |

**→ Chiến lược chốt: dùng (a) để huấn luyện + (c) để tạo luồng. Không dùng (b).**

---

## 3. Quyết định ngôn ngữ và cách xử lý văn bản

### 3.1. So sánh

| Tiêu chí | Tiếng Việt | Tiếng Anh |
|---|---|---|
| Dữ liệu có nhãn sẵn | UIT-VSFC (16.175 dòng, **đúng 3 lớp**), UIT-VSMEC (6.927 dòng, 7 lớp) | Sentiment140 (1,6 triệu, **chỉ 2 lớp**), **bộ cục bộ 18.408 dòng, đúng 3 lớp** |
| Giấy phép | ⚠️ **"Unknown"** ở cả hai bộ | ⚠️ Bộ cục bộ **chưa rõ nguồn**; Sentiment140 không nêu rõ |
| Tách từ | ❌ **Cần tách từ** (`underthesea`/`pyvi`) → phải dùng **Python UDF / pandas_udf** | ✅ Không cần — `Tokenizer` khoảng trắng dùng được ngay |
| Hiệu năng streaming | ❌ UDF làm chậm đáng kể, tốn RAM — **rủi ro trên máy 7 GB** | ✅ Toàn bộ bằng **hàm Spark SQL**, chạy nhanh, đúng quy ước dự án |
| Stopword | ❌ Không có danh sách chuẩn → phải tự soạn | ✅ Spark ML có `StopWordsRemover` sẵn cho tiếng Anh |
| Teencode / viết tắt | Nhiều và biến đổi liên tục | Có, nhưng từ điển ổn định và dễ xây hơn |
| Emoji | Quan trọng, phải giữ | Quan trọng, phải giữ |
| Tính mới & liên quan địa phương | ✅ Cao — ít công trình về cảm xúc livestream tiếng Việt | Trung bình — nhiều công trình đã có |
| Rủi ro tiến độ | ⚠️ Cao hơn (UDF, từ điển, thiếu stopword) | ✅ Thấp hơn |

### 3.2. Khuyến nghị: **chọn tiếng Anh làm ngôn ngữ chính**

**Lý do:**
1. **Khớp đúng bài toán:** bộ dữ liệu tiếng Anh sẵn có trên máy có **đúng 3 lớp** negative/neutral/positive — trùng khớp với thiết kế hệ thống, không phải gộp lớp như UIT-VSMEC.
2. **Không cần Python UDF:** toàn bộ làm sạch + tách từ làm được **bằng hàm Spark SQL**, đúng quy ước "tránh Python UDF khi có thể", và **giữ luồng streaming nhanh trên máy ảo chỉ có 7 GB RAM**.
3. **Giấy phép:** UIT-VSFC và UIT-VSMEC đều ghi giấy phép **"Unknown"** — rủi ro cho một báo cáo bắt buộc ghi nguồn dữ liệu. (Bộ tiếng Anh cục bộ **cũng đang chưa rõ nguồn** — vì vậy **đây không phải lý do quyết định**, mà là lý do phải truy vết nguồn cả hai.)
4. **Rủi ro tiến độ thấp hơn** với thời gian chỉ còn rất ít.

**Tiếng Việt giữ ở đâu:** đưa vào **phần "Future Improvements"** của báo cáo (mở rộng sang tiếng Việt), và **nếu còn thời gian sau Day 12** thì làm một thí nghiệm phụ nhỏ để chứng minh pipeline không phụ thuộc ngôn ngữ.

> ⚠️ **Đây là quyết định cần cô xác nhận** (câu hỏi số 3) — vì nhóm là người Việt và cô có thể ưu tiên tính liên quan địa phương.

### 3.3. Quy tắc xử lý văn bản (viết **một lần** ở `src/common/text_cleaning.py`)

Áp dụng **giống hệt nhau** cho cả huấn luyện và streaming:

| Bước | Quy tắc | Hiện thực (Spark SQL) |
|---|---|---|
| 1 | Về chữ thường | `lower(col)` |
| 2 | Thay URL bằng token | `regexp_replace(col, 'https?://\S+\|\s*www\.\S+', '<url>')` |
| 3 | Thay @mention bằng token | `regexp_replace(col, '@\w+', '<user>')` |
| 4 | Rút gọn ký tự lặp — "haaaay" → "haay" | `regexp_replace(col, '(.)\\1{2,}', '$1$1')` |
| 5 | **Giữ emoji dưới dạng token riêng** | trích emoji bằng regex Unicode, thay bằng token dạng `:smile:`; **đếm tần suất emoji theo lớp** cho phần EDA |
| 6 | Mở rộng teencode / viết tắt | từ điển trong `config.yaml` (ví dụ `imho`, `tbh`, `lol`…) — **cấu hình được, không hard-code** |
| 7 | Chuẩn hóa khoảng trắng | `regexp_replace(col, '\\s+', ' ' )` + `trim(col)` |
| 8 | Loại bản ghi rỗng / quá ngắn / quá dài | `length` / `size(split(...))` |

**Nếu chọn tiếng Việt (phương án dự phòng):** thêm bước **tách từ** bằng `underthesea` hoặc `pyvi`
dưới dạng **`pandas_udf`** — và **phải đo, ghi rõ chi phí hiệu năng** trong báo cáo.

⚠️ **Điểm dễ sai:** bước làm sạch **phải là cùng một hàm** ở cả hai nhánh. Nếu huấn luyện làm sạch kiểu A
mà streaming làm sạch kiểu B thì phân phối đầu vào của mô hình bị lệch, chỉ số trên luồng sẽ tụt so với offline.

---

## 4. Kiến trúc đề xuất

```
┌──────────────────────┐
│  replay_producer.py  │  đọc dữ liệu có nhãn từ data/raw
│  (--rate --burst     │  gửi JSON: {comment_id, stream_id,
│   --late-ratio)      │   user_hash, text, event_ts}
└──────────┬───────────┘         ▲ KHÔNG chứa nhãn
           │                     │ nhãn -> data/processed/eval_labels.parquet
           ▼                     │ (ghép lại theo comment_id khi đánh giá)
┌──────────────────────┐
│ Kafka: comments_raw  │  3 partition, chịu được đợt bùng nổ
└──────────┬───────────┘
           ▼
┌────────────────────────────────────────────────────────────────┐
│  Spark Structured Streaming   (src/streaming/stream_job.py)    │
│                                                                │
│  1. readStream + from_json(schema TƯỜNG MINH)                  │
│  2. làm sạch  ──► import từ src/common/text_cleaning.py        │
│                   (DÙNG CHUNG với src/training)                │
│  3. chấm điểm ──► PipelineModel (TF-IDF đã fit CHỈ trên train) │
│  4. cửa sổ thời gian + watermark (event time)                  │
└───┬──────────────┬──────────────┬──────────────┬───────────────┘
    │              │              │              │
    ▼              ▼              ▼              ▼
 Parquet      Kafka topic     Parquet        Kafka topic
 chi tiết    comments_scored  tổng hợp    comments_dlq
 (ngày/giờ)                   1 phút      (bản ghi lỗi + lý do)
    │                                          ▲
    │        mỗi query MỘT checkpointLocation riêng trong checkpoints/
    ▼
┌──────────────────────┐
│  Streamlit dashboard │  3 tab: Live Monitor / Try It / About
│  (src/app/app.py)    │  chỉ hiển thị số liệu TỔNG HỢP, đã ẩn danh
└──────────────────────┘
```

### Vì sao kiến trúc này phù hợp với Big Data?

Cần trả lời trung thực, vì **khối lượng dữ liệu ở đây không lớn** (18.408 dòng — một máy tính cá nhân
cũng xử lý được bằng pandas). Đặc trưng Big Data của bài toán nằm ở **velocity (vận tốc)**, không phải volume:

| Đặc trưng | Thể hiện trong bài toán |
|---|---|
| **Velocity — vận tốc** | Bình luận đến **liên tục, không ngừng**, theo từng giây chứ không theo lô. Không thể chờ dữ liệu "đủ rồi" mới xử lý. |
| **Unbounded — không có điểm kết thúc** | Luồng chat **không có điểm dừng xác định** → mô hình xử lý theo lô (batch) không áp dụng được; phải dùng xử lý luồng có trạng thái. |
| **Burstiness — bùng nổ** | Lưu lượng tăng vọt đột ngột (khi có sự kiện trong phiên live) rồi giảm ngay. **Kafka đóng vai trò đệm (buffer)**, tách rời tốc độ sản xuất khỏi tốc độ tiêu thụ — Spark đọc chậm lại cũng không mất dữ liệu. |
| **Low latency — độ trễ thấp** | Yêu cầu cảnh báo **trong lúc phiên live đang diễn ra**, không phải báo cáo sau khi kết thúc. |
| **Event time ≠ processing time** | Bình luận có thể đến muộn hoặc sai thứ tự (mạng chậm, thiết bị yếu) → cần **event time + watermark** mới tính đúng theo cửa sổ thời gian. |
| **Khả năng mở rộng ngang** | Kiến trúc partition hóa cho phép mở rộng bằng cách thêm consumer/broker — điều mà đọc file tuần tự không làm được. |

> **Kết luận trung thực:** kiến trúc này **không** nhằm xử lý khối lượng dữ liệu khổng lồ, mà nhằm xử lý
> **một luồng dữ liệu liên tục, có bùng nổ, cần phản hồi trong thời gian ngắn, và không được mất dữ liệu**.
> Đây chính là lý do phải dùng Kafka + Structured Streaming thay vì đọc file — và nhóm nên **nói đúng như vậy**
> trong báo cáo thay vì phóng đại khối lượng. `REQUIREMENTS.md` và phần hỏi đáp (`docs/qa_prep.md`) sẽ cần lập luận này.

---

## 5. Khuyến nghị cuối cùng

### 5.1. Chốt phương án

| Hạng mục | Chốt |
|---|---|
| **Cách định khung** | **(A) An toàn cộng đồng & sức khỏe tinh thần cho người làm livestream nhỏ** — giữ được đề tài gốc, novelty cao, khớp dữ liệu sẵn có. **Dự phòng: (B)** nếu cô cho rằng livestream bị coi là lĩnh vực giải trí. |
| **Ngôn ngữ** | **Tiếng Anh** |
| **Dữ liệu huấn luyện chính** | Bộ bình luận YouTube 3 lớp (18.408 dòng) **sau khi truy vết được nguồn**. **Dự phòng:** UIT-VSFC nếu cô yêu cầu tiếng Việt (chấp nhận rủi ro giấy phép "Unknown" và phải ghi rõ). |
| **Cách tạo luồng** | **Replay qua Kafka** (`--rate`, `--burst`, `--late-ratio`) |
| **Không dùng** | Livestream thật (rủi ro điều khoản quá cao) |
| **Sản phẩm thấy được** | Dashboard Streamlit + cảnh báo khi tỷ lệ tiêu cực vượt ngưỡng |

### 5.2. Việc phải làm ngay sau khi cô xác nhận

1. Truy vết nguồn gốc `YoutubeCommentsDataSet.csv` → ghi `data/raw/SOURCE.md` (URL, giấy phép, ngày tải, md5). **Chặn Task 6 nếu chưa xong.**
2. Xác nhận lại **Day 1 thực tế** và toàn bộ mốc Day 5/11/18/20 (xem cảnh báo trong `REQUIREMENTS.md` §2).
3. Kiểm tra tài nguyên: đóng bớt ứng dụng đồ họa trước khi chạy Kafka + Spark.

### 5.3. Năm câu hỏi nên hỏi cô

> **Câu 1 — Định khung (quan trọng nhất).**
> Đề tài "phân loại cảm xúc bình luận livestream" hướng tới **an toàn cộng đồng và sức khỏe tinh thần
> cho người làm livestream nhỏ** (phát hiện sớm các đợt bình luận tiêu cực) có được coi là thuộc
> "Technology for Good" không? Em lo ngại cô và hội đồng sẽ xếp livestream vào lĩnh vực **giải trí**
> — nếu vậy, em xin chuyển sang định khung **livestream giáo dục / dịch vụ công**. Cô thấy hướng nào phù hợp hơn?

> **Câu 2 — Dữ liệu mô phỏng.**
> Vì bình luận livestream thật không có nhãn cảm xúc (và điều khoản của YouTube/Twitch hạn chế việc lưu trữ),
> em dự định **huấn luyện trên bộ dữ liệu công khai có nhãn, rồi phát lại (replay) qua Kafka để mô phỏng luồng livestream**.
> Cách này có được chấp nhận không, và trong báo cáo em cần trình bày phần mô phỏng này như thế nào cho đúng?
> Em có nên bổ sung một **mẫu nhỏ bình luận thật được đánh nhãn tay** để đo độ lệch miền dữ liệu không?

> **Câu 3 — Ngôn ngữ.**
> Em đang cân nhắc chọn **tiếng Anh** vì (i) bộ dữ liệu sẵn có đúng 3 lớp, (ii) không cần tách từ nên pipeline
> streaming chạy nhanh hơn nhiều trên máy ảo 7 GB RAM. Bộ tiếng Việt UIT-VSFC/UIT-VSMEC thì giấy phép ghi
> **"Unknown"**. Cô có yêu cầu bắt buộc dùng **tiếng Việt** không, hay tiếng Anh vẫn được điểm tương đương?

> **Câu 4 — Mốc Day 11 và mức độ code.**
> Trong Student's Guide, phần Prototype showing (Day 11) ghi chú là **"KHÔNG nhằm bao gồm code thực tế"**,
> nhưng ở phần mô tả hình thức nộp lại ghi "slides + data + code". Vậy ở **Day 11** nhóm cần nộp ở mức nào —
> chỉ **sơ đồ kiến trúc + chiến lược dữ liệu**, hay đã phải có **prototype chạy được**?

> **Câu 5 — Mốc thời gian.**
> Với **Day 1 = 15/09/2026**, thì hôm nay (02/10/2026) đã là **Day 18 — hạn nộp Final Report**, trong khi nhóm
> mới đang ở bước lập kế hoạch. Cô cho em xin xác nhận **mốc Day 1 thực tế của lớp** và các hạn nộp
> Day 5 / 11 / 18 / 20, cũng như **thứ tự ưu tiên** nếu không kịp tiến độ?

---

## 6. Nhật ký kiểm chứng

Ghi rõ **cái gì đã kiểm chứng** và **cái gì chưa**, để không có con số nào bị bịa ra.

| Thông tin | Đã kiểm chứng? | Cách kiểm / Ghi chú |
|---|---|---|
| UIT-VSFC: 16.175 dòng (11.426/1.583/3.166), cột `sentence`/`sentiment`/`topic`, nhãn 0-1-2 | ✅ **Có** | API `datasets-server.huggingface.co/size` + `/rows`, ngày 02/10/2026 |
| UIT-VSMEC: 6.927 dòng (5.548/686/693), cột `Sentence`/`Emotion`, 7 nhãn | ✅ **Có** | API `datasets-server.huggingface.co/size` + `/rows`, ngày 02/10/2026 |
| Giấy phép UIT-VSFC và UIT-VSMEC = "Unknown" | ✅ **Có** (từ dataset card) | Cần đối chiếu thêm với trang chủ `nlp.uit.edu.vn` trước khi nộp |
| Sentiment140 ~1,6 triệu dòng, nhãn 2 lớp từ distant supervision | ⚠️ **Một phần** | Từ mô tả công khai. **Chưa tải về đếm trực tiếp** → *cần kiểm chứng* |
| Trang Kaggle `kazanova/sentiment140` tồn tại | ✅ **Có** | HTTP 200, ngày 02/10/2026 |
| Bộ cục bộ: 18.408 dòng, phân bố 11.432/4.638/2.338, 536 trùng chính xác, 44 rỗng, 5 nhãn mâu thuẫn, md5 `dc4323…` | ✅ **Có** | Tự đo bằng Python trên `/home/hadoop/YoutubeCommentsDataSet.csv` |
| **Nguồn gốc + giấy phép bộ cục bộ** | ❌ **Chưa** | Chưa tìm được trang gốc. Có bộ Kaggle 18.409 mục nhưng **cột khác** → **phải truy vết trước Task 6** |
| YouTube API: quota 10.000 units/ngày; chi phí `liveChatMessages.list`; yêu cầu xóa dữ liệu trong 30 ngày | ⚠️ **Một phần** | Từ tìm kiếm web. **Chi phí thực của `liveChatMessages.list` không có tài liệu chính thức** → *cần kiểm chứng* trên `developers.google.com/youtube/v3/determine_quota_cost` |
| Twitch Developer Services Agreement hạn chế lưu chat log / cấm tạo database công khai | ⚠️ **Một phần** | Từ tìm kiếm web (bản lưu trữ của `twitch.tv/p/en/legal/developer-agreement`) → *cần đọc bản gốc mới nhất* |
| Tài nguyên máy ảo: 219 GB trống, 7,0 GB RAM, 4 CPU | ✅ **Có** | `df -h`, `free -h`, `nproc` ngày 02/10/2026 |
| Day 1 = 15/09/2026 ⇒ hôm nay là Day 18 | ⚠️ **Suy ra** | Tính từ thông tin nhóm cung cấp. **Cần cô xác nhận** |
