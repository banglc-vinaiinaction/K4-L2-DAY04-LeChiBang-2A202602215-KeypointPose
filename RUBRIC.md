# Rubric Ngày 4 - Keypoint & Pose Annotation (100 điểm)

| Tiêu chí | Bằng chứng | Điểm |
| --- | --- | ---: |
| Định dạng và tính hợp lệ | `check_pose_labels.py` chạy 0 lỗi; export đúng **COCO Keypoints 1.0** (mảng `keypoints` có 51 số mỗi người), không phải COCO 1.0 hay YOLO 1.1 | 10 |
| Độ bao phủ | mọi người trong gold đều có skeleton tương ứng; mọi skeleton đều đủ 17 điểm, không ai bị xoá bớt điểm | 10 |
| **Trái/phải và định danh người** | không có lỗi `dao_trai_phai`, không có lỗi `nham_nguoi` trong `outputs/eval_vs_gold.json` | 25 |
| Cờ visibility | khớp bị che dùng `v = 1` **và vẫn có chấm**; `v = 0` chỉ dùng cho khớp ra ngoài khung; không dùng Hidden | 15 |
| Độ chính xác vị trí | `OKS trung bình` và `OKS@0.75` trong `outputs/eval_vs_gold.json` | 10 |
| Visibility report | `reports/visibility_report.md` + bản so với bạn cùng nhóm, có nhận xét khớp nào lệch nhiều nhất và vì sao | 10 |
| Mini guideline | `GUIDELINE_MINI.md` nêu luật cho hông, cho tai bị tóc/mũ che, cho người bị cắt ở mép ảnh, và ít nhất ba ca mơ hồ có lý do | 13 |
| Kiểm chéo | `reports/review_partner.md`: mỗi lỗi ghi rõ ảnh / người thứ mấy / khớp nào / lỗi gì / sửa thế nào, kèm reviewer checklist đã điền | 7 |

## Cổng bắt buộc

- **Export sai định dạng làm mất 17 điểm** (nộp COCO 1.0 hoặc YOLO 1.1 - chỉ còn box):
  tối đa 40 điểm. Bài hôm nay chính là 17 điểm đó.
- **`kpt_shape: [17, 2]`** hoặc nhãn không có cột `v`: tối đa 40 điểm - toàn bộ cờ
  visibility đã bị vứt.
- Không chạy `check_pose_labels.py`, hoặc nộp file còn lỗi định dạng: tối đa 49 điểm.
- Không có `outputs/eval_vs_gold.json`: tối đa 69 điểm.
- Không có `reports/visibility_report.md`: trừ 10 điểm - đó là một trong ba deliverable.
- **Sửa gold sau khi nhận**, sửa `dataset/labels/test/`, hoặc truy ngược dataset nguồn
  để lấy nhãn: bài không được chấm; áp dụng theo quy định học phần.
- **Chạy model trước khi khoá nhãn** rồi sửa nhãn theo model: coi như không có phần
  annotation. Thứ tự tự-gán-trước là bắt buộc, và lịch sử commit cho thấy điều đó.

## Mức chất lượng annotation (nhãn của bạn vs gold)

| Mức | OKS trung bình | OKS@0.75 | Diễn giải |
| --- | ---: | ---: | --- |
| Xuất sắc | >= 0.85 | >= 0.85 | chấm rất sát khớp, không lỗi trái/phải |
| Đạt | >= 0.75 | >= 0.70 | qua cổng, đủ chất lượng để train |
| Cần rework | < 0.75 | < 0.70 | đọc danh sách lỗi trong JSON, sửa rồi chạy lại |

Cổng qua bài là **OKS trung bình >= 0.75 và OKS@0.75 >= 0.70**, **và** không còn lỗi
`dao_trai_phai` nào. Một lỗi đảo trái/phải còn sót lại giữ bài ở mức "Cần rework" dù
điểm số có đẹp đến đâu - vì đó là lỗi model học sai vĩnh viễn.

## Cách đọc điểm cho đúng

- **Rework không bị trừ điểm.** Vòng sửa nhãn sau khi đọc báo cáo lỗi là phần được dạy,
  không phải phần bị phạt. Báo cáo nên ghi: OKS trước rework, sửa gì, OKS sau rework.
  Một bài đi từ 0.71 lên 0.88 và giải thích được mình sửa gì thì tốt hơn một bài 0.89
  không giải thích được gì.
- **Điểm model thấp không bị trừ.** 20 ảnh là quá ít để fine-tune ra một model tốt, và
  `yolo26n-pose` vốn đã được train trên COCO. `pose_mAP` có thể **giảm** sau fine-tune.
  Việc của bạn là *giải thích* con số, không phải làm nó đẹp.
- **Lệch cờ so với gold không bị trừ.** Gold lấy từ COCO, mà COCO dùng `v = 0` cho cả
  "không gán nhãn" lẫn "ra ngoài khung". Hai mục `co_khac_gold` và `gold_khong_gan_nhan`
  trong JSON là thông tin chẩn đoán, không phải lỗi. Xem mục cuối [README.md](README.md).
- **`%v=1` cao hơn gold là đúng luật của lớp**, không phải là gán ẩu.
