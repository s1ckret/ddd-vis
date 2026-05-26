import logging
import os
from scipy.io import wavfile
import numpy as np

from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, pyqtSignal
import pyqtgraph as pg # Import pyqtgraph

class FileTab(QWidget):
    fileSelected = pyqtSignal(str)       # Emits selected WAV filepath

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        self.file_container = QWidget()
        file_layout = QHBoxLayout(self.file_container)
        file_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_file = QLabel("WAV File:")
        self.line_file = QLineEdit()
        self.line_file.setReadOnly(True)
        self.line_file.setMinimumWidth(250)
        self.btn_browse = QPushButton("Browse...")
        
        file_layout.addWidget(self.lbl_file)
        file_layout.addWidget(self.line_file)
        file_layout.addWidget(self.btn_browse)
        layout.addWidget(self.file_container)
        
        # Plotting Area
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)
        layout.addWidget(self.plot_widget)
        
        self.btn_browse.clicked.connect(self.on_browse_file)
    
    def on_browse_file(self):
        """Trigger file selection dialog to select a WAV file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Open Audio File", 
            "", 
            "WAV Audio Files (*.wav)"
        )
        if file_path:
            self.line_file.setText(file_path)
            fs, data = FileTab.load_wav(file_path)
            if data is not None:
                self.plot_data(fs, data)
                n_samples, n_channels = data.shape
                duration = n_samples / fs

                logging.info(
                    f"Successfully loaded: {file_path} {fs} Hz Data shape: {data.shape} Duration: {duration:.2f} seconds"
                )
            
            
    def plot_data(self, fs, data):
        self.plot_widget.clear()
        
        legend = self.plot_widget.addLegend()
        
        n_samples, n_channels = data.shape
        time = np.arange(n_samples) / fs
        colors = ['r', 'b', 'g', 'c', 'm', 'y']
        
        for i in range(n_channels):
            color = colors[i % len(colors)]
            # 2. Add the 'name' argument so the legend knows what to display
            self.plot_widget.plot(
                time, 
                data[:, i], 
                pen=pg.mkPen(color=color, width=1), 
                name=f"Channel {i+1}"
            )
            
    @staticmethod
    def load_wav(filename):
        if not os.path.exists(filename):
            logging.error(f"Error: File '{filename}' not found.")
            return None, None
        
        fs, data = wavfile.read(filename)
        
        # data shape is typically (samples, channels)
        if len(data.shape) == 1:
            data = data.reshape(-1, 1)
        
        return fs, data
