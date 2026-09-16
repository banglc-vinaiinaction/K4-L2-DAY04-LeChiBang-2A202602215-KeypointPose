# Báo cáo Review chéo bài bạn cùng nhóm

- Người kiểm: Lê Chí Bằng (lechibang)
- Người được kiểm: Bạn cùng nhóm (Partner)
- Ngày kiểm: 2026-09-16
- Thư mục đối chiếu: `../ban_cung_nhom/dataset/labels/train`

## 1. Danh sách lỗi chi tiết

| Ảnh | Người thứ | Khớp | Lỗi gì | Sửa thế nào |
| --- | ---: | --- | --- | --- |
| `train_12.jpg` | 1 | `left_shoulder`, `right_shoulder` | Đảo trái/phải theo góc nhìn người chụp | Hoán đổi toạ độ và cờ giữa `left_shoulder` và `right_shoulder`. Cần xác định theo cơ thể người |
| `train_05.jpg` | 1 | `right_wrist` | Xoá khớp bị che (`v = 0`) | Chuyển thành `v = 1`, chấm vị trí ước lượng tại vị trí tay lái xe máy |
| `train_07.jpg` | 1 | `right_elbow` | Chấm trôi khỏi mỏm khớp khuỷu tay | Dịch chuyển keypoint về đúng vị trí giải phẫu khớp khuỷu |
| Toàn bài | Tất cả | `left_hip`, `right_hip` | Không gắn cờ occluded (`v = 2` thay vì `v = 1`) | Toàn bộ các ca mặc quần áo dài đều phải để `v = 1` do hông luôn bị trang phục che khuất |

## 2. Kết luận & Đề xuất

1. **Lỗi lặp lại nhiều nhất**: Sử dụng `v = 2` cho khớp hông trên toàn bộ 20 ảnh và bỏ qua khớp bị che thành `v = 0`.
2. **Nguyên nhân**: Lỗi **guideline chưa rõ** giữa hai bên về định nghĩa khớp bị che (`v = 1`) so với khớp nhìn thấy rõ (`v = 2`). Cần tuân thủ thống nhất quy ước: mọi khớp nằm trong khung hình nhưng bị vật thể hoặc trang phục che khuất đều phải giữ `v = 1` kèm vị trí ước lượng.
