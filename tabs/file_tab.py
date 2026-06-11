import logging
import threading
import time
from collections import deque
from queue import Empty, Queue

import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl

from PyQt6.QtCore import QObject, QThread, QTimer
from PyQt6.QtWidgets import (
    QFileDialog, QGridLayout, QHBoxLayout, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from logic.doa_processor import DoaProcessor
from logic.filters import HighPassFilter
from logic.loader import AudioChunk
from logic.stft_processor import StftProcessor
from logic.wav_loader import WavLoader

log = logging.getLogger(__name__)

# ── Pipeline config ────────────────────────────────────────────────────────────

SAMPLE_RATE    = 44100
CHUNK_SIZE     = 8192
NPERSEG        = 512
NOVERLAP       = 256
HP_CUTOFF_HZ   = 400
INNER_IDX      = slice(4, 8)
DOA_FREQ_RANGE = [400, 808]

L_INNER = np.array([
    [-0.075,  0.075, -0.075,  0.075],
    [-0.075, -0.075,  0.075,  0.075],
    [ 0.000,  0.000,  0.000,  0.000],
])

WAVEFORM_BUFFER_SIZE = SAMPLE_RATE * 2  # 2 seconds of samples
SPEC_MAX_COLS        = 200              # scrolling spectrogram width in STFT frames
AZIMUTH_HISTORY      = 20              # dots kept on sphere
SPHERE_RADIUS        = 1.0

CHANNEL_COLORS = ['r', 'g', 'b', 'c', 'm', 'y', 'w', (255, 128, 0)]


# ── Pipeline helpers ───────────────────────────────────────────────────────────

def spy(upstream, queue):
    """Pass-through generator: enqueues each item and yields it unchanged."""
    for item in upstream:
        queue.put(item)
        yield item


def extract_channels(upstream, ch_slice):
    """Yield AudioChunks containing only the selected channel slice."""
    for chunk in upstream:
        yield AudioChunk(
            data=chunk.data[:, ch_slice],
            sampling_rate=chunk.sampling_rate,
            timestamp=chunk.timestamp,
        )


# ── Pipeline worker ────────────────────────────────────────────────────────────

class PipelineWorker(QObject):
    """
    Runs the full audio pipeline in a background QThread.

    Queues receive items at each stage so the UI can display all intermediate
    results independently, following the same spy/queue pattern as main_test.py.
    """

    def __init__(self, file_path, raw_q, filtered_q, stft_q, doa_q, pause_event):
        super().__init__()
        self.file_path  = file_path
        self.raw_q      = raw_q
        self.filtered_q = filtered_q
        self.stft_q     = stft_q
        self.doa_q      = doa_q
        self._pause     = pause_event
        self.running    = True

    def run(self):
        hp   = HighPassFilter(cutoff_hz=HP_CUTOFF_HZ, sampling_rate=SAMPLE_RATE, order=4)
        stft = StftProcessor(nperseg=NPERSEG, noverlap=NOVERLAP)
        doa  = DoaProcessor(mic_locs=L_INNER, sampling_rate=SAMPLE_RATE,
                            nfft=NPERSEG, freq_range=DOA_FREQ_RANGE)

        chunk_duration = CHUNK_SIZE / SAMPLE_RATE

        # Build the pipeline with spy taps at each stage
        raw_stream      = WavLoader(self.file_path, chunk_size=CHUNK_SIZE).stream()
        raw_stream      = spy(raw_stream, self.raw_q)

        filtered_stream = hp.process(raw_stream)
        inner_stream    = extract_channels(filtered_stream, INNER_IDX)
        inner_stream    = spy(inner_stream, self.filtered_q)

        stft_stream     = stft.process(inner_stream)
        stft_stream     = spy(stft_stream, self.stft_q)

        doa_stream      = doa.process(stft_stream)

        for doa_chunk in doa_stream:
            if not self.running:
                break
            self.doa_q.put(doa_chunk)
            self._pause.wait()           # blocks here when paused
            time.sleep(chunk_duration)   # pace output to real-time audio speed

        log.info("PipelineWorker: finished streaming '%s'", self.file_path)

    def stop(self):
        self.running = False
        self._pause.set()  # unblock if currently paused


# ── Waveform plot ──────────────────────────────────────────────────────────────

class WaveformPlot(pg.PlotWidget):
    """
    Scrolling multi-channel waveform. Shows the last 2 seconds of audio.

    channel_offset adjusts channel label numbers (e.g. 4 → labels start at CH5).
    """

    def __init__(self, title, channel_offset=0, parent=None):
        super().__init__(parent, title=title)
        self._channel_offset = channel_offset
        self.setBackground('w')
        self.showGrid(x=True, y=True)
        self.setLabel('left', 'Amplitude')
        self.setLabel('bottom', 'Time', units='s')
        self.addLegend()
        self.setYRange(-1.0, 1.0)
        self._buffers: list[deque] = []
        self._curves:  list[pg.PlotDataItem] = []

    def _ensure_channels(self, n_channels):
        while len(self._curves) < n_channels:
            ch    = len(self._curves)
            label = ch + self._channel_offset
            color = CHANNEL_COLORS[label % len(CHANNEL_COLORS)]
            curve = self.plot(pen=pg.mkPen(color=color, width=1),
                              name=f"CH{label + 1}")
            self._curves.append(curve)
            self._buffers.append(deque(maxlen=WAVEFORM_BUFFER_SIZE))

    def update_chunk(self, chunk: AudioChunk):
        n = chunk.data.shape[1]
        self._ensure_channels(n)
        for ch in range(n):
            self._buffers[ch].extend(chunk.data[:, ch])
            buf = np.array(self._buffers[ch])
            x   = np.arange(len(buf)) / SAMPLE_RATE
            self._curves[ch].setData(x, buf)

    def clear_buffers(self):
        for buf in self._buffers:
            buf.clear()
        for curve in self._curves:
            curve.setData([], [])


# ── Spectrogram ────────────────────────────────────────────────────────────────

class SpectrogramWidget(pg.PlotWidget):
    """
    Scrolling STFT spectrogram in dB. Displays channel 0 of whatever
    StftChunk it receives (the first inner mic, CH5).
    """

    def __init__(self, parent=None):
        super().__init__(parent, title="Spectrogram — CH5 (HP-filtered, inner mic)")
        self.setBackground('k')
        self.setLabel('left', 'Frequency', units='Hz')
        self.setLabel('bottom', 'Time frames')

        self._img = pg.ImageItem()
        self.addItem(self._img)
        self._img.setColorMap(pg.colormap.get('viridis'))

        self._cols:  list[np.ndarray] = []
        self._freqs: np.ndarray | None = None

    def update_chunk(self, chunk):
        # magnitudes shape: (n_ch, n_freqs, n_frames) — use first inner mic
        mag = np.abs(chunk.magnitudes[0])        # (n_freqs, n_frames)
        db  = 20.0 * np.log10(mag + 1e-9)

        self._cols.extend(db[:, t] for t in range(mag.shape[1]))
        if len(self._cols) > SPEC_MAX_COLS:
            del self._cols[:-SPEC_MAX_COLS]

        if self._freqs is None:
            self._freqs = chunk.freqs

        img_data = np.stack(self._cols, axis=0)  # (time_cols, n_freqs)
        self._img.setImage(img_data, autoLevels=True)

        if self._freqs is not None and len(self._freqs) > 1:
            self._img.setRect(pg.QtCore.QRectF(
                0.0, float(self._freqs[0]),
                float(img_data.shape[0]),
                float(self._freqs[-1] - self._freqs[0]),
            ))

    def clear_buffers(self):
        self._cols.clear()
        self._freqs = None
        self._img.clear()


# ── Azimuth sphere ─────────────────────────────────────────────────────────────

class AzimuthSphereWidget(gl.GLViewWidget):
    """
    3D sphere showing numbered azimuth prediction history.

    Dots are placed on the equator at each predicted azimuth angle.
    Older dots fade; newer dots are brighter and larger.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCameraPosition(distance=4)

        sphere_mesh = gl.MeshData.sphere(rows=20, cols=20)
        sphere_item = gl.GLMeshItem(
            meshdata=sphere_mesh,
            smooth=True, drawFaces=False, drawEdges=True,
            edgeColor=(0.3, 0.3, 0.3, 0.4),
        )
        self.addItem(sphere_item)

        # Equator guide ring
        theta    = np.linspace(0, 2 * np.pi, 64)
        ring_pts = np.column_stack([np.cos(theta), np.sin(theta), np.zeros(64)])
        self.addItem(gl.GLLinePlotItem(
            pos=ring_pts, color=(0.5, 0.5, 0.5, 0.5),
            width=1, mode='line_strip', antialias=True,
        ))

        # Cardinal direction labels: 90°=N, 0°=E, 270°=S, 180°=W
        for deg, label in [(90, 'N'), (0, 'E'), (270, 'S'), (180, 'W')]:
            az = np.deg2rad(deg)
            self.addItem(gl.GLTextItem(
                pos=np.array([np.cos(az) * SPHERE_RADIUS * 1.35,
                              np.sin(az) * SPHERE_RADIUS * 1.35,
                              0.0]),
                text=f"{label} {deg}°",
                color='g',
            ))

        self._history: deque[float] = deque(maxlen=AZIMUTH_HISTORY)
        self._scatter = gl.GLScatterPlotItem()
        self.addItem(self._scatter)
        self._text_items: list[gl.GLTextItem] = []

    def update_chunk(self, chunk):
        self._history.append(chunk.azimuth_rad)
        history = list(self._history)
        n       = len(history)

        pos = np.array([
            [np.cos(az) * SPHERE_RADIUS, np.sin(az) * SPHERE_RADIUS, 0.0]
            for az in history
        ])

        # Colour fades from dim orange (old) to bright white (newest)
        colors = np.zeros((n, 4), dtype=float)
        for i in range(n):
            t         = (i + 1) / n
            colors[i] = (1.0, 0.5 + 0.5 * t, 0.0, 0.3 + 0.7 * t)

        self._scatter.setData(
            pos=pos,
            color=colors,
            size=np.linspace(4, 14, n),
        )

        # Sequence number text labels
        for item in self._text_items:
            self.removeItem(item)
        self._text_items.clear()

        for i, (az, p) in enumerate(zip(history, pos)):
            label_pos = p * 1.18
            item = gl.GLTextItem(
                pos=np.array([label_pos[0], label_pos[1], 0.08]),
                text=f"{i + 1}. {np.rad2deg(az):.0f}°",
                color='w',
            )
            self.addItem(item)
            self._text_items.append(item)

    def clear_buffers(self):
        self._history.clear()
        self._scatter.setData(pos=np.zeros((0, 3)))
        for item in self._text_items:
            self.removeItem(item)
        self._text_items.clear()


# ── File tab ───────────────────────────────────────────────────────────────────

class FileTab(QWidget):
    """
    Debug tab: open a multichannel WAV, run the DOA pipeline, and watch all
    four stages animate in real time — raw waveform, filtered waveform,
    spectrogram, and a 3D azimuth sphere.
    """

    _STOPPED = "stopped"
    _PLAYING = "playing"
    _PAUSED  = "paused"

    def __init__(self, parent=None):
        super().__init__(parent)

        self._file_path: str | None = None
        self._state = self._STOPPED

        self._pause_event = threading.Event()
        self._pause_event.set()

        self._raw_q      = Queue()
        self._filtered_q = Queue()
        self._stft_q     = Queue()
        self._doa_q      = Queue()

        self._thread: QThread | None = None
        self._worker: PipelineWorker | None = None

        self._build_ui()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(50)
        self._poll_timer.timeout.connect(self._poll_queues)
        self._poll_timer.start()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)

        file_row = QHBoxLayout()
        self._btn_open  = QPushButton("Open")
        self._line_path = QLineEdit()
        self._line_path.setReadOnly(True)
        self._line_path.setPlaceholderText("No file selected…")
        file_row.addWidget(self._btn_open)
        file_row.addWidget(self._line_path)
        root.addLayout(file_row)

        ctrl_row = QHBoxLayout()
        self._btn_play  = QPushButton("Play")
        self._btn_reset = QPushButton("Reset")
        ctrl_row.addWidget(self._btn_play)
        ctrl_row.addWidget(self._btn_reset)
        ctrl_row.addStretch()
        root.addLayout(ctrl_row)

        self._raw_plot      = WaveformPlot("Raw Waveform (all channels)")
        self._filtered_plot = WaveformPlot(
            "HP-Filtered Waveform (inner CH5–8, ≥400 Hz)", channel_offset=4
        )
        self._spectrogram   = SpectrogramWidget()
        self._sphere        = AzimuthSphereWidget()

        grid = QGridLayout()
        grid.addWidget(self._raw_plot,      0, 0)
        grid.addWidget(self._filtered_plot, 0, 1)
        grid.addWidget(self._spectrogram,   1, 0)
        grid.addWidget(self._sphere,        1, 1)
        root.addLayout(grid)

        self._btn_open.clicked.connect(self._on_open)
        self._btn_play.clicked.connect(self._on_play_pause)
        self._btn_reset.clicked.connect(self._on_reset)

    # ── Button handlers ────────────────────────────────────────────────────────

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open WAV File", "", "WAV Files (*.wav)"
        )
        if not path:
            return
        self._on_reset()
        self._file_path = path
        self._line_path.setText(path)

    def _on_play_pause(self):
        if self._file_path is None:
            return

        if self._state == self._STOPPED:
            self._start_worker()
            self._state = self._PLAYING
            self._btn_play.setText("Pause")

        elif self._state == self._PLAYING:
            self._pause_event.clear()
            self._state = self._PAUSED
            self._btn_play.setText("Play")

        elif self._state == self._PAUSED:
            self._pause_event.set()
            self._state = self._PLAYING
            self._btn_play.setText("Pause")

    def _on_reset(self):
        self._stop_worker()
        self._raw_q      = Queue()
        self._filtered_q = Queue()
        self._stft_q     = Queue()
        self._doa_q      = Queue()
        self._raw_plot.clear_buffers()
        self._filtered_plot.clear_buffers()
        self._spectrogram.clear_buffers()
        self._sphere.clear_buffers()
        self._state = self._STOPPED
        self._btn_play.setText("Play")

    # ── Worker lifecycle ───────────────────────────────────────────────────────

    def _start_worker(self):
        self._pause_event.set()
        self._thread = QThread(self)
        self._worker = PipelineWorker(
            file_path   = self._file_path,
            raw_q       = self._raw_q,
            filtered_q  = self._filtered_q,
            stft_q      = self._stft_q,
            doa_q       = self._doa_q,
            pause_event = self._pause_event,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def _stop_worker(self):
        if self._worker:
            self._worker.stop()
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self._worker = None
        self._thread = None

    # ── Queue polling ──────────────────────────────────────────────────────────

    def _drain(self, queue, callback):
        while True:
            try:
                callback(queue.get_nowait())
            except Empty:
                break

    def _poll_queues(self):
        self._drain(self._raw_q,      self._raw_plot.update_chunk)
        self._drain(self._filtered_q, self._filtered_plot.update_chunk)
        self._drain(self._stft_q,     self._spectrogram.update_chunk)
        self._drain(self._doa_q,      self._sphere.update_chunk)

    # ── Cleanup ────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._poll_timer.stop()
        self._stop_worker()
        super().closeEvent(event)
