from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QComboBox,
    QPlainTextEdit,
    QHBoxLayout,
    QPushButton,
)
from typing import Optional


class FeatureEditorPanel(QWidget):
    featureUpdateRequested = pyqtSignal(int, dict)
    featureResetRequested = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_index: Optional[int] = None
        self._sequence_length: int = 0
        self._updating_ui: bool = False

        layout = QVBoxLayout(self)
        header = QLabel(
            "<b>Editor de anotaciones</b><br>"
            "Selecciona una fila en la tabla o un elemento en el visor para modificar sus metadatos."
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        form = QFormLayout()
        self.type_edit = QLineEdit()
        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 0)
        self.end_spin = QSpinBox()
        self.end_spin.setRange(0, 0)
        self.strand_combo = QComboBox()
        self.strand_combo.addItem("Forward (+1)", 1)
        self.strand_combo.addItem("Sin dirección (0)", 0)
        self.strand_combo.addItem("Reverse (-1)", -1)

        form.addRow("Tipo de feature:", self.type_edit)
        form.addRow("Inicio (bp):", self.start_spin)
        form.addRow("Fin (bp):", self.end_spin)
        form.addRow("Orientación:", self.strand_combo)
        layout.addLayout(form)

        qualifiers_label = QLabel("Metadatos (formato clave=valor; usar «;» para separar):")
        qualifiers_label.setWordWrap(True)
        layout.addWidget(qualifiers_label)

        self.qualifiers_edit = QPlainTextEdit()
        self.qualifiers_edit.setPlaceholderText("gene=abc; product=enzima X; note=comentario opcional")
        self.qualifiers_edit.setFixedHeight(90)
        layout.addWidget(self.qualifiers_edit)

        btn_layout = QHBoxLayout()
        self.apply_btn = QPushButton("Aplicar cambios")
        self.reset_btn = QPushButton("Restablecer")
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.reset_btn)
        layout.addLayout(btn_layout)

        self.info_label = QLabel(
            "Consejo: los rangos se interpretan en pares de bases (bp). Mantén el inicio menor que el fin."
        )
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        layout.addStretch(1)

        self.apply_btn.clicked.connect(self._emit_update)
        self.reset_btn.clicked.connect(self._emit_reset)

        self.setDisabled(True)

    # --- Public API ----------------------------------------------------------

    def set_sequence_length(self, length: int):
        self._sequence_length = max(0, length)
        self.start_spin.setMaximum(max(0, length))
        self.end_spin.setMaximum(max(0, length))

    def load_feature(self, index: int, feature):
        self._current_index = index
        if feature is None:
            self.clear()
            return
        self.setEnabled(True)
        self._updating_ui = True
        self.type_edit.setText(feature.type)
        self.start_spin.setValue(int(feature.location.start))
        self.end_spin.setValue(int(feature.location.end))
        strand = feature.location.strand if feature.location.strand in (-1, 1) else 0
        combo_index = max(0, self.strand_combo.findData(strand))
        self.strand_combo.setCurrentIndex(combo_index)
        qualifiers = feature.qualifiers or {}
        qtext = "; ".join(
            f"{key}={values[0] if isinstance(values, list) and values else values}"
            for key, values in qualifiers.items()
        )
        self.qualifiers_edit.setPlainText(qtext)
        self._updating_ui = False

    def clear(self):
        self._current_index = None
        self.setDisabled(True)
        self.type_edit.clear()
        self.start_spin.setValue(0)
        self.end_spin.setValue(0)
        self.strand_combo.setCurrentIndex(0)
        self.qualifiers_edit.clear()

    # --- Internal callbacks --------------------------------------------------

    def _emit_update(self):
        if self._current_index is None or self._updating_ui:
            return
        data = {
            "type": self.type_edit.text().strip(),
            "start": self.start_spin.value(),
            "end": self.end_spin.value(),
            "strand": int(self.strand_combo.currentData()),
            "qualifiers": self._parse_qualifiers(self.qualifiers_edit.toPlainText()),
        }
        self.featureUpdateRequested.emit(self._current_index, data)

    def _emit_reset(self):
        if self._current_index is None:
            return
        self.featureResetRequested.emit(self._current_index)

    # --- Helpers -------------------------------------------------------------

    @staticmethod
    def _parse_qualifiers(text: str):
        qualifiers = {}
        for part in [fragment.strip() for fragment in text.split(";") if fragment.strip()]:
            if "=" in part:
                key, value = part.split("=", 1)
                qualifiers[key.strip()] = [value.strip()]
            else:
                qualifiers[part] = ["true"]
        return qualifiers

