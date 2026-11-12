# Phạm vi và giới hạn còn giữ

Báo cáo chi tiết từng nhóm: [remediation-report-2026-11-12.md](remediation-report-2026-11-12.md).

- Chỉ giám sát Windows/LAN IPv4 cùng miền broadcast. Không bao phủ IPv6, VLAN, client isolation, thiết bị ngủ hoặc thiết bị không trả ARP.
- MAC, ARP, OUI, hostname và dịch vụ tự công bố không xác thực danh tính. Pin router là quyết định sau khi người dùng đối chiếu thiết bị thật. Hồ sơ Windows là ngữ cảnh lưu trữ, không phải ranh giới xác thực chống giả mạo.
- Một đích ICMP và một hop sau gateway không chứng minh DNS/HTTP/băng thông hoặc nguyên nhân ISP. Các kết luận được trình bày theo bằng chứng và mức nghi ngờ.
- Wi-Fi là gợi ý từ AP/tín hiệu; chưa đo phổ, channel width, tải hay loại AP của chính người dùng. Band không rõ giữ Unknown.
- Subnet lớn được phủ dần từng phần 1.024 địa chỉ; không có trần 1.024 host cho cả subnet. Mỗi phần tối đa 4.096 claim; ngân sách hồ sơ tăng theo subnet (ít nhất 10.000 hoặc 4 lần số địa chỉ). Claim/MAC vượt ngân sách vẫn bị báo lỗi và không suy ra Offline từ phần thiếu dữ liệu. Một vòng quét mạng lớn mất nhiều thời gian hơn mạng nhỏ; ba lần vắng mặt tính theo lần IP đó thực sự được quét.
- Khi Windows không trả hồ sơ, cần nhãn mạng dự phòng riêng. Nhãn dự phòng không tự xác thực hoặc tự đổi nếu hệ điều hành không phân biệt mạng.
- Không thể cưỡng bức kết thúc một lời gọi driver bị treo vĩnh viễn trong Python. API stop không báo đã dừng hay đóng CSDL khi worker vẫn còn sống.
- Thông báo từ xa cần opt-in, token và quyền của nhà cung cấp; chưa thử gửi thật. Queue RAM chưa bảo đảm giao sau khi ứng dụng tắt; OA token chưa tự refresh.
- Retention chi tiết mặc định 30 ngày; báo cáo tối đa 31 ngày. Một số danh sách sự kiện được giới hạn/tổng hợp để giữ kích thước có kiểm soát.
- Dữ liệu cũ chưa có network/session ID được giữ ở hồ sơ legacy, không tự gán tin cậy cho mọi mạng mới.
- Cache/sidecar đã bỏ track từ phiên bản này. File đã commit trước đó vẫn còn trong lịch sử Git; bản sửa không viết lại lịch sử.
- Chưa có diễn tập lỗi driver/Npcap thật, xác nhận khay thật trên mọi Windows, đo RF thực hoặc bài tải nhiều ngày. Kiểm thử tự động dùng SQLite tạm và I/O mạng giả.
