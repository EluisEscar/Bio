from PyQt5.QtWidgets import QMessageBox
from ..event_bus import bus

class FeatureController:
    def __init__(self, doc, table, canvas, editor):
        self.doc = doc
        self.table = table
        self.canvas = canvas
        self.editor = editor
        self.filter_text = ""
        self._row_to_index = []
        self._block_selection = False
        self._current_index = None

        bus.subscribe("record_loaded", self.on_record_loaded)
        bus.subscribe("features_changed", self.on_features_changed)
        bus.subscribe("feature_selected", self.on_canvas_feature_selected)

        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        self.table.cellChanged.connect(self.on_cell_changed)
        self.editor.featureUpdateRequested.connect(self.on_editor_apply)
        self.editor.featureResetRequested.connect(self.on_editor_reset)

    def on_record_loaded(self, record):
        seq_len = len(record.seq) if record else 0
        self.editor.set_sequence_length(seq_len)
        self.refresh_table()
        self._current_index = 0 if self.doc.features() else None
        if self._current_index is not None:
            self._apply_selection_by_index(self._current_index, update_editor=True, center_canvas=True)
        else:
            self.editor.clear()

    def on_features_changed(self, record):
        # Evitar bucles de eventos: refrescamos tabla y canvas
        self.refresh_table()
        self.canvas.update_from_record(self.doc.record)
        if self._current_index is not None:
            self._apply_selection_by_index(self._current_index, update_editor=True, center_canvas=False)

    def refresh_table(self):
        rec = self.doc.record
        self.table.blockSignals(True)
        if not rec:
            self.table.setRowCount(0)
            self.table.blockSignals(False)
            return
        feats = rec.features or []
        visible = [(idx, f) for idx, f in enumerate(feats) if self._matches_filter(f)]
        self._row_to_index = [idx for idx, _ in visible]
        self.table.setRowCount(len(visible))
        for row, (idx, f) in enumerate(visible):
            self.table.setItem(row, 0, self._mkitem(f.type))
            self.table.setItem(row, 1, self._mkitem(str(int(f.location.start))))
            self.table.setItem(row, 2, self._mkitem(str(int(f.location.end))))
            strand = f.location.strand if f.location.strand in (-1, 1) else 0
            self.table.setItem(row, 3, self._mkitem(str(strand)))
            qtext = "; ".join([
                f"{k}={v[0] if isinstance(v, list) and v else v}"
                for k, v in (f.qualifiers or {}).items()
            ])
            self.table.setItem(row, 4, self._mkitem(qtext))
        self.table.blockSignals(False)
        self.canvas.update_from_record(rec)
        self._restore_table_selection()

    def _mkitem(self, text):
        from PyQt5.QtWidgets import QTableWidgetItem
        it = QTableWidgetItem(text)
        return it

    def on_cell_changed(self, row, col):
        rec = self.doc.record
        if not rec or row >= len(rec.features):
            return
        if row >= len(self._row_to_index):
            return
        feature_idx = self._row_to_index[row]
        # Leer fila completa y propagar al modelo
        try:
            ftype = self.table.item(row, 0).text().strip()
            start = int(self.table.item(row, 1).text().strip())
            end = int(self.table.item(row, 2).text().strip())
            strand = int(self.table.item(row, 3).text().strip())
            qtext = self.table.item(row, 4).text().strip()
            qualifiers = self._parse_qualifiers(qtext)
            if start < 0 or end <= start or end > len(rec.seq):
                raise ValueError("Rango inválido")
            if strand not in (-1, 0, 1):
                raise ValueError("Strand inválido")
            self.doc.update_feature(feature_idx, ftype, start, end, strand, qualifiers)
            self._current_index = feature_idx
            self.editor.load_feature(feature_idx, rec.features[feature_idx])
        except Exception as e:
            QMessageBox.warning(self.table, "Error al editar", str(e))
            # Revertir tabla desde modelo
            self.refresh_table()

    # --- Filtering & selection ------------------------------------------------

    def set_filter_text(self, text):
        self.filter_text = text.strip()
        self.refresh_table()

    def _matches_filter(self, feature):
        if not self.filter_text:
            return True
        terms = [t for t in self.filter_text.lower().split() if t]
        if not terms:
            return True
        parts = [
            feature.type,
            str(int(feature.location.start)),
            str(int(feature.location.end)),
        ]
        qualifiers = feature.qualifiers or {}
        for key, values in qualifiers.items():
            parts.append(key)
            if isinstance(values, list):
                parts.extend([str(v) for v in values])
            else:
                parts.append(str(values))
        haystack = " ".join(parts).lower()
        return all(term in haystack for term in terms)

    def on_table_selection_changed(self):
        if self._block_selection:
            return
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            self._current_index = None
            self.editor.clear()
            return
        row = selected[0].row()
        if row >= len(self._row_to_index):
            return
        feature_idx = self._row_to_index[row]
        self._current_index = feature_idx
        self._update_editor_and_canvas(feature_idx, center_canvas=False, emit_event=True)

    def _restore_table_selection(self):
        if self._current_index is None:
            if not self._row_to_index:
                self.table.clearSelection()
                self.editor.clear()
                return
            self._current_index = self._row_to_index[0]
        if self._current_index not in self._row_to_index and self._row_to_index:
            # Si la selección desapareció por el filtro, seleccionamos la primera visible
            feature_idx = self._row_to_index[0]
            self._current_index = feature_idx
        if self._current_index in self._row_to_index:
            row = self._row_to_index.index(self._current_index)
            self._block_selection = True
            self.table.selectRow(row)
            self._block_selection = False
            self._update_editor_and_canvas(self._current_index, center_canvas=False, emit_event=False)
        else:
            self.editor.clear()

    def _apply_selection_by_index(self, feature_idx, update_editor=True, center_canvas=False):
        if feature_idx is None:
            return
        self._current_index = feature_idx
        if feature_idx in self._row_to_index:
            row = self._row_to_index.index(feature_idx)
            self._block_selection = True
            self.table.selectRow(row)
            self._block_selection = False
        elif self._row_to_index:
            row = 0
            self._current_index = self._row_to_index[row]
            self._block_selection = True
            self.table.selectRow(row)
            self._block_selection = False
        if update_editor:
            self._update_editor_and_canvas(self._current_index, center_canvas=center_canvas, emit_event=False)

    def _update_editor_and_canvas(self, feature_idx, center_canvas=False, emit_event=False):
        rec = self.doc.record
        if not rec or feature_idx is None or feature_idx >= len(rec.features):
            self.editor.clear()
            return
        feature = rec.features[feature_idx]
        self.editor.load_feature(feature_idx, feature)
        self.canvas.select_feature(feature_idx, center=center_canvas)

    def on_canvas_feature_selected(self, index):
        if index is None:
            return
        self._apply_selection_by_index(index, update_editor=True, center_canvas=False)

    # --- Editor integration ---------------------------------------------------

    def on_editor_apply(self, feature_idx, data):
        rec = self.doc.record
        if not rec or feature_idx is None or feature_idx >= len(rec.features):
            return
        try:
            self.doc.update_feature(
                feature_idx,
                data["type"],
                data["start"],
                data["end"],
                data["strand"],
                data["qualifiers"],
            )
            self._current_index = feature_idx
            self.refresh_table()
        except Exception as exc:
            QMessageBox.warning(self.table, "No se pudo actualizar", str(exc))

    def on_editor_reset(self, feature_idx):
        rec = self.doc.record
        if not rec or feature_idx is None or feature_idx >= len(rec.features):
            return
        self.editor.load_feature(feature_idx, rec.features[feature_idx])
        self._apply_selection_by_index(feature_idx, update_editor=False, center_canvas=False)

    # --- Public helpers -------------------------------------------------------

    def focus_last_feature(self):
        rec = self.doc.record
        if rec and rec.features:
            last_idx = len(rec.features) - 1
            self._apply_selection_by_index(last_idx, update_editor=True, center_canvas=True)

    def delete_selected_feature(self):
        if self._current_index is None:
            return
        rec = self.doc.record
        if not rec:
            return
        feature = rec.features[self._current_index]
        confirm = QMessageBox.question(
            self.table,
            "Eliminar característica",
            f"¿Deseas eliminar la anotación «{feature.type}» (posiciones {int(feature.location.start)}-{int(feature.location.end)})?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.doc.delete_feature(self._current_index)
            self._current_index = None
            self.editor.clear()

    # --- Utility --------------------------------------------------------------

    def _parse_qualifiers(self, qtext):
        qualifiers = {}
        if not qtext:
            return qualifiers
        parts = [p.strip() for p in qtext.split(";")]
        for p in parts:
            if not p:
                continue
            if "=" in p:
                k, v = p.split("=", 1)
                qualifiers[k.strip()] = [v.strip()]
            else:
                qualifiers[p] = ["true"]
        return qualifiers
