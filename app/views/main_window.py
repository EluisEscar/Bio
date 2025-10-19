import os
from PyQt5.QtWidgets import (QMainWindow,QWidget,QFileDialog,QMessageBox,QAction,QSplitter,QTableWidget,
    QVBoxLayout,QToolBar,QDialog,QFormLayout,QLineEdit,QDialogButtonBox,QLabel,QGroupBox,QHBoxLayout,QPushButton,QSpinBox,QSizePolicy,
)
from PyQt5.QtCore import Qt

from ..models import GenomeDocument
from ..event_bus import bus
from ..io import make_demo_record
from ..controllers.feature_controller import FeatureController
from .genome_canvas import GenomeCanvas
from .feature_editor import FeatureEditorPanel


class AddFeatureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Añadir característica")
        self.ftype = QLineEdit("gene")
        self.start = QLineEdit("100")
        self.end = QLineEdit("200")
        self.strand = QLineEdit("1")
        self.qual = QLineEdit("gene=demo")

        form = QFormLayout(self)
        form.addRow("Tipo", self.ftype)
        form.addRow("Inicio", self.start)
        form.addRow("Fin", self.end)
        form.addRow("Strand (-1,0,1)", self.strand)
        form.addRow("Metadatos (k=v; ...)", self.qual)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def values(self):
        qtext = self.qual.text().strip()
        qualifiers = {}
        if qtext:
            for part in [x.strip() for x in qtext.split(";")]:
                if not part:
                    continue
                if "=" in part:
                    k, v = part.split("=", 1)
                    qualifiers[k.strip()] = [v.strip()]
                else:
                    qualifiers[part] = ["true"]
        return (
            self.ftype.text().strip(),
            int(self.start.text().strip()),
            int(self.end.text().strip()),
            int(self.strand.text().strip()),
            qualifiers,
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Genome Annotation Studio")
        self.resize(1500, 900)

        self.doc = GenomeDocument()

        # Toolbar ----------------------------------------------------------------
        toolbar = QToolBar("Principal", self)
        self.addToolBar(toolbar)
        act_open = QAction("Abrir…", self)
        act_save = QAction("Guardar", self)
        act_save_as = QAction("Guardar como…", self)
        act_add = QAction("Añadir característica", self)
        act_del = QAction("Eliminar característica", self)
        act_zoom_in = QAction("Zoom +", self)
        act_zoom_out = QAction("Zoom −", self)
        act_zoom_reset = QAction("Ver todo", self)

        act_open.triggered.connect(self.on_open)
        act_save.triggered.connect(self.on_save)
        act_save_as.triggered.connect(self.on_save_as)
        act_add.triggered.connect(self.on_add_feature)
        act_del.triggered.connect(self.on_del_feature)
        act_zoom_in.triggered.connect(lambda: self.canvas.zoom(0.8))
        act_zoom_out.triggered.connect(lambda: self.canvas.zoom(1.25))
        act_zoom_reset.triggered.connect(self.on_reset_view)

        for action in (
            act_open,
            act_save,
            act_save_as,
            act_add,
            act_del,
            act_zoom_in,
            act_zoom_out,
            act_zoom_reset,
        ):
            toolbar.addAction(action)

        # Panel izquierdo: guía y resumen --------------------------------------
        left_panel = QWidget(self)
        left_panel.setMinimumWidth(200)
        left_panel.setMaximumWidth(350)
        left_layout = QVBoxLayout(left_panel)

        summary_box = QGroupBox("Resumen del genoma", left_panel)
        summary_form = QFormLayout(summary_box)
        self.summary_labels = {
            "id": QLabel("—"),
            "description": QLabel("—"),
            "length": QLabel("—"),
            "features": QLabel("—"),
            "topology": QLabel("—"),
            "path": QLabel("—"),
        }
        for label in self.summary_labels.values():
            label.setWordWrap(True)
        summary_form.addRow("Identificador:", self.summary_labels["id"])
        summary_form.addRow("Descripción:", self.summary_labels["description"])
        summary_form.addRow("Longitud (bp):", self.summary_labels["length"])
        summary_form.addRow("N.º de anotaciones:", self.summary_labels["features"])
        summary_form.addRow("Topología:", self.summary_labels["topology"])
        summary_form.addRow("Archivo:", self.summary_labels["path"])
        left_layout.addWidget(summary_box)

        navigation_box = QGroupBox("Navegación y zoom", left_panel)
        navigation_layout = QVBoxLayout(navigation_box)
        nav_buttons = QHBoxLayout()
        btn_zoom_in = QPushButton("Acercar", navigation_box)
        btn_zoom_out = QPushButton("Alejar", navigation_box)
        btn_zoom_reset = QPushButton("Ver todo", navigation_box)
        btn_zoom_in.clicked.connect(lambda: self.canvas.zoom(0.8))
        btn_zoom_out.clicked.connect(lambda: self.canvas.zoom(1.25))
        btn_zoom_reset.clicked.connect(self.on_reset_view)
        nav_buttons.addWidget(btn_zoom_in)
        nav_buttons.addWidget(btn_zoom_out)
        nav_buttons.addWidget(btn_zoom_reset)
        navigation_layout.addLayout(nav_buttons)

        goto_layout = QHBoxLayout()
        goto_label = QLabel("Ir a posición:", navigation_box)
        self.position_spin = QSpinBox(navigation_box)
        self.position_spin.setRange(0, 0)
        self.position_spin.setSuffix(" bp")
        self.position_spin.setEnabled(False)
        self.view_width_spin = QSpinBox(navigation_box)
        self.view_width_spin.setRange(50, 500000)
        self.view_width_spin.setSingleStep(50)
        self.view_width_spin.setValue(500)
        self.view_width_spin.setSuffix(" bp")
        self.view_width_spin.setEnabled(False)
        self.goto_button = QPushButton("Ir", navigation_box)
        self.goto_button.setEnabled(False)
        self.goto_button.clicked.connect(self.on_center_view)
        goto_layout.addWidget(goto_label)
        goto_layout.addWidget(self.position_spin)
        goto_layout.addWidget(self.view_width_spin)
        goto_layout.addWidget(self.goto_button)
        navigation_layout.addLayout(goto_layout)

        nav_hint = QLabel(
            "Consejo: usa la rueda del ratón para hacer zoom y arrastra con el botón izquierdo para desplazarte.",
            navigation_box,
        )
        nav_hint.setWordWrap(True)
        navigation_layout.addWidget(nav_hint)
        left_layout.addWidget(navigation_box)

        guide_box = QGroupBox("Guía rápida", left_panel)
        guide_layout = QVBoxLayout(guide_box)
        quick_help = QLabel(
            "<ul>"
            "<li>Abre un archivo GenBank con «Abrir…» o explora la muestra incluida.</li>"
            "<li>Selecciona cualquier anotación para revisar y modificar sus metadatos.</li>"
            "<li>Usa el buscador y el visor para ubicar regiones específicas rápidamente.</li>"
            "<li>Guarda tus cambios en el mismo archivo o usa «Guardar como…» para exportar.</li>"
            "</ul>",
            guide_box,
        )
        quick_help.setWordWrap(True)
        guide_layout.addWidget(quick_help)
        left_layout.addWidget(guide_box)
        left_layout.addStretch(1)

        # Panel derecho
        self.canvas = GenomeCanvas(self)

        table_container = QWidget(self)
        table_layout = QVBoxLayout(table_container)
        search_layout = QHBoxLayout()
        search_label = QLabel("Buscar anotación:", table_container)
        self.search_box = QLineEdit(table_container)
        self.search_box.setPlaceholderText("Filtra por tipo, gen, producto o cualquier metadato…")
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_box)
        table_layout.addLayout(search_layout)

        action_layout = QHBoxLayout()
        btn_add_feature = QPushButton("Añadir anotación", table_container)
        btn_remove_feature = QPushButton("Eliminar selección", table_container)
        btn_add_feature.clicked.connect(self.on_add_feature)
        btn_remove_feature.clicked.connect(self.on_del_feature)
        action_layout.addWidget(btn_add_feature)
        action_layout.addWidget(btn_remove_feature)
        action_layout.addStretch(1)
        table_layout.addLayout(action_layout)

        self.table = QTableWidget(0, 5, table_container)
        self.table.setHorizontalHeaderLabels(["Tipo", "Inicio", "Fin", "Strand", "Metadatos"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        table_layout.addWidget(self.table)

        self.editor = FeatureEditorPanel(self)
        self.editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        detail_splitter = QSplitter(Qt.Vertical, self)
        detail_splitter.addWidget(table_container)
        detail_splitter.addWidget(self.editor)
        detail_splitter.setStretchFactor(0, 3)
        detail_splitter.setStretchFactor(1, 2)

        right_splitter = QSplitter(Qt.Vertical, self)
        right_splitter.addWidget(self.canvas)
        right_splitter.addWidget(detail_splitter)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 2)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_splitter)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        # Controller y conexiones -------------------------------------------------
        self.controller = FeatureController(self.doc, self.table, self.canvas, self.editor)
        self.search_box.textChanged.connect(self.controller.set_filter_text)

        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        example_path = os.path.join(data_dir, "example.gb")
        if not os.path.exists(example_path):
            record = make_demo_record()
            from ..io import save_genbank

            save_genbank(record, example_path)
        self.doc.load(example_path)

        bus.subscribe("record_saved", self.on_record_saved)
        bus.subscribe("record_loaded", self.on_record_loaded_event)
        bus.subscribe("features_changed", self.on_features_changed_event)

    # ---------------------------------------------------------------------
    # Acciones de la interfaz
    # ---------------------------------------------------------------------
    def on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir GenBank", "", "GenBank (*.gb *.gbk);;Todos los archivos (*)"
        )
        if path:
            try:
                self.doc.load(path)
            except Exception as exc:
                QMessageBox.critical(self, "Error al abrir", str(exc))

    def on_save(self):
        try:
            self.doc.save()
        except Exception as exc:
            QMessageBox.critical(self, "Error al guardar", str(exc))

    def on_save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar GenBank como…", "", "GenBank (*.gb *.gbk)"
        )
        if path:
            try:
                self.doc.save(path)
            except Exception as exc:
                QMessageBox.critical(self, "Error al exportar", str(exc))

    def on_add_feature(self):
        if not self.doc.record:
            return
        dialog = AddFeatureDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            ftype, start, end, strand, qualifiers = dialog.values()
            if start < 0 or end <= start or end > len(self.doc.record.seq):
                QMessageBox.warning(
                    self,
                    "Rango inválido",
                    "El rango de la nueva anotación no es válido dentro de la secuencia.",
                )
                return
            if strand not in (-1, 0, 1):
                QMessageBox.warning(self, "Strand inválido", "El strand debe ser -1, 0 o 1.")
                return
            self.doc.add_feature(ftype, start, end, strand, qualifiers)
            self.controller.focus_last_feature()

    def on_del_feature(self):
        self.controller.delete_selected_feature()

    def on_reset_view(self):
        self.canvas.reset_view()

    def on_center_view(self):
        position = self.position_spin.value()
        span = self.view_width_spin.value()
        self.canvas.center_on(position, span)

    # ---------------------------------------------------------------------
    # Respuestas a eventos del modelo
    # ---------------------------------------------------------------------
    def on_record_saved(self, path):
        self.statusBar().showMessage(f"Guardado: {path}", 3000)
        self.summary_labels["path"].setText(path)

    def on_record_loaded_event(self, record):
        if not record:
            return
        self.statusBar().showMessage("GenBank cargado correctamente", 3000)
        self.update_summary(record)
        self.canvas.reset_view()
        title_suffix = self.doc.filepath or record.id or "sin nombre"
        self.setWindowTitle(f"Genome Annotation Studio — {title_suffix}")
        length = len(record.seq)
        self.position_spin.blockSignals(True)
        self.position_spin.setRange(0, max(0, length))
        self.position_spin.setValue(0)
        self.position_spin.setEnabled(True)
        self.position_spin.blockSignals(False)
        self.view_width_spin.setMaximum(max(50, length))
        self.view_width_spin.setEnabled(True)
        self.goto_button.setEnabled(True)
        self.editor.set_sequence_length(length)

    def on_features_changed_event(self, record):
        if record:
            self.summary_labels["features"].setText(str(len(record.features)))

    def update_summary(self, record):
        if not record:
            return
        self.summary_labels["id"].setText(record.id or "—")
        self.summary_labels["description"].setText(record.description or "—")
        self.summary_labels["length"].setText(str(len(record.seq)))
        self.summary_labels["features"].setText(str(len(record.features or [])))
        topology = record.annotations.get("topology") or record.annotations.get("molecule_type")
        self.summary_labels["topology"].setText(str(topology) if topology else "—")
        self.summary_labels["path"].setText(self.doc.filepath or "—")
