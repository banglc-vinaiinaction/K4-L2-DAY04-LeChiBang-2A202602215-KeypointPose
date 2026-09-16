#!/usr/bin/env python3
"""Chuyển bản export COCO Keypoints 1.0 của CVAT sang nhãn Ultralytics YOLO Pose.

Bản nộp của Ngày 4 là COCO Keypoints 1.0 (slide 40). Nhưng để train thì
Ultralytics cần mỗi ảnh một file .txt với 5 + 51 = 56 số một dòng. Script này làm
đúng một việc đó - và sắp lại thứ tự khớp THEO TÊN, nên nếu bạn dựng skeleton
trong CVAT theo thứ tự khác COCO thì nó vẫn ra đúng.

    python3 tools/coco_kp_to_yolo_pose.py \\
        --coco annotations/person_keypoints_default.json --out dataset/labels/train
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from poselib import KEYPOINT_NAMES, NUM_KEYPOINTS, OUTSIDE, Person, format_yolo_pose_line


def build_order(category: dict) -> list[int]:
    """Trả về danh sách vị trí: order[i] = vị trí của KEYPOINT_NAMES[i] trong file COCO."""
    names = category.get("keypoints") or []
    if len(names) != NUM_KEYPOINTS:
        raise SystemExit(
            f"Category '{category.get('name')}' khai báo {len(names)} điểm, cần đúng {NUM_KEYPOINTS}.\n"
            "Skeleton của bạn không phải bộ 17 điểm COCO - dựng lại bằng "
            "'From model -> Human pose estimation' trong CVAT."
        )
    lookup = {name: index for index, name in enumerate(names)}
    missing = [name for name in KEYPOINT_NAMES if name not in lookup]
    if missing:
        raise SystemExit(
            "Thiếu hoặc sai tên khớp trong skeleton: " + ", ".join(missing) + "\n"
            f"Tên trong file của bạn: {names}\n"
            "Tên phải đúng chính tả COCO (left_wrist, right_wrist, ...)."
        )
    return [lookup[name] for name in KEYPOINT_NAMES]


def main() -> int:
    parser = argparse.ArgumentParser(description="COCO Keypoints 1.0 (CVAT) -> Ultralytics YOLO Pose.")
    parser.add_argument("--coco", type=Path, required=True, help="file .json trong bản export CVAT")
    parser.add_argument("--out", type=Path, default=Path("dataset/labels/train"))
    parser.add_argument("--label", default=None,
                        help="tên skeleton label cần lấy, khi file có nhiều bộ (vd: person)")
    parser.add_argument("--empty-for-all-images", action="store_true",
                        help="ghi cả file .txt rỗng cho ảnh không có người nào")
    arguments = parser.parse_args()

    document = json.loads(arguments.coco.read_text(encoding="utf-8"))
    for key in ("images", "annotations", "categories"):
        if key not in document:
            raise SystemExit(
                f"File thiếu khoá '{key}' - đây không phải bản export COCO Keypoints 1.0.\n"
                "Trong CVAT: Export -> COCO Keypoints 1.0 (KHÔNG phải 'COCO 1.0', "
                "cũng không phải 'YOLO 1.1' - hai định dạng đó vứt hết 17 điểm)."
            )
    person_categories = [c for c in document["categories"] if c.get("keypoints")]
    if not person_categories:
        raise SystemExit(
            "Không category nào có danh sách 'keypoints'. Bản export này chỉ có box, không có khớp.\n"
            "Đúng cái bẫy của slide 40: chọn nhầm 'COCO 1.0' hoặc 'YOLO 1.1' thay vì 'COCO Keypoints 1.0'."
        )
    if arguments.label:
        category = next((c for c in person_categories if c["name"] == arguments.label), None)
        if category is None:
            raise SystemExit(
                f"Không có skeleton label tên '{arguments.label}'. Có trong file: "
                + ", ".join(c["name"] for c in person_categories)
            )
    else:
        # Chỉ lấy skeleton đúng 17 điểm; không dựa vào thứ tự category trong export.
        matching = [c for c in person_categories if len(c["keypoints"]) == NUM_KEYPOINTS]
        if not matching:
            raise SystemExit(
                "Không có skeleton label nào đúng 17 điểm. Có trong file: "
                + ", ".join(f"{c['name']} ({len(c['keypoints'])} điểm)" for c in person_categories)
                + "\nHãy export lại task core với skeleton `person` 17 điểm."
            )
        if len(matching) > 1:
            raise SystemExit(
                "Có nhiều skeleton 17 điểm: "
                + ", ".join(c["name"] for c in matching)
                + " - chỉ rõ bằng --label."
            )
        category = matching[0]
        if len(person_categories) > 1:
            print(f"File có {len(person_categories)} skeleton label, đã chọn "
                  f"'{category['name']}' (bộ 17 điểm).")
    order = build_order(category)

    images = {image["id"]: image for image in document["images"]}
    per_image: dict[int, list[str]] = {image_id: [] for image_id in images}
    skipped = 0

    for annotation in document["annotations"]:
        if annotation.get("category_id") != category["id"]:
            continue
        image = images.get(annotation["image_id"])
        if image is None:
            continue
        width, height = image["width"], image["height"]
        flat = annotation.get("keypoints") or []
        if len(flat) != NUM_KEYPOINTS * 3:
            raise SystemExit(
                f"annotation id={annotation.get('id')} có {len(flat)} số trong 'keypoints', "
                f"cần đúng {NUM_KEYPOINTS * 3} = 17 x (x, y, v). Export lại, đừng gán lại nhãn."
            )
        keypoints = []
        for source_index in order:
            x, y, visibility = flat[source_index * 3: source_index * 3 + 3]
            visibility = int(visibility)
            keypoints.append((0.0, 0.0, OUTSIDE) if visibility == OUTSIDE
                             else (x / width, y / height, visibility))

        box = annotation.get("bbox")
        if box and box[2] > 0 and box[3] > 0:
            x, y, box_width, box_height = box
            normalized = ((x + box_width / 2) / width, (y + box_height / 2) / height,
                          box_width / width, box_height / height)
        else:
            marked = [(x, y) for x, y, visibility in keypoints if visibility != OUTSIDE]
            if not marked:
                skipped += 1
                continue
            xs, ys = [p[0] for p in marked], [p[1] for p in marked]
            normalized = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                          max(xs) - min(xs), max(ys) - min(ys))
        per_image[annotation["image_id"]].append(
            format_yolo_pose_line(Person(normalized, keypoints))
        )

    arguments.out.mkdir(parents=True, exist_ok=True)
    written = 0
    for image_id, image in images.items():
        lines = per_image[image_id]
        if not lines and not arguments.empty_for_all_images:
            continue
        (arguments.out / f"{Path(image['file_name']).stem}.txt").write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        written += 1

    print(f"Đã ghi {written} file nhãn vào {arguments.out} "
          f"({sum(len(v) for v in per_image.values())} skeleton).")
    if skipped:
        print(f"Bỏ qua {skipped} skeleton không có khớp nào và không có bbox.")
    if order != list(range(NUM_KEYPOINTS)):
        print("Lưu ý: thứ tự khớp trong file CVAT khác thứ tự COCO - script đã sắp lại theo TÊN.")
    print("Chạy tiếp: python3 tools/check_pose_labels.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
