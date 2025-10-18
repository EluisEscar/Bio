from PyQt5.QtWidgets import QMessageBox
from ..event_bus import bus

class FeatureController:
    def __init__(self, doc, table, canvas):
        self.doc = doc
        self.table = table
        self.canvas = canvas

        bus.subscribe("record_loaded", self.on_record_loaded)
        bus.subscribe("features_changed", self.on_features_changed)

        self.table.cellChanged.connect(self.on_cell_changed)

    def on_record_loaded(self, record):
        self.refresh_table()

    def on_features_changed(self, record):
        # Evitar bucles de eventos: refrescamos tabla y canvas
        self.refresh_table()
        self.canvas.update_from_record(self.doc.record)

    def refresh_table(self):
        rec = self.doc.record
        self.table.blockSignals(True)
        if not rec:
            self.table.setRowCount(0)
            self.table.blockSignals(False)
            return
        feats = rec.features or []
        self.table.setRowCount(len(feats))
        for i, f in enumerate(feats):
            # type, start, end, strand, qualifiers
            self.table.setItem(i, 0, self._mkitem(f.type))
            self.table.setItem(i, 1, self._mkitem(str(int(f.location.start))))
            self.table.setItem(i, 2, self._mkitem(str(int(f.location.end))))
            strand = f.location.strand if f.location.strand in (-1, 1) else 0
            self.table.setItem(i, 3, self._mkitem(str(strand)))
            qtext = "; ".join([f"{k}={v[0] if isinstance(v, list) and v else v}" for k, v in (f.qualifiers or {}).items()])
            self.table.setItem(i, 4, self._mkitem(qtext))
        self.table.blockSignals(False)
        self.canvas.update_from_record(rec)

    def _mkitem(self, text):
        from PyQt5.QtWidgets import QTableWidgetItem
        it = QTableWidgetItem(text)
        return it

    def on_cell_changed(self, row, col):
        rec = self.doc.record
        if not rec or row >= len(rec.features):
            return
        # Leer fila completa y propagar al modelo
        try:
            ftype = self.table.item(row, 0).text().strip()
            start = int(self.table.item(row, 1).text().strip())
            end = int(self.table.item(row, 2).text().strip())
            strand = int(self.table.item(row, 3).text().strip())
            qtext = self.table.item(row, 4).text().strip()
            qualifiers = {}
            if qtext:
                parts = [p.strip() for p in qtext.split(";")]
                for p in parts:
                    if not p:
                        continue
                    if "=" in p:
                        k, v = p.split("=", 1)
                        qualifiers[k.strip()] = [v.strip()]
                    else:
                        qualifiers[p] = ["true"]
            if start < 0 or end <= start or end > len(rec.seq):
                raise ValueError("Rango inválido")
            if strand not in (-1, 0, 1):
                raise ValueError("Strand inválido")
            self.doc.update_feature(row, ftype, start, end, strand, qualifiers)
        except Exception as e:
            QMessageBox.warning(self.table, "Error al editar", str(e))
            # Revertir tabla desde modelo
            self.refresh_table()
