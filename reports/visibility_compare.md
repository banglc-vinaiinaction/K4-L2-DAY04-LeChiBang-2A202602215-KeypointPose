# Visibility report

- Thư mục nhãn: `dataset/labels/train`
- 20 ảnh, 29 skeleton, trung bình 15.45 khớp có v > 0 mỗi người
- Tổng: v=2 317 | v=1 131 | v=0 45

So sánh với `../ban_cung_nhom/dataset/labels/train` (29 skeleton).
Cột **lệch** là hiệu số phần trăm v=1 - chỗ nào lệch nhiều nhất là chỗ guideline chưa nói rõ.

| # | Khớp | %v=1 (bạn) | %v=1 (đối chiếu) | lệch |
| ---: | --- | ---: | ---: | ---: |
| 11 | left_hip | 97% | 0% | 97 |
| 12 | right_hip | 97% | 0% | 97 |
| 0 | nose | 14% | 14% | 0 |
| 1 | left_eye | 17% | 17% | 0 |
| 2 | right_eye | 14% | 14% | 0 |
| 3 | left_ear | 21% | 21% | 0 |
| 4 | right_ear | 21% | 21% | 0 |
| 5 | left_shoulder | 7% | 7% | 0 |
| 6 | right_shoulder | 3% | 3% | 0 |
| 7 | left_elbow | 14% | 14% | 0 |
| 8 | right_elbow | 14% | 14% | 0 |
| 9 | left_wrist | 17% | 17% | 0 |
| 10 | right_wrist | 24% | 24% | 0 |
| 13 | left_knee | 21% | 21% | 0 |
| 14 | right_knee | 17% | 17% | 0 |
| 15 | left_ankle | 28% | 28% | 0 |
| 16 | right_ankle | 28% | 28% | 0 |

## Đọc bảng này thế nào

1. Khớp nào có **%v=1 cao**: khớp hay bị che. Cổ tay và hông thường là hai vị trí cần xem lại guideline trước khi kết luận.
2. Khớp nào có **v=0 cao bất thường**: mọi người đang dùng Outside ở chỗ đáng lẽ là Occluded. Đó là lỗi số 3 của slide 46, và nó xoá thẳng khớp đó khỏi bảng điểm OKS.
3. Khi so hai người: **lệch lớn = bất đồng về guideline**, không phải về bức ảnh. Sửa guideline trước, sửa nhãn sau.
