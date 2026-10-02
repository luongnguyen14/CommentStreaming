# REQUIREMENTS.md — Tổng hợp yêu cầu Capstone

Tài liệu này tóm tắt lại các yêu cầu rút ra từ tài liệu gốc của giảng viên trong `TEMPLATES_DIR`.
**Nguồn gốc:** `SIC_Big Data_Capstone Project_Action Plan.docx`, `..._Evaluation Sheet.docx`,
`..._Final Report.docx`, `..._Presentation Slide Template.pptx`, `..._Student_s Guide.pptx`,
`..._Work Breakdown Structure.xlsx`.

> Mọi nội dung dưới đây là bản tóm tắt/diễn giải từ tài liệu gốc. Khi có mâu thuẫn, **tài liệu gốc trong `TEMPLATES_DIR` là nguồn đúng cuối cùng** — hãy mở lại và đối chiếu.

---

## 1. Sản phẩm phải nộp

| # | Sản phẩm | Định dạng | Mốc |
|---|---|---|---|
| 1 | **Action Plan** (kế hoạch hành động) | `.docx` theo template | **Day 5** (bản trình bày sơ bộ) |
| 2 | **WBS** (Work Breakdown Structure) | `.xlsx` theo template | Day 5, nộp lại Day 10, **kiểm tra Day 9 / 14 / 19** |
| 3 | **Prototype presentation** (trình bày nguyên mẫu) | Slide | **Day 11** |
| 4 | **Final Report** (báo cáo cuối) | `.docx` theo template | **Day 18** |
| 5 | **Final presentation** (trình bày cuối) | Slide | **Day 20** |
| 6 | Mã nguồn + dữ liệu + kết quả | `src/`, `outputs/`, `docs/` | kèm các mốc trên |

