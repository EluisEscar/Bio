from PyQt5.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

class GenomeCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = None
        try:
            from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavToolbar
            self.toolbar = NavToolbar(self.canvas, self)
        except Exception:
            pass

        layout = QVBoxLayout(self)
        if self.toolbar:
            layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.record = None
        self._press_event = None
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)

    def update_from_record(self, record):
        self.record = record
        self._redraw()

    def _redraw(self):
        self.ax.clear()
        if not self.record:
            self.canvas.draw_idle()
            return
        L = len(self.record.seq)
        self.ax.set_xlim(0, L)
        self.ax.set_ylim(0, 10)
        self.ax.set_yticks([])
        self.ax.set_xlabel("Position (bp)")
        self.ax.set_title(self.record.description or self.record.id)

        # Dibujar features como rectángulos
        y = 5
        h = 3
        for i, f in enumerate(self.record.features or []):
            start = int(f.location.start)
            end = int(f.location.end)
            strand = f.location.strand if f.location.strand in (-1, 1) else 0
            # No elegir colores específicos según las reglas
            rect = plt.Rectangle((start, y - h/2 + (strand*0.5)), end - start, h, fill=False)
            self.ax.add_patch(rect)
            label = f.type
            try:
                if "gene" in f.qualifiers:
                    label += f" ({f.qualifiers['gene'][0]})"
                elif "product" in f.qualifiers:
                    label += f" ({f.qualifiers['product'][0]})"
            except Exception:
                pass
            self.ax.text(start, y + (strand*1.2), label, fontsize=8, va="bottom", rotation=0)

        self.canvas.draw_idle()

    # Zoom con rueda
    def _on_scroll(self, event):
        if self.record is None or event.xdata is None:
            return
        cur_xlim = self.ax.get_xlim()
        xdata = event.xdata
        scale_factor = 1.2 if event.button == 'up' else 1/1.2
        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        relx = (xdata - cur_xlim[0]) / (cur_xlim[1] - cur_xlim[0])
        new_left = xdata - new_width * relx
        new_right = new_left + new_width
        # Limitar a los bordes
        new_left = max(0, new_left)
        new_right = min(len(self.record.seq), new_right)
        self.ax.set_xlim(new_left, new_right)
        self.canvas.draw_idle()

    # Pan con arrastre
    def _on_press(self, event):
        if event.button == 1:
            self._press_event = event

    def _on_release(self, event):
        self._press_event = None

    def _on_motion(self, event):
        if self._press_event is None or event.xdata is None:
            return
        dx = event.xdata - self._press_event.xdata
        x0, x1 = self.ax.get_xlim()
        self.ax.set_xlim(x0 - dx, x1 - dx)
        # Clamp
        if self.record:
            L = len(self.record.seq)
            x0, x1 = self.ax.get_xlim()
            w = x1 - x0
            x0 = max(0, min(x0, L - w))
            x1 = x0 + w
            self.ax.set_xlim(x0, x1)
        self.canvas.draw_idle()
