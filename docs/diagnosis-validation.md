# Kiểm chứng chẩn đoán mạng — 16/11/2026

Phạm vi đợt này: kết luận khi mất gói, tăng độ trễ, lỗi phép đo và phục hồi. Không thay đổi thuật toán quét/nhận diện thiết bị, cảnh báo hoặc cấu trúc CSDL.

## Lỗi đã tái hiện và sửa

Sau khi ứng dụng kết luận `ok`, `home_issue`, `isp_issue` hoặc `internet_issue`, lỗi socket ở router/đích ngoài làm `diagnose()` trả `unknown`. Trước sửa, bộ ổn định trạng thái vẫn chờ ba chu kỳ nên UI/lịch sử kết luận giữ trạng thái cũ trong khi phép đo hiện tại đã không đủ bằng chứng. Test trường hợp router lỗi ngay sau `ok` đã thất bại trước bản sửa.

Hiện tại, khi chuyển từ một kết luận có bằng chứng sang `unknown`, worker phát cập nhật ngay. Kết luận mới được lưu và hiển thị bằng luồng backend hiện có. Không xóa các mẫu đo hợp lệ trước đó; lỗi đo lưu `measurement_error` và không đưa vào mẫu tính loss. Sau khi đo được lại, cần ba chu kỳ xác nhận để kết luận ổn định/nghi ngờ lỗi trở lại. Không phát lặp cùng một kết luận/nội dung khi trạng thái không đổi.

Trạng thái thiếu gateway/mất kết nối vẫn được báo ngay theo cơ chế có sẵn. Khi mới mở/làm mới mạng, thông báo đang thu thập mẫu được giữ; bản sửa chỉ gỡ ngay một kết luận cũ khi bằng chứng không còn đủ.

## Cách hiểu các tình huống

| Quan sát | Kết luận được kiểm tra |
|---|---|
| Router và đích ngoài cùng suy giảm | Nghi ngờ LAN/router (`home_issue`) |
| Router ổn, hop sau gateway và đích ngoài cùng suy giảm | Nghi ngờ đường sau gateway (`isp_issue`); chưa xác minh chủ sở hữu hop |
| Đích ngoài suy giảm, các mốc trước ổn | Đích ngoài/đường truyền có vấn đề (`internet_issue`); không khẳng định nguyên nhân duy nhất |
| Hop trung gian mất gói nhưng đích ngoài vẫn tốt | Chưa có bằng chứng lỗi chuyển tiếp (`unknown`), không quy lỗi ISP |
| Lỗi phép đo router hoặc đích ngoài | Gỡ kết luận cũ ngay, chờ dữ liệu (`unknown`) |
| Chỉ không đo được hop tùy chọn, router/đích ngoài vẫn tốt | Không tự biến thành lỗi mạng hoặc thiếu dữ liệu của hai đích chính |
| Một mẫu RTT tăng đột biến | Không tự tạo lỗi kéo dài khi cửa sổ median vẫn bình thường |
| Mất gói thật do timeout probe đã gửi | Vẫn tính loss, không coi là lỗi đo socket |
| RTT đã cao từ lúc mở ứng dụng | Ngưỡng tuyệt đối vẫn phát hiện; không học độ trễ cao đó thành kết nối tốt |

Cửa sổ tối đa 30 mẫu, tối thiểu 10 mẫu cần thiết; kết luận ổn định/nghi ngờ lỗi cần ba chu kỳ liên tiếp. Các cửa sổ là cửa sổ trượt, có mẫu chồng nhau; không phải ba đợt đo độc lập. Thời gian phản ứng phụ thuộc chu kỳ, timeout, số mẫu và thời gian mẫu cũ ra khỏi cửa sổ. Không mặc định ba chu kỳ luôn bằng sáu giây.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_diagnosis_scenarios.py tests/test_diagnosis.py tests/test_network_recovery.py tests/test_network_refresh.py -q
```

`tests/test_diagnosis_scenarios.py` bổ sung 23 trường hợp. Các probe nhận kết quả/tình huống được điều khiển, chạy qua `PingMonitor` thật, ghi SQLite tạm; có test tích hợp backend/UI Qt để kiểm tra nhãn, trạng thái phép đo và kết luận đã lưu cùng chuyển về `unknown`. Các ngưỡng được cố định về mặc định trong fixture, không sửa cấu hình người dùng.

Đã kiểm tra suy giảm/phục hồi do cả RTT và loss tại từng nhóm mốc; mất gói xen kẽ; hồi phục cần xác nhận lại; không phát lặp; hop trung gian bị hạn chế ICMP; lỗi đo không làm sai loss; kết nối chậm ngay từ đầu. Bộ liên quan có 78 test đạt.

Kết quả toàn dự án sau đợt này: **286 test pass**, coverage dòng **78%**, Ruff và `git diff --check` đạt.

Đây là kiểm chứng bằng I/O giả, không phải diễn tập tạo mất gói/độ trễ trên mạng vật lý hoặc lỗi driver thật. Không thay đổi kết nối người dùng hay phát probe thật trong đợt này. ICMP không chứng minh DNS/HTTP/băng thông hoặc xác nhận nguyên nhân ISP; kiểm thử mạng thật vẫn cần thực hiện riêng.
