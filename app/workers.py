"""Hilos auxiliares utilizados por la interfaz para tareas costosas."""
import subprocess
from typing import Optional, Dict, Any
from PyQt5.QtCore import QThread, pyqtSignal
from Bio import SeqIO

from .io import fetch_genbank_from_entrez
from .llm_client import generate_bio_help, DEFAULT_MODEL, OLLAMA_HOST


class RecordLoadWorker(QThread):
    """Carga registros GenBank desde disco o Entrez sin bloquear la UI."""

    completed = pyqtSignal(object, dict)
    failed = pyqtSignal(str, dict)

    def __init__(
        self,
        *,
        mode: str,
        path: Optional[str] = None,
        entrez_params: Optional[Dict[str, Any]] = None,
        parent=None,
    ):
        """Recibe el modo de carga y parámetros opcionales."""
        super().__init__(parent)
        self.mode = mode
        self.path = path
        self.entrez_params = entrez_params or {}

    def run(self):
        """Ejecuta la lectura concreta y emite las señales correspondientes."""
        try:
            if self.mode == "file":
                if not self.path:
                    raise ValueError("No se especificó una ruta de archivo para la carga.")
                with open(self.path, "r") as handle:
                    record = SeqIO.read(handle, "genbank")
                info = {"mode": self.mode, "path": self.path}
            elif self.mode == "entrez":
                record, extra = fetch_genbank_from_entrez(**self.entrez_params)
                info = {"mode": self.mode, **extra}
            else:
                raise ValueError(f"Modo de carga no soportado: {self.mode}")
        except Exception as exc:
            info = {"mode": self.mode, "path": self.path, **self.entrez_params}
            self.failed.emit(str(exc), info)
            return

        self.completed.emit(record, info)


class LLMQueryWorker(QThread):
    """Consulta un modelo de Ollama en segundo plano."""

    completed = pyqtSignal(str)
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, question: str, *, model: Optional[str] = None, host: Optional[str] = None, parent=None):
        """Guarda la pregunta y el modelo/host que se utilizarán."""
        super().__init__(parent)
        self.question = question
        self.model = model or DEFAULT_MODEL
        self.host = host or OLLAMA_HOST

    def run(self):
        """Realiza la petición HTTP en streaming y entrega la respuesta o el error."""
        try:
            text = generate_bio_help(
                self.question,
                model=self.model,
                host=self.host,
                on_chunk=lambda chunk: self.progress.emit(chunk),
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        self.completed.emit(text)


class OllamaPullWorker(QThread):
    """Ejecuta `ollama pull` para descargar modelos desde la UI."""

    progress = pyqtSignal(str)
    completed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, model: str, parent=None):
        """Recibe el nombre del modelo a descargar."""
        super().__init__(parent)
        self.model = model

    def run(self):
        """Invoca el comando de descarga y manda las líneas a la interfaz."""
        cmd = ["ollama", "pull", self.model]
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except FileNotFoundError:
            self.failed.emit(
                "No se encontró el comando `ollama`. Instálalo desde https://ollama.com/download."
            )
            return
        except Exception as exc:
            self.failed.emit(f"No se pudo iniciar la descarga: {exc}")
            return

        lines = []
        try:
            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.strip()
                if line:
                    self.progress.emit(line)
                    lines.append(line)
                if self.isInterruptionRequested():
                    process.terminate()
                    self.failed.emit("Descarga interrumpida.")
                    return
            exit_code = process.wait()
        except Exception as exc:
            process.kill()
            self.failed.emit(f"Error durante la descarga: {exc}")
            return

        if exit_code != 0:
            last = lines[-1] if lines else "Fallo al descargar el modelo."
            self.failed.emit(last)
            return

        summary = lines[-1] if lines else f"Modelo {self.model} descargado."
        self.completed.emit(summary)
