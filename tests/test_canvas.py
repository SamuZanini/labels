import unittest

from labeler.canvas import AnnotationCanvas


class PolygonSnappingTests(unittest.TestCase):
    def test_snaps_to_nearest_vertex_within_radius(self) -> None:
        clicked = (104.0, 103.0)
        vertices = [
            ((100.0, 100.0), (10.0, 10.0)),
            ((108.0, 103.0), (20.0, 20.0)),
        ]

        self.assertEqual(
            AnnotationCanvas._snap_to_vertex(clicked, vertices, radius=9.0),
            (20.0, 20.0),
        )

    def test_does_not_snap_outside_radius(self) -> None:
        clicked = (110.0, 100.0)
        vertices = [((100.0, 100.0), (10.0, 10.0))]

        self.assertIsNone(AnnotationCanvas._snap_to_vertex(clicked, vertices, radius=9.0))

    def test_empty_vertices_do_not_snap(self) -> None:
        self.assertIsNone(AnnotationCanvas._snap_to_vertex((100.0, 100.0), [], radius=9.0))


if __name__ == "__main__":
    unittest.main()
