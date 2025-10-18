import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QFileDialog, QMessageBox, QAction, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QToolBar, QDialog, QFormLayout, QLineEdit, QDialogButtonBox
)
from PyQt5.QtCore import Qt
from ..models import GenomeDocument
from ..event_bus import bus
from .genome_canvas import GenomeCanvas
from ..io import make_demo_record
from ..controllers.feature_controller import FeatureController

class AddFeatureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Feature")
        self.ftype = QLineEdit("gene")
        self.start = QLineEdit("100")
        self.end = QLineEdit("200")
        self.strand = QLineEdit("1")
        self.qual = QLineEdit("gene=demo")

        form = QFormLayout(self)
        form.addRow("type", self.ftype)
        form.addRow("start", self.start)
        form.addRow("end", self.end)
        form.addRow("strand (-1,0,1)", self.strand)
        form.addRow("qualifiers (k=v; ...)", self.qual)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def values(self):
        # retorna (type, start, end, strand, qualifiers_dict)
        qtext = self.qual.text().strip()
        qualifiers = {}
        if qtext:
            for p in [x.strip() for x in qtext.split(";")]:
                if not p:
                    continue
                if "=" in p:
                    k, v = p.split("=", 1)
                    qualifiers[k.strip()] = [v.strip()]
                else:
                    qualifiers[p] = ["true"]
        return (self.ftype.text().strip(),
                int(self.start.text().strip()),
                int(self.end.text().strip()),
                int(self.strand.text().strip()),
                qualifiers)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Genome Annotation Viewer")
        self.resize(1200, 700)

        self.doc = GenomeDocument()

        # Toolbar / actions
        tb = QToolBar("Main")
        self.addToolBar(tb)
        act_open = QAction("Open", self)
        act_save = QAction("Save", self)
        act_save_as = QAction("Save As...", self)
        act_add = QAction("Add Feature", self)
        act_del = QAction("Delete Feature", self)

        act_open.triggered.connect(self.on_open)
        act_save.triggered.connect(self.on_save)
        act_save_as.triggered.connect(self.on_save_as)
        act_add.triggered.connect(self.on_add_feature)
        act_del.triggered.connect(self.on_del_feature)

        for a in (act_open, act_save, act_save_as, act_add, act_del):
            tb.addAction(a)

        # Central widgets: splitter with canvas + table
        splitter = QSplitter(Qt.Vertical, self)
        self.canvas = GenomeCanvas(self)
        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(["type", "start", "end", "strand", "qualifiers"])
        self.table.horizontalHeader().setStretchLastSection(True)

        # controller
        self.controller = FeatureController(self.doc, self.table, self.canvas)

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.addWidget(self.canvas)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.addWidget(self.table)

        splitter.addWidget(top)
        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

        # Inicializar con un record demo (y guardar a data/example.gb si no existe)
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        example_path = os.path.join(data_dir, "example.gb")
        if not os.path.exists(example_path):
            from Bio import SeqIO
            rec = make_demo_record()
            from ..io import save_genbank
            save_genbank(rec, example_path)
        self.doc.load(example_path)

        bus.subscribe("record_saved", self.on_record_saved)

    def on_open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open GenBank", "", "GenBank (*.gb *.gbk);;All files (*)")
        if path:
            try:
                self.doc.load(path)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def on_save(self):
        try:
            self.doc.save()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def on_save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save GenBank As", "", "GenBank (*.gb *.gbk)")
        if path:
            try:
                self.doc.save(path)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def on_add_feature(self):
        if not self.doc.record:
            return
        dlg = AddFeatureDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            ftype, start, end, strand, qualifiers = dlg.values()
            if start < 0 or end <= start or end > len(self.doc.record.seq):
                QMessageBox.warning(self, "Rango inválido", "El rango de la nueva feature es inválido.")
                return
            self.doc.add_feature(ftype, start, end, strand, qualifiers)

    def on_del_feature(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self.doc.delete_feature(row)

    def on_record_saved(self, path):
        self.statusBar().showMessage(f"Guardado: {path}", 3000)
