# Kịch bản video demo — Bạn Nhà Nông (~5 phút)

> Thông điệp xuyên suốt, nhắc ít nhất 3 lần trong video:
> **"Con số về thuốc — liều lượng, ngày cách ly — KHÔNG BAO GIỜ do AI sinh ra.
> AI chỉ hiểu câu hỏi; con số được tra từ cơ sở dữ liệu pháp lý và chép nguyên văn từ nhãn."**
> Đây là điểm ăn tiền số 1 vì tiêu chí chấm nặng nhất là hallucination.

## Chuẩn bị trước khi quay (checklist)

- [ ] `.env` đã có `GEMINI_API_KEY` thật (đường B + ảnh + hỏi nối tiếp cần nó) — restart server
- [ ] Muốn quay cảnh SMS thật: điền `SPEEDSMS_ACCESS_TOKEN`, để điện thoại cạnh máy quay
- [ ] Server chạy `http://localhost:8010`, hard-refresh cả 2 tab (chat + officer) trước
- [ ] Dashboard có sẵn: 1 ticket "Chờ trả lời", alert "An Giang — đạo ôn" sáng đèn
  (nếu trống: hỏi 3 câu triệu chứng đạo ôn khác nhau ở tab chat trước khi quay)
- [ ] Chuẩn bị 1 ảnh nhãn thuốc rõ nét (chụp chai thuốc thật) để demo gửi ảnh
- [ ] 2 cửa sổ trình duyệt đặt sẵn: trái = app nông dân, phải = `/officer/`
- [ ] Tắt notification hệ điều hành, ẩn bookmark bar cho sạch hình

---

## CẢNH 1 — Hook: vấn đề (0:00 – 0:25)

**[HÌNH]** Landing page `http://localhost:8010`. Cuộn chậm.

**[NÓI]**
> "Sáng sớm ra thăm đồng, thấy lúa cháy rầy, bác nông dân bây giờ làm đúng cái điều
> mà hàng triệu người đang làm: mở điện thoại, hỏi AI.
> AI trả lời ngay — trôi chảy, tự tin, kèm cả con số liều lượng. Chỉ có một vấn đề:
> con số đó, rất có thể, là do nó... tự nghĩ ra.
> Trên mạng, một câu trả lời sai chỉ là một câu trả lời sai. Nhưng trên đồng ruộng,
> nó là lúa cháy thuốc, là một vụ mùa mất trắng, là dư lượng nằm lại trên chính hạt
> gạo nhà mình ăn.
> Đó là lý do **Bạn Nhà Nông** ra đời, với một nguyên tắc duy nhất và không có
> ngoại lệ: **AI không được phép tự nghĩ ra bất kỳ con số nào.** Liều lượng, ngày
> cách ly — tất cả đều tra từ nguồn chính thống, và truy được đến tận trang giấy
> nơi nó được in ra."

*(Phương án ngắn gọn hơn nếu muốn vào thẳng vấn đề:)*
> "Hỏi AI 'lúa bị rầy nâu, phun liều bao nhiêu' — bạn sẽ nhận được một con số rất
> tự tin. Không ai biết con số đó từ đâu ra, kể cả chính AI. Với thuốc bảo vệ thực
> vật, đoán sai một con số là cháy lúa, là mất mùa. Bạn Nhà Nông được xây trên một
> nguyên tắc duy nhất: AI lo phần hiểu câu hỏi — còn **mọi con số đều phải chép từ
> nguồn chính thống**, không bịa, không làm tròn, không ngoại lệ."

---

## CẢNH 2 — Tra thuốc có căn cứ pháp lý (0:25 – 1:10)

**[HÌNH]** Vào chat. Gõ (hoặc NÓI bằng mic để khoe voice luôn):
`Lúa bị rầy nâu thì xịt thuốc gì?`

**[NÓI]** (trong lúc kết quả hiện)
> "Hệ thống tra trực tiếp **danh mục thuốc BVTV được phép sử dụng** — Thông tư
> 75/2025 và bản sửa đổi 28/2026 của Bộ Nông nghiệp — đã được chúng tôi parse
> thành cơ sở dữ liệu **6.883 sản phẩm**. Với rầy nâu trên lúa, có 627 sản phẩm
> còn hiệu lực. Mỗi phiếu thuốc kèm hoạt chất và **trích dẫn đúng thông tư**.
> Sản phẩm nào đã kiểm chứng nhãn thì hiện **liều + ngày cách ly chép nguyên văn
> từ nhãn** — quy trình nhập liệu 2 người độc lập, có trọng tài. AI không tham gia
> vào con số nào ở đây cả."

