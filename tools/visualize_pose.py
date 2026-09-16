#!/usr/bin/env python3
"""Vẽ skeleton lên ảnh - đây là 'lượt hình dáng' của slide 42, làm bằng script.

Bật đường nối lên rồi nhìn: xương người gần như không bao giờ tự cắt chéo ở thân.
Chỗ nào cắt chéo là chỗ nghi đảo trái/phải.

    python3 tools/visualize_pose.py --images dataset/images/train \
        --labels dataset/labels/train --out outputs/vis_train
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from poselib import KEYPOINT_NAMES, OCCLUDED, OUTSIDE, SKELETON, VISIBLE, image_paths, parse_yolo_pose_file

LEFT_COLOR = (64, 160, 255)
RIGHT_COLOR = (255, 128, 64)
CENTER_COLOR = (240, 240, 240)
OCCLUDED_COLOR = (255, 215, 0)
BOX_COLOR = (0, 220, 120)


def side_color(index: int) -> tuple[int, int, int]:
    name = KEYPOINT_NAMES[index]
    if name.startswith("left_"):
        return LEFT_COLOR
    if name.startswith("right_"):
        return RIGHT_COLOR
    return CENTER_COLOR


def draw_image(image_path: Path, label_path: Path, output_path: Path, show_names: bool) -> int:
    from PIL import Image, ImageDraw

    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    canvas = ImageDraw.Draw(image)
    people = parse_yolo_pose_file(label_path)

    for person in people:
        center_x, center_y, box_width, box_height = person.box
        canvas.rectangle(
            [(center_x - box_width / 2) * width, (center_y - box_height / 2) * height,
             (center_x + box_width / 2) * width, (center_y + box_height / 2) * height],
            outline=BOX_COLOR, width=2,
        )
        points = person.pixel_keypoints(width, height)
        for first, second in SKELETON:
            if points[first][2] == OUTSIDE or points[second][2] == OUTSIDE:
                continue
            dashed = points[first][2] == OCCLUDED or points[second][2] == OCCLUDED
            canvas.line(
                [points[first][:2], points[second][:2]],
                fill=OCCLUDED_COLOR if dashed else side_color(second),
                width=2 if dashed else 3,
            )
        for index, (x, y, visibility) in enumerate(points):
            if visibility == OUTSIDE:
                continue
            radius = 4 if visibility == VISIBLE else 3
            color = side_color(index) if visibility == VISIBLE else OCCLUDED_COLOR
            canvas.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color, outline=(20, 20, 20))
            if show_names:
                canvas.text((x + 5, y - 6), KEYPOINT_NAMES[index], fill=color)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, "JPEG", quality=88)
    return len(people)


def main() -> int:
    parser = argparse.ArgumentParser(description="Vẽ skeleton 17 điểm lên ảnh để soi bằng mắt.")
    parser.add_argument("--images", type=Path, default=Path("dataset/images/train"))
    parser.add_argument("--labels", type=Path, default=Path("dataset/labels/train"))
    parser.add_argument("--out", type=Path, default=Path("outputs/vis_train"))
    parser.add_argument("--names", action="store_true", help="ghi tên khớp cạnh mỗi chấm")
    arguments = parser.parse_args()

    paths = image_paths(arguments.images)
    if not paths:
        print(f"Không tìm thấy ảnh trong {arguments.images}")
        return 1
    total = 0
    for image_path in paths:
        label_path = arguments.labels / f"{image_path.stem}.txt"
        if not label_path.exists():
            print(f"- {image_path.stem}: chưa có nhãn, bỏ qua")
            continue
        total += draw_image(image_path, label_path, arguments.out / image_path.name, arguments.names)
    print(f"Đã vẽ {total} skeleton vào {arguments.out}")
    print("Xanh = bên trái cơ thể, cam = bên phải, vàng = khớp bị che (v=1).")
    print("Nhìn vùng vai và hông: hai đường nối cắt chéo nhau => nghi đảo trái/phải.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
