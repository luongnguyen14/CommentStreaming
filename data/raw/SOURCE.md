# data/raw/SOURCE.md — Truy vết nguồn dữ liệu

> ⚠️ **Mọi bộ dữ liệu đặt trong `data/raw/` PHẢI được khai báo ở đây.**
> Báo cáo cuối bắt buộc ghi nguồn dữ liệu — không có mục này thì không được dùng dữ liệu đó.

---

## 1. `part-01.json` — ✅ ĐÃ XÁC ĐỊNH ĐƯỢC BỘ DỮ LIỆU NGUỒN (kiểm tra 14/10/2026)

| Trường | Giá trị |
|---|---|
| Tên file | `part-01.json` |
| Vị trí | `data/raw/part-01.json` (1,1 GB) |
| Bộ dữ liệu nguồn | **IMDb Review Dataset - ebD** — https://www.kaggle.com/datasets/ebiswas/imdb-review-dataset (DOI `10.34740/KAGGLE/DSV/1836923`) |
| Tác giả / tổ chức | Enam Biswas (Kaggle: `ebiswas`), đăng trên Kaggle |
| Giấy phép | **CC0: Public Domain** (ghi trên trang Kaggle, kiểm tra 14/10/2026) |
| Ngày tải | **Không rõ** — file có sẵn trên máy; zip `part-01.json.zip` ghi ngày 19/09/2026, shard bên trong ghi 11/01/2021. Không do nhóm tải trong dự án này. |
| Kích thước | `1.095.550.407` byte (≈ 1,1 GB) |
| Số bản ghi | **1.010.293** review — đo lại 14/10/2026 (Task 6): `grep -o '"review_id"' \| wc -l` = 1.010.293, khớp đúng số dòng JSONL sinh ra từ file; md5 không đổi. Con số 1.010.296 ghi trước đó **sai 3 bản ghi** |
| Các trường | `review_id`, `reviewer`, `movie`, `rating`, `review_summary`, `review_date`, `spoiler_tag`, `review_detail`, `helpful` (9 trường) |
| ⚠️ `review_id` **KHÔNG duy nhất** | Đo 14/10/2026 trên cả file: **994.692 id khác nhau** ⇒ **15.601 dòng (1,54%) lặp id**, gần như toàn bộ là bản sao y hệt (cùng phim, cùng người, cùng văn bản). `prepare.py` **loại trùng theo `comment_id`** trước khi chia tập — nếu không, phép nối nhãn đánh giá theo `comment_id` sẽ nhập nhằng |
| Phân bố `rating` (1–10) | 958.776 bản ghi có rating. Đo 14/10/2026: 1★ 111.357 · 2★ 42.242 · 3★ 43.669 · 4★ 44.636 · 5★ 58.654 · 6★ 74.483 · 7★ 99.790 · 8★ 121.886 · 9★ 112.082 · 10★ 249.977 |
| Checksum | `md5 = e723d956b3b4a0dcd3e8d54ec1e9d4ca` (bản trong `data/raw/`, khớp bản gốc `/home/hadoop/part-01.json`) |
| Checksum zip gốc | `md5 = bba9d5187587cd46ec65176390c639bb` (`/home/hadoop/part-01.json.zip`) |
| Ghi chú | (1) Đây là **một shard (`part-01`)** của bộ đầy đủ — trang Kaggle ghi bộ gốc có **5.571.499 review**; báo cáo phải nói rõ nhóm chỉ dùng 1 phần. (2) Bộ dữ liệu **không có nhãn cảm xúc** — nhóm **tự suy nhãn 3 lớp từ `rating`** theo ánh xạ sẽ ghi tại `docs/data_dictionary.md` (Task 6); khi báo cáo phải gọi đúng là "nhãn suy ra từ rating", không được gọi là nhãn gốc. |

**Việc còn lại:** xác minh bộ dữ liệu gốc đúng là bộ Kaggle `ebiswas/imdb-review-dataset` (đối chiếu vài `review_id` mẫu với trang gốc) trước khi nộp Final Report.

---

## 2. Bộ dữ liệu đã loại bỏ

| File | Lý do loại | Ngày quyết định |
|---|---|---|
| `YoutubeCommentsDataSet.csv` (18.408 dòng, 3 lớp, md5 `dc4323696d2aac0cd2f9a10707b9a18a`) | **Không truy vết được nguồn gốc và giấy phép** → không được dùng trong báo cáo nộp. Phân tích đầy đủ ở `docs/topic_decision.md` §2.2. File vẫn còn ở `/home/hadoop/YoutubeCommentsDataSet.csv` (ngoài dự án), **không dùng cho kết quả báo cáo**. | 14/10/2026 |
