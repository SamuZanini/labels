from dataclasses import dataclass
from typing import Literal

Point = tuple[float, float]
ShapeKind = Literal["box", "polygon"]


@dataclass
class Annotation:
    class_id: int
    kind: ShapeKind
    points: list[Point]

    def __post_init__(self) -> None:
        if self.class_id < 0:
            raise ValueError("class_id must be non-negative")
        minimum_points = 2 if self.kind == "box" else 3
        if len(self.points) < minimum_points:
            raise ValueError(f"{self.kind} requires at least {minimum_points} points")

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        xs = [point[0] for point in self.points]
        ys = [point[1] for point in self.points]
        return min(xs), min(ys), max(xs), max(ys)
