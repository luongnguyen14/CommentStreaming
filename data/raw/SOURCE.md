# data/raw/SOURCE.md — Truy vết nguồn dữ liệu

> ⚠️ **Mọi bộ dữ liệu đặt trong `data/raw/` PHẢI được khai báo ở đây.**
> Báo cáo cuối bắt buộc ghi nguồn dữ liệu — không có mục này thì không được dùng dữ liệu đó.

Mẫu khai báo:

| Trường | Giá trị |
|---|---|
| Tên file | |
| Nguồn (URL trang gốc) | |
| Tác giả / tổ chức | |
| Giấy phép | |
| Ngày tải | |
| Kích thước / số dòng | |
| Checksum (md5/sha256) | |
| Ghi chú | |

---

## 1. `YoutubeCommentsDataSet.csv` — ⚠️ CHƯA XÁC ĐỊNH ĐƯỢC NGUỒN

| Trường | Giá trị |
|---|---|
| Tên file | `YoutubeCommentsDataSet.csv` |
| Vị trí | `/home/hadoop/YoutubeCommentsDataSet.csv` (ngoài dự án — **cần copy vào `data/raw/`**) |
| Nguồn (URL trang gốc) | ❌ **CHƯA TÌM ĐƯỢC** |
| Tác giả / tổ chức | ❌ Chưa rõ |
| Giấy phép | ❌ **Chưa rõ** |
| Ngày tải | Không rõ (file ghi ngày 24/09/2025, không phải do nhóm tải) |
| Số dòng | 18.408 dòng dữ liệu (18.409 dòng kể cả header) |
| Cột | `Comment`, `Sentiment` |
| Phân bố nhãn | positive 11.432 (62,1%) / neutral 4.638 (25,2%) / negative 2.338 (12,7%) |
| Chất lượng (đã đo 02/10/2026) | 536 dòng trùng chính xác; 569 dòng trùng sau chuẩn hóa; 44 bình luận rỗng; 5 văn bản có nhãn mâu thuẫn |
| Checksum | `md5 = dc4323696d2aac0cd2f9a10707b9a18a` |
| Ghi chú | Có một bộ dữ liệu Kaggle mô tả **18.409 mục** với cột *Video ID, Comment, Likes, Sentiment* — **gần giống về số dòng nhưng KHÁC về cột**. Chưa kết luận được đây có phải cùng một bộ. |

**Việc phải làm trước Task 6:** tìm lại trang gốc trên Kaggle/Hugging Face, điền URL + giấy phép vào bảng trên.
Nếu **không truy vết được**, phải xin ý kiến cô trước khi dùng — hoặc chuyển sang phương án dự phòng UIT-VSFC (xem `docs/topic_decision.md` §5.1).
