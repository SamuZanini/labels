import tempfile
import unittest
from pathlib import Path

from labeler.models import Annotation
from labeler.yolo import load_annotations, save_annotations


class YoloFormatTests(unittest.TestCase):
    def test_box_and_polygon_round_trip(self) -> None:
        annotations = [
            Annotation(2, "box", [(20, 10), (80, 90)]),
            Annotation(1, "polygon", [(10, 15), (50, 20), (40, 70)]),
        ]
        with tempfile.TemporaryDirectory() as directory:
            label_path = Path(directory) / "sample.txt"
            save_annotations(label_path, annotations, 100, 100)
            loaded = load_annotations(label_path, 100, 100)

        self.assertEqual([item.kind for item in loaded], ["box", "polygon"])
        self.assertEqual([item.class_id for item in loaded], [2, 1])
        for expected, actual in zip(annotations, loaded):
            for expected_point, actual_point in zip(expected.points, actual.points):
                for expected_value, actual_value in zip(expected_point, actual_point):
                    self.assertAlmostEqual(expected_value, actual_value, places=4)

    def test_missing_label_file_is_empty(self) -> None:
        self.assertEqual(load_annotations(Path("missing.txt"), 100, 80), [])


if __name__ == "__main__":
    unittest.main()
