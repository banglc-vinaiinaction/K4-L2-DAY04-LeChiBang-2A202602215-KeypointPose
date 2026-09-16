# Reviewer checklist - điền khi kiểm bài người khác

Người gán: Bạn cùng nhóm (Partner)   Người kiểm: Lê Chí Bằng (lechibang)   Ngày: 2026-09-16

Chạy trước khi soi bằng mắt:

```bash
python3 tools/check_pose_labels.py --images dataset/images/train --labels ../ban_cung_nhom/dataset/labels/train
python3 tools/visualize_pose.py --images dataset/images/train --labels ../ban_cung_nhom/dataset/labels/train --out /tmp/vis_review
python3 tools/visibility_report.py --labels dataset/labels/train --compare ../ban_cung_nhom/dataset/labels/train --markdown reports/visibility_compare.md
```

| | Mục kiểm | Đạt? | Ghi chú / ảnh nào |
| --- | --- | :---: | --- |
| 1 | Mọi người trong ảnh đều có đủ 17 điểm, không ai bị thiếu | ☑ | Đủ 20 ảnh, 29 skeleton, mỗi skeleton đủ 17 điểm |
| 2 | Bật đường nối: không có xương nào cắt chéo ở vai hoặc hông | ☒ | `train_12.jpg`: vai trái/phải cắt chéo do đảo chiều |
| 3 | Không có xương nào kéo dài sang một cơ thể khác | ☑ | Không có hiện tượng nhầm người sang box lân cận |
| 4 | Khớp bị che dùng `v = 1` **và có chấm**, không phải `v = 0` | ☒ | `train_05.jpg`: cổ tay bị xe che nhưng để v=0; Hông toàn bài để v=2 thay vì v=1 |
| 5 | `v = 0` chỉ xuất hiện ở khớp thật sự ra ngoài mép ảnh | ☑ | Các khớp v=0 còn lại đều do tràn mép khung hình |
| 6 | Không có dấu hiệu dùng `Hidden` (điểm `v = 2` nằm ở chỗ vô lý) | ☑ | Không có toạ độ treo vô lý |
| 7 | Export đúng **COCO Keypoints 1.0**: mảng `keypoints` có 51 số mỗi người | ☑ | Đạt chuẩn COCO keypoints |
| 8 | Bản YOLO Pose: mỗi dòng 56 số, `kpt_shape: [17, 3]` | ☑ | Đúng format YOLO Pose chuẩn hoá [0, 1] |
| 9 | Visibility report đã nộp, và hai bảng đã được đặt cạnh nhau | ☑ | Đã đối chiếu tại `reports/visibility_compare.md` |
| 10 | Mọi ca không rõ đều được ghi trong `GUIDELINE_MINI.md` | ☑ | Đã đồng bộ các ca biên |
| 11 | `check_pose_labels.py` chạy 0 lỗi | ☑ | 0 lỗi cú pháp, 1 cảnh báo hình dáng tại `train_12.txt:1` |

## Lỗi tìm được

Chép sang `reports/review_partner.md`. Mỗi dòng một lỗi, đủ bốn cột - người sửa phải
mở đúng chỗ đó được mà không cần hỏi lại.

| Ảnh | Người thứ | Khớp | Lỗi gì | Sửa thế nào |
| --- | ---: | --- | --- | --- |
| `train_12.jpg` | 1 | `left_shoulder`, `right_shoulder` | Đảo trái/phải theo góc nhìn ảnh | Đổi lại toạ độ hai vai theo giải phẫu cơ thể người |
| `train_05.jpg` | 1 | `right_wrist` | Xoá khớp bị che (để `v = 0`) | Chuyển sang `v = 1`, đặt chấm ước lượng sau tay lái |
| `train_07.jpg` | 1 | `right_elbow` | Trôi khớp (trôi ra ngoài cánh tay) | Kéo chấm về đúng mỏm khuỷu tay |
| Toàn bộ bài | Tất cả | `left_hip`, `right_hip` | Đánh `v = 2` thay vì `v = 1` | Đổi thành `v = 1` theo guideline chung về khớp hông bị quần áo che |

## Hai câu kết luận

- Lỗi lặp đi lặp lại nhiều nhất của bài này: Nhầm lẫn cờ `v = 2` cho khớp hông khi mặc trang phục dài và xoá khớp bị che thành `v = 0`.
- Nó là lỗi **guideline chưa rõ** về quy ước đánh giá khớp bị che bởi quần áo/vật cản.
