"""Ventana principal y diálogos auxiliares de la aplicación."""

import os
from PyQt5.QtWidgets import (QMainWindow,QWidget,QFileDialog,QMessageBox,QAction,QSplitter,QTableWidget,QVBoxLayout,QToolBar,QDialog,QFormLayout,
    QLineEdit,QDialogButtonBox,QLabel,QGroupBox,QHBoxLayout,QPushButton,QSpinBox,QSizePolicy,QComboBox,QToolButton,QProgressDialog,QSlider,
)
from PyQt5.QtCore import Qt

from ..models import GenomeDocument
from ..event_bus import bus
from ..io import make_demo_record
from ..controllers.feature_controller import FeatureController
from .genome_canvas import GenomeCanvas
from .feature_editor import FeatureEditorPanel
from .bio_help_dialog import BioHelpDialog
from ..workers import RecordLoadWorker


class EntrezImportDialog(QDialog):
    """Cuadro de diálogo para consultar y descargar registros desde NCBI/Entrez."""

    def __init__(self, parent=None, default_email="", default_db="nuccore"):
        """Construye el formulario solicitando términos de búsqueda y parámetros Entrez."""
        super().__init__(parent)
        self.setWindowTitle("Importar desde NCBI (Entrez)")

        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("Accession, nombre de gen o término de búsqueda…")
        self.email_edit = QLineEdit(default_email)
        self.email_edit.setPlaceholderText("correo@institucion.edu (requerido por NCBI)")
        self.db_combo = QComboBox()
        self.db_combo.addItem("Nucleótidos (nuccore)", "nuccore")
        self.retmax_spin = QSpinBox()
        self.retmax_spin.setRange(1, 20)
        self.retmax_spin.setValue(5)
        for idx in range(self.db_combo.count()):
            if self.db_combo.itemData(idx) == default_db:
                self.db_combo.setCurrentIndex(idx)
                break

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Consulta*", self.query_edit)
        form.addRow("Base de datos", self.db_combo)
        form.addRow("Resultados a explorar", self.retmax_spin)
        form.addRow("Correo electrónico*", self.email_edit)
        layout.addLayout(form)

        info = QLabel(
            "NCBI requiere un correo electrónico válido para monitorizar el uso. "
            "Usaremos el primer resultado devuelto por Entrez. "
            "Actualmente esta aplicación solo descarga secuencias NUCLEOTÍDICAS (nuccore) para fortalecer el aprendizaje en ADN."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def accept(self):
        """Valida entradas requeridas antes de cerrar con éxito."""
        if not self.query_edit.text().strip():
            QMessageBox.warning(self, "Falta información", "Introduce un término de búsqueda o accession.")
            return
        if not self.email_edit.text().strip():
            QMessageBox.warning(self, "Correo requerido", "Debes proporcionar un correo electrónico para NCBI.")
            return
        super().accept()

    def values(self):
        """Devuelve las opciones elegidas por el usuario."""
        return {
            "query": self.query_edit.text().strip(),
            "db": self.db_combo.currentData(),
            "retmax": self.retmax_spin.value(),
            "email": self.email_edit.text().strip()
        }


class AddFeatureDialog(QDialog):
    """Formulario simple para crear anotaciones GenBank de prueba."""

    def __init__(self, parent=None):
        """Define los campos básicos necesarios para una Feature."""
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
        """Convierte el texto ingresado en tipos nativos para crear la anotación."""
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
    """Ventana principal que integra el visor genómico, la tabla y herramientas."""

    def __init__(self):
        """Inicializa la interfaz, controladores y carga un ejemplo base."""
        super().__init__()
        self.setWindowTitle("Genome Annotation Studio")
        self.resize(1500, 900)

        self.doc = GenomeDocument()
        self._entrez_email = os.environ.get("NCBI_ENTREZ_EMAIL", "")
        self._entrez_api_key = os.environ.get("NCBI_ENTREZ_API_KEY", "")
        self._entrez_db = os.environ.get("NCBI_ENTREZ_DB", "nuccore")
        self._last_import_source = None
        self._loader = None
        self._loading_dialog = None
        self._sidebar_width = 300
        self._detail_visible = True
        self._detail_sizes = [500, 300]

        # Toolbar
        toolbar = QToolBar("Principal", self)
        self.addToolBar(toolbar)
        act_open = QAction("Abrir…", self)
        act_import_entrez = QAction("Importar desde NCBI…", self)
        act_save = QAction("Guardar", self)
        act_save_as = QAction("Guardar como…", self)
        act_delete_file = QAction("Eliminar archivo…", self)
        act_toggle_sidebar = QAction("Mostrar panel guía", self)
        act_toggle_sidebar.setCheckable(True)
        act_toggle_sidebar.setChecked(True)
        act_toggle_details = QAction("Mostrar detalles", self)
        act_toggle_details.setCheckable(True)
        act_toggle_details.setChecked(True)
        act_bio_help = QAction("Ayuda Bioinformática IA", self)
        #act_add = QAction("Añadir característica", self)
        #act_del = QAction("Eliminar característica", self)
        act_zoom_reset = QAction("Ver todo", self)

        act_open.triggered.connect(self.on_open)
        act_import_entrez.triggered.connect(self.on_import_entrez)
        act_save.triggered.connect(self.on_save)
        act_save_as.triggered.connect(self.on_save_as)
        act_delete_file.triggered.connect(self.on_delete_file)
        act_toggle_sidebar.toggled.connect(self.on_toggle_sidebar)
        act_toggle_details.toggled.connect(self.on_toggle_details)
        act_bio_help.triggered.connect(self.on_open_bio_help)
        #act_add.triggered.connect(self.on_add_feature)
        #act_del.triggered.connect(self.on_del_feature)
        act_zoom_reset.triggered.connect(self.on_reset_view)

        act_delete_file.setEnabled(False)
        self.act_delete_file = act_delete_file
        self.act_toggle_sidebar = act_toggle_sidebar
        self.act_toggle_details = act_toggle_details

        for action in (
            act_open,
            act_import_entrez,
            act_save,
            act_save_as,
            act_delete_file,
            act_bio_help,
            #act_add,
            #act_del,
            act_zoom_reset,
        ):
            toolbar.addAction(action)

        view_menu = self.menuBar().addMenu("Vista")
        view_menu.addAction(act_toggle_sidebar)
        view_menu.addAction(act_toggle_details)
        view_menu.addSeparator()
        view_menu.addAction(act_zoom_reset)

        view_button = QToolButton(self)
        view_button.setText("Vista")
        view_button.setPopupMode(QToolButton.InstantPopup)
        view_button.setMenu(view_menu)
        toolbar.addWidget(view_button)

        # Panel izquierdo: guía y resumen
        left_panel = QWidget(self)
        left_panel.setMinimumWidth(140)
        left_panel.setMaximumWidth(360)
        left_layout = QVBoxLayout(left_panel)
        self.left_panel = left_panel

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
        btn_remove_feature = QPushButton("Eliminar anotación", table_container)
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
        detail_splitter.setChildrenCollapsible(True)
        detail_splitter.addWidget(table_container)
        detail_splitter.addWidget(self.editor)
        detail_splitter.setStretchFactor(0, 3)
        detail_splitter.setStretchFactor(1, 2)
        detail_splitter.splitterMoved.connect(self._on_detail_splitter_moved)
        self.detail_splitter = detail_splitter

        right_splitter = QSplitter(Qt.Vertical, self)
        right_splitter.setChildrenCollapsible(True)
        right_splitter.addWidget(self.canvas)
        right_splitter.addWidget(detail_splitter)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 2)
        right_splitter.splitterMoved.connect(self._on_right_splitter_moved)
        self.right_splitter = right_splitter

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setChildrenCollapsible(True)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_splitter)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        container = QWidget(self)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        container_layout.addWidget(splitter, 1)
        self.view_slider = QSlider(Qt.Horizontal, self)
        self.view_slider.setRange(0, 0)
        self.view_slider.setEnabled(False)
        self.view_slider.setSingleStep(1)
        self.view_slider.valueChanged.connect(self.on_slider_changed)
        container_layout.addWidget(self.view_slider, 0)
        self.setCentralWidget(container)
        self.primary_splitter = splitter
        initial_left = min(left_panel.maximumWidth(), 320)
        splitter.setSizes([initial_left, max(500, self.width() - initial_left)])
        splitter.splitterMoved.connect(self._on_splitter_moved)
        default_detail = [max(320, int(self.height() * 0.55)), max(200, int(self.height() * 0.35))]
        self.right_splitter.setSizes(default_detail)
        self._detail_sizes = self.right_splitter.sizes()
        self._syncing_slider = False
        self._current_span = 0
        bus.subscribe("view_changed", self.on_view_changed)

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
    def on_import_entrez(self):
        """Abre el diálogo de Entrez y lanza un worker para descargar el registro."""
        dialog = EntrezImportDialog(
            self,
            default_email=self._entrez_email,
            default_db=self._entrez_db,
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        params = dialog.values()
        self._entrez_email = params["email"]
        self._entrez_db = params["db"]
        self._start_record_loader(mode="entrez", entrez_params=params)

    def on_open_bio_help(self):
        """Abre la ventana modal con el tutor de bioinformática."""
        dialog = BioHelpDialog(self)
        dialog.exec_()

    def on_open(self):
        """Permite seleccionar un archivo GenBank local y lo carga."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir GenBank", "", "GenBank (*.gb *.gbk);;Todos los archivos (*)"
        )
        if path:
            self._start_record_loader(mode="file", path=path)

    def on_save(self):
        """Guarda el documento actual en la misma ruta asociada."""
        try:
            self.doc.save()
        except Exception as exc:
            QMessageBox.critical(self, "Error al guardar", str(exc))

    def on_save_as(self):
        """Solicita una ruta y exporta el documento actual."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar GenBank como…", "", "GenBank (*.gb *.gbk)"
        )
        if path:
            try:
                self.doc.save(path)
            except Exception as exc:
                QMessageBox.critical(self, "Error al exportar", str(exc))

    def on_add_feature(self):
        """Crea una anotación manual usando los datos facilitados por el usuario."""
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
        """Elimina la anotación seleccionada en la tabla."""
        self.controller.delete_selected_feature()

    def on_reset_view(self):
        """Ordena al lienzo que muestre la secuencia completa."""
        self.canvas.reset_view()

    def on_center_view(self):
        """Centra el lienzo en una posición concreta con el ancho especificado."""
        position = self.position_spin.value()
        span = self.view_width_spin.value()
        self.canvas.center_on(position, span)

    def on_slider_changed(self, value):
        """Sincroniza el desplazamiento horizontal del lienzo con el deslizador."""
        if self._syncing_slider:
            return
        if not self.canvas.record:
            return
        if self._current_span <= 0:
            return
        seq_len = len(self.canvas.record.seq)
        left = max(0, min(value, max(0, seq_len - self._current_span)))
        right = left + self._current_span
        self._syncing_slider = True
        self.canvas.pan_to(left, self._current_span)
        self._syncing_slider = False

    def on_toggle_sidebar(self, checked):
        """Muestra u oculta el panel lateral y recuerda su tamaño."""
        if not hasattr(self, "left_panel") or not hasattr(self, "primary_splitter"):
            return
        if checked:
            target = max(160, min(self.left_panel.maximumWidth(), self._sidebar_width))
            self.left_panel.show()
            total = max(self.primary_splitter.width(), target + 300)
            self.primary_splitter.setSizes([target, total - target])
        else:
            current = self.left_panel.width()
            if current:
                self._sidebar_width = current
            self.left_panel.hide()
            total = max(self.primary_splitter.width(), 1)
            self.primary_splitter.setSizes([0, total])

    def _on_splitter_moved(self, pos, index):
        """Actualiza el ancho recordado del panel lateral al ajustar el splitter."""
        if self.left_panel.isVisible():
            self._sidebar_width = self.left_panel.width()

    def on_toggle_details(self, checked):
        """Controla la visibilidad del panel inferior (tabla y editor)."""
        if not hasattr(self, "right_splitter") or not hasattr(self, "detail_splitter"):
            return
        self._detail_visible = checked
        if checked:
            self.detail_splitter.show()
            if self._detail_sizes and sum(self._detail_sizes) > 0:
                self.right_splitter.setSizes(self._detail_sizes)
            else:
                height = max(self.right_splitter.height(), 1)
                self.right_splitter.setSizes([int(height * 0.7), int(height * 0.3)])
        else:
            self._detail_sizes = self.right_splitter.sizes()
            self.detail_splitter.hide()
            total = sum(self._detail_sizes) or max(self.right_splitter.height(), 1)
            self.right_splitter.setSizes([total, 0])

    def _on_right_splitter_moved(self, pos, index):
        """Guarda las proporciones del splitter vertical cuando está visible."""
        if self._detail_visible:
            self._detail_sizes = self.right_splitter.sizes()

    def on_view_changed(self, left, right, length):
        """Actualiza el deslizador de navegación al recibir cambios desde el lienzo."""
        self._current_span = max(1, int(right - left))
        max_pos = max(0, int(length - self._current_span))
        self._syncing_slider = True
        self.view_slider.blockSignals(True)
        self.view_slider.setRange(0, max_pos)
        self.view_slider.setEnabled(max_pos > 0)
        self.view_slider.setValue(int(left))
        self.view_slider.blockSignals(False)
        self._syncing_slider = False

    def _on_detail_splitter_moved(self, pos, index):
        """Mantiene las proporciones actuales del panel inferior."""
        if self._detail_visible:
            self._detail_sizes = self.right_splitter.sizes()

    def _start_record_loader(self, *, mode, path=None, entrez_params=None):
        """Lanza un hilo que carga datos desde archivo o Entrez mostrando progreso."""
        if self._loader and self._loader.isRunning():
            QMessageBox.information(
                self,
                "Carga en curso",
                "Ya hay una operación de carga ejecutándose. Espera a que termine antes de iniciar otra.",
            )
            return
        self._loading_dialog = QProgressDialog(
            "Cargando anotaciones…", "Cancelar", 0, 0, self
        )
        self._loading_dialog.setWindowTitle("Importando GenBank")
        self._loading_dialog.setWindowModality(Qt.ApplicationModal)
        self._loading_dialog.canceled.connect(self._cancel_loader)
        self._loading_dialog.show()

        self._loader = RecordLoadWorker(
            mode=mode,
            path=path,
            entrez_params=entrez_params or {},
            parent=self,
        )
        self._loader.completed.connect(self._on_loader_completed)
        self._loader.failed.connect(self._on_loader_failed)
        self._loader.finished.connect(self._clear_loader)
        self._loader.start()

    def _cancel_loader(self):
        """Interrumpe la carga en curso a petición del usuario."""
        if self._loader and self._loader.isRunning():
            self._loader.requestInterruption()
            if self._loading_dialog:
                self._loading_dialog.setLabelText("Cancelando… espera un momento.")
                self._loading_dialog.setCancelButton(None)

    def _on_loader_completed(self, record, info):
        """Se ejecuta cuando la descarga o lectura termina correctamente."""
        self._close_loading_dialog()
        mode = info.get("mode")
        if mode == "file":
            path = info.get("path")
            self._last_import_source = None
            self._apply_loaded_record(record, path)
            if path:
                basename = os.path.basename(path)
                self.statusBar().showMessage(f"Archivo cargado: {basename}", 4000)
        elif mode == "entrez":
            accession = info.get("accession") or info.get("id")
            self._last_import_source = f"NCBI:{accession}" if accession else "NCBI"
            self._apply_loaded_record(record, None)
            count = int(info.get("count", 0))
            extra = ""
            if count > 1:
                extra = f" (primer resultado de {count})"
            self.statusBar().showMessage(
                f"Importado {accession or 'registro'} desde {info.get('db', 'NCBI')}{extra}",
                5000,
            )
        else:
            self._apply_loaded_record(record, None)

    def _on_loader_failed(self, error_message, context):
        """Muestra ventanas de error adaptadas al origen del fallo."""
        self._close_loading_dialog()
        mode = context.get("mode")
        if mode == "file":
            path = context.get("path") or ""
            QMessageBox.critical(
                self,
                "No se pudo abrir el archivo",
                f"El archivo no pudo cargarse.\n\nRuta: {path}\nError: {error_message}",
            )
        elif mode == "entrez":
            query = context.get("query", "")
            QMessageBox.critical(
                self,
                "No se pudo importar desde NCBI",
                f"No se pudo completar la descarga para «{query}».\n\nDetalle: {error_message}",
            )
        else:
            QMessageBox.critical(
                self,
                "Error de carga",
                error_message,
            )

    def _apply_loaded_record(self, record, path):
        """Refresca el documento y notifica al bus que hay un nuevo registro."""
        self.doc.record = record
        self.doc.filepath = path
        self.doc.dirty = False
        bus.publish("record_loaded", record=record)
        self._update_file_actions()

    def _close_loading_dialog(self):
        """Cierra el diálogo de progreso si sigue visible."""
        if self._loading_dialog:
            self._loading_dialog.hide()
            self._loading_dialog.deleteLater()
            self._loading_dialog = None

    def _clear_loader(self):
        """Limpia la referencia al hilo que terminó."""
        self._loader = None

    # ---------------------------------------------------------------------
    # Respuestas a eventos del modelo
    # ---------------------------------------------------------------------
    def on_record_saved(self, path):
        """Actualiza la barra de estado al completar un guardado."""
        self.statusBar().showMessage(f"Guardado: {path}", 3000)
        self.summary_labels["path"].setText(path)
        self._update_file_actions()

    def on_record_loaded_event(self, record):
        """Carga valores en paneles al recibir un nuevo registro desde el bus."""
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
        if self._last_import_source:
            self.summary_labels["path"].setText(self._last_import_source)
            self._last_import_source = None
        self._update_file_actions()

    def on_features_changed_event(self, record):
        """Refresca el contador de anotaciones cuando cambian."""
        if record:
            self.summary_labels["features"].setText(str(len(record.features)))

    def update_summary(self, record):
        """Puebla el panel de resumen con los metadatos del registro."""
        if not record:
            return
        self.summary_labels["id"].setText(record.id or "—")
        self.summary_labels["description"].setText(record.description or "—")
        self.summary_labels["length"].setText(str(len(record.seq)))
        self.summary_labels["features"].setText(str(len(record.features or [])))
        topology = record.annotations.get("topology") or record.annotations.get("molecule_type")
        self.summary_labels["topology"].setText(str(topology) if topology else "—")
        self.summary_labels["path"].setText(self.doc.filepath or "—")
        self._update_file_actions()

    def on_delete_file(self):
        """Elimina físicamente el archivo GenBank asociado al documento."""
        path = self.doc.filepath
        if not path:
            QMessageBox.information(
                self,
                "Sin archivo asociado",
                "No hay un archivo GenBank asociado a este documento. Usa «Guardar como…» para crear uno.",
            )
            return
        if not os.path.exists(path):
            QMessageBox.warning(
                self,
                "Archivo no encontrado",
                f"El archivo {path} ya no existe en el disco.",
            )
            self.doc.filepath = None
            self.summary_labels["path"].setText("—")
            self._update_file_actions()
            return
        reply = QMessageBox.question(
            self,
            "Eliminar archivo",
            f"¿Seguro que quieres eliminar el archivo GenBank?\n\n{path}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            os.remove(path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "No se pudo eliminar",
                f"Ocurrió un error al eliminar el archivo:\n{exc}",
            )
            return
        self.doc.filepath = None
        self.doc.dirty = True
        self.summary_labels["path"].setText("Archivo eliminado")
        self.statusBar().showMessage("Archivo GenBank eliminado.", 4000)
        self._update_file_actions()

    def _update_file_actions(self):
        """Habilita o deshabilita acciones según exista un archivo físico."""
        path = self.doc.filepath
        can_delete = bool(path and os.path.exists(path))
        self.act_delete_file.setEnabled(can_delete)
