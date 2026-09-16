# Visibility report

- Thư mục nhãn: `dataset/labels/train`
- 20 ảnh, 29 skeleton, trung bình 15.45 khớp có v > 0 mỗi người
- Tổng: v=2 316 | v=1 132 | v=0 45

| # | Khớp | v=2 | v=1 | v=0 | %v=1 |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0 | nose | 22 | 4 | 3 | 14% |
| 1 | left_eye | 19 | 5 | 5 | 17% |
| 2 | right_eye | 22 | 4 | 3 | 14% |
| 3 | left_ear | 15 | 6 | 8 | 21% |
| 4 | right_ear | 20 | 6 | 3 | 21% |
| 5 | left_shoulder | 27 | 2 | 0 | 7% |
| 6 | right_shoulder | 28 | 1 | 0 | 3% |
| 7 | left_elbow | 24 | 4 | 1 | 14% |
| 8 | right_elbow | 25 | 4 | 0 | 14% |
| 9 | left_wrist | 23 | 5 | 1 | 17% |
| 10 | right_wrist | 20 | 8 | 1 | 28% |
| 11 | left_hip | 0 | 28 | 1 | 97% |
| 12 | right_hip | 0 | 28 | 1 | 97% |
| 13 | left_knee | 20 | 6 | 3 | 21% |
| 14 | right_knee | 21 | 5 | 3 | 17% |
| 15 | left_ankle | 15 | 8 | 6 | 28% |
| 16 | right_ankle | 15 | 8 | 6 | 28% |

## Đọc bảng này thế nào

1. Khớp nào có **%v=1 cao**: khớp hay bị che. Cổ tay và hông thường là hai vị trí cần xem lại guideline trước khi kết luận.
2. Khớp nào có **v=0 cao bất thường**: mọi người đang dùng Outside ở chỗ đáng lẽ là Occluded. Đó là lỗi số 3 của slide 46, và nó xoá thẳng khớp đó khỏi bảng điểm OKS.
3. Khi so hai người: **lệch lớn = bất đồng về guideline**, không phải về bức ảnh. Sửa guideline trước, sửa nhãn sau.
