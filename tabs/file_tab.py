import logging
import os
import numpy as np
from scipy.io import wavfile
import pyqtgraph as pg
import sounddevice as sd

from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLineEdit, QPushButton, 
    QWidget, QVBoxLayout, QLabel, QSlider, QComboBox
)
from PyQt6.QtCore import Qt, QTimer

class FileTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Audio Data Variables
        self.fs = None
        self.data = None
        self.duration = 0.0
        self.current_sample_idx = 0
        
        # Audio Playback Stream
        self.stream = None
        
        # Timer to update UI during playback
        self.ui_timer = QTimer()
        self.ui_timer.setInterval(30)  # Update UI roughly ~33 FPS
        self.ui_timer.timeout.connect(self.update_playback_ui)

        # 1. File Selection UI
        file_container = QWidget()
        file_layout = QHBoxLayout(file_container)
        file_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_file = QLabel("WAV File:")
        self.line_file = QLineEdit()
        self.line_file.setReadOnly(True)
        self.btn_browse = QPushButton("Browse...")
        file_layout.addWidget(self.lbl_file)
        file_layout.addWidget(self.line_file)
        file_layout.addWidget(self.btn_browse)
        self.layout.addWidget(file_container)
        
        # 2. Plotting Area
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)
        self.layout.addWidget(self.plot_widget)
        
        # 3. Playback Head (Vertical line in graph)
        self.playback_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('k', width=2, style=Qt.PenStyle.DashLine))
        
        # 4. Media Player Controls (Timeline Slider)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)  # High resolution slider (0.0% to 100.0%)
        self.slider.sliderMoved.connect(self.on_slider_moved)
        self.layout.addWidget(self.slider)
        
        # 5. Buttons & Channel Selector Layout
        controls_container = QWidget()
        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_play = QPushButton("Play")
        self.btn_pause = QPushButton("Pause")
        self.btn_reset = QPushButton("Reset")
        
        self.channel_selector = QComboBox()
        self.channel_selector.addItem("All Channels (Mixed Mono)")
        self.channel_selector.currentIndexChanged.connect(self.on_channel_changed)
        
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.btn_pause)
        controls_layout.addWidget(self.btn_reset)
        controls_layout.addWidget(QLabel("Play Channel:"))
        controls_layout.addWidget(self.channel_selector)
        controls_layout.addStretch()
        
        self.layout.addWidget(controls_container)
        
        # Signal Connections
        self.btn_browse.clicked.connect(self.on_browse_file)
        self.btn_play.clicked.connect(self.start_audio)
        self.btn_pause.clicked.connect(self.pause_audio)
        self.btn_reset.clicked.connect(self.reset_audio)

    def on_browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Audio File", "", "WAV Audio Files (*.wav)")
        if file_path:
            self.stop_stream()
            self.line_file.setText(file_path)
            self.fs, self.data = FileTab.load_wav(file_path)
            
            if self.data is not None:
                n_samples, n_channels = self.data.shape
                self.duration = n_samples / self.fs
                self.current_sample_idx = 0
                
                # Update Channel Dropdown
                self.channel_selector.clear()
                self.channel_selector.addItem("All Channels (Mixed Mono)")
                for i in range(n_channels):
                    self.channel_selector.addItem(f"Channel {i+1}")
                
                self.plot_data()
                self.update_playback_ui()
                
                logging.info(
                    f"Successfully loaded: {os.path.basename(file_path)}\n"
                    f"  Sampling rate      : {self.fs} Hz\n"
                    f"  Number of channels : {n_channels}\n"
                    f"  Duration           : {self.duration:.2f} seconds"
                )

    def plot_data(self):
        self.plot_widget.clear()
        self.plot_widget.addLegend()
        
        n_samples, n_channels = self.data.shape
        time = np.arange(n_samples) / self.fs
        colors = ['r', 'b', 'g', 'c', 'm', 'y']
        
        for i in range(n_channels):
            color = colors[i % len(colors)]
            self.plot_widget.plot(
                time, self.data[:, i], 
                pen=pg.mkPen(color=color, width=1), 
                name=f"Channel {i+1}"
            )
        
        # Re-add playback line on top of the waveforms
        self.plot_widget.addItem(self.playback_line)
        self.playback_line.setValue(0)

    def get_selected_audio_mono(self):
        """Extracts the selected channel data or mixes all down to mono."""
        if self.data is None:
            return None
        
        idx = self.channel_selector.currentIndex()
        if idx <= 0:  # Mixed Mono (Average of all channels)
            return np.mean(self.data, axis=1).astype(self.data.dtype)
        else:  # Specific Channel (0-indexed adjustment)
            return self.data[:, idx - 1]

    def start_audio(self):
        if self.data is None:
            return
        
        if self.stream is None or not self.stream.active:
            mono_data = self.get_selected_audio_mono()
            
            # Setup sounddevice callback for seamless playback
            def callback(outdata, frames, time, status):
                if status:
                    print(status)
                
                start = self.current_sample_idx
                end = start + frames
                
                if start >= len(mono_data):
                    outdata.fill(0)
                    self.ui_timer.stop()
                    return
                
                if end > len(mono_data):
                    remainder = len(mono_data) - start
                    outdata[:remainder, 0] = mono_data[start:]
                    outdata[remainder:, 0] = 0
                    self.current_sample_idx = len(mono_data)
                else:
                    outdata[:, 0] = mono_data[start:end]
                    self.current_sample_idx = end

            self.stream = sd.OutputStream(
                samplerate=self.fs, 
                channels=1, 
                dtype=self.data.dtype, 
                callback=callback
            )
            self.stream.start()
            self.ui_timer.start()

    def pause_audio(self):
        self.stop_stream()

    def reset_audio(self):
        self.stop_stream()
        self.current_sample_idx = 0
        self.update_playback_ui()

    def on_channel_changed(self):
        """If user changes channel while playing, restart stream to apply."""
        if self.stream and self.stream.active:
            self.stop_stream()
            self.start_audio()

    def on_slider_moved(self, value):
        """Allows clicking/dragging slider to scrub through the track."""
        if self.data is None:
            return
        fraction = value / 1000.0
        self.current_sample_idx = int(fraction * len(self.data))
        self.update_playback_ui()

    def update_playback_ui(self):
        """Updates the moving vertical line and timeline slider."""
        if self.data is None or self.fs is None:
            return
        
        current_time = self.current_sample_idx / self.fs
        
        # Move the pyqtgraph line
        self.playback_line.setValue(current_time)
        
        # Move slider without triggering on_slider_moved loop
        self.slider.blockSignals(True)
        if self.duration > 0:
            progress = int((current_time / self.duration) * 1000)
            self.slider.setValue(progress)
        self.slider.blockSignals(False)

    def stop_stream(self):
        self.ui_timer.stop()
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    @staticmethod
    def load_wav(filename):
        if not os.path.exists(filename):
            logging.error(f"Error: File '{filename}' not found.")
            return None, None
        try:
            fs, data = wavfile.read(filename)
            if len(data.shape) == 1:
                data = data.reshape(-1, 1)
            return fs, data
        except Exception as e:
            logging.error(f"Could not load WAV: {e}")
            return None, None

    def closeEvent(self, event):
        """Clean up audio threads if widget closes."""
        self.stop_stream()
        super().closeEvent(event)