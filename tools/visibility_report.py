#!/usr/bin/env python3
"""Deliverable thứ ba của Ngày 4: bảng đếm cờ visibility theo từng khớp.

Slide 47: "so report trước, so pixel sau". Hai người gán cùng một bộ ảnh mà tỉ lệ
v=1 lệch hẳn nhau thì họ đang bất đồng về GUIDELINE, không phải về bức ảnh - và
bảng này trả lời trong 2 phút, còn soi từng chấm mất 2 giờ.

    python3 tools/visibility_report.py --labels dataset/labels/train \
        --out outputs/visibility_report.json --markdown reports/visibility_report.md
    # so với bài của bạn cùng nhóm:
    python3 tools/visibility_report.py --labels dataset/labels/train --compare ../ban_cung_nhom/labels/train
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from poselib import (KEYPOINT_NAMES, NUM_KEYPOINTS, OCCLUDED, OUTSIDE, VISIBLE,
                     LabelFormatError, parse_yolo_pose_file)


def collect(label_dir: Path) -> dict:
    counts = [{VISIBLE: 0, OCCLUDED: 0, OUTSIDE: 0} for _ in range(NUM_KEYPOINTS)]
    people = 0
    files = 0
    num_keypoints_total = 0
    for path in sorted(label_dir.glob("*.txt")):
        files += 1
        for person in parse_yolo_pose_file(path):
            people += 1
            num_keypoints_total += person.num_keypoints
            for index, (_, _, visibility) in enumerate(person.keypoints):
                counts[index][visibility] += 1
    return {
        "label_dir": str(label_dir),
        "files": files,
        "people": people,
        "mean_num_keypoints": round(num_keypoints_total / people, 2) if people else 0.0,
        "per_keypoint": [
            {
                "index": index,
                "name": KEYPOINT_NAMES[index],
                "v2_visible": counts[index][VISIBLE],
                "v1_occluded": counts[index][OCCLUDED],
                "v0_outside": counts[index][OUTSIDE],
            }
            for index in range(NUM_KEYPOINTS)
        ],
        "totals": {
            "v2_visible": sum(row[VISIBLE] for row in counts),
            "v1_occluded": sum(row[OCCLUDED] for row in counts),
            "v0_outside": sum(row[OUTSIDE] for row in counts),
        },
    }


def percentage(value: int, total: int) -> str:
    return f"{100 * value / total:.0f}%" if total else "-"


def render_markdown(report: dict, comparison: dict | None) -> str:
    people = report["people"]
    lines = [
        "# Visibility report",
        "",
        f"- Thư mục nhãn: `{report['label_dir']}`",
        f"- {report['files']} ảnh, {people} skeleton, trung bình {report['mean_num_keypoints']} khớp có v > 0 mỗi người",
        f"- Tổng: v=2 {report['totals']['v2_visible']} | v=1 {report['totals']['v1_occluded']} | v=0 {report['totals']['v0_outside']}",
        "",
    ]
    if comparison is None:
        lines += ["| # | Khớp | v=2 | v=1 | v=0 | %v=1 |", "| ---: | --- | ---: | ---: | ---: | ---: |"]
        for row in report["per_keypoint"]:
            total = row["v2_visible"] + row["v1_occluded"] + row["v0_outside"]
            lines.append(
                f"| {row['index']} | {row['name']} | {row['v2_visible']} | {row['v1_occluded']} "
                f"| {row['v0_outside']} | {percentage(row['v1_occluded'], total)} |"
            )
    else:
        lines += [
            f"So sánh với `{comparison['label_dir']}` ({comparison['people']} skeleton).",
            "Cột **lệch** là hiệu số phần trăm v=1 - chỗ nào lệch nhiều nhất là chỗ guideline chưa nói rõ.",
            "",
            "| # | Khớp | %v=1 (bạn) | %v=1 (đối chiếu) | lệch |",
            "| ---: | --- | ---: | ---: | ---: |",
        ]
        rows = []
        for mine, theirs in zip(report["per_keypoint"], comparison["per_keypoint"]):
            mine_total = mine["v2_visible"] + mine["v1_occluded"] + mine["v0_outside"]
            their_total = theirs["v2_visible"] + theirs["v1_occluded"] + theirs["v0_outside"]
            mine_rate = 100 * mine["v1_occluded"] / mine_total if mine_total else 0.0
            their_rate = 100 * theirs["v1_occluded"] / their_total if their_total else 0.0
            rows.append((abs(mine_rate - their_rate), mine, mine_rate, their_rate))
        for gap, row, mine_rate, their_rate in sorted(rows, key=lambda item: -item[0]):
            lines.append(
                f"| {row['index']} | {row['name']} | {mine_rate:.0f}% | {their_rate:.0f}% | {gap:.0f} |"
            )
    lines += [
        "",
        "## Đọc bảng này thế nào",
        "",
        "1. Khớp nào có **%v=1 cao**: khớp hay bị che. Cổ tay và hông thường là hai vị trí"
        " cần xem lại guideline trước khi kết luận.",
        "2. Khớp nào có **v=0 cao bất thường**: mọi người đang dùng Outside ở chỗ đáng lẽ là Occluded."
        " Đó là lỗi số 3 của slide 46, và nó xoá thẳng khớp đó khỏi bảng điểm OKS.",
        "3. Khi so hai người: **lệch lớn = bất đồng về guideline**, không phải về bức ảnh."
        " Sửa guideline trước, sửa nhãn sau.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Đếm cờ visibility theo từng khớp.")
    parser.add_argument("--labels", type=Path, default=Path("dataset/labels/train"))
    parser.add_argument("--compare", type=Path, default=None, help="thư mục nhãn của người khác để so")
    parser.add_argument("--out", type=Path, default=Path("outputs/visibility_report.json"))
    parser.add_argument("--markdown", type=Path, default=Path("reports/visibility_report.md"))
    arguments = parser.parse_args()

    try:
        report = collect(arguments.labels)
        comparison = collect(arguments.compare) if arguments.compare else None
    except LabelFormatError as error:
        print(f"KHÔNG ĐẠT - nhãn sai định dạng: {error}")
        print("Chạy tools/check_pose_labels.py trước.")
        return 1

    if report["people"] == 0:
        print(f"Không đọc được skeleton nào trong {arguments.labels}")
        return 1

    payload = {"report": report, "comparison": comparison}
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = render_markdown(report, comparison)
    arguments.markdown.parent.mkdir(parents=True, exist_ok=True)
    arguments.markdown.write_text(markdown, encoding="utf-8")

    print(markdown)
    print(f"Đã ghi {arguments.out} và {arguments.markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
