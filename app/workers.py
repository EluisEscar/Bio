from typing import Optional, Dict, Any
from PyQt5.QtCore import QThread, pyqtSignal
from Bio import SeqIO

from .io import fetch_genbank_from_entrez


class RecordLoadWorker(QThread):
    """
    Hilo auxiliar para cargar registros GenBank desde disco o NCBI sin bloquear la UI.
    """

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
        super().__init__(parent)
        self.mode = mode
        self.path = path
        self.entrez_params = entrez_params or {}

    def run(self):
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
