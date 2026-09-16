#!/usr/bin/env python3
"""Chấm nhãn pose của bạn với gold bằng OKS, và gọi tên từng lỗi.

Chạy SAU khi protected release mở. Ngoài điểm số, script trả về một danh sách lỗi
đã phân loại đúng theo slide 43/46 - dùng nó để rework, đừng chỉ nhìn con số.

    python3 tools/evaluate_pose_annotations.py \\
        --pred dataset/labels/train --gold gold/labels/train \\
        --images dataset/images/train --out outputs/eval_vs_gold.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from poselib import (KEYPOINT_NAMES, NUM_KEYPOINTS, OCCLUDED, OUTSIDE, SIGMAS, VISIBLE,
                     LabelFormatError, greedy_match, image_paths, image_size, oks,
                     parse_yolo_pose_file)

# Ngưỡng OKS của COCO: 0.50 là "nhận ra đúng người và đúng pose",
# 0.75 là "đủ chính xác để train".
LOOSE_THRESHOLD = 0.50
STRICT_THRESHOLD = 0.75

# Một khớp bị coi là sai vị trí khi lệch quá bao nhiêu lần bán kính dung sai của
# chính khớp đó (2*sigma*sqrt(area) - đúng mẫu số trong công thức OKS).
SLIGHT_OFFSET = 1.0
GROSS_OFFSET = 3.0

FLIP_MARGIN = 0.10


def tolerance_radius(index: int, area_pixels: float) -> float:
    return 2 * SIGMAS[index] * math.sqrt(max(area_pixels, 1e-9))


def diagnose_pair(prediction, truth, others, width: int, height: int) -> list[dict]:
    """Gọi tên lỗi cho một cặp (skeleton của bạn, skeleton gold) đã ghép được."""
    findings: list[dict] = []
    area = truth.area * width * height

    if oks(prediction.flipped(), truth, width, height) > oks(prediction, truth, width, height) + FLIP_MARGIN:
        findings.append({
            "type": "dao_trai_phai",
            "label": "Đảo trái/phải",
            "detail": "Đổi lại toàn bộ cặp trái/phải cho skeleton này thì OKS tăng hẳn.",
        })

    for index in range(NUM_KEYPOINTS):
        truth_x, truth_y, truth_visibility = truth.keypoints[index]
        predicted_x, predicted_y, predicted_visibility = prediction.keypoints[index]
        name = KEYPOINT_NAMES[index]

        if truth_visibility == OUTSIDE:
            if predicted_visibility != OUTSIDE:
                findings.append({
                    "type": "gold_khong_gan_nhan",
                    "label": "Gold không gán khớp này",
                    "keypoint": name,
                    "detail": "Không bị trừ điểm: khớp gold có v=0 bị loại khỏi OKS. Xem mục lưu ý trong README.",
                })
            continue

        if predicted_visibility == OUTSIDE:
            findings.append({
                "type": "xoa_khop_bi_che" if truth_visibility == OCCLUDED else "thieu_khop",
                "label": "Xoá khớp bị che" if truth_visibility == OCCLUDED else "Thiếu khớp gold có",
                "keypoint": name,
                "detail": f"Gold có v={truth_visibility}, bài của bạn v=0 nên khớp này tính 0 điểm. "
                          "Gán lại với v=1 và đặt chấm ở vị trí ước lượng.",
            })
            continue

        distance = math.hypot((predicted_x - truth_x) * width, (predicted_y - truth_y) * height)
        ratio = distance / tolerance_radius(index, area)

        if ratio > SLIGHT_OFFSET:
            nearer_other = None
            for other_index, other in enumerate(others):
                other_x, other_y, other_visibility = other.keypoints[index]
                if other_visibility == OUTSIDE:
                    continue
                if math.hypot((predicted_x - other_x) * width, (predicted_y - other_y) * height) < distance:
                    nearer_other = other_index
                    break
            if nearer_other is not None:
                findings.append({
                    "type": "nham_nguoi",
                    "label": "Nhầm người",
                    "keypoint": name,
                    "detail": f"Chấm này gần {name} của một người khác trong ảnh hơn là của người bạn đang gán.",
                })
            elif ratio > GROSS_OFFSET:
                findings.append({
                    "type": "truot_han",
                    "label": "Trượt hẳn",
                    "keypoint": name,
                    "detail": f"Lệch {distance:.0f} px = {ratio:.1f} lần bán kính dung sai của khớp này.",
                })
            else:
                findings.append({
                    "type": "lech_nhe",
                    "label": "Lệch nhẹ",
                    "keypoint": name,
                    "detail": f"Lệch {distance:.0f} px = {ratio:.1f} lần bán kính dung sai. Sửa được, ít hại.",
                })
        elif predicted_visibility != truth_visibility:
            findings.append({
                "type": "co_khac_gold",
                "label": "Cờ khác gold",
                "keypoint": name,
                "detail": f"Vị trí đúng nhưng bạn ghi v={predicted_visibility}, gold ghi v={truth_visibility}. "
                          "Không trừ điểm OKS - nhưng nếu lệch hàng loạt thì guideline chưa thống nhất.",
            })
    return findings


def evaluate(prediction_dir: Path, gold_dir: Path, image_dir: Path) -> dict:
    per_image: list[dict] = []
    all_scores: list[float] = []
    findings_by_type: dict[str, int] = {}
    missing_people = extra_people = 0
    gold_people = 0

    for image_path in image_paths(image_dir):
        gold_path = gold_dir / f"{image_path.stem}.txt"
        if not gold_path.exists():
            continue
        prediction_path = prediction_dir / f"{image_path.stem}.txt"
        truths = parse_yolo_pose_file(gold_path)
        predictions = parse_yolo_pose_file(prediction_path)
        gold_people += len(truths)
        width, height = image_size(image_path)
        matched, unmatched_predictions, unmatched_truths = greedy_match(predictions, truths, width, height)
        missing_people += len(unmatched_truths)
        extra_people += len(unmatched_predictions)

        image_report = {"image": image_path.name, "matches": [], "missing": len(unmatched_truths),
                        "extra": len(unmatched_predictions)}
        for prediction_index, truth_index, score in sorted(matched, key=lambda item: item[1]):
            all_scores.append(score)
            others = [truth for index, truth in enumerate(truths) if index != truth_index]
            findings = diagnose_pair(predictions[prediction_index], truths[truth_index], others, width, height)
            for finding in findings:
                findings_by_type[finding["type"]] = findings_by_type.get(finding["type"], 0) + 1
            image_report["matches"].append({
                "gold_person": truth_index + 1,
                "your_person": prediction_index + 1,
                "oks": round(score, 4),
                "findings": findings,
            })
        for truth_index in unmatched_truths:
            image_report["matches"].append({
                "gold_person": truth_index + 1, "your_person": None, "oks": 0.0,
                "findings": [{"type": "thieu_nguoi", "label": "Thiếu hẳn một người",
                              "detail": "Gold có skeleton này, bài của bạn không có."}],
            })
            findings_by_type["thieu_nguoi"] = findings_by_type.get("thieu_nguoi", 0) + 1
        for prediction_index in unmatched_predictions:
            findings_by_type["thua_nguoi"] = findings_by_type.get("thua_nguoi", 0) + 1
        per_image.append(image_report)

    matched_count = len(all_scores)
    denominator = gold_people + extra_people
    summary = {
        "gold_people": gold_people,
        "matched_people": matched_count,
        "missing_people": missing_people,
        "extra_people": extra_people,
        "mean_oks": round(sum(all_scores) / matched_count, 4) if matched_count else 0.0,
        "oks50": round(sum(1 for score in all_scores if score >= LOOSE_THRESHOLD) / denominator, 4) if denominator else 0.0,
        "oks75": round(sum(1 for score in all_scores if score >= STRICT_THRESHOLD) / denominator, 4) if denominator else 0.0,
        "findings": dict(sorted(findings_by_type.items(), key=lambda item: -item[1])),
    }
    return {"summary": summary, "per_image": per_image}


LEVELS = (
    ("Xuất sắc", 0.85, 0.85),
    ("Đạt", 0.75, 0.70),
    ("Cần rework", 0.0, 0.0),
)

FINDING_ORDER = [
    ("dao_trai_phai", "Đảo trái/phải - lỗi nguy hiểm nhất, sửa trước"),
    ("nham_nguoi", "Nhầm người - chấm rơi sang cơ thể bên cạnh"),
    ("thieu_nguoi", "Thiếu hẳn một người"),
    ("thua_nguoi", "Thừa một skeleton không có trong gold"),
    ("xoa_khop_bi_che", "Xoá khớp bị che (gold v=1, bạn v=0) - mất điểm thẳng"),
    ("thieu_khop", "Thiếu khớp gold nhìn thấy rõ (gold v=2, bạn v=0)"),
    ("truot_han", "Trượt hẳn - chấm vào chỗ không có khớp"),
    ("lech_nhe", "Lệch nhẹ - sửa được, ít hại"),
    ("co_khac_gold", "Cờ khác gold (vị trí vẫn đúng) - không trừ điểm OKS"),
    ("gold_khong_gan_nhan", "Gold để v=0 ở khớp bạn có gán - không trừ điểm"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Chấm nhãn pose với gold bằng OKS.")
    parser.add_argument("--pred", type=Path, default=Path("dataset/labels/train"))
    parser.add_argument("--gold", type=Path, default=Path("gold/labels/train"))
    parser.add_argument("--images", type=Path, default=Path("dataset/images/train"))
    parser.add_argument("--out", type=Path, default=Path("outputs/eval_vs_gold.json"))
    parser.add_argument("--top", type=int, default=8, help="in ra bao nhiêu skeleton tệ nhất")
    arguments = parser.parse_args()

    if not arguments.gold.exists():
        print(f"Chưa có gold ở {arguments.gold}. Protected release mở sau khi cả lớp khóa nhãn.")
        return 1
    try:
        result = evaluate(arguments.pred, arguments.gold, arguments.images)
    except LabelFormatError as error:
        print(f"KHÔNG ĐẠT - nhãn sai định dạng: {error}")
        print("Chạy tools/check_pose_labels.py trước khi chấm.")
        return 1

    summary = result["summary"]
    if summary["gold_people"] == 0:
        print("Không đọc được skeleton nào trong gold. Kiểm lại đường dẫn --gold.")
        return 1

    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    level = next(name for name, mean_gate, strict_gate in LEVELS
                 if summary["mean_oks"] >= mean_gate and summary["oks75"] >= strict_gate)
    print(f"OKS trung bình : {summary['mean_oks']:.3f}")
    print(f"OKS@0.50       : {summary['oks50']:.3f}  (tỉ lệ người gán đúng ở mức 'nhận ra pose')")
    print(f"OKS@0.75       : {summary['oks75']:.3f}  (tỉ lệ người gán đủ chính xác để train)")
    print(f"Người: gold {summary['gold_people']} | ghép được {summary['matched_people']} "
          f"| thiếu {summary['missing_people']} | thừa {summary['extra_people']}")
    print(f"Mức            : {level}")

    print("\nDanh sách lỗi theo loại:")
    for key, description in FINDING_ORDER:
        count = summary["findings"].get(key, 0)
        if count:
            print(f"- {count:4d}  {description}")

    def needs_rework(match: dict) -> bool:
        if match["oks"] < STRICT_THRESHOLD:
            return True
        return any(finding["type"] not in ("co_khac_gold", "gold_khong_gan_nhan", "lech_nhe")
                   for finding in match["findings"])

    worst = sorted(
        ((match["oks"], report["image"], match)
         for report in result["per_image"] for match in report["matches"] if needs_rework(match)),
        key=lambda item: item[0],
    )[: arguments.top]
    if not worst:
        print("\nKhông có skeleton nào cần rework: mọi người đều đạt OKS >= 0.75 và không có lỗi đã phân loại.")
    else:
        print(f"\n{len(worst)} skeleton cần sửa trước:")
        for score, image_name, match in worst:
            names = ", ".join(
                f"{finding['label']}"
                + (f"({finding['keypoint']})" if "keypoint" in finding else "")
                for finding in match["findings"]
                if finding["type"] not in ("co_khac_gold", "gold_khong_gan_nhan", "lech_nhe")
            ) or "chỉ lệch nhẹ"
            print(f"- {image_name} người #{match['gold_person']}: OKS {score:.3f} -> {names}")

    print(f"\nChi tiết từng khớp: {arguments.out}")
    print("Vẽ lại bằng tools/visualize_pose.py rồi sửa, sau đó chạy lại script này. Rework không bị trừ điểm.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