**[ZOOM]** vào 1 thẻ liều + dòng trích dẫn nguồn.

---

## CẢNH 3 — Hai cái bẫy hallucination (1:10 – 1:55)

**[HÌNH]** Gõ tiếp 2 câu, mỗi câu chờ trả lời xong mới câu sau:
1. `Cho tôi liều gấp đôi cho nhanh hết rầy`
2. `Folpan 50WP còn dùng được không?`

**[NÓI]**
> "Đây là loại câu mà AI thường 'chiều' người dùng. Bạn Nhà Nông **từ chối** —
> phun quá liều là vi phạm nhãn và nguy hiểm, hệ thống nói thẳng.
> Câu thứ hai khó hơn: Folpan 50WP **sắp bị loại khỏi danh mục**. Hệ thống trả
> lời đúng theo mốc pháp lý: còn dùng được đến 15/08/2026, sau đó bị loại theo
> Thông tư 28. Cơ sở dữ liệu của chúng tôi **version theo ngày hiệu lực** — hỏi
> hôm nay và hỏi tháng 9 sẽ ra câu trả lời pháp lý khác nhau. Đối thủ dùng RAG
> trên tài liệu tĩnh không làm được điều này."

---

## CẢNH 4 — Gửi ảnh nhãn thuốc (1:55 – 2:20)

**[HÌNH]** Bấm nút đính kèm ảnh → chọn ảnh chai thuốc → hỏi `thuốc này xịt cho lúa được không?`

**[NÓI]**
> "Bà con không cần gõ đúng tên thuốc — chụp ảnh nhãn chai là đủ. Hệ thống nhận
> diện tên thương mại từ ảnh rồi vẫn đi qua đúng đường tra cứu pháp lý đó,
> không đoán mò."

---

## CẢNH 5 — Hỏi nối tiếp như hội thoại thật (2:20 – 2:45)

**[HÌNH]** Gõ tiếp không nhắc lại tên thuốc: `liều dùng của nó thế nào?` rồi `còn ngày cách ly?`

**[NÓI]**
> "Hội thoại có ngữ cảnh — 'nó' được hiểu là sản phẩm đang nói dở. Nông dân hỏi
> như nói chuyện với cán bộ thật, không phải điền form."

---

## CẢNH 6 — Tư vấn canh tác có trích dẫn + biết mình biết gì (2:45 – 3:15)

**[HÌNH]** Gõ: `Tháng 11 này ở An Giang xuống giống lúa được chưa?`

**[NÓI]**
> "Câu canh tác đi đường RAG trên kho tài liệu chính thống — lịch thời vụ của Sở
> Nông nghiệp, quy trình của Cục Trồng trọt. Câu trả lời kèm trích dẫn, và có một
> tầng **validator đối chiếu bằng máy**: con số nào không chép nguyên văn từ tài
> liệu nguồn sẽ bị chặn trước khi đến người dùng. Chủ đề ngoài kho tài liệu, hệ
> thống tự tìm trên nguồn web và **ghi rõ nguồn** — minh bạch cái gì là chính
> thống, cái gì là tham khảo."

---

## CẢNH 7 — Biết chịu thua: chuyển cán bộ khuyến nông (3:15 – 3:45)

**[HÌNH]** Gõ câu ngoài phạm vi, ví dụ: `cây mít nhà tôi xoăn lá phải làm sao?`
→ bot từ chối minh bạch → bấm **"Gửi cán bộ khuyến nông"** → popup form (điền tên +
SĐT) → Gửi → toast "✓ Đã gửi — mã #N".

**[NÓI]**
> "Điểm chúng tôi tin là khác biệt lớn nhất: **hệ thống biết mình không biết gì**.
> Không đủ căn cứ — nó không đoán, nó nói thẳng và mở đường đến người thật. Một
> phiếu hỏi được tạo, kèm liên hệ của bà con. Và đây không phải nút hình thức —
> phía sau là cả một hệ thống làm việc cho cán bộ khuyến nông."

---

## CẢNH 8 — Dashboard cán bộ: trả lời + giám sát dịch bệnh (3:45 – 4:35)

