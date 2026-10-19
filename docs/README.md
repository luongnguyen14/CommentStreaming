# docs/ — Tài liệu nội bộ

- `topic_decision.md` — định khung đề tài + chiến lược dữ liệu (Task 1)
- `data_dictionary.md` — từ điển dữ liệu (Task 6)
- `scenario.md` — kịch bản sử dụng (Task 13)
- `self_assessment.md`, `qa_prep.md` — tự chấm và chuẩn bị hỏi đáp (Task 16)
- `talk_script_vi.md` — kịch bản nói tiếng Việt cho slide cuối
- `huong_dan_bao_cao.md` — **hướng dẫn báo cáo trước hội đồng**: trạng thái GitHub,
  cách dùng chương trình thử nghiệm mô hình (`src/app/model_trial.py`), bản đồ số liệu
  → từng mục Final Report, kịch bản demo 5 phút, được nói/không được nói, Q&A, checklist
- `bao_cao_tien_do.md` — **kịch bản báo cáo tiến độ**: từng bước đã làm (dữ liệu →
  chuẩn bị → huấn luyện → đánh giá → streaming → EDA → dashboard), cách train/test chi
  tiết, kết quả thật, hạn chế, kế hoạch và **30 câu hỏi–đáp án** cho buổi báo cáo
- `bao_cao_ky_thuat_vi.docx` / `.pdf` — **báo cáo kỹ thuật chi tiết bằng tiếng Việt**
  (33 trang): kiến trúc, dữ liệu, mô hình, kết quả, phân tích lỗi, streaming, EDA,
  dashboard, chương trình thử nghiệm, cách chạy lại, hạn chế và phụ lục. Sinh bằng
  `scripts/make_vi_technical_report.py`
- `bao_cao_ky_thuat_vi.md` — bản tóm tắt Markdown của báo cáo kỹ thuật, để đọc trên GitHub
- `huong_dan_lay_file_word.md` — **hướng dẫn lấy file Word về máy** (GitHub, `scp`,
  VirtualBox shared folder), mở bằng Word/LibreOffice, cài font, xuất PDF, và chạy
  lại chương trình trên máy gốc / máy mới
- `huong_dan_share_streamlit.md` — **hướng dẫn chia sẻ dashboard Streamlit cho máy
  khác**: cùng mạng LAN (Bridged/NAT port forwarding), qua Internet bằng ngrok hoặc
  Cloudflare Tunnel, cài độc lập trên máy mới, bảo vệ bằng mật khẩu Nginx, và xử lý
  lỗi kết nối thường gặp

Tài liệu trong đây là **nội bộ**; tài liệu nộp cho cô nằm ở `deliverables/` (tiếng Anh).
