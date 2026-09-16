"""Regression checks for the public Day 4 learner data contract."""

from __future__ import annotations

import html.parser
import json
import subprocess
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]


class LocalReferenceParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.references.append(value)


class PublicLearnerContractTest(unittest.TestCase):
    def test_core_route_has_train_and_read_only_test_sets(self) -> None:
        train_images = sorted((ROOT / "dataset/images/train").glob("*.jpg"))
        test_images = sorted((ROOT / "dataset/images/test").glob("*.jpg"))
        test_labels = sorted((ROOT / "dataset/labels/test").glob("*.txt"))
        train_labels = list((ROOT / "dataset/labels/train").glob("*.txt"))

        self.assertEqual(len(train_images), 20)
        self.assertEqual(len(test_images), 10)
        self.assertEqual(len(test_labels), 10)
        self.assertEqual(train_labels, [])
        self.assertFalse((ROOT / "data").exists())
        self.assertFalse((ROOT / "scripts").exists())
        self.assertTrue((ROOT / "assets/schema/coco17-cvat-skeleton.svg").is_file())
        self.assertTrue((ROOT / "assets/schema/coco17-keypoints.json").is_file())

    def test_entry_points_state_one_core_route_only(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guide = (ROOT / "GUIDE.md").read_text(encoding="utf-8")
        rubric = (ROOT / "RUBRIC.md").read_text(encoding="utf-8")
        html = (ROOT / "lab-guide.html").read_text(encoding="utf-8")
        annotations = (ROOT / "annotations/README.md").read_text(encoding="utf-8")
        checklist = (ROOT / "reports/REVIEWER_CHECKLIST.md").read_text(encoding="utf-8")
        learner_surfaces = "\n".join((readme, guide, rubric, html, annotations, checklist))

        self.assertIn("Core: 20 ảnh chưa nhãn", readme)
        self.assertIn("Test: 10 ảnh đã có nhãn", readme)
        self.assertIn("task core 20 ảnh", guide)
        self.assertIn('class="scope-map"', html)
        self.assertIn("20 ảnh core", html)
        self.assertIn("10 ảnh test", html)
        self.assertIn("8 artifact", html)
        self.assertNotIn("Task B", learner_surfaces)
        self.assertNotIn("face_hand", learner_surfaces)
        for prohibited in (
            "cabin",
            "data/images",
            "DATA_GOVERNANCE",
            "audit-data-pack",
            "GENERATION_RECORD",
            "image-manifest",
        ):
            self.assertNotIn(prohibited.lower(), learner_surfaces.lower())
        self.assertFalse((ROOT / "annotations/face_hand").exists())

    def test_local_html_references_resolve(self) -> None:
        parser = LocalReferenceParser()
        parser.feed((ROOT / "lab-guide.html").read_text(encoding="utf-8"))

        for reference in parser.references:
            parsed = urlparse(reference)
            if parsed.scheme or reference.startswith("#") or reference.startswith("data:"):
                continue
            self.assertTrue((ROOT / parsed.path).exists(), reference)

    def test_notebook_parses_and_test_set_validates(self) -> None:
        notebook = json.loads((ROOT / "notebooks/day4_pose_finetune_yolo26.ipynb").read_text(encoding="utf-8"))
        self.assertTrue(all(not cell.get("outputs") for cell in notebook["cells"] if cell["cell_type"] == "code"))
        source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
        self.assertIn('REPO_URL = ""', source)
        self.assertIn("subprocess.run(['git', 'clone', '--depth', '1'", source)
        self.assertNotIn("shutil.rmtree", source)
        self.assertNotIn("<>>>", source)
        result = subprocess.run(
            [
                sys.executable,
                "tools/check_pose_labels.py",
                "--images",
                "dataset/images/test",
                "--labels",
                "dataset/labels/test",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ĐẠT định dạng", result.stdout)


if __name__ == "__main__":
    unittest.main()
