#!/usr/bin/env python3
"""Định nghĩa chung cho bộ 17 điểm COCO: topology, sigma, đọc/ghi nhãn, OKS.

Chỉ dùng thư viện chuẩn của Python. Mọi script trong tools/ đều import từ đây,
nên sửa topology ở một chỗ là cả bộ công cụ đổi theo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]
NUM_KEYPOINTS = len(KEYPOINT_NAMES)
INDEX_OF = {name: index for index, name in enumerate(KEYPOINT_NAMES)}

# 19 cạnh COCO, đánh số 0-based. Chỉ dùng để VẼ - model không học các cạnh này.
SKELETON = [
    (15, 13), (13, 11), (16, 14), (14, 12), (11, 12), (5, 11), (6, 12),
    (5, 6), (5, 7), (6, 8), (7, 9), (8, 10), (1, 2), (0, 1), (0, 2),
    (1, 3), (2, 4), (3, 5), (4, 6),
]

# Cặp trái/phải - dùng cho cả augmentation lật ảnh lẫn phát hiện lỗi đảo trái/phải.
FLIP_PAIRS = [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16)]
FLIP_INDEX = list(range(NUM_KEYPOINTS))
for _left, _right in FLIP_PAIRS:
    FLIP_INDEX[_left], FLIP_INDEX[_right] = _right, _left

# Per-keypoint sigma của COCO: đo từ chính sự bất đồng giữa những người gán nhãn.
# Mắt nhỏ nhất (0.025), hông lớn nhất trong nhóm thân (0.107) - xem slide 11-12.
SIGMAS = [
    0.026, 0.025, 0.025, 0.035, 0.035, 0.079, 0.079, 0.072, 0.072,
    0.062, 0.062, 0.107, 0.107, 0.087, 0.087, 0.089, 0.089,
]

VISIBLE = 2
OCCLUDED = 1
OUTSIDE = 0


@dataclass
class Person:
    """Một skeleton: box chuẩn hoá + 17 bộ ba (x, y, v) chuẩn hoá."""

    box: tuple[float, float, float, float]  # cx, cy, w, h
    keypoints: list[tuple[float, float, int]]
    source: str = ""
    line_number: int = 0

    @property
    def area(self) -> float:
        return self.box[2] * self.box[3]

    @property
    def num_keypoints(self) -> int:
        """Đúng định nghĩa num_keypoints của COCO: số khớp có v > 0."""
        return sum(1 for _, _, visibility in self.keypoints if visibility > OUTSIDE)

    def flipped(self) -> "Person":
        return Person(self.box, [self.keypoints[index] for index in FLIP_INDEX], self.source, self.line_number)

    def pixel_keypoints(self, width: int, height: int) -> list[tuple[float, float, int]]:
        return [(x * width, y * height, visibility) for x, y, visibility in self.keypoints]


class LabelFormatError(ValueError):
    pass


def parse_yolo_pose_file(path: Path) -> list[Person]:
    """Đọc một file nhãn Ultralytics YOLO Pose: mỗi dòng 5 + 51 = 56 số."""
    people: list[Person] = []
    if not path.exists():
        return people
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5 + 3 * NUM_KEYPOINTS:
            raise LabelFormatError(
                f"{path.name}:{line_number}: có {len(parts)} số, cần đúng "
                f"{5 + 3 * NUM_KEYPOINTS} (5 box + 17x3 keypoint)"
            )
        try:
            values = [float(part) for part in parts]
        except ValueError as error:
            raise LabelFormatError(f"{path.name}:{line_number}: có giá trị không phải số") from error
        keypoints = []
        for index in range(NUM_KEYPOINTS):
            x, y, visibility = values[5 + index * 3: 8 + index * 3]
            if visibility not in (0.0, 1.0, 2.0):
                raise LabelFormatError(
                    f"{path.name}:{line_number}: cờ visibility của {KEYPOINT_NAMES[index]} "
                    f"là {visibility:g}, chỉ chấp nhận 0, 1 hoặc 2"
                )
            keypoints.append((x, y, int(visibility)))
        people.append(Person(tuple(values[1:5]), keypoints, path.name, line_number))
    return people


def format_yolo_pose_line(person: Person, class_id: int = 0) -> str:
    parts = [str(class_id)] + [f"{value:.6f}" for value in person.box]
    for x, y, visibility in person.keypoints:
        parts += (["0.000000", "0.000000", "0"] if visibility == OUTSIDE
                  else [f"{x:.6f}", f"{y:.6f}", str(visibility)])
    return " ".join(parts)


def oks(prediction: Person, truth: Person, width: int, height: int) -> float:
    """Object Keypoint Similarity - IoU của pose. Khớp v=0 trong gold bị loại khỏi phép tính."""
    scale = truth.area * width * height
    if scale <= 0:
        return 0.0
    total, counted = 0.0, 0
    for index in range(NUM_KEYPOINTS):
        truth_x, truth_y, truth_visibility = truth.keypoints[index]
        if truth_visibility == OUTSIDE:
            continue
        counted += 1
        predicted_x, predicted_y, predicted_visibility = prediction.keypoints[index]
        if predicted_visibility == OUTSIDE:
            continue  # sinh viên bỏ khớp gold có -> tính là 0 điểm cho khớp này
        dx = (predicted_x - truth_x) * width
        dy = (predicted_y - truth_y) * height
        variance = (2 * SIGMAS[index]) ** 2
        total += math.exp(-(dx * dx + dy * dy) / (2 * scale * variance + 1e-12))
    return total / counted if counted else 0.0


def greedy_match(predictions: list[Person], truths: list[Person], width: int, height: int,
                 threshold: float = 0.0) -> tuple[list[tuple[int, int, float]], list[int], list[int]]:
    """Ghép một-một theo OKS giảm dần. Trả về (cặp đã ghép, index thừa, index thiếu)."""
    scored = sorted(
        ((oks(prediction, truth, width, height), prediction_index, truth_index)
         for prediction_index, prediction in enumerate(predictions)
         for truth_index, truth in enumerate(truths)),
        key=lambda item: -item[0],
    )
    used_predictions: set[int] = set()
    used_truths: set[int] = set()
    matched: list[tuple[int, int, float]] = []
    for score, prediction_index, truth_index in scored:
        if score <= threshold or prediction_index in used_predictions or truth_index in used_truths:
            continue
        used_predictions.add(prediction_index)
        used_truths.add(truth_index)
        matched.append((prediction_index, truth_index, score))
    unmatched_predictions = [index for index in range(len(predictions)) if index not in used_predictions]
    unmatched_truths = [index for index in range(len(truths)) if index not in used_truths]
    return matched, unmatched_predictions, unmatched_truths


def image_size(path: Path) -> tuple[int, int]:
    """Đọc kích thước JPEG/PNG bằng thư viện chuẩn - không cần Pillow."""
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:2] != b"\xff\xd8":
        raise LabelFormatError(f"{path.name}: không phải JPEG hoặc PNG")
    offset = 2
    while offset < len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            offset += 2
            continue
        length = int.from_bytes(data[offset + 2: offset + 4], "big")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height = int.from_bytes(data[offset + 5: offset + 7], "big")
            width = int.from_bytes(data[offset + 7: offset + 9], "big")
            return width, height
        offset += 2 + length
    raise LabelFormatError(f"{path.name}: không đọc được kích thước ảnh")


def image_paths(directory: Path) -> list[Path]:
    return sorted(
        path for extension in ("*.jpg", "*.jpeg", "*.png") for path in directory.glob(extension)
    )