**Hình thức trình bày** (theo Student's Guide):
- Day 5 — Preliminary presentation: **15 phút trình bày + 5 phút Q&A**, 3–5 slide/đội.
- Day 11 — Prototype showing: **20 phút + 10 phút Q&A**; slides + data + code.
- Day 20 — Final presentation: **20 phút + 10 phút Q&A** mỗi đội.
- Slide nộp ở định dạng PowerPoint, PDF hoặc Word.

**Lưu ý về Day 11 (Prototype showing):** theo ghi chú của giảng viên trong Student's Guide,
buổi này tập trung vào **chiến lược thu thập dữ liệu, kiến trúc và pipeline biến đổi** —
nên có **sơ đồ** ingestion pipeline và transformation pipeline. Ghi chú nêu rõ phần prototype
"**KHÔNG** nhằm bao gồm code thực tế". Tuy nhiên Action Plan của khóa vẫn yêu cầu nộp kèm
"slides + data + code" — **cần hỏi lại giảng viên** mức độ code mong đợi ở Day 11.

---

## 2. Mốc thời gian Day 1–20

Day 1 = **15/09/2026**. WBS của cô đánh số D1–D20 liên tiếp (20 ngày liên tục, không phải ngày làm việc).

| Day | Ngày | Hoạt động / Mốc |
|---|---|---|
| 1 | 15/09/2026 | Tổng quan capstone; bài giảng "Starting a Big Data Project"; chia nhóm (3–4 người) |
| 2 | 16/09/2026 | Bài giảng "Big Data Capstone Project Tutorial"; điền Action Plan, nộp cô duyệt (Design Thinking: Empathize, Define, Ideate) |
| 3 | 17/09/2026 | Hoàn thiện Action Plan |
| 4 | 18/09/2026 | Điền form WBS nộp cô; chuẩn bị trình bày sơ bộ |
| **5** | **19/09/2026** | 🚩 **Preliminary presentation – project proposal** (15' + 5' Q&A). Nộp **Action Plan**. Feedback & wrap-up |
| 6–9 | 20–23/09/2026 | Execution #1: xây dựng & thử nguyên mẫu ban đầu |
| **9** | **23/09/2026** | 📋 **WBS được kiểm tra (lần 1)** |
| 10 | 24/09/2026 | Nộp WBS; chuẩn bị trình bày prototype |
| **11** | **25/09/2026** | 🚩 **Prototype showing** (20' + 10' Q&A). Feedback & wrap-up |
| 12–17 | 26/09–01/10/2026 | Execution #2: cải tiến prototype, khảo sát kịch bản sử dụng |
| **14** | **28/09/2026** | 📋 **WBS được kiểm tra (lần 2)** |
| **18** | **02/10/2026** | 🚩 **Nộp Capstone Project Report** (dùng template) |
| 19 | 03/10/2026 | Chuẩn bị trình bày cuối; **WBS kiểm tra lần 3** |
| **20** | **04/10/2026** | 🚩 **Final presentation** (20' + 10' Q&A) + lễ tốt nghiệp |

> ⚠️ **Cần kiểm tra:** hôm nay là **02/10/2026**, tức là **Day 18** theo mốc Day 1 = 15/09/2026 —
> đúng ngày hạn nộp Final Report. Nếu Day 1 thực tế của nhóm khác ngày này, **phải cập nhật lại
> toàn bộ bảng mốc và cột ngày D1–D20 trong WBS**. Hãy xác nhận với cô.

---

## 3. Rubric chấm điểm (Evaluation Sheet)

**Tổng: 100 điểm.** Mỗi tiêu chí chấm theo thang **①–⑤ (1–5 điểm)**, sau đó nhân hệ số theo công thức ghi trong phiếu.

| Mục | Điểm | Tiêu chí | Quy đổi |
|---|---|---|---|
| **IDEA** | **10** | 1. Creativity and novelty<br>2. Differentiation from the existing known cases<br>3. Impact on the public interest<br>4. Project topics that may be in demand in the real field | 4 tiêu chí × 5 = 20 → **÷2** = /10 |
| **APPLICATION** | **30** | 1. Maintenance and sustainable development<br>2. Proper tool usage base on each condition<br>3. Proper utilization of methods learned in the class<br>4. Utilization of tools and solutions based on own research | 4 × 5 = 20 → **×3/2** = /30 |
| **RESULT** | **30** | 1. Performance<br>2. Practicality<br>3. Visualization of result and data flow<br>4. Maturity level as a SW | 4 × 5 = 20 → **×3/2** = /30 |
| **PROJECT MANAGEMENT** | **10** | 1. Evenly shared workload by all team members<br>2. Fluid communication among the team members and demonstrated good teamwork<br>3. Ability to adapt to unexpected issues and challenges<br>4. Reached the desired milestones in a timely manner (according to the WBS form) | 4 × 5 = 20 → **÷2** = /10 |
| **PRESENTATION & REPORT** | **20** | 1. The report was well-written and clearly conveyed the main points<br>2. Slides and supporting material were well prepared<br>3. The presentation was fluid and successfully communicated the main results<br>4. The speaker was able to answer the questions that were raised | 4 tiêu chí × 5 = /20 |
| | **100** | | |

**Cơ cấu hội đồng** (ghi ở cột NOTE trong Student's Guide): **60% giảng viên / 40% hội đồng khác**
(ví dụ chuyên gia nghiên cứu của Samsung).

> ⚠️ **Điểm không nhất quán giữa hai tài liệu** — cần hỏi cô:
> - **Evaluation Sheet**: Idea **10** điểm (tổng 100).
> - **Student's Guide** (slide 2.1): Idea **20 Pts** (tổng 110).
> - **Final Report** (bảng điểm cuối): IDEA `__/10`, APPLICATION `__/30`, RESULT `__/30`,
>   PROJECT MANAGEMENT `__/10`, PRESENTATION & REPORT `__/20`, TOTAL `__/100`.
>
> Bản **100 điểm** (Evaluation Sheet + Final Report) khớp nhau và mới hơn → dùng bản này.
> "20 Pts" ở Student's Guide nhiều khả năng là tổng thô 4 tiêu chí × 5 **trước khi chia 2**.

**Hàm ý cho nhóm** — những gì cần chứng minh trong báo cáo/slide:
- *Idea*: vấn đề thật, lợi ích công chúng, khác biệt so với các case đã biết, có nhu cầu thực tế.
- *Application*: chọn đúng công cụ **có lý do**, dùng được kiến thức trên lớp **và** có tự nghiên cứu thêm; hệ thống bảo trì/mở rộng được.
- *Result*: hiệu năng đo được, tính thực tiễn, **trực quan hóa kết quả và luồng dữ liệu**, mức độ hoàn thiện như một sản phẩm phần mềm.
- *Project Management*: chia việc đều, teamwork, khả năng ứng phó sự cố, **đúng hạn theo WBS**.
- *Presentation & Report*: viết rõ, slide tốt, trình bày mạch lạc, **trả lời được câu hỏi**.

---

## 4. Technology Readiness Level (TRL) — bảng trong Evaluation Sheet

Nhóm cần **tự đánh giá dự án đạt mức nào** và giải thích.

| Level | Tên | Tiêu chí |
|---|---|---|
| **1** | Project initiation | Project owner identified. Project principles and high-level objectives defined. Use case definitions (including target users and activities). |
| **2** | Conceptualization | Development has begun. Basic individual algorithms or functions are prototyped and documented. Results are speculative, and there is no proof or detailed analysis to support assumptions or expectations. |
| **3** | Proof of concept implementation | Active research, development, and documentation are initiated. Implementations of key functions. Validation of critical concepts. |
| **4** | Prototype component | Validation of prototype components. PoC has become a prototype component. System technology selection has been made. |
| **5** | Prototype integration | All components are integrated with reasonably realistic supporting elements so that the software can be tested and completely validated in a simulated environment. In a restricted environment with a small number of real users. Data formats specified. |
| **6** | Pilot-scale prototype to real-world integration | Represents a step up from the lab scale to the engineering scale. Tested in a real-world environment with a small number of real users. Requires initial System & User documentation. |
| **7** | Operational integration | Requires the demonstration of an actual system prototype in an operational environment. Verification and validation are completed, and the validity of the solution is confirmed within an intended application. Engineering support and maintenance organization, including helpdesk, are in place. |
| **8** | Deployment | Demonstrated to work in its final form and under expected conditions. In most cases, this represents the end of system development. Full documentation should be provided (specifications, design definition and justification, verification and validation (qualification file), users and installation manuals, training and education materials, software problem reports, and non-compliances). |
| **9** | Production | Represents actual application in its final form and under designed conditions. In almost all cases, this is the end of the last "bug fixing" aspects of the system development. |

> **Lưu ý quan trọng:** mức **TRL 5** yêu cầu hệ thống chạy được trong **môi trường mô phỏng** — điều này
> **phù hợp** với cách tiếp cận dùng dữ liệu **replay** thay vì livestream thật. Nhóm nên nhắm tới
> **TRL 5** và ghi rõ trong báo cáo rằng dữ liệu livestream là **mô phỏng**, vì mức 6 đòi hỏi
> "real-world environment with real users".

---

## 5. Hạn chế đề tài — FAQ trong Student's Guide

**Q1. Capstone project là gì?**
- Là trải nghiệm toàn diện để xây dựng portfolio cá nhân thông qua giải quyết vấn đề.
- **Phải thể hiện đủ tính mới (novelty) và độc đáo (uniqueness).**
- Phải hoàn thành trong khung thời gian cho trước.
- Là hoạt động **theo nhóm**, hợp tác là bắt buộc.

**Q2. Có ràng buộc gì về đề tài không?** ⚠️ *Phần quan trọng nhất*
- Về chủ đề, phải nằm trong phạm vi **"Technology for Good"**.
  - Phải vì **lợi ích công chúng**.
  - ❌ **Rất không khuyến khích**: dự đoán giá chứng khoán, chiến lược cờ bạc/đầu tư, dự đoán kết quả đua xe...
  - ❌ Không khuyến khích: đề tài mà **giá trị chính là giải trí**.
  - ❌ Không khuyến khích: đề tài mà **chỉ một cá nhân hoặc một công ty** hưởng lợi.
- **Đừng giới hạn dự án trong những gì đã học trên lớp.**
  - Phải có đủ **tính mới và độc đáo**.
  - Khuyến khích tự nghiên cứu **bối cảnh vấn đề và domain**.
  - Khuyến khích tự nghiên cứu **kỹ thuật và phương pháp Big Data**.
  - ❌ **Không khuyến khích** đề tài **chỉ chứng minh phương pháp/kỹ thuật** — dự án phải giải quyết **vấn đề thực tế**.

**Q3. Thành lập nhóm thế nào?**
- Lý tưởng: mỗi thành viên đóng góp một bộ kỹ năng **bổ trợ** cho nhau.
- Tốt nhất là lập nhóm theo **sở thích chung**.
- Giảng viên có thể can thiệp để hỗ trợ/gộp/tách/sắp xếp lại nhóm.
- Khuyến khích nhóm **4–5 người**.

**Q4. Project Advisors là ai?**
- Là chuyên gia có kinh nghiệm làm việc/giảng dạy liên quan.
- Tư vấn ở **mọi giai đoạn** của dự án.
- **Hãy hỏi xin lời khuyên nhưng đừng mong họ viết code cho bạn.**
- Advisor sẽ cho ý kiến trung thực theo hiểu biết của họ.
- Advisor có thể tham gia làm hội đồng đánh giá.

> 🔎 **Áp dụng cho đề tài của nhóm:** "phân loại cảm xúc bình luận livestream" rất dễ bị đọc thành
> **công cụ bán hàng** (thương mại thuần túy) hoặc **chỉ chứng minh kỹ thuật** (Kafka + Spark).
> Phải chọn **cách định khung vì lợi ích cộng đồng** rõ ràng ngay từ Action Plan — xem
> `docs/topic_decision.md` (Task 1).

---

## 6. Cấu trúc Final Report (theo template)

Trang bìa: `<Project Title>`, `<Date (DD/MM/YY)>`, Team Name, Member 1–5.
Sau đó là **Content** (mục lục) và các mục:

| # | Mục | Nội dung cần điền |
|---|---|---|
| **1** | **Introduction** | |
| 1.1 | Background Information | Bối cảnh vấn đề |
| 1.2 | Motivation and Objective | Động lực và mục tiêu |
| 1.3 | Members and Role Assignments | Bảng phân công thành viên |
| 1.4 | Schedule and Milestones | Tóm tắt lịch trình từ WBS |
| **2** | **Project Execution** | |
| 2.1 | Simulated Scenario Description | Kịch bản mô phỏng (nguồn, cách tạo luồng, giới hạn) |
| 2.2 | Datasets Selection and Description | Chọn và mô tả bộ dữ liệu (ghi nguồn, giấy phép) |
| 2.3 | Data Ingestion Pipeline | Pipeline thu thập (Kafka) + sơ đồ |
| 2.4 | Data Transformation Processing | Biến đổi dữ liệu (Structured Streaming, làm sạch, cửa sổ, watermark) |
| 2.5 | Data Query and Insight | Truy vấn và insight rút ra |
| **3** | **Results** | |
| 3.1 | Data Ingestion Scripts and Code | Code thu thập dữ liệu |
| 3.2 | Data Transformation Scripts and Code | Code biến đổi + mô hình |
| 3.3 | Description and Sample of Transformed Datasets | Mô tả + mẫu dữ liệu đã biến đổi |
| 3.4 | Data Visualization of Query Results | Trực quan hóa kết quả truy vấn |
| **4** | **Projected Impact** | |
| 4.1 | Accomplishments and Benefits | Thành quả và lợi ích |
| 4.2 | Future Improvements | Cải tiến tương lai |
| **5** | **Team Member Review and Comment** | Bảng NAME / REVIEW and COMMENT (mỗi thành viên tự điền) + ảnh nhóm `<ATTACH A TEAM PICTURE HERE>` |
| **6** | **Instructor Review and Comment** | Bảng CATEGORY / SCORE / REVIEW and COMMENT — **để trống cho giảng viên** |

**Bảng điểm ở mục 6** (để trống, giảng viên điền):
`IDEA __/10` · `APPLICATION __/30` · `RESULT __/30` · `PROJECT MANAGEMENT __/10` ·
`PRESENTATION & REPORT __/20` · `TOTAL __/100`

---

## 7. Template Action Plan — các ô phải điền

Bảng 1: `Team Name` · `Team Leader / Members` · `Project Title` · `Goal` · `Abstract` · `Method`
Bảng 2: `Data` · `Expected Outcome` · `Role by Member`
Bảng 3: `Schedule Summary` · `Comment & Assessment` (**để trống cho giảng viên**)

## 8. Template Presentation Slide

- Slide 1 (bìa): `Team Name` + `ProjectName`
- Slide 2 (mục lục): Unit 1–3 với các mục con 1.1–3.3
- Slide 3 (nội dung): `Slide Title`, số mục `1.1`, `Subtitle`, số `01`, `UNIT`, nội dung `Level-1 / Level-2`
- Slide 4: trống
- 💬 **Ghi chú trong template**: *"Please edit project name and page number in slide master."* —
  nhớ sửa **tên dự án** và **số trang** trong **slide master**, không chỉ trên từng slide.

## 9. Template WBS (`.xlsx`)

- Sheet `Cover Page` (B5:O27) và sheet `WBS` (B2:AD45).
- `B7 = Today`; `B8 = Project Team Name`; `B9 = Project Topic` — **cần điền**.
- Cột: `B–E` Task (gộp, phân cấp 1. / 1.1. / 1.1.1. / 1.1.1.1.), `F` Start date, `G` End date,
  `H` Responsibility, `I` Deliverable, `J` Task Status, `K–AD` = W1–W4 và **D1–D20** (Gantt).
- Ô `B7` chứa công thức `=TODAY()`; hàng 13 là **ngày của 20 ngày** (template đang để mẫu năm 2021 → phải thay bằng ngày thật).
- `J14:J45` có **data validation** kiểu list, nguồn `$J$3:$J$5` = `Done` / `In-progress` / `Delayed`.
- Các dòng 14–29 hiện là **dòng mẫu** ("1. Title", "1.1. Sub-title"...) và trạng thái `In-progress` — sẽ được thay bằng công việc thật.
> Ghi chú: lần kiểm tra đầu tiên **không tìm thấy rule conditional formatting** trong file này;
> màu trạng thái có thể được tô trực tiếp bằng cell style. Cần kiểm lại kỹ ở Task 3 trước khi sửa.
