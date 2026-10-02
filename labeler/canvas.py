import tkinter as tk
from collections.abc import Callable

from PIL import Image, ImageTk

from .models import Annotation, Point


class AnnotationCanvas(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        on_create: Callable[[Annotation], None],
        on_select: Callable[[int | None], None],
        on_change: Callable[[], None],
        on_zoom: Callable[[float], None],
    ) -> None:
        super().__init__(master, background="#1c2728", highlightthickness=0, cursor="crosshair")
        self.on_create = on_create
        self.on_select = on_select
        self.on_change = on_change
        self.on_zoom = on_zoom
        self.image: Image.Image | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.annotations: list[Annotation] = []
        self.selected_index: int | None = None
        self.tool = "select"
        self.class_id = 0
        self.fit_scale = 1.0
        self.zoom = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self._ready = False
        self._start: Point | None = None
        self._draft: list[Point] = []
        self._drag: tuple[str, int | None, Point, list[Point]] | None = None
        self._pan_start: tuple[float, float, float, float] | None = None

        self.bind("<Configure>", self._on_configure)
        self.bind("<Button-1>", self._on_left_down)
        self.bind("<B1-Motion>", self._on_left_drag)
        self.bind("<ButtonRelease-1>", self._on_left_up)
        self.bind("<Motion>", self._on_motion)
        self.bind("<ButtonPress-2>", self._on_pan_start)
        self.bind("<B2-Motion>", self._on_pan_drag)
        self.bind("<ButtonRelease-2>", self._on_pan_end)
        self.bind("<MouseWheel>", self._on_mousewheel)
        self.bind("<Button-4>", lambda event: self.zoom_at(1.15, event.x, event.y))
        self.bind("<Button-5>", lambda event: self.zoom_at(1 / 1.15, event.x, event.y))
        self.bind("<Return>", lambda _event: self.finish_polygon())
        self.bind("<Escape>", lambda _event: self.cancel_drawing())
        self.bind("<Button-3>", self._undo_polygon_point)

    @property
    def scale(self) -> float:
        return self.fit_scale * self.zoom

    def set_image(self, image: Image.Image | None, annotations: list[Annotation]) -> None:
        self.image = image
        self.annotations = annotations
        self.selected_index = None
        self._ready = False
        self._start = None
        self._draft.clear()
        self.zoom = 1.0
        self.after_idle(self._fit_image)

    def set_tool(self, tool: str) -> None:
        if self.tool == "polygon" and tool != "polygon":
            self._draft.clear()
        self.tool = tool
        self.configure(cursor="fleur" if tool == "select" else "crosshair")
        self.redraw()

    def set_class_id(self, class_id: int) -> None:
        self.class_id = class_id

    def zoom_at(self, factor: float, x: float, y: float) -> None:
        if self.image is None:
            return
        image_x = (x - self.offset_x) / self.scale
        image_y = (y - self.offset_y) / self.scale
        self.zoom = min(8.0, max(0.2, self.zoom * factor))
        self.offset_x = x - image_x * self.scale
        self.offset_y = y - image_y * self.scale
        self.on_zoom(self.zoom)
        self.redraw()

    def fit_image(self) -> None:
        self._fit_image()

    def finish_polygon(self) -> None:
        if len(self._draft) < 3:
            return
        annotation = Annotation(self.class_id, "polygon", self._draft.copy())
        self._draft.clear()
        self.on_create(annotation)

    def cancel_drawing(self) -> None:
        self._start = None
        self._draft.clear()
        self._drag = None
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        if self.image is None or self.winfo_width() < 2 or self.winfo_height() < 2:
            return

        viewport = (max(1, self.winfo_width()), max(1, self.winfo_height()))
        inverse_scale = 1 / self.scale
        transformed = self.image.transform(
            viewport,
            Image.Transform.AFFINE,
            (
                inverse_scale,
                0,
                -self.offset_x * inverse_scale,
                0,
                inverse_scale,
                -self.offset_y * inverse_scale,
            ),
            resample=Image.Resampling.BILINEAR,
            fillcolor="#1c2728",
        )
        self.photo = ImageTk.PhotoImage(transformed)
        self.create_image(0, 0, image=self.photo, anchor="nw")

        for index, annotation in enumerate(self.annotations):
            points = self._display_points(annotation)
            coords = [coordinate for point in points for coordinate in point]
            selected = index == self.selected_index
            color = "#f3c969" if selected else "#69d6bd"
            if annotation.kind == "box":
                self.create_polygon(*coords, fill="", outline=color, width=2)
            else:
                self.create_polygon(*coords, fill="", outline=color, width=2)
            if selected:
                for x, y in points:
                    self.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#f3c969", outline="#152021")
            label_x, label_y = points[0]
            self.create_text(
                label_x + 4,
                label_y - 8,
                text=str(annotation.class_id),
                fill=color,
                anchor="sw",
                font=("Segoe UI", 9, "bold"),
            )

        if self._start is not None and self.tool == "box":
            start = self._to_canvas(self._start)
            end = self._last_pointer
            self.create_rectangle(*start, *end, outline="#f3c969", width=2, dash=(5, 3))
        if self._draft:
            draft_points = [self._to_canvas(point) for point in self._draft]
            coords = [coordinate for point in draft_points for coordinate in point]
            if len(coords) >= 4:
                self.create_line(*coords, *self._last_pointer, fill="#f3c969", width=2, dash=(5, 3))
            for x, y in draft_points:
                self.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#f3c969", outline="")

    @property
    def _last_pointer(self) -> tuple[float, float]:
        return getattr(self, "_pointer", (0.0, 0.0))

    def _on_configure(self, _event: tk.Event) -> None:
        if self.image is not None and not self._ready:
            self._fit_image()
        else:
            self.redraw()

    def _fit_image(self) -> None:
        if self.image is None or self.winfo_width() < 2 or self.winfo_height() < 2:
            return
        margin = 32
        self.fit_scale = min(
            max(1, self.winfo_width() - margin) / self.image.width,
            max(1, self.winfo_height() - margin) / self.image.height,
        )
        self.zoom = 1.0
        self.offset_x = (self.winfo_width() - self.image.width * self.scale) / 2
        self.offset_y = (self.winfo_height() - self.image.height * self.scale) / 2
        self._ready = True
        self.on_zoom(self.zoom)
        self.redraw()

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.zoom_at(1.15 if event.delta > 0 else 1 / 1.15, event.x, event.y)

    def _on_pan_start(self, event: tk.Event) -> None:
        self._pan_start = (event.x, event.y, self.offset_x, self.offset_y)
        self.configure(cursor="fleur")

    def _on_pan_drag(self, event: tk.Event) -> None:
        if self._pan_start is None:
            return
        start_x, start_y, offset_x, offset_y = self._pan_start
        self.offset_x = offset_x + event.x - start_x
        self.offset_y = offset_y + event.y - start_y
        self.redraw()

    def _on_pan_end(self, _event: tk.Event) -> None:
        self._pan_start = None
        self.configure(cursor="crosshair" if self.tool != "select" else "fleur")

    def _on_left_down(self, event: tk.Event) -> None:
        self.focus_set()
        self._pointer = (event.x, event.y)
        if self.image is None:
            return
        point = self._to_image(event.x, event.y)
        if self.tool == "box":
            self._start = point
            self.redraw()
        elif self.tool == "polygon":
            self._draft.append(point)
            self.redraw()
        else:
            self._begin_selection_drag(event.x, event.y, point)

    def _on_left_drag(self, event: tk.Event) -> None:
        self._pointer = (event.x, event.y)
        if self._start is not None and self.tool == "box":
            self.redraw()
            return
        if self._drag is None:
            return
        drag_kind, handle_index, start_point, original_points = self._drag
        current = self._to_image(event.x, event.y)
        if drag_kind == "move":
            dx, dy = current[0] - start_point[0], current[1] - start_point[1]
            bounds = self.annotations[self.selected_index].bounds
            if self.image is not None:
                dx = min(max(dx, -bounds[0]), self.image.width - bounds[2])
                dy = min(max(dy, -bounds[1]), self.image.height - bounds[3])
            updated = [(x + dx, y + dy) for x, y in original_points]
        elif drag_kind == "resize":
            updated = self._resize_box(original_points, int(handle_index), current)
        else:
            updated = original_points.copy()
            updated[int(handle_index)] = current
        self.annotations[self.selected_index] = Annotation(
            self.annotations[self.selected_index].class_id,
            self.annotations[self.selected_index].kind,
            updated,
        )
        self.redraw()

    def _on_left_up(self, event: tk.Event) -> None:
        if self._start is not None and self.tool == "box":
            end = self._to_image(event.x, event.y)
            start = self._start
            self._start = None
            if abs(end[0] - start[0]) >= 2 and abs(end[1] - start[1]) >= 2:
                self.on_create(Annotation(self.class_id, "box", [start, end]))
            else:
                self.redraw()
        elif self._drag is not None:
            self._drag = None
            self.on_change()

    def _on_motion(self, event: tk.Event) -> None:
        self._pointer = (event.x, event.y)
        if self._start is not None or self._draft:
            self.redraw()

    def _begin_selection_drag(self, x: float, y: float, point: Point) -> None:
        if self.selected_index is not None:
            annotation = self.annotations[self.selected_index]
            handles = self._display_points(annotation)
            for index, (handle_x, handle_y) in enumerate(handles):
                if (handle_x - x) ** 2 + (handle_y - y) ** 2 <= 9**2:
                    if annotation.kind == "box":
                        self._drag = ("resize", index, point, annotation.points.copy())
                        return
                    self._drag = ("vertex", index, point, annotation.points.copy())
                    return

        hit = self._hit_test(x, y)
        self.selected_index = hit
        self.on_select(hit)
        if hit is not None:
            annotation = self.annotations[hit]
            self._drag = ("move", None, point, annotation.points.copy())
        self.redraw()

    def _hit_test(self, x: float, y: float) -> int | None:
        for index in range(len(self.annotations) - 1, -1, -1):
            points = self._display_points(self.annotations[index])
            if self._inside_polygon((x, y), points):
                return index
            if any(self._distance_to_segment((x, y), points[i], points[(i + 1) % len(points)]) <= 7 for i in range(len(points))):
                return index
        return None

    def _display_points(self, annotation: Annotation) -> list[tuple[float, float]]:
        points = annotation.points
        if annotation.kind == "box":
            left, top, right, bottom = annotation.bounds
            points = [(left, top), (right, top), (right, bottom), (left, bottom)]
        return [self._to_canvas(point) for point in points]

    def _to_canvas(self, point: Point) -> tuple[float, float]:
        return self.offset_x + point[0] * self.scale, self.offset_y + point[1] * self.scale

    def _to_image(self, x: float, y: float) -> Point:
        if self.image is None:
            return 0.0, 0.0
        image_x = (x - self.offset_x) / self.scale
        image_y = (y - self.offset_y) / self.scale
        return (
            min(max(image_x, 0.0), float(self.image.width)),
            min(max(image_y, 0.0), float(self.image.height)),
        )

    @staticmethod
    def _resize_box(points: list[Point], handle_index: int, current: Point) -> list[Point]:
        left = min(points[0][0], points[1][0])
        top = min(points[0][1], points[1][1])
        right = max(points[0][0], points[1][0])
        bottom = max(points[0][1], points[1][1])
        corners = [(left, top), (right, top), (right, bottom), (left, bottom)]
        opposite = corners[(handle_index + 2) % 4]
        return [
            (min(current[0], opposite[0]), min(current[1], opposite[1])),
            (max(current[0], opposite[0]), max(current[1], opposite[1])),
        ]

    @staticmethod
    def _inside_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
        inside = False
        x, y = point
        previous = polygon[-1]
        for current in polygon:
            x1, y1 = current
            x2, y2 = previous
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
            previous = current
        return inside

    @staticmethod
    def _distance_to_segment(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
        dx, dy = end[0] - start[0], end[1] - start[1]
        length_squared = dx * dx + dy * dy
        if length_squared == 0:
            return ((point[0] - start[0]) ** 2 + (point[1] - start[1]) ** 2) ** 0.5
        fraction = max(0, min(1, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared))
        projected = (start[0] + fraction * dx, start[1] + fraction * dy)
        return ((point[0] - projected[0]) ** 2 + (point[1] - projected[1]) ** 2) ** 0.5

    def _undo_polygon_point(self, _event: tk.Event) -> None:
        if self.tool == "polygon" and self._draft:
            self._draft.pop()
            self.redraw()

