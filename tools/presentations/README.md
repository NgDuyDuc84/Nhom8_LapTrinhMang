# Công cụ trình chiếu tùy chọn

Ứng dụng NetGuard không phụ thuộc thư mục này hoặc Node.js. Mã ở đây được giữ lại từ công cụ dựng bài trình chiếu cũ; nội dung slide là bản lịch sử, không thay thế báo cáo sửa mã hiện tại.

- Node.js 22+, chạy `npm ci --legacy-peer-deps` tại thư mục này để cài Sharp đúng lockfile.
- Các script export cần runtime riêng `@oai/artifact-tool` phiên bản 2.8.146. Package này là private, không giả định người dùng có thể tải từ npm công khai. Cung cấp đường dẫn entry module bằng `NETGUARD_ARTIFACT_TOOL_ENTRY`, thư mục node modules của runtime bằng `NETGUARD_ARTIFACT_NODE_MODULES` và thư mục skill qua `PRESENTATIONS_SKILL_DIR`.
- `NETGUARD_BUILD_PYTHON` chọn Python dùng để validate; mặc định `python` trong PATH.
- Mọi đường dẫn dự án được tính từ vị trí script. Dữ liệu trung gian/ảnh/PPTX JSON đặt ở `.presentation-build/`, không commit. Chuẩn bị lại input bằng các script `prepare.mjs`, `render_demo_v2.py`; input slide lịch sử cần bản JSON của bộ slide tương ứng.
- `.presentation-build` cũ được giữ nguyên trên máy khi bỏ theo dõi Git; không xóa hay viết lại lịch sử Git. Việc loại dữ liệu đã commit khỏi lịch sử là quyết định riêng của chủ repository trước khi chia sẻ.

Không cần chạy bất kỳ công cụ nào ở đây để cài đặt, kiểm thử hoặc mở NetGuard.
