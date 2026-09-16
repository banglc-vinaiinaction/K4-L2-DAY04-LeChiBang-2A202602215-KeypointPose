# Bài thực hành Ngày 4 - Gán nhãn keypoint & pose

> Bắt đầu bằng [lab-guide.html](lab-guide.html) nếu bạn mới dùng CVAT. Sau đó làm theo
> [GUIDE.md](GUIDE.md) để hoàn thành toàn bộ route 240 phút. Hướng dẫn HTML có ảnh CVAT thật,
> thao tác phóng to/đóng bằng bàn phím, và không yêu cầu kinh nghiệm lập trình.

Ngày 2 bạn ghi 4 con số cho một người. Ngày 3 bạn thêm một con số nữa (`track_id`).
Hôm nay bạn ghi **51 con số cho một người** - 17 khớp có tên, mỗi khớp một cặp toạ độ
và một **cờ visibility**. Cái cờ đó không phải ghi chú cho người đọc sau; nó là một
phần ba của nhãn, và nó quyết định khớp đó có được tính điểm hay không.

```text
20 ảnh chưa có nhãn -> CVAT Skeleton (17 điểm) -> export COCO Keypoints 1.0
   -> tự kiểm 3 lượt + visibility report -> khoá nhãn
   -> protected release mở -> chấm bằng OKS -> rework
   -> Colab: fine-tune YOLO26-Pose -> visualize -> đánh giá
```

## Phạm vi dữ liệu — đọc trước khi tạo task

Lab có **một route bắt buộc**: 20 ảnh `person` COCO-17. Ba bộ dưới đây có vai trò khác nhau;
không đổi chỗ cho nhau.

| Bộ dữ liệu | Ở đâu | Bạn làm gì | Có train / nộp? |
| --- | --- | --- | --- |
| **Core: 20 ảnh chưa nhãn** | `dataset/images/train/` | Tạo một task CVAT `person` 17 điểm, gán tất cả người trong ảnh, export và chuyển thành nhãn YOLO Pose | **Có** |
| **Test: 10 ảnh đã có nhãn** | `dataset/images/test/`, `dataset/labels/test/` | Chỉ dùng để đánh giá model trong notebook | **Không sửa, không train** |

Không có bài hand/face trong bản phát hành này. Đừng tự tạo skeleton thứ hai hoặc thêm thư mục
export thứ hai: repo chưa phát hành input và schema có thể kiểm chứng cho phần đó.

## Mục tiêu học tập

Sau lab, bạn có thể:

1. Dựng một **skeleton label 17 điểm COCO** trong CVAT và tái sử dụng nó bằng file `.SVG`.
2. Chọn đúng **v = 0 / 1 / 2** cho từng khớp, và giải thích được vì sao "bị che" khác
   "ra ngoài khung".
3. Export đúng **COCO Keypoints 1.0**, và biết đếm 51 (hoặc 56) số để phát hiện export sai.
4. Đọc **OKS** để tìm lỗi trong nhãn của chính mình, và gọi đúng tên bốn kiểu sai:
   lệch nhẹ, đảo trái/phải, nhầm người, trượt hẳn.
5. Dùng **visibility report** để phát hiện bất đồng về *guideline* trước khi đi soi từng pixel.
6. Fine-tune một model pose trên chính nhãn của mình và giải thích được con số thu được.

## Bài nộp

| Tệp | Nội dung |
| --- | --- |
| `dataset/labels/train/*.txt` | nhãn 20 ảnh train, định dạng Ultralytics YOLO Pose (56 số/dòng) |
| `annotations/coco_keypoints/person_keypoints_default.json` | đúng bản export **COCO Keypoints 1.0** từ CVAT |
| `reports/visibility_report.md`, `outputs/visibility_report.json` | bảng đếm cờ theo từng khớp |
| `GUIDELINE_MINI.md` | luật của nhóm bạn + ít nhất ba ca mơ hồ đã gặp và cách quyết |
| `outputs/eval_vs_gold.json` | kết quả chấm với gold (sau khi protected release mở) |
| `outputs/eval_model.json` | số liệu model trước/sau fine-tune, từ notebook |
| `reports/REPORT.md` | báo cáo, điền từ `reports/REPORT_TEMPLATE.md` |
| `reports/review_partner.md` | lỗi tìm được trong bài người khác + reviewer checklist đã điền |

