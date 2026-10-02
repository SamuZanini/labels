from pathlib import Path

from .models import Annotation


def load_annotations(path: Path, image_width: int, image_height: int) -> list[Annotation]:
    annotations: list[Annotation] = []
    if not path.exists():
        return annotations

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        values = line.split()
        if not values:
            continue
        try:
            class_id = int(values[0])
            coordinates = [float(value) for value in values[1:]]
        except ValueError as error:
            raise ValueError(f"Invalid YOLO label at {path.name}:{line_number}") from error

        if class_id < 0 or any(value < 0 or value > 1 for value in coordinates):
            raise ValueError(f"Out-of-range YOLO label at {path.name}:{line_number}")
        if len(coordinates) == 4:
            center_x, center_y, width, height = coordinates
            left = (center_x - width / 2) * image_width
            top = (center_y - height / 2) * image_height
            right = (center_x + width / 2) * image_width
            bottom = (center_y + height / 2) * image_height
            annotations.append(
                Annotation(class_id, "box", [(left, top), (right, bottom)])
            )
        elif len(coordinates) >= 6 and len(coordinates) % 2 == 0:
            points = [
                (coordinates[index] * image_width, coordinates[index + 1] * image_height)
                for index in range(0, len(coordinates), 2)
            ]
            annotations.append(Annotation(class_id, "polygon", points))
        else:
            raise ValueError(f"Invalid coordinate count at {path.name}:{line_number}")

    return annotations


def save_annotations(path: Path, annotations: list[Annotation], image_width: int, image_height: int) -> None:
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Image dimensions must be positive")

    lines: list[str] = []
    for annotation in annotations:
        if annotation.kind == "box":
            left, top, right, bottom = annotation.bounds
            values = [
                (left + right) / 2 / image_width,
                (top + bottom) / 2 / image_height,
                (right - left) / image_width,
                (bottom - top) / image_height,
            ]
        else:
            values = [
                coordinate / image_width if index % 2 == 0 else coordinate / image_height
                for point in annotation.points
                for index, coordinate in enumerate(point)
            ]
        lines.append(f"{annotation.class_id} " + " ".join(f"{value:.6f}" for value in values))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
