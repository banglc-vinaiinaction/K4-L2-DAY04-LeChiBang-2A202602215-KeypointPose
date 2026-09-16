#!/usr/bin/env python3
"""Pre-labels remaining images in CVAT Job 5 using a Large Pose model (yolo11l-pose).

Auto-detects GPU (CUDA) availability and falls back to CPU if the driver is not loaded.
Applies:
  - Outside Truncation Filter (v=0) for boundary-truncated joints.
  - Clothed Hip Rule (v=1) for all hips.
  - State-aware confidence mapping (v=1 vs v=2).
Preserves existing verified skeletons on frames 0, 1, and 2.
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

TOKEN = "6edb69a3c8b7bd3465b5f4b51e0ae72fb417717f"
BASE_URL = "http://localhost:8080"
JOB_ID = 5

KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]

def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-label remaining CVAT frames with Large Pose model.")
    parser.add_argument("--model", type=str, default="yolo11l-pose.pt", help="Model weight path or name")
    parser.add_argument("--device", type=str, default="auto", help="Device: cuda:0, cpu, or auto")
    parser.add_argument("--conf", type=float, default=0.35, help="Confidence threshold for person detection")
    parser.add_argument("--iou", type=float, default=0.45, help="NMS IoU threshold to suppress duplicate boxes")
    arguments = parser.parse_args()

    try:
        import torch
        from ultralytics import YOLO
    except ImportError:
        print("ERROR: 'ultralytics' / 'torch' not found in environment.", file=sys.stderr)
        print("Run via: uv run --with ultralytics python3 tools/prelabel_pose.py", file=sys.stderr)
        return 1

    # Device selection
    if arguments.device == "auto":
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
    else:
        device = arguments.device

    if "cuda" in device and not torch.cuda.is_available():
        print("WARNING: CUDA requested but torch.cuda.is_available() is False.", file=sys.stderr)
        print("Falling back to CPU inference.", file=sys.stderr)
        device = "cpu"

    print(f"Loading model '{arguments.model}' on device: {device}...")
    model = YOLO(arguments.model)

    headers = {"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"}

    # 1. Fetch labels
    req_lbl = urllib.request.Request(f"{BASE_URL}/api/labels?job_id={JOB_ID}", headers={"Authorization": f"Token {TOKEN}"})
    with urllib.request.urlopen(req_lbl) as resp:
        lbl_data = json.loads(resp.read().decode("utf-8"))

    name_to_label_id = {}
    person_label_id = None
    for r in lbl_data["results"]:
        person_label_id = r["id"]
        for sub in r["sublabels"]:
            name_to_label_id[sub["name"]] = sub["id"]

    # 2. Fetch current annotations to preserve frames 0, 1, 2
    req_anno = urllib.request.Request(f"{BASE_URL}/api/jobs/{JOB_ID}/annotations", headers={"Authorization": f"Token {TOKEN}"})
    with urllib.request.urlopen(req_anno) as resp:
        current_data = json.loads(resp.read().decode("utf-8"))

    # Keep existing verified shapes from frames 0, 1, 2
    preserved_shapes = []
    for s in current_data.get("shapes", []):
        if s.get("type") == "skeleton" and s.get("frame", 0) in (0, 1, 2):
            preserved_shapes.append(s)

    print(f"Preserved {len(preserved_shapes)} existing verified skeletons on frames 0, 1, 2.")

    # 3. Fetch data meta to get frame list
    req_job = urllib.request.Request(f"{BASE_URL}/api/jobs/{JOB_ID}", headers={"Authorization": f"Token {TOKEN}"})
    with urllib.request.urlopen(req_job) as resp:
        job_info = json.loads(resp.read().decode("utf-8"))
    task_id = job_info["task_id"]

    req_meta = urllib.request.Request(f"{BASE_URL}/api/tasks/{task_id}/data/meta", headers={"Authorization": f"Token {TOKEN}"})
    with urllib.request.urlopen(req_meta) as resp:
        meta_data = json.loads(resp.read().decode("utf-8"))
    frames_meta = meta_data.get("frames", [])

    new_shapes = []

    # Process unannotated frames: 3 to 19
    for f_idx in range(3, len(frames_meta)):
        fname = frames_meta[f_idx]["name"]
        im_path = Path("dataset/images/train") / fname
        if not im_path.exists():
            print(f"Frame {f_idx}: image {fname} not found, skipping.")
            continue

        W = frames_meta[f_idx]["width"]
        H = frames_meta[f_idx]["height"]

        results = model.predict(source=str(im_path), conf=arguments.conf, iou=arguments.iou, device=device, verbose=False)
        result = results[0]

        if not result.keypoints or len(result.keypoints) == 0:
            print(f"Frame {f_idx:2d} ({fname}): 0 persons detected.")
            continue

        kpts_xy = result.keypoints.xy.cpu().numpy()
        kpts_conf = result.keypoints.conf.cpu().numpy() if result.keypoints.conf is not None else None
        boxes = result.boxes.xyxy.cpu().numpy() if result.boxes is not None else []

        num_persons = len(kpts_xy)
        print(f"Frame {f_idx:2d} ({fname}): detected {num_persons} persons.")

        l_sh_idx = KEYPOINT_NAMES.index("left_shoulder")
        r_sh_idx = KEYPOINT_NAMES.index("right_shoulder")

        for p_idx in range(num_persons):
            elements = []
            pts = kpts_xy[p_idx]
            confs = kpts_conf[p_idx] if kpts_conf is not None else [1.0] * len(KEYPOINT_NAMES)
            box = boxes[p_idx] if len(boxes) > p_idx else [0, 0, W, H]
            box_touches_border = (box[0] <= 6.0 or box[1] <= 6.0 or box[2] >= (W - 6.0) or box[3] >= (H - 6.0))

            # Check if person is facing away (back to camera: left shoulder is to viewer's left of right shoulder)
            facing_away = (
                confs[l_sh_idx] > 0.4 and confs[r_sh_idx] > 0.4 and
                (pts[l_sh_idx][0] < pts[r_sh_idx][0] - 10.0)
            )

            for k_idx, kname in enumerate(KEYPOINT_NAMES):
                x, y = float(pts[k_idx][0]), float(pts[k_idx][1])
                c = float(confs[k_idx])

                clamped_x = max(0.0, min(float(W), x))
                clamped_y = max(0.0, min(float(H), y))

                # Boundary Truncation Rule (v=0):
                is_outside = False
                if x < 0.0 or x > W or y < 0.0 or y > H:
                    is_outside = True
                elif (clamped_x <= 6.0 or clamped_x >= (W - 6.0) or clamped_y <= 6.0 or clamped_y >= (H - 6.0)):
                    is_outside = True
                elif facing_away and kname in ("nose", "left_eye", "right_eye") and c < 0.35:
                    # Back turned to camera: facial features have no evidence from behind
                    is_outside = True
                elif c < 0.08:
                    # Completely zero visual evidence (< 8% confidence)
                    is_outside = True

                if is_outside:
                    is_occluded = True
                else:
                    # Inside image bounds: retain joint on CVAT canvas
                    # Clothed Hip Rule (v=1) or low confidence / obscured joint:
                    if "hip" in kname or c < 0.50:
                        is_occluded = True
                    else:
                        is_occluded = False

                lid = name_to_label_id[kname]
                elements.append({
                    "label_id": lid,
                    "type": "points",
                    "frame": f_idx,
                    "group": 0,
                    "source": "auto",
                    "occluded": is_occluded,
                    "outside": is_outside,
                    "points": [round(clamped_x, 2), round(clamped_y, 2)],
                    "attributes": []
                })

            new_shapes.append({
                "label_id": person_label_id,
                "type": "skeleton",
                "frame": f_idx,
                "group": 0,
                "source": "auto",
                "occluded": False,
                "outside": False,
                "points": [],
                "attributes": [],
                "elements": elements
            })

    # Combine preserved and new shapes
    all_shapes = []
    # Strip IDs for PUT
    for s in preserved_shapes + new_shapes:
        s_copy = dict(s)
        s_copy.pop("id", None)
        s_copy["elements"] = [dict(el) for el in s["elements"]]
        for el in s_copy["elements"]:
            el.pop("id", None)
        all_shapes.append(s_copy)

    payload = {
        "version": 0,
        "tags": [],
        "shapes": all_shapes,
        "tracks": [],
        "intervals": []
    }

    print(f"\nUploading {len(all_shapes)} total skeletons to CVAT Job 5...")
    put_req = urllib.request.Request(
        f"{BASE_URL}/api/jobs/{JOB_ID}/annotations",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="PUT"
    )

    with urllib.request.urlopen(put_req) as resp:
        print(f"Successfully uploaded to CVAT! HTTP {resp.status}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