Đọc [GUIDE.md](GUIDE.md) theo thứ tự thao tác và đối chiếu [RUBRIC.md](RUBRIC.md) trước khi nộp.

## Cấu trúc thư mục

```text
Day4-Lab/
  dataset/images/train/   20 ảnh - BÀI CHÍNH, không có nhãn khi pull
  dataset/images/test/    10 ảnh - có nhãn sẵn, dùng để đánh giá model
  dataset/labels/train/   nhãn của bạn đặt ở đây (đang trống)
  dataset/labels/test/    nhãn phát sẵn - KHÔNG sửa, KHÔNG dùng để train
  gold/                   trống; protected release đặt gold của train ở đây tại mốc 2:30
  annotations/            bản export gốc COCO Keypoints của 20 ảnh core
  tools/                  check / visibility / evaluate / visualize / convert
  notebooks/              notebook Colab: fine-tune YOLO26-Pose + đánh giá
  reports/                mẫu báo cáo và reviewer checklist
  outputs/                kết quả chấm, kết quả model
  data.yaml               cấu hình dataset cho Ultralytics (kpt_shape [17, 3])
```

Không đổi tên ảnh, không sửa `dataset/labels/test/`, và không sửa gold sau khi nhận.

## Công cụ

Mọi script trong `tools/` **chỉ dùng thư viện chuẩn của Python** - chạy được ngay,
không cần cài gì (trừ `visualize_pose.py` cần Pillow). OKS và per-keypoint sigma lấy
đúng theo định nghĩa của COCO, xem `tools/poselib.py`.

```bash
# 1. Sau khi export từ CVAT: COCO Keypoints 1.0 -> nhãn để train
python3 tools/coco_kp_to_yolo_pose.py \
    --coco annotations/coco_keypoints/person_keypoints_default.json \
    --out dataset/labels/train

# 2. Kiểm định dạng - chạy trước khi nộp, không cần gold
python3 tools/check_pose_labels.py --images dataset/images/train --labels dataset/labels/train

# 3. Lượt hình dáng: bật đường nối lên và nhìn
python3 tools/visualize_pose.py --images dataset/images/train \
    --labels dataset/labels/train --out outputs/vis_train

# 4. Deliverable thứ ba: bảng đếm cờ visibility
python3 tools/visibility_report.py --labels dataset/labels/train \
    --out outputs/visibility_report.json --markdown reports/visibility_report.md

# 5. Kiểm chéo: so bảng đếm của bạn với của bạn cùng nhóm
python3 tools/visibility_report.py --labels dataset/labels/train \
    --compare ../ban_cung_nhom/dataset/labels/train --markdown reports/visibility_compare.md

# 6. Chấm với gold - CHỈ chạy sau khi protected release mở
python3 tools/evaluate_pose_annotations.py --pred dataset/labels/train \
    --gold gold/labels/train --images dataset/images/train --out outputs/eval_vs_gold.json
```

## Một lưu ý về gold - đọc trước khi cãi nhau với điểm số

Gold của lab này lấy từ COCO. COCO dùng `v = 0` cho **cả hai** trường hợp: "ra ngoài
khung" *và* "người gán nhãn quyết định không gán khớp này". Luật của lớp mình chặt hơn:
khớp bị che mà còn trong khung thì phải là `v = 1` và vẫn đặt chấm.

Hệ quả, và nó là cố ý:

- Khớp nào gold để `v = 0` thì **bị loại khỏi phép tính OKS** - bạn không được và cũng
  không mất điểm ở khớp đó. Cứ theo luật của lớp, gắn `v = 1` và đặt chấm.
- Nên `%v = 1` trong visibility report của bạn sẽ **cao hơn của gold**. Đó không phải lỗi
  của bạn. Đó đúng là thứ slide 47 nói: hai bảng đếm lệch nhau = hai guideline khác nhau,
  không phải hai bức ảnh khác nhau.
- `tools/check_pose_labels.py` chạy trên chính gold cũng in ra cảnh báo vì lý do này.
  Lớp sẽ dùng nó làm ví dụ.
