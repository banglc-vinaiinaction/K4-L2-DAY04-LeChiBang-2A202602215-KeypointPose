#!/usr/bin/env python3
"""Comprehensive skeleton verification script for COCO 17-keypoint annotations.

Performs static rule-based, perspective, biomechanical, occlusion, and
boundary-truncation audits without requiring gold ground truth.

Supports:
  1. Direct CVAT API inspection:
     python3 tools/verify_skeleton_annotations.py --cvat-url http://localhost:8080/tasks/7/jobs/5 --token <token>
  2. CVAT COCO Keypoints JSON export:
     python3 tools/verify_skeleton_annotations.py --coco annotations/coco_keypoints.json --images dataset/images/train
  3. YOLO Pose labels directory:
     python3 tools/verify_skeleton_annotations.py --labels dataset/labels/train --images dataset/images/train
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]
NUM_KEYPOINTS = len(KEYPOINT_NAMES)
INDEX_OF = {name: i for i, name in enumerate(KEYPOINT_NAMES)}

# Visibility flags
OUTSIDE = 0    # v=0: outside image frame (no point placed)
OCCLUDED = 1   # v=1: occluded inside frame (point placed at estimate)
VISIBLE = 2    # v=2: directly visible inside frame

SEVERITY_FATAL = "FATAL"      # Model training failure / completely wrong
SEVERITY_ERROR = "ERROR"      # Guideline violation / incorrect annotation
SEVERITY_WARNING = "WARNING"  # Anatomical / edge anomaly requiring review


@dataclass
class Keypoint:
    name: str
    index: int
    x: float  # Normalized [0, 1]
    y: float  # Normalized [0, 1]
    visibility: int  # 0, 1, 2
    raw_x: float = 0.0
    raw_y: float = 0.0


@dataclass
class SkeletonInstance:
    id: str | int
    frame_name: str
    frame_index: int
    image_width: int
    image_height: int
    keypoints: list[Keypoint]
    bbox: tuple[float, float, float, float]  # cx, cy, w, h (normalized)


@dataclass
class Issue:
    severity: str
    category: str
    message: str
    keypoint: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationScores:
    topology_valid: bool
    visibility_state_valid: bool
    geometry_valid: bool
    topology_score: float
    visibility_score: float
    geometry_score: float
    topology_issues: list[Issue] = field(default_factory=list)
    visibility_issues: list[Issue] = field(default_factory=list)
    geometry_issues: list[Issue] = field(default_factory=list)


class PoseVerifier:
    def __init__(self, edge_margin_px: float = 3.0):
        self.edge_margin_px = edge_margin_px

    def verify_skeleton(self, skel: SkeletonInstance) -> tuple[ValidationScores, list[Issue]]:
        kps = {kp.name: kp for kp in skel.keypoints}
        W, H = skel.image_width, skel.image_height

        # 1. Topology checks
        topology_issues = self._check_topology(skel, kps)

        # 2. Visibility & Outside/Occlusion checks
        visibility_issues = []
        visibility_issues.extend(self._check_outside_boundaries(skel, kps, W, H))
        visibility_issues.extend(self._check_occlusion_rules(skel, kps, W, H))

        # 3. Geometric & Perspective checks (state-aware: outside excluded, occluded relaxed)
        geometry_issues = []
        geometry_issues.extend(self._check_perspective(skel, kps, W, H))
        geometry_issues.extend(self._check_biomechanics(skel, kps, W, H))

        all_issues = topology_issues + visibility_issues + geometry_issues

        # Compute dimension validity
        top_errors = [i for i in topology_issues if i.severity in (SEVERITY_FATAL, SEVERITY_ERROR)]
        vis_errors = [i for i in visibility_issues if i.severity in (SEVERITY_FATAL, SEVERITY_ERROR)]
        geom_errors = [i for i in geometry_issues if i.severity in (SEVERITY_FATAL, SEVERITY_ERROR)]

        scores = ValidationScores(
            topology_valid=len(top_errors) == 0,
            visibility_state_valid=len(vis_errors) == 0,
            geometry_valid=len(geom_errors) == 0,
            topology_score=max(0.0, 1.0 - len(top_errors) * 0.5),
            visibility_score=max(0.0, 1.0 - len(vis_errors) * 0.25 - len(visibility_issues) * 0.1),
            geometry_score=max(0.0, 1.0 - len(geom_errors) * 0.3 - len(geometry_issues) * 0.1),
            topology_issues=topology_issues,
            visibility_issues=visibility_issues,
            geometry_issues=geometry_issues,
        )

        return scores, all_issues

    def _check_topology(self, skel: SkeletonInstance, kps: dict[str, Keypoint]) -> list[Issue]:
        issues = []
        # COCO 17 completeness
        if len(skel.keypoints) != NUM_KEYPOINTS:
            issues.append(Issue(
                severity=SEVERITY_FATAL,
                category="Topology Incomplete",
                message=f"Skeleton has {len(skel.keypoints)} keypoints, required exactly {NUM_KEYPOINTS} COCO points."
            ))

        missing = [name for name in KEYPOINT_NAMES if name not in kps]
        if missing:
            issues.append(Issue(
                severity=SEVERITY_FATAL,
                category="Missing Graph Nodes",
                message=f"Nodes missing from skeleton graph: {', '.join(missing)}. Outside nodes must exist with v=0."
            ))
        return issues

    def _check_perspective(self, skel: SkeletonInstance, kps: dict[str, Keypoint], W: int, H: int) -> list[Issue]:
        issues = []
        nose = kps.get("nose")
        l_eye = kps.get("left_eye")
        r_eye = kps.get("right_eye")
        l_ear = kps.get("left_ear")
        r_ear = kps.get("right_ear")
        l_sh = kps.get("left_shoulder")
        r_sh = kps.get("right_shoulder")
        l_hip = kps.get("left_hip")
        r_hip = kps.get("right_hip")

        # Check facial geometry for facing-camera orientation
        # In viewer perspective: X increases from left to right.
        # An anatomical person facing camera has:
        #   Their RIGHT is on viewer's LEFT (smaller X)
        #   Their LEFT is on viewer's RIGHT (larger X)
        # If annotator annotated from viewer's perspective:
        #   left_eye.x < right_eye.x
        #   left_shoulder.x < right_shoulder.x
        # Determine dorsal (back-facing) orientation:
        # If left_shoulder is to the viewer's left of right_shoulder (l_sh.x < r_sh.x)
        # and ears or face confirm dorsal view (left_ear is to viewer's left, or face obscured),
        # the subject is facing AWAY from the camera. In dorsal view, left side = viewer's left.
        is_dorsal = False
        if l_sh and r_sh and l_sh.visibility > OUTSIDE and r_sh.visibility > OUTSIDE:
            if l_sh.x < r_sh.x - 0.02:
                if (l_ear and r_ear and l_ear.visibility > OUTSIDE and r_ear.visibility > OUTSIDE and l_ear.x < r_ear.x) or \
                   (nose is None or nose.visibility == OUTSIDE) or \
                   (l_eye is None or l_eye.visibility == OUTSIDE):
                    is_dorsal = True

        if not is_dorsal:
            # Check facial geometry for facing-camera orientation
            if l_eye and r_eye and nose and l_eye.visibility > OUTSIDE and r_eye.visibility > OUTSIDE and nose.visibility > OUTSIDE:
                min_eye_x = min(l_eye.x, r_eye.x)
                max_eye_x = max(l_eye.x, r_eye.x)
                eye_span = max_eye_x - min_eye_x

                if eye_span > 0.005 and (min_eye_x - 0.05 * eye_span <= nose.x <= max_eye_x + 0.05 * eye_span):
                    # Face is facing frontally.
                    # Anatomically: right_eye must have smaller X than left_eye (right_eye is to viewer's left).
                    if l_eye.x < r_eye.x:
                        issues.append(Issue(
                            severity=SEVERITY_FATAL,
                            category="Perspective Inversion",
                            message=(
                                "SYSTEMATIC LEFT-RIGHT INVERSION DETECTED: Face is facing forward, "
                                f"but left_eye (x={l_eye.raw_x:.1f}) is to the viewer's left of right_eye (x={r_eye.raw_x:.1f}). "
                                "Per COCO guideline, left/right is anatomical (person's left = viewer's right)."
                            ),
                            keypoint="left_eye / right_eye",
                            details={"left_eye_x": l_eye.raw_x, "right_eye_x": r_eye.raw_x}
                        ))

            # Check Ears relative to Eyes if visible
            if l_ear and r_ear and l_eye and r_eye and all(k.visibility > OUTSIDE for k in [l_ear, r_ear, l_eye, r_eye]):
                if l_ear.x < l_eye.x and r_eye.x < r_ear.x:
                    issues.append(Issue(
                        severity=SEVERITY_FATAL,
                        category="Perspective Inversion",
                        message=(
                            "Viewer-perspective ears/eyes ordering: left_ear < left_eye < right_eye < right_ear. "
                            "The entire head is annotated from viewer's perspective instead of anatomical perspective."
                        ),
                        keypoint="ears / eyes"
                    ))

            # Check Shoulders
            if l_sh and r_sh and l_sh.visibility > OUTSIDE and r_sh.visibility > OUTSIDE:
                sh_span = abs(l_sh.x - r_sh.x)
                if sh_span > 0.03:
                    if l_eye and r_eye and l_eye.visibility > OUTSIDE and r_eye.visibility > OUTSIDE:
                        if (l_sh.x < r_sh.x) and (l_eye.x < r_eye.x):
                            issues.append(Issue(
                                severity=SEVERITY_FATAL,
                                category="Perspective Inversion",
                                message=(
                                    f"Shoulders are inverted (left_shoulder x={l_sh.raw_x:.1f} < right_shoulder x={r_sh.raw_x:.1f}). "
                                    "Both torso and face are laterally flipped from viewer's perspective."
                                ),
                                keypoint="left_shoulder / right_shoulder"
                            ))

        # Check Hips
        if l_hip and r_hip and l_hip.visibility > OUTSIDE and r_hip.visibility > OUTSIDE:
            hip_span = abs(l_hip.x - r_hip.x)
            if hip_span > 0.02 and l_sh and r_sh and l_sh.visibility > OUTSIDE and r_sh.visibility > OUTSIDE:
                sh_dir = l_sh.x - r_sh.x
                hip_dir = l_hip.x - r_hip.x
                if sh_dir * hip_dir < 0:
                    issues.append(Issue(
                        severity=SEVERITY_ERROR,
                        category="Laterality Conflict",
                        message=(
                            "Torso twist / lateral conflict: shoulders and hips have opposing lateral directions "
                            f"(left_sh - right_sh = {sh_dir:.3f}, left_hip - right_hip = {hip_dir:.3f})."
                        ),
                        keypoint="hips / shoulders"
                    ))

        return issues

    def _check_outside_boundaries(self, skel: SkeletonInstance, kps: dict[str, Keypoint], W: int, H: int) -> list[Issue]:
        issues = []
        margin_x = self.edge_margin_px / max(W, 1)
        margin_y = self.edge_margin_px / max(H, 1)

        # 1. Edge-clamping detection: Keypoint marked visible or occluded (v>0) but touching extreme frame edge
        for name, kp in kps.items():
            if kp.visibility == OUTSIDE:
                continue

            # Bottom edge cutoff (most common: ankles/feet)
            if kp.y >= 1.0 - margin_y:
                issues.append(Issue(
                    severity=SEVERITY_ERROR,
                    category="Edge Clamping (Should be Outside)",
                    message=(
                        f"{name} placed at frame bottom (y={kp.raw_y:.1f}/{H}, within {self.edge_margin_px}px of border) "
                        f"with visibility={kp.visibility}. If the limb extends beyond the frame boundary, it must be "
                        "marked Outside (v=0 / 'o' in CVAT) with NO point placed."
                    ),
                    keypoint=name,
                    details={"y": kp.raw_y, "H": H, "visibility": kp.visibility}
                ))
            elif kp.y <= margin_y:
                issues.append(Issue(
                    severity=SEVERITY_ERROR,
                    category="Edge Clamping (Should be Outside)",
                    message=(
                        f"{name} placed at top frame border (y={kp.raw_y:.1f}/{H}) with visibility={kp.visibility}. "
                        "If truncated by top boundary, mark Outside (v=0)."
                    ),
                    keypoint=name
                ))

            if kp.x <= margin_x or kp.x >= 1.0 - margin_x:
                issues.append(Issue(
                    severity=SEVERITY_WARNING,
                    category="Edge Clamping (Should be Outside)",
                    message=(
                        f"{name} placed at side frame border (x={kp.raw_x:.1f}/{W}) with visibility={kp.visibility}. "
                        "Verify if the joint is truncated outside the image edge."
                    ),
                    keypoint=name
                ))

        # 2. Centered subject with joints falsely set to Outside (v=0)
        # If the person's bbox has comfortable distance from all borders, v=0 is likely a misclassified occluded joint.
        cx, cy, bw, bh = skel.bbox
        is_far_from_edges = (
            (cx - bw / 2) > 0.05 and (cx + bw / 2) < 0.95 and
            (cy - bh / 2) > 0.05 and (cy + bh / 2) < 0.95
        )
        touches_border = any(
            (kp.raw_x <= 10.0 or kp.raw_x >= (W - 10.0) or kp.raw_y <= 10.0 or kp.raw_y >= (H - 10.0))
            for kp in kps.values() if (kp.raw_x > 0 or kp.raw_y > 0)
        )
        if touches_border:
            is_far_from_edges = False

        l_sh = kps.get("left_shoulder")
        r_sh = kps.get("right_shoulder")
        is_dorsal = False
        if l_sh and r_sh and l_sh.visibility > OUTSIDE and r_sh.visibility > OUTSIDE:
            if l_sh.raw_x < r_sh.raw_x - 10:
                is_dorsal = True

        outside_kps = [k for k, v in kps.items() if v.visibility == OUTSIDE]
        if is_dorsal:
            # Back-facing person cannot see facial points from behind
            outside_kps = [k for k in outside_kps if k not in ("nose", "left_eye", "right_eye")]

        if is_far_from_edges and len(outside_kps) >= 3:
            issues.append(Issue(
                severity=SEVERITY_WARNING,
                category="Spurious Outside (Should be Occluded)",
                message=(
                    f"Subject is comfortably inside image bounds, but has {len(outside_kps)} joints marked Outside: "
                    f"{', '.join(outside_kps)}. If joints are obscured by body/clothing/objects inside frame, "
                    "they must be marked Occluded (v=1 / 'q'), NEVER Outside (v=0)."
                ),
                keypoint=", ".join(outside_kps)
            ))

        return issues

    def _check_occlusion_rules(self, skel: SkeletonInstance, kps: dict[str, Keypoint], W: int, H: int) -> list[Issue]:
        issues = []

        # Guideline Rule: Hips on clothed subjects cannot be directly visible.
        for hip_name in ("left_hip", "right_hip"):
            hip = kps.get(hip_name)
            if hip and hip.visibility == VISIBLE:
                issues.append(Issue(
                    severity=SEVERITY_WARNING,
                    category="Guideline Occlusion Violation",
                    message=(
                        f"{hip_name} is marked directly VISIBLE (v=2). Per project guideline (GUIDELINE_MINI.md), "
                        "hip joints cannot be seen directly through clothing/aprons; they are anatomical estimates "
                        "and must be flagged Occluded (v=1 / 'q' in CVAT)."
                    ),
                    keypoint=hip_name
                ))

        # Guideline Rule: 17/17 all visible on complex scene
        visible_count = sum(1 for kp in kps.values() if kp.visibility == VISIBLE)
        if visible_count == NUM_KEYPOINTS:
            issues.append(Issue(
                severity=SEVERITY_WARNING,
                category="Suspicious 100% Visibility",
                message=(
                    "All 17 keypoints are marked directly VISIBLE (v=2). "
                    "Ensure hips, ears covered by hair/hat, and partially hidden joints are properly flagged Occluded (v=1)."
                )
            ))

        return issues

    def _check_biomechanics(self, skel: SkeletonInstance, kps: dict[str, Keypoint], W: int, H: int) -> list[Issue]:
        issues = []

        # Torso reference scale (neck/shoulder to hip distance in pixels)
        l_sh = kps.get("left_shoulder")
        r_sh = kps.get("right_shoulder")
        l_hip = kps.get("left_hip")
        r_hip = kps.get("right_hip")

        torso_height_px = 0.0
        if l_sh and l_hip and l_sh.visibility > OUTSIDE and l_hip.visibility > OUTSIDE:
            torso_height_px = math.hypot((l_sh.raw_x - l_hip.raw_x), (l_sh.raw_y - l_hip.raw_y))
        elif r_sh and r_hip and r_sh.visibility > OUTSIDE and r_hip.visibility > OUTSIDE:
            torso_height_px = math.hypot((r_sh.raw_x - r_hip.raw_x), (r_sh.raw_y - r_hip.raw_y))

        if torso_height_px <= 1.0:
            torso_height_px = max(skel.bbox[3] * H * 0.4, 20.0)

        # 1. Collapsed limbs / Zero-length bones (e.g. elbow dumped on wrist)
        limbs = [
            ("left_shoulder", "left_elbow", "left upper arm"),
            ("left_elbow", "left_wrist", "left forearm"),
            ("right_shoulder", "right_elbow", "right upper arm"),
            ("right_elbow", "right_wrist", "right forearm"),
            ("left_hip", "left_knee", "left thigh"),
            ("left_knee", "left_ankle", "left shank"),
            ("right_hip", "right_knee", "right thigh"),
            ("right_knee", "right_ankle", "right shank"),
        ]

        for p1_name, p2_name, limb_desc in limbs:
            kp1 = kps.get(p1_name)
            kp2 = kps.get(p2_name)
            if not kp1 or not kp2 or kp1.visibility == OUTSIDE or kp2.visibility == OUTSIDE:
                continue

            dist_px = math.hypot(kp1.raw_x - kp2.raw_x, kp1.raw_y - kp2.raw_y)
            # Bone length less than 4% of torso height or < 8 pixels is anatomically impossible for full body
            if dist_px < max(8.0, 0.05 * torso_height_px):
                issues.append(Issue(
                    severity=SEVERITY_ERROR,
                    category="Collapsed Limb / Zero-length Bone",
                    message=(
                        f"Collapsed {limb_desc}: distance between {p1_name} and {p2_name} is only {dist_px:.1f}px "
                        f"({dist_px/torso_height_px*100:.1f}% of torso scale). Keypoints appear coincident or stacked."
                    ),
                    keypoint=f"{p1_name} / {p2_name}",
                    details={"distance_px": dist_px, "torso_height_px": torso_height_px}
                ))

        # 2. Forearm crossing over torso unnaturally
        # If right wrist crosses past left hip/shoulder or vice-versa
        l_w = kps.get("left_wrist")
        r_w = kps.get("right_wrist")
        l_e = kps.get("left_elbow")
        r_e = kps.get("right_elbow")

        if l_e and l_w and l_sh and r_sh and all(k.visibility > OUTSIDE for k in [l_e, l_w, l_sh, r_sh]):
            min_sh_x = min(l_sh.raw_x, r_sh.raw_x)
            max_sh_x = max(l_sh.raw_x, r_sh.raw_x)
            sh_width = max_sh_x - min_sh_x
            torso_scale = torso_height_px if torso_height_px > 10 else 100.0
            is_profile = (sh_width < 0.35 * torso_scale)
            forearm_span = abs(l_w.raw_x - l_e.raw_x)
            if not is_profile and sh_width > 15:
                # Check for unnatural cross-body reaching in frontal view
                if forearm_span > 1.8 * sh_width:
                    issues.append(Issue(
                        severity=SEVERITY_WARNING,
                        category="Unnatural Limb Span",
                        message=(
                            f"Left forearm horizontal stretch ({forearm_span:.1f}px) is > 1.8x shoulder width ({sh_width:.1f}px). "
                            "Verify if wrist was accidentally swapped or assigned to wrong person."
                        ),
                        keypoint="left_wrist"
                    ))
            elif is_profile:
                # In side profile view, shoulder width is foreshortened; check against torso height
                if forearm_span > 0.85 * torso_scale:
                    issues.append(Issue(
                        severity=SEVERITY_WARNING,
                        category="Unnatural Limb Span",
                        message=(
                            f"Left forearm horizontal stretch ({forearm_span:.1f}px) is > 0.85x torso scale ({torso_scale:.1f}px). "
                            "Verify if wrist was accidentally swapped or assigned to wrong person."
                        ),
                        keypoint="left_wrist"
                    ))

        return issues


def parse_cvat_job_annotations(cvat_url: str, token: str, job_id: int) -> list[SkeletonInstance]:
    """Fetches job metadata and annotations directly from running CVAT server API."""
    base_url = cvat_url.rstrip("/")
    # Check if cvat_url is full job URL e.g. http://localhost:8080/tasks/7/jobs/5
    m = re.search(r"jobs/(\d+)", cvat_url)
    if m:
        job_id = int(m.group(1))
        # Find host base
        parsed = urllib.parse.urlparse(cvat_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

    headers = {"Authorization": f"Token {token}"}

    # 1. Fetch labels
    labels_req = urllib.request.Request(f"{base_url}/api/labels?job_id={job_id}", headers=headers)
    with urllib.request.urlopen(labels_req) as resp:
        labels_data = json.loads(resp.read().decode("utf-8"))

    label_map: dict[int, str] = {}
    for result in labels_data.get("results", []):
        for sub in result.get("sublabels", []):
            label_map[sub["id"]] = sub["name"]

    # 2. Fetch data meta (frames and dimensions)
    # First get job details to know task_id
    job_req = urllib.request.Request(f"{base_url}/api/jobs/{job_id}", headers=headers)
    with urllib.request.urlopen(job_req) as resp:
        job_info = json.loads(resp.read().decode("utf-8"))
    task_id = job_info["task_id"]

    meta_req = urllib.request.Request(f"{base_url}/api/tasks/{task_id}/data/meta", headers=headers)
    with urllib.request.urlopen(meta_req) as resp:
        meta_data = json.loads(resp.read().decode("utf-8"))

    frame_meta = meta_data.get("frames", [])

    # 3. Fetch annotations
    anno_req = urllib.request.Request(f"{base_url}/api/jobs/{job_id}/annotations", headers=headers)
    with urllib.request.urlopen(anno_req) as resp:
        anno_data = json.loads(resp.read().decode("utf-8"))

    instances: list[SkeletonInstance] = []
    shapes = anno_data.get("shapes", [])

    for shape in shapes:
        if shape.get("type") != "skeleton":
            continue
        frame_idx = shape.get("frame", 0)
        f_meta = frame_meta[frame_idx] if frame_idx < len(frame_meta) else {}
        W = f_meta.get("width", 640)
        H = f_meta.get("height", 480)
        frame_name = f_meta.get("name", f"frame_{frame_idx:04d}.jpg")

        elements = shape.get("elements", [])
        elem_by_name: dict[str, dict[str, Any]] = {}
        for el in elements:
            lname = label_map.get(el["label_id"])
            if lname:
                elem_by_name[lname] = el

        keypoints: list[Keypoint] = []
        xs, ys = [], []
        for idx, name in enumerate(KEYPOINT_NAMES):
            el = elem_by_name.get(name)
            if not el:
                vis = OUTSIDE
                raw_x, raw_y = 0.0, 0.0
                norm_x, norm_y = 0.0, 0.0
            elif el.get("outside", False):
                vis = OUTSIDE
                raw_x = float(el["points"][0]) if el.get("points") else 0.0
                raw_y = float(el["points"][1]) if el.get("points") else 0.0
                norm_x = raw_x / W
                norm_y = raw_y / H
            else:
                vis = OCCLUDED if el.get("occluded", False) else VISIBLE
                raw_x, raw_y = float(el["points"][0]), float(el["points"][1])
                norm_x = raw_x / W
                norm_y = raw_y / H
                xs.append(norm_x)
                ys.append(norm_y)

            keypoints.append(Keypoint(
                name=name,
                index=idx,
                x=norm_x,
                y=norm_y,
                visibility=vis,
                raw_x=raw_x,
                raw_y=raw_y
            ))

        if xs and ys:
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            bbox = ((min_x + max_x) / 2, (min_y + max_y) / 2, max_x - min_x, max_y - min_y)
        else:
            bbox = (0.5, 0.5, 0.1, 0.1)

        instances.append(SkeletonInstance(
            id=shape.get("id", len(instances)),
            frame_name=frame_name,
            frame_index=frame_idx,
            image_width=W,
            image_height=H,
            keypoints=keypoints,
            bbox=bbox
        ))

    return instances


def parse_coco_json(coco_path: Path, images_dir: Optional[Path]) -> list[SkeletonInstance]:
    """Parses CVAT COCO Keypoints 1.0 export JSON."""
    with open(coco_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    images_info = {img["id"]: img for img in data.get("images", [])}
    instances = []

    for anno in data.get("annotations", []):
        img_id = anno.get("image_id")
        img_info = images_info.get(img_id, {})
        W = img_info.get("width", 640)
        H = img_info.get("height", 480)
        fname = img_info.get("file_name", f"img_{img_id}.jpg")

        raw_kps = anno.get("keypoints", [])
        if len(raw_kps) != NUM_KEYPOINTS * 3:
            continue

        keypoints = []
        xs, ys = [], []
        for idx in range(NUM_KEYPOINTS):
            x, y, v = raw_kps[idx * 3: (idx + 1) * 3]
            name = KEYPOINT_NAMES[idx]
            vis = int(v)
            norm_x = x / W if W else 0.0
            norm_y = y / H if H else 0.0
            if vis > OUTSIDE:
                xs.append(norm_x)
                ys.append(norm_y)
            keypoints.append(Keypoint(
                name=name,
                index=idx,
                x=norm_x,
                y=norm_y,
                visibility=vis,
                raw_x=x,
                raw_y=y
            ))

        bbox_raw = anno.get("bbox", [0, 0, 10, 10])
        cx = (bbox_raw[0] + bbox_raw[2] / 2) / W
        cy = (bbox_raw[1] + bbox_raw[3] / 2) / H
        bw = bbox_raw[2] / W
        bh = bbox_raw[3] / H

        instances.append(SkeletonInstance(
            id=anno.get("id", len(instances)),
            frame_name=fname,
            frame_index=img_id,
            image_width=W,
            image_height=H,
            keypoints=keypoints,
            bbox=(cx, cy, bw, bh)
        ))

    return instances


def parse_yolo_labels(labels_dir: Path, images_dir: Path) -> list[SkeletonInstance]:
    """Parses Ultralytics YOLO pose label txt files."""
    instances = []
    for txt_file in sorted(labels_dir.glob("*.txt")):
        stem = txt_file.stem
        # find matching image
        img_path = None
        for ext in (".jpg", ".jpeg", ".png"):
            candidate = images_dir / f"{stem}{ext}"
            if candidate.exists():
                img_path = candidate
                break

        W, H = 640, 480
        if img_path and HAS_PIL:
            with Image.open(img_path) as im:
                W, H = im.size

        lines = txt_file.read_text(encoding="utf-8").splitlines()
        for l_idx, line in enumerate(lines):
            parts = line.strip().split()
            if len(parts) != 5 + 3 * NUM_KEYPOINTS:
                continue
            vals = [float(p) for p in parts]
            cx, cy, bw, bh = vals[1:5]
            keypoints = []
            for k_idx in range(NUM_KEYPOINTS):
                kx = vals[5 + k_idx * 3]
                ky = vals[6 + k_idx * 3]
                kv = int(vals[7 + k_idx * 3])
                name = KEYPOINT_NAMES[k_idx]
                keypoints.append(Keypoint(
                    name=name,
                    index=k_idx,
                    x=kx,
                    y=ky,
                    visibility=kv,
                    raw_x=kx * W,
                    raw_y=ky * H
                ))
            instances.append(SkeletonInstance(
                id=f"{stem}_{l_idx}",
                frame_name=img_path.name if img_path else f"{stem}.jpg",
                frame_index=0,
                image_width=W,
                image_height=H,
                keypoints=keypoints,
                bbox=(cx, cy, bw, bh)
            ))
    return instances


def render_verification_image(
    skel: SkeletonInstance,
    issues: list[Issue],
    image_dir: Optional[Path],
    output_dir: Path
):
    """Draws skeleton on image with color-coded keypoints and issue callouts."""
    if not HAS_PIL:
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    img_path = None
    if image_dir:
        for ext in (".jpg", ".jpeg", ".png"):
            p = image_dir / skel.frame_name
            if p.exists():
                img_path = p
                break
            p = image_dir / f"{Path(skel.frame_name).stem}{ext}"
            if p.exists():
                img_path = p
                break

    if img_path:
        img = Image.open(img_path).convert("RGB")
    else:
        img = Image.new("RGB", (skel.image_width, skel.image_height), color=(30, 30, 30))

    draw = ImageDraw.Draw(img)
    W, H = img.size

    # Pairs
    SKELETON_PAIRS = [
        ("nose", "left_eye"), ("nose", "right_eye"),
        ("left_eye", "left_ear"), ("right_eye", "right_ear"),
        ("left_shoulder", "right_shoulder"),
        ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
        ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
        ("left_shoulder", "left_hip"), ("right_shoulder", "right_hip"),
        ("left_hip", "right_hip"),
        ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
        ("right_hip", "right_knee"), ("right_knee", "right_ankle")
    ]

    kps = {kp.name: kp for kp in skel.keypoints}

    # Draw bones
    for p1, p2 in SKELETON_PAIRS:
        kp1 = kps.get(p1)
        kp2 = kps.get(p2)
        if kp1 and kp2 and kp1.visibility > OUTSIDE and kp2.visibility > OUTSIDE:
            color = (255, 215, 0) if (kp1.visibility == OCCLUDED or kp2.visibility == OCCLUDED) else (
                (64, 160, 255) if "left" in p2 else (255, 128, 64)
            )
            draw.line([(kp1.raw_x, kp1.raw_y), (kp2.raw_x, kp2.raw_y)], fill=color, width=2)

    # Draw joints
    issue_kps = set()
    for iss in issues:
        if iss.keypoint:
            for k in iss.keypoint.split("/"):
                issue_kps.add(k.strip())

    for kp in skel.keypoints:
        if kp.visibility == OUTSIDE:
            continue
        r = 5 if kp.name in issue_kps else 3
        outline = (255, 0, 0) if kp.name in issue_kps else (0, 0, 0)
        fill = (255, 215, 0) if kp.visibility == OCCLUDED else (
            (64, 160, 255) if "left" in kp.name else ((255, 128, 64) if "right" in kp.name else (230, 230, 230))
        )
        draw.ellipse([kp.raw_x - r, kp.raw_y - r, kp.raw_x + r, kp.raw_y + r], fill=fill, outline=outline, width=2)

    out_file = output_dir / f"audit_{Path(skel.frame_name).stem}_skel_{skel.id}.jpg"
    img.save(out_file, quality=90)


def print_audit_report(results: list[tuple[SkeletonInstance, ValidationScores, list[Issue]]], out_md: Optional[Path] = None):
    total_skeletons = len(results)
    fatal_count = 0
    error_count = 0
    warning_count = 0

    top_pass = sum(1 for _, s, _ in results if s.topology_valid)
    vis_pass = sum(1 for _, s, _ in results if s.visibility_state_valid)
    geom_pass = sum(1 for _, s, _ in results if s.geometry_valid)

    lines = []
    lines.append("# SKELETON ANNOTATION AUDIT REPORT")
    lines.append(f"Total Skeletons Audited: {total_skeletons}\n")
    lines.append("## Three-Tier Verification Checklist Summary:")
    lines.append(f"- `topology_valid`        : {top_pass}/{total_skeletons} ({top_pass/total_skeletons*100:.1f}%) " + ("✅ PASS" if top_pass == total_skeletons else "❌ FAIL"))
    lines.append(f"- `visibility_state_valid`: {vis_pass}/{total_skeletons} ({vis_pass/total_skeletons*100:.1f}%) " + ("✅ PASS" if vis_pass == total_skeletons else "❌ FAIL"))
    lines.append(f"- `geometry_valid`        : {geom_pass}/{total_skeletons} ({geom_pass/total_skeletons*100:.1f}%) " + ("✅ PASS" if geom_pass == total_skeletons else "❌ FAIL"))
    lines.append("")

    for skel, scores, issues in results:
        fatals = [i for i in issues if i.severity == SEVERITY_FATAL]
        errors = [i for i in issues if i.severity == SEVERITY_ERROR]
        warnings = [i for i in issues if i.severity == SEVERITY_WARNING]

        fatal_count += len(fatals)
        error_count += len(errors)
        warning_count += len(warnings)

        status = "FAIL (FATAL)" if fatals else ("FAIL" if errors else ("REVIEW" if warnings else "PASS"))
        banner = f"[{status}] Frame: {skel.frame_name} | Skeleton ID: {skel.id} (Res: {skel.image_width}x{skel.image_height})"
        lines.append(banner)
        lines.append("-" * len(banner))

        # 3 Validation Dimension Checklist for this Skeleton
        top_icon = "PASS" if scores.topology_valid else "FAIL"
        vis_icon = "PASS" if scores.visibility_state_valid else "FAIL"
        geom_icon = "PASS" if scores.geometry_valid else "FAIL"
        lines.append(f"  [CHECKLIST] topology_valid: {top_icon} | visibility_state_valid: {vis_icon} | geometry_valid: {geom_icon}")

        # Visibility breakdown
        v2 = sum(1 for k in skel.keypoints if k.visibility == VISIBLE)
        v1 = sum(1 for k in skel.keypoints if k.visibility == OCCLUDED)
        v0 = sum(1 for k in skel.keypoints if k.visibility == OUTSIDE)
        lines.append(f"  Keypoints: Visible(v=2): {v2} | Occluded(v=1): {v1} | Outside(v=0): {v0}")

        if not issues:
            lines.append("  No issues detected. Skeleton compliant.\n")
            continue

        for iss in issues:
            badge = f"[{iss.severity}]"
            lines.append(f"  {badge:9s} {iss.category}: {iss.message}")
        lines.append("")

    summary_banner = (
        f"\n=======================================================\n"
        f"AUDIT SUMMARY: {total_skeletons} skeletons audited\n"
        f"  - topology_valid        : {'PASS' if top_pass == total_skeletons else 'FAIL'} ({top_pass}/{total_skeletons})\n"
        f"  - visibility_state_valid: {'PASS' if vis_pass == total_skeletons else 'FAIL'} ({vis_pass}/{total_skeletons})\n"
        f"  - geometry_valid        : {'PASS' if geom_pass == total_skeletons else 'FAIL'} ({geom_pass}/{total_skeletons})\n"
        f"  - Total FATAL Issues   : {fatal_count}\n"
        f"  - Total ERROR Issues   : {error_count}\n"
        f"  - Total WARNING Issues : {warning_count}\n"
        f"  - OVERALL QUALITY STATUS: {'FAIL' if (fatal_count > 0 or error_count > 0) else ('REVIEW' if warning_count > 0 else 'PASS')}\n"
        f"======================================================="
    )
    lines.append(summary_banner)
    report_text = "\n".join(lines)
    print(report_text)

    if out_md:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(report_text, encoding="utf-8")
        print(f"\nSaved report to {out_md}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit skeleton pose annotations for perspective, occlusion, and outside truncation.")
    parser.add_argument("--cvat-url", type=str, help="CVAT job or task URL (e.g. http://localhost:8080/tasks/7/jobs/5)")
    parser.add_argument("--job-id", type=int, default=5, help="CVAT Job ID")
    parser.add_argument("--token", type=str, default="6edb69a3c8b7bd3465b5f4b51e0ae72fb417717f", help="CVAT API Token")
    parser.add_argument("--coco", type=Path, help="Path to exported COCO Keypoints JSON file")
    parser.add_argument("--labels", type=Path, help="Path to YOLO pose labels directory")
    parser.add_argument("--images", type=Path, default=Path("dataset/images/train"), help="Images directory")
    parser.add_argument("--out-dir", type=Path, default=Path("outputs/audit"), help="Output directory for visual debugging")
    parser.add_argument("--report", type=Path, default=Path("reports/skeleton_verification_report.md"), help="Path to save markdown report")
    parser.add_argument("--visualize", action="store_true", default=True, help="Generate visual debugging artifacts")
    arguments = parser.parse_args()

    instances: list[SkeletonInstance] = []

    if arguments.cvat_url:
        print(f"Connecting to CVAT: {arguments.cvat_url}...")
        try:
            instances = parse_cvat_job_annotations(arguments.cvat_url, arguments.token, arguments.job_id)
        except Exception as e:
            print(f"Error fetching CVAT annotations: {e}", file=sys.stderr)
            return 1
    elif arguments.coco:
        print(f"Reading COCO JSON: {arguments.coco}...")
        instances = parse_coco_json(arguments.coco, arguments.images)
    elif arguments.labels:
        print(f"Reading YOLO labels from: {arguments.labels}...")
        instances = parse_yolo_labels(arguments.labels, arguments.images)
    else:
        # Default fallback to CVAT local default
        default_url = "http://localhost:8080/tasks/7/jobs/5"
        print(f"No source specified, defaulting to CVAT job: {default_url}...")
        try:
            instances = parse_cvat_job_annotations(default_url, arguments.token, arguments.job_id)
        except Exception as e:
            print(f"Failed connecting to CVAT at {default_url}: {e}", file=sys.stderr)
            return 1

    if not instances:
        print("No skeleton instances found to audit.")
        return 0

    verifier = PoseVerifier()
    audit_results = []

    for skel in instances:
        scores, issues = verifier.verify_skeleton(skel)
        audit_results.append((skel, scores, issues))
        if arguments.visualize:
            render_verification_image(skel, issues, arguments.images, arguments.out_dir)

    print_audit_report(audit_results, arguments.report)

    has_failures = any(
        any(i.severity in (SEVERITY_FATAL, SEVERITY_ERROR) for i in issues)
        for _, _, issues in audit_results
    )
    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
