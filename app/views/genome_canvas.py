from PyQt5.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from ..event_bus import bus


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
            self.toolbar = None

        layout = QVBoxLayout(self)
        if self.toolbar:
            layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.record = None
        self.selected_index = None
        self._press_event = None
        self._dragging = False
        self._feature_regions = []
        self._last_xlim = None
        self._palette = [
            "#2563EB", "#16A34A", "#F97316", "#9333EA", "#EA580C",
            "#0EA5E9", "#D97706", "#EF4444", "#059669", "#7C3AED"
        ]
        self._type_colors = {}
        self._palette_idx = 0
        self._base_colors = {
            "A": "#F59E0B",
            "T": "#38BDF8",
            "C": "#22C55E",
            "G": "#EF4444",
        }
        self._sequence_threshold = 260

        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)

    # --- Lifecycle -----------------------------------------------------------

    def update_from_record(self, record):
        self.record = record
        if record is None:
            self.selected_index = None
            self._last_xlim = None
        self._redraw()

    # --- Public API ----------------------------------------------------------

    def select_feature(self, index, center=False):
        if self.record is None:
            return
        self.selected_index = index
        if center and index is not None and index < len(self.record.features):
            feat = self.record.features[index]
            start = int(feat.location.start)
            end = int(feat.location.end)
            midpoint = (start + end) // 2
            span = max(200, end - start)
            self.center_on(midpoint, span)
        self._redraw()

    def zoom(self, factor):
        if self.record is None or factor <= 0:
            return
        x0, x1 = self.ax.get_xlim()
        cx = (x0 + x1) / 2.0
        width = (x1 - x0) * factor
        width = max(50, min(width, len(self.record.seq)))
        new_left = cx - width / 2.0
        new_right = cx + width / 2.0
        self._apply_xlim(new_left, new_right, repaint=False)
        self._redraw()

    def reset_view(self):
        if not self.record:
            return
        self._apply_xlim(0, len(self.record.seq))
        self._redraw()

    def center_on(self, position, span):
        if self.record is None:
            return
        L = len(self.record.seq)
        half = max(25, span // 2)
        left = position - half
        right = position + half
        self._apply_xlim(left, right)
        self._redraw()

    def pan_to(self, left, span=None):
        if self.record is None:
            return
        if span is None:
            x0, x1 = self.ax.get_xlim()
            span = x1 - x0
        right = left + span
        self._apply_xlim(left, right, repaint=False)
        self._redraw()

    # --- Drawing -------------------------------------------------------------

    def _redraw(self):
        prev_xlim = self._last_xlim
        self.ax.clear()
        if not self.record:
            self.canvas.draw_idle()
            return

        L = len(self.record.seq)
        if prev_xlim is None:
            self._apply_xlim(0, L, repaint=False)
        else:
            self.ax.set_xlim(prev_xlim)
        self.ax.set_ylim(0, 10)
        self.ax.set_yticks([])
        self.ax.set_xlabel("Posición (bp)")
        self.ax.set_title(self.record.description or self.record.id or "")
        self.ax.axhline(5, color="#CBD5F5", linewidth=0.8, linestyle="--", zorder=1)

        self._feature_regions = []
        default_height = 1.6
        features = self.record.features or []
        for idx, feature in enumerate(features):
            start = int(feature.location.start)
            end = int(feature.location.end)
            strand = feature.location.strand if feature.location.strand in (-1, 1) else 0
            y_center = 6.2 if strand == 1 else 3.8 if strand == -1 else 5
            color = self._color_for_type(feature.type)
            linewidth = 1.4
            alpha = 0.25
            if idx == self.selected_index:
                linewidth = 2.6
                alpha = 0.45
            width = max(1, end - start)
            rect = Rectangle(
                (start, y_center - default_height / 2),
                width,
                default_height,
                facecolor=color,
                alpha=alpha,
                edgecolor=color,
                linewidth=linewidth,
                zorder=2,
            )
            self.ax.add_patch(rect)

            label = feature.type
            qualifiers = feature.qualifiers or {}
            gene_name = self._first_value(qualifiers, "gene") or self._first_value(qualifiers, "product")
            if gene_name:
                label += f" ({gene_name})"
            self.ax.text(
                start,
                y_center + default_height / 2 + 0.25,
                label,
                fontsize=8,
                va="bottom",
                color="#1F2937",
                zorder=3,
            )
            self._feature_regions.append((idx, start, end))

        self._draw_sequence_letters()
        self.canvas.draw_idle()

    # --- Matplotlib interactions --------------------------------------------

    def _on_scroll(self, event):
        if self.record is None or event.xdata is None:
            return
        cur_xlim = self.ax.get_xlim()
        xdata = event.xdata
        scale_factor = 1.2 if event.button == "up" else 1 / 1.2
        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        relx = (xdata - cur_xlim[0]) / (cur_xlim[1] - cur_xlim[0])
        new_left = xdata - new_width * relx
        new_right = new_left + new_width
        self._apply_xlim(new_left, new_right, repaint=False)
        self._redraw()

    def _on_press(self, event):
        if event.button == 1:
            self._press_event = event
            self._dragging = False

    def _on_release(self, event):
        if event.button != 1:
            return
        if self._press_event and not self._dragging and event.xdata is not None:
            feature_idx = self._feature_at(event.xdata)
            if feature_idx is not None:
                self.selected_index = feature_idx
                bus.publish("feature_selected", index=feature_idx)
                self._redraw()
        self._press_event = None
        self._dragging = False

    def _on_motion(self, event):
        if self._press_event is None or event.xdata is None:
            return
        if abs(event.x - self._press_event.x) > 3:
            self._dragging = True
        dx = event.xdata - self._press_event.xdata
        x0, x1 = self.ax.get_xlim()
        self.ax.set_xlim(x0 - dx, x1 - dx)
        if self.record:
            L = len(self.record.seq)
            x0, x1 = self.ax.get_xlim()
            width = x1 - x0
            x0 = max(0, min(x0, L - width))
            x1 = x0 + width
            self.ax.set_xlim(x0, x1)
            self._last_xlim = (x0, x1)
        self._redraw()

    # --- Utilities -----------------------------------------------------------

    def _apply_xlim(self, left, right, repaint=False):
        if self.record is None:
            return
        L = len(self.record.seq)
        width = right - left
        if width <= 0:
            width = L
        left = max(0, left)
        right = min(L, left + width)
        if right - left < 50:
            center = (left + right) / 2
            half = 25
            left = max(0, center - half)
            right = min(L, center + half)
        self.ax.set_xlim(left, right)
        self._last_xlim = (left, right)
        bus.publish("view_changed", left=left, right=right, length=L)
        if repaint:
            self.canvas.draw_idle()

    def _draw_sequence_letters(self):
        if self.record is None:
            return
        x0, x1 = self.ax.get_xlim()
        window = x1 - x0
        if window > self._sequence_threshold:
            return
        sequence = str(self.record.seq)
        if not sequence:
            return
        start = max(0, int(x0))
        end = min(len(sequence), int(x1) + 1)
        y_bottom = 0.7
        height = 1.4
        for pos in range(start, end):
            base = sequence[pos].upper()
            color = self._base_colors.get(base, "#CBD5F5")
            rect = Rectangle(
                (pos, y_bottom),
                1,
                height,
                facecolor=color,
                edgecolor="none",
                alpha=0.35,
                zorder=1.5,
            )
            self.ax.add_patch(rect)
            self.ax.text(
                pos + 0.5,
                y_bottom + height / 2,
                base,
                fontsize=8,
                color="#111827",
                ha="center",
                va="center",
                zorder=3.5,
                clip_on=True,
            )

    def _feature_at(self, xdata):
        for idx, start, end in self._feature_regions:
            if start <= xdata <= end:
                return idx
        return None

    def _color_for_type(self, feature_type):
        if feature_type not in self._type_colors:
            color = self._palette[self._palette_idx % len(self._palette)]
            self._type_colors[feature_type] = color
            self._palette_idx += 1
        return self._type_colors[feature_type]

    @staticmethod
    def _first_value(qualifiers, key):
        val = qualifiers.get(key)
        if isinstance(val, list) and val:
            return val[0]
        if isinstance(val, str):
            return val
        return None
