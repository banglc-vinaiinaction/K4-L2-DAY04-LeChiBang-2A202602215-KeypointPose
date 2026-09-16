#!/usr/bin/env python3
"""Kiểm nhãn pose TRƯỚC khi protected release mở. Không cần gold, chạy trong 2 giây.

Đây là "lượt đếm" của slide 42: bắt lỗi định dạng và lỗi cờ bằng script, không
bằng mắt. Chạy nó trước khi nộp - export sai định dạng là lỗi mất điểm nhiều
nhất mà lại dễ sửa nhất.

    python3 tools/check_pose_labels.py --images dataset/images/train --labels dataset/labels/train
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from poselib import (KEYPOINT_NAMES, NUM_KEYPOINTS, OCCLUDED, OUTSIDE, VISIBLE, INDEX_OF,
                     LabelFormatError, image_paths, image_size, parse_yolo_pose_file)

EPSILON = 1e-6


def touches_image_edge(person, margin: float = 0.02) -> bool:
    center_x, center_y, box_width, box_height = person.box
    return (center_x - box_width / 2 <= margin or center_y - box_height / 2 <= margin
            or center_x + box_width / 2 >= 1 - margin or center_y + box_height / 2 >= 1 - margin)


def check_person(person, stem: str, others: list) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    where = f"{stem}.txt:{person.line_number}"

    center_x, center_y, box_width, box_height = person.box
    if box_width <= 0 or box_height <= 0:
        errors.append(f"{where}: box có width/height <= 0")
    if not all(-EPSILON <= value <= 1 + EPSILON for value in person.box):
        errors.append(f"{where}: box không nằm trong [0, 1] - nhãn chưa được chuẩn hoá?")

    for index, (x, y, visibility) in enumerate(person.keypoints):
        name = KEYPOINT_NAMES[index]
        if visibility == OUTSIDE:
            if abs(x) > EPSILON or abs(y) > EPSILON:
                warnings.append(f"{where}: {name} có v=0 nhưng toạ độ khác 0 - Ultralytics sẽ bỏ qua toạ độ này")
            continue
        if not (-EPSILON <= x <= 1 + EPSILON and -EPSILON <= y <= 1 + EPSILON):
            errors.append(f"{where}: {name} có v={visibility} nhưng toạ độ ra ngoài ảnh ({x:.3f}, {y:.3f}) - phải là v=0")

    if person.num_keypoints == 0:
        errors.append(f"{where}: cả 17 khớp đều v=0 - skeleton này sẽ bị loại khỏi mọi phép chấm")

    # Lỗi số 3 của slide 46: xoá khớp bị che thay vì gắn cờ v=1.
    # Chỉ cảnh báo khi box nằm gọn trong ảnh: lúc đó khớp KHÔNG THỂ "ra ngoài khung",
    # nên v=0 hàng loạt gần như chắc chắn là đã xoá khớp bị che.
    hidden = NUM_KEYPOINTS - person.num_keypoints
    if hidden >= 4 and not touches_image_edge(person):
        warnings.append(
            f"{where}: có {hidden} khớp v=0 trong khi cả người nằm gọn giữa ảnh. "
            "Khớp không ra khỏi khung được thì phải là v=1 (bị che, vẫn đặt chấm), không phải v=0"
        )

    # Lượt hình dáng, làm bằng số: vai trái/phải và hông trái/phải không được cắt chéo.
    for left_name, right_name in (("left_shoulder", "right_shoulder"), ("left_hip", "right_hip")):
        left = person.keypoints[INDEX_OF[left_name]]
        right = person.keypoints[INDEX_OF[right_name]]
        if left[2] == OUTSIDE or right[2] == OUTSIDE:
            continue
        nose = person.keypoints[INDEX_OF["nose"]]
        left_eye = person.keypoints[INDEX_OF["left_eye"]]
        right_eye = person.keypoints[INDEX_OF["right_eye"]]
        if left_eye[2] == OUTSIDE or right_eye[2] == OUTSIDE or nose[2] == OUTSIDE:
            continue
        # Hai mắt cho biết người này quay mặt về phía nào; vai/hông phải theo cùng chiều đó.
        eye_direction = left_eye[0] - right_eye[0]
        body_direction = left[0] - right[0]
        if eye_direction * body_direction < 0 and abs(body_direction) > 0.01:
            warnings.append(
                f"{where}: {left_name}/{right_name} nằm ngược chiều so với hai mắt - "
                "dấu hiệu đảo trái/phải, mở tools/visualize_pose.py xem lại"
            )

    # Lỗi số 2 của slide 46 - "nhầm người": một khớp rơi hẳn vào box của người khác
    # trong cùng ảnh, mà lại ở xa box của chính mình.
    for index, (x, y, visibility) in enumerate(person.keypoints):
        if visibility == OUTSIDE:
            continue
        def outside_box(box, slack: float) -> bool:
            box_cx, box_cy, box_w, box_h = box
            reach = slack * max(box_w, box_h)
            return not (box_cx - box_w / 2 - reach <= x <= box_cx + box_w / 2 + reach
                        and box_cy - box_h / 2 - reach <= y <= box_cy + box_h / 2 + reach)

        in_other = any(not outside_box(other.box, 0.0) for other in others)
        if in_other and outside_box(person.box, 0.25):
            warnings.append(
                f"{where}: {KEYPOINT_NAMES[index]} rơi vào box của người khác trong cùng ảnh - "
                "nghi 'nhầm người' (lỗi 2 của slide 46)"
            )
        elif outside_box(person.box, 0.75):
            warnings.append(
                f"{where}: {KEYPOINT_NAMES[index]} nằm rất xa box của chính người này - "
                "nghi 'trượt hẳn' (lỗi 4 của slide 43)"
            )
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiểm định dạng nhãn pose 17 điểm trước khi nộp.")
    parser.add_argument("--images", type=Path, default=Path("dataset/images/train"))
    parser.add_argument("--labels", type=Path, default=Path("dataset/labels/train"))
    parser.add_argument("--strict", action="store_true", help="coi cảnh báo là lỗi (dùng khi chấm)")
    arguments = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    paths = image_paths(arguments.images)
    if not paths:
        print(f"KHÔNG ĐẠT - không tìm thấy ảnh nào trong {arguments.images}")
        return 1

    expected = {path.stem for path in paths}
    actual = {path.stem for path in arguments.labels.glob("*.txt")}
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        errors.append(f"Thiếu {len(missing)} file nhãn: {', '.join(missing[:8])}{' ...' if len(missing) > 8 else ''}")
    if extra:
        errors.append(f"Có {len(extra)} file nhãn không khớp ảnh nào: {', '.join(extra[:8])}")

    total_people = 0
    flag_counts = {VISIBLE: 0, OCCLUDED: 0, OUTSIDE: 0}
    for image_path in paths:
        label_path = arguments.labels / f"{image_path.stem}.txt"
        if not label_path.exists():
            continue
        try:
            people = parse_yolo_pose_file(label_path)
        except LabelFormatError as error:
            errors.append(str(error))
            continue
        if not people:
            warnings.append(f"{label_path.name}: file rỗng - ảnh này thật sự không có người nào?")
        width, height = image_size(image_path)
        for person in people:
            total_people += 1
            for _, _, visibility in person.keypoints:
                flag_counts[visibility] += 1
            others = [other for other in people if other is not person]
            person_errors, person_warnings = check_person(person, image_path.stem, others)
            errors.extend(person_errors)
            warnings.extend(person_warnings)

    print(f"Đã đọc {len(actual & expected)}/{len(expected)} file nhãn, {total_people} skeleton.")
    print(f"Cờ visibility: v=2 {flag_counts[VISIBLE]} | v=1 {flag_counts[OCCLUDED]} | v=0 {flag_counts[OUTSIDE]}")
    if flag_counts[OCCLUDED] == 0 and total_people:
        warnings.append(
            "Toàn bộ bài không có một khớp v=1 nào. Trong ảnh thật gần như không thể - "
            "kiểm lại xem bạn có đang xoá khớp bị che thay vì bấm q (occluded) không"
        )

    if warnings:
        print(f"\nCẢNH BÁO ({len(warnings)}) - không chặn nộp, nhưng phải xem lại:")
        print("\n".join(f"- {warning}" for warning in warnings[:40]))
        if len(warnings) > 40:
            print(f"- ... và {len(warnings) - 40} cảnh báo nữa")
    if errors:
        print(f"\nKHÔNG ĐẠT ({len(errors)} lỗi) - sửa rồi chạy lại:")
        print("\n".join(f"- {error}" for error in errors[:40]))
        if len(errors) > 40:
            print(f"- ... và {len(errors) - 40} lỗi nữa")
        return 1
    if arguments.strict and warnings:
        print("\nKHÔNG ĐẠT ở chế độ --strict: còn cảnh báo chưa xử lý.")
        return 1
    print("\nĐẠT định dạng. Chạy tiếp tools/visibility_report.py, rồi chờ gold để chấm chất lượng.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