**[HÌNH]** Chuyển sang cửa sổ `/officer/`:
1. Tab "Chờ trả lời" → mở đúng phiếu vừa gửi → gõ câu trả lời → Gửi.
2. Chỉ vào dải **"Theo dõi vùng dịch"**: tab Đang diễn ra (alert "An Giang — N câu
   hỏi về đạo ôn"), bấm "xem mẫu"; lướt qua tab **Lịch sử** (đợt dịch, đỉnh điểm)
   và **Tổng quan** (thống kê năm theo vùng).

**[NÓI]**
> "Cán bộ khuyến nông có bảng điều hành riêng: hàng đợi câu hỏi, trả lời ngay tại chỗ.
> Và phần này là thứ chúng tôi tâm đắc: **mỗi câu hỏi của nông dân là một tín hiệu
> giám sát dịch bệnh**. AI phân loại cả những câu chỉ mô tả triệu chứng — 'lúa cháy
> lá thành vệt hình thoi' — gom về đúng tên bệnh đạo ôn. Nhiều bà con cùng vùng hỏi
> về cùng một bệnh trong 7 ngày → dashboard tự nổi cảnh báo **sớm hơn báo cáo hành
> chính**. Có lịch sử từng đợt dịch và thống kê theo năm. Từ một chatbot, dữ liệu
> cộng đồng trở thành hệ thống cảnh báo sớm cho cả vùng."

---

## CẢNH 9 — Vòng lặp khép kín: bà con nhận trả lời (4:35 – 4:55)

**[HÌNH]** Quay lại cửa sổ nông dân: chuông trên header hiện chấm đỏ → bấm chuông →
**hộp thư kiểu Gmail** → mở thư đọc câu hỏi + trả lời của cán bộ.
(Nếu đã cấu hình SpeedSMS: quay cảnh **tin nhắn SMS đến điện thoại thật** — rất ăn hình.)

**[NÓI]**
> "Cán bộ vừa trả lời, bên bà con báo ngay: tin nhắn SMS về điện thoại — nông dân
> không cần mở app — và trong app có hộp thư riêng đọc lại mọi câu đã hỏi.
> Vòng lặp khép kín: AI trả lời cái nó chắc chắn, người thật trả lời phần còn lại,
> và hệ thống học được vùng nào đang cần giúp đỡ."

---

## CẢNH 10 — Chốt: vì sao chúng tôi khác (4:55 – 5:20)

**[HÌNH]** Quay lại landing page hoặc slide chốt (nếu có).

**[NÓI]**
> "Tóm lại, Bạn Nhà Nông khác các trợ lý AI nông nghiệp khác ở bốn điểm:
> **Một** — kiến trúc chống bịa: con số chỉ được chép từ cơ sở dữ liệu pháp lý và
> nhãn thuốc đã kiểm chứng, có validator máy chặn số lạ, kèm bộ kiểm thử
> hallucination riêng — gần 400 test tự động và bộ red-team đối chiếu từng claim
> với nguồn thật.
> **Hai** — đúng pháp luật theo thời gian: danh mục thuốc version theo ngày hiệu
> lực của từng Thông tư.
> **Ba** — biết từ chối, và từ chối có lối ra: chuyển thẳng đến cán bộ khuyến nông
> thật, có dashboard, có SMS báo về tận điện thoại.
> **Bốn** — mỗi câu hỏi là dữ liệu giám sát: hệ thống cảnh báo sớm dịch bệnh theo
> vùng, miễn phí, từ chính hành vi hỏi đáp của bà con.
> Nông nghiệp không có chỗ cho con số bịa. Xin cảm ơn."

---

## Ghi chú kỹ thuật khi quay

- Mỗi cảnh quay riêng rồi ghép — đừng quay một mạch (Gemini có thể chậm vài giây,
  cắt phần chờ đi).
- Đường B/ảnh/nối tiếp đều gọi Gemini: câu đầu sau khi restart server thường chậm
  hơn — chạy "làm nóng" 1 câu trước khi bấm quay.
- KHÔNG demo Zalo. Notify khoe: popup/hộp thư trong app + SMS (nếu có token).
- Nếu quay màn hình 16:9, thu nhỏ cửa sổ officer về ~1366×768 cho chữ to dễ đọc.
- Số liệu được phép nói (đã kiểm chứng trong repo): 6.883 sản phẩm thuốc, 627 sản
  phẩm cho rầy nâu/lúa, 412 đoạn tài liệu chính thống, ~392 test tự động, mốc
  Folpan 15/08/2026.
