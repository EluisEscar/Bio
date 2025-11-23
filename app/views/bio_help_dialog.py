from PyQt5.QtWidgets import (QDialog,QVBoxLayout,QLabel,QPlainTextEdit,QPushButton,QHBoxLayout,
)
from PyQt5.QtCore import Qt

from ..llm_client import DEFAULT_MODEL, OLLAMA_HOST
from ..workers import LLMQueryWorker, OllamaPullWorker


class BioHelpDialog(QDialog):
    def __init__(self, parent=None, model: str = None, host: str = None):
        """Configura la interfaz y los workers utilizados."""
        super().__init__(parent)
        self.setWindowTitle("Asistente Bioinformático")
        self.model = model or DEFAULT_MODEL
        self.host = host or OLLAMA_HOST
        self._busy = False
        self._query_worker = None
        self._pull_worker = None

        layout = QVBoxLayout(self)

        info = QLabel(
            f"Este asistente utiliza el modelo <b>{self.model}</b> para responder preguntas "
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.question_edit = QPlainTextEdit(self)
        self.question_edit.setPlaceholderText("Escribe tu pregunta aquí…")
        self.question_edit.setFixedHeight(90)
        layout.addWidget(self.question_edit)

        buttons = QHBoxLayout()
        self.ask_button = QPushButton("Preguntar", self)
        self.ask_button.clicked.connect(self.start_query)
        self.pull_button = QPushButton("Descargar modelo", self)
        self.pull_button.clicked.connect(self.start_pull)
        close_button = QPushButton("Cerrar", self)
        close_button.clicked.connect(self.reject)
        buttons.addWidget(self.ask_button)
        buttons.addWidget(self.pull_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self.status_label = QLabel("", self)
        self.status_label.setStyleSheet("color: #444;")
        layout.addWidget(self.status_label)

        self.answer_edit = QPlainTextEdit(self)
        self.answer_edit.setReadOnly(True)
        self.answer_edit.setPlaceholderText("Las respuestas aparecerán aquí.")
        layout.addWidget(self.answer_edit)

    def start_query(self):
        """Lanza un worker para enviar la pregunta actual a Ollama."""
        if self._busy:
            return
        question = self.question_edit.toPlainText().strip()
        if not question:
            self.status_label.setText("Escribe una pregunta antes de enviar.")
            return
        self._set_busy(True, "Consultando modelo…")
        self.answer_edit.clear()
        worker = LLMQueryWorker(question, model=self.model, host=self.host, parent=self)
        worker.completed.connect(self._on_query_completed)
        worker.progress.connect(self._on_query_progress)
        worker.failed.connect(self._on_query_failed)
        worker.finished.connect(self._clear_query_worker)
        self._query_worker = worker
        worker.start()

    def _on_query_progress(self, partial_text: str):
        """Actualiza la respuesta mientras el modelo va generando texto."""
        self.answer_edit.setPlainText(partial_text)
        # Desplaza el scroll al final para que se vea lo último generado
        self.answer_edit.verticalScrollBar().setValue(
            self.answer_edit.verticalScrollBar().maximum()
        )

    def start_pull(self):
        """Descarga el modelo seleccionado usando `ollama pull`."""
        if self._busy:
            return
        self._set_busy(True, f"Descargando modelo {self.model}…")
        self.answer_edit.clear()
        worker = OllamaPullWorker(self.model, parent=self)
        worker.progress.connect(self._on_pull_progress)
        worker.completed.connect(self._on_pull_completed)
        worker.failed.connect(self._on_query_failed)
        worker.finished.connect(self._clear_pull_worker)
        self._pull_worker = worker
        worker.start()

    def _on_query_completed(self, text: str):
        """Renderiza la respuesta recibida y habilita la UI nuevamente."""
        self.answer_edit.setPlainText(text)
        self._set_busy(False, "Completado.")

    def _on_query_failed(self, message: str):
        """Presenta el mensaje de error cuando el worker falla."""
        self.answer_edit.setPlainText(message)
        self._set_busy(False, "Ocurrió un problema.")

    def _on_pull_progress(self, line: str):
        """Agrega cada línea de progreso emitida durante la descarga."""
        current = self.answer_edit.toPlainText()
        new_text = f"{current}\n{line}".strip()
        self.answer_edit.setPlainText(new_text)
        self.answer_edit.verticalScrollBar().setValue(self.answer_edit.verticalScrollBar().maximum())

    def _on_pull_completed(self, message: str):
        """Indica que la descarga terminó con éxito."""
        self._set_busy(False, message)

    def _clear_query_worker(self):
        """Libera la referencia al worker de consulta."""
        self._query_worker = None

    def _clear_pull_worker(self):
        """Libera la referencia al worker de descarga."""
        self._pull_worker = None

    def _set_busy(self, busy: bool, message: str = ""):
        """Habilita o bloquea los botones y actualiza el mensaje de estado."""
        self._busy = busy
        self.ask_button.setEnabled(not busy)
        self.pull_button.setEnabled(not busy)
        self.status_label.setText(message)
