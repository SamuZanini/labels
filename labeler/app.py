import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageOps

from .canvas import AnnotationCanvas
from .images import list_images
from .models import Annotation
from .yolo import load_annotations, save_annotations


class LabelingApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Label Studio | YOLO")
        self.root.geometry("1380x860")
        self.root.minsize(980, 620)
        self.root.configure(background="#edf1ec")
        self.folder: Path | None = None
        self.image_paths: list[Path] = []
        self.current_index = -1
        self.current_image: Image.Image | None = None
        self.annotations: list[Annotation] = []
        self.classes: list[str] = []
        self.current_class_id = 0
        self.tool = "select"
        self._build_ui()
        self.root.bind("<Control-s>", lambda _event: self.save_current())
        self.root.bind("<Left>", lambda _event: self.select_image(self.current_index - 1))
        self.root.bind("<Right>", lambda _event: self.select_image(self.current_index + 1))
        self.root.bind("<Delete>", lambda _event: self.delete_selected())

    def _build_ui(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background="#edf1ec")
        style.configure("Panel.TFrame", background="#f8faf7")
        style.configure("TLabel", background="#edf1ec", foreground="#233437", font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background="#f8faf7", foreground="#233437", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 12, "bold"), foreground="#18383a")
        style.configure("TButton", padding=(9, 6), font=("Segoe UI", 9))
        style.configure("Accent.TButton", background="#176c62", foreground="white")
        style.map("Accent.TButton", background=[("active", "#10584f")])
        style.configure("TCombobox", padding=5)

        toolbar = ttk.Frame(self.root, padding=(12, 10))
        toolbar.pack(side="top", fill="x")
        ttk.Button(toolbar, text="Abrir pasta", command=self.open_folder, style="Accent.TButton").pack(side="left")
        ttk.Button(toolbar, text="Salvar", command=self.save_current).pack(side="left", padx=(8, 14))
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=2)

        self.tool_buttons: dict[str, ttk.Button] = {}
        for tool, label in (("select", "Selecionar"), ("box", "Retângulo"), ("polygon", "Polígono")):
            button = ttk.Button(toolbar, text=label, command=lambda value=tool: self.set_tool(value))
            button.pack(side="left", padx=3)
            self.tool_buttons[tool] = button
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(toolbar, text="−", width=3, command=lambda: self.zoom(1 / 1.2)).pack(side="left")
        ttk.Button(toolbar, text="Ajustar", command=self.canvas_fit).pack(side="left", padx=4)
        ttk.Button(toolbar, text="+", width=3, command=lambda: self.zoom(1.2)).pack(side="left")
        ttk.Button(toolbar, text="Excluir label", command=self.delete_selected).pack(side="right")

        workspace = ttk.Frame(self.root, padding=(12, 0, 12, 10))
        workspace.pack(fill="both", expand=True)
        workspace.columnconfigure(1, weight=1)
        workspace.rowconfigure(0, weight=1)

        left = ttk.Frame(workspace, style="Panel.TFrame", padding=10, width=210)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.grid_propagate(False)
        ttk.Label(left, text="IMAGENS", style="Panel.TLabel", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(2, 8))
        image_list_frame = ttk.Frame(left, style="Panel.TFrame")
        image_list_frame.pack(fill="both", expand=True)
        self.image_list = tk.Listbox(
            image_list_frame,
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
            selectbackground="#d3e8df",
            selectforeground="#143f39",
            font=("Segoe UI", 9),
        )
        image_scroll = ttk.Scrollbar(image_list_frame, orient="vertical", command=self.image_list.yview)
        self.image_list.configure(yscrollcommand=image_scroll.set)
        self.image_list.pack(side="left", fill="both", expand=True)
        image_scroll.pack(side="right", fill="y")
        self.image_list.bind("<<ListboxSelect>>", self._on_image_selected)
        nav = ttk.Frame(left, style="Panel.TFrame")
        nav.pack(fill="x", pady=(8, 0))
        ttk.Button(nav, text="← Anterior", command=lambda: self.select_image(self.current_index - 1)).pack(side="left", expand=True, fill="x", padx=(0, 3))
        ttk.Button(nav, text="Próxima →", command=lambda: self.select_image(self.current_index + 1)).pack(side="left", expand=True, fill="x", padx=(3, 0))

        self.canvas = AnnotationCanvas(
            workspace,
            self._on_create_annotation,
            self._on_select_annotation,
            self._on_canvas_change,
            self._on_zoom_changed,
            self._request_class,
        )
        self.canvas.grid(row=0, column=1, sticky="nsew")

        right = ttk.Frame(workspace, style="Panel.TFrame", padding=12, width=250)
        right.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        right.grid_propagate(False)
        ttk.Label(right, text="CLASSE PARA NOVOS LABELS", style="Panel.TLabel", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(2, 8))
        self.class_combo = ttk.Combobox(right, state="readonly", values=[])
        self.class_combo.pack(fill="x")
        self.class_combo.bind("<<ComboboxSelected>>", self._on_class_selected)
        add_class_row = ttk.Frame(right, style="Panel.TFrame")
        add_class_row.pack(fill="x", pady=(7, 16))
        self.new_class_entry = ttk.Entry(add_class_row)
        self.new_class_entry.pack(side="left", fill="x", expand=True)
        self.new_class_entry.bind("<Return>", lambda _event: self.add_class())
        ttk.Button(add_class_row, text="+", width=3, command=self.add_class).pack(side="left", padx=(5, 0))
        ttk.Button(
            right,
            text="Alterar classe do label selecionado",
            command=self.change_selected_class,
        ).pack(fill="x", pady=(0, 16))
        ttk.Button(
            right,
            text="Renomear classe selecionada",
            command=self.rename_selected_class,
        ).pack(fill="x", pady=(0, 16))

        ttk.Separator(right).pack(fill="x", pady=(0, 12))
        ttk.Label(right, text="ANOTAÇÕES", style="Panel.TLabel", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 8))
        self.annotation_list = tk.Listbox(
            right,
            height=12,
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
            selectbackground="#d3e8df",
            selectforeground="#143f39",
            font=("Segoe UI", 9),
        )
        self.annotation_list.pack(fill="both", expand=True)
        self.annotation_list.bind("<<ListboxSelect>>", self._on_annotation_list_selected)
        ttk.Label(
            right,
            text="Polígono: clique nos vértices e pressione Enter para fechar.\nArraste o meio do mouse para mover a imagem.",
            style="Panel.TLabel",
            wraplength=215,
            justify="left",
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(12, 2))

        self.status = tk.StringVar(value="Abra uma pasta para começar")
        status_bar = ttk.Label(self.root, textvariable=self.status, anchor="w", padding=(14, 7), relief="sunken")
        status_bar.pack(side="bottom", fill="x")
        self._update_tool_buttons()

    def open_folder(self) -> None:
        selected = filedialog.askdirectory(title="Selecione a pasta de imagens")
        if not selected:
            return
        self.save_current()
        self.folder = Path(selected)
        self.image_paths = list_images(self.folder)
        self.current_index = -1
        self._load_classes()
        self.image_list.delete(0, tk.END)
        for path in self.image_paths:
            self.image_list.insert(tk.END, path.name)
        if not self.image_paths:
            self.current_image = None
            self.annotations = []
            self.canvas.set_image(None, self.annotations)
            self._refresh_annotations()
            self.status.set("Nenhuma imagem encontrada nesta pasta")
            return
        self.select_image(0)

    def select_image(self, index: int) -> None:
        if not 0 <= index < len(self.image_paths) or index == self.current_index:
            return
        self.save_current()
        path = self.image_paths[index]
        try:
            with Image.open(path) as source:
                self.current_image = ImageOps.exif_transpose(source).convert("RGB")
            self.annotations = load_annotations(self._label_path(path), self.current_image.width, self.current_image.height)
        except (OSError, ValueError) as error:
            messagebox.showerror("Não foi possível abrir", f"{path.name}\n\n{error}", parent=self.root)
            return
        self.current_index = index
        self.canvas.set_image(self.current_image, self.annotations)
        self.image_list.selection_clear(0, tk.END)
        self.image_list.selection_set(index)
        self.image_list.activate(index)
        self.image_list.see(index)
        self._refresh_annotations()
        self._update_status()

    def save_current(self) -> None:
        if self.current_image is None or self.current_index < 0:
            return
        try:
            save_annotations(
                self._label_path(self.image_paths[self.current_index]),
                self.annotations,
                self.current_image.width,
                self.current_image.height,
            )
        except OSError as error:
            messagebox.showerror("Erro ao salvar", str(error), parent=self.root)

    def add_class(self) -> None:
        name = self.new_class_entry.get().strip()
        if not self._add_class_name(name):
            return
        self.new_class_entry.delete(0, tk.END)

    def _add_class_name(self, name: str) -> bool:
        if not name or name in self.classes:
            return False
        self.classes.append(name)
        self._save_classes()
        self._refresh_class_combo(len(self.classes) - 1)
        return True

    def _request_class(self) -> bool:
        if self.classes:
            return True

        dialog = tk.Toplevel(self.root)
        dialog.title("Criar classe")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()

        content = ttk.Frame(dialog, padding=14)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Crie uma classe para iniciar a marcação:").pack(anchor="w", pady=(0, 8))
        name_entry = ttk.Entry(content, width=32)
        name_entry.pack(fill="x")
        error = tk.StringVar()
        ttk.Label(content, textvariable=error, foreground="#a12622").pack(anchor="w", pady=(4, 0))

        created = False

        def confirm() -> None:
            nonlocal created
            if not self._add_class_name(name_entry.get().strip()):
                error.set("Informe um nome de classe válido.")
                name_entry.focus_set()
                return
            created = True
            dialog.destroy()

        buttons = ttk.Frame(content)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Cancelar", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Criar", command=confirm).pack(side="right", padx=(0, 6))
        dialog.bind("<Return>", lambda _event: confirm())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        name_entry.focus_set()
        dialog.wait_window()
        return created

    def delete_selected(self) -> None:
        index = self.canvas.selected_index
        if index is None or not 0 <= index < len(self.annotations):
            return
        del self.annotations[index]
        self.canvas.selected_index = None
        self._refresh_annotations()
        self.save_current()
        self.canvas.redraw()

    def change_selected_class(self) -> None:
        index = self.canvas.selected_index
        class_id = self.class_combo.current()
        if index is None or not 0 <= index < len(self.annotations):
            self.status.set("Selecione um label para alterar sua classe")
            return
        if not 0 <= class_id < len(self.classes):
            self.status.set("Selecione uma classe válida")
            return

        self.annotations[index].class_id = class_id
        self._refresh_annotations()
        self.canvas.redraw()
        self.save_current()

    def rename_selected_class(self) -> None:
        class_id = self.class_combo.current()
        if not 0 <= class_id < len(self.classes):
            self.status.set("Selecione uma classe para renomear")
            return

        name = simpledialog.askstring(
            "Renomear classe",
            "Novo nome da classe:",
            initialvalue=self.classes[class_id],
            parent=self.root,
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            messagebox.showerror("Nome inválido", "O nome da classe não pode ficar vazio.", parent=self.root)
            return
        if name in self.classes and name != self.classes[class_id]:
            messagebox.showerror("Nome já utilizado", "Já existe uma classe com esse nome.", parent=self.root)
            return

        self.classes[class_id] = name
        self._save_classes()
        self._refresh_class_combo(class_id)
        self._refresh_annotations()
        self.canvas.redraw()

    def set_tool(self, tool: str) -> None:
        self.tool = tool
        self.canvas.set_tool(tool)
        self._update_tool_buttons()

    def zoom(self, factor: float) -> None:
        self.canvas.zoom_at(factor, self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2)

    def canvas_fit(self) -> None:
        self.canvas.fit_image()

    def _on_create_annotation(self, annotation: Annotation) -> None:
        self.annotations.append(annotation)
        self.canvas.selected_index = len(self.annotations) - 1
        self._refresh_annotations()
        self._update_status()
        self.save_current()
        self.canvas.redraw()

    def _on_select_annotation(self, index: int | None) -> None:
        self.canvas.selected_index = index
        self._refresh_annotations()

    def _on_canvas_change(self) -> None:
        self._refresh_annotations()
        self._update_status()
        self.save_current()

    def _on_zoom_changed(self, zoom: float) -> None:
        self._update_status(zoom)

    def _on_image_selected(self, _event: tk.Event) -> None:
        selected = self.image_list.curselection()
        if selected:
            self.select_image(selected[0])

    def _on_class_selected(self, _event: tk.Event) -> None:
        selected = self.class_combo.current()
        if selected >= 0:
            self.current_class_id = selected
            self.canvas.set_class_id(selected)

    def _on_annotation_list_selected(self, _event: tk.Event) -> None:
        selected = self.annotation_list.curselection()
        if not selected:
            return
        self.canvas.selected_index = selected[0]
        self.canvas.redraw()

    def _refresh_annotations(self) -> None:
        self.annotation_list.delete(0, tk.END)
        for index, annotation in enumerate(self.annotations):
            class_name = self.classes[annotation.class_id] if annotation.class_id < len(self.classes) else f"classe {annotation.class_id}"
            self.annotation_list.insert(tk.END, f"{index + 1:03d}  {class_name}  ·  {annotation.kind}")
        if self.canvas.selected_index is not None and 0 <= self.canvas.selected_index < len(self.annotations):
            self.annotation_list.selection_set(self.canvas.selected_index)

    def _load_classes(self) -> None:
        assert self.folder is not None
        classes_path = self.folder / "classes.txt"
        self.classes = [line.strip() for line in classes_path.read_text(encoding="utf-8").splitlines() if line.strip()] if classes_path.exists() else []
        self.current_class_id = 0
        self._refresh_class_combo(0)

    def _save_classes(self) -> None:
        if self.folder is not None:
            (self.folder / "classes.txt").write_text("\n".join(self.classes) + "\n", encoding="utf-8")

    def _refresh_class_combo(self, selected: int) -> None:
        self.class_combo.configure(values=[f"{index}: {name}" for index, name in enumerate(self.classes)])
        if self.classes:
            selected = min(max(selected, 0), len(self.classes) - 1)
            self.class_combo.current(selected)
            self.current_class_id = selected
            self.canvas.set_class_id(selected)

    def _label_path(self, image_path: Path) -> Path:
        assert self.folder is not None
        return self.folder / "labels" / f"{image_path.stem}.txt"

    def _update_tool_buttons(self) -> None:
        for tool, button in self.tool_buttons.items():
            button.configure(style="Accent.TButton" if tool == self.tool else "TButton")

    def _update_status(self, zoom: float | None = None) -> None:
        if self.current_index < 0 or self.current_image is None:
            return
        zoom_value = self.canvas.zoom if zoom is None else zoom
        path = self.image_paths[self.current_index]
        self.status.set(
            f"{self.current_index + 1}/{len(self.image_paths)}   {path.name}   "
            f"{self.current_image.width} × {self.current_image.height} px   "
            f"Zoom {zoom_value * 100:.0f}%   ·   {len(self.annotations)} labels"
        )


def main() -> None:
    root = tk.Tk()
    LabelingApp(root)
    root.mainloop()
