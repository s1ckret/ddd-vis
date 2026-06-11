import logging
import os
import numpy as np
from scipy.io import wavfile
import pyqtgraph as pg
import sounddevice as sd

from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLineEdit, QPushButton, 
    QWidget, QVBoxLayout, QLabel, QSlider
)
from PyQt6.QtCore import Qt, QTimer

class FileTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Timer to update UI during playback
        self.ui_timer = QTimer()
        self.ui_timer.setInterval(30)  # Update UI roughly ~33 FPS
        # self.ui_timer.timeout.connect(self.update_playback_ui)

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
        
        # 4. Media Player Controls (Timeline Slider)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)  # High resolution slider (0.0% to 100.0%)
        # self.slider.sliderMoved.connect(self.on_slider_moved)
        self.layout.addWidget(self.slider)
        
        # 5. Buttons & Channel Selector Layout
        controls_container = QWidget()
        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_play = QPushButton("Play")
        self.btn_pause = QPushButton("Pause")
        self.btn_reset = QPushButton("Reset")
        
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.btn_pause)
        controls_layout.addWidget(self.btn_reset)
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
            self.ui_timer.stop()
            self.line_file.setText(file_path)

            # TODO: Load the WAV file and update the plot

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

    def start_audio(self):
        self.ui_timer.start()

    def pause_audio(self):
        self.ui_timer.stop()

    def reset_audio(self):
        self.ui_timer.stop()

    def closeEvent(self, event):
        """Clean up audio threads if widget closes."""
        self.ui_timer.stop()
        super().closeEvent(event)