import os
import wavfile

from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, pyqtSignal

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
            FileTab.load_wav(file_path)
    
    def load_wav(filename):
        """
        Loads a WAV file and prints metadata.
        
        Parameters:
        filename (str): Path to the WAV file.
        
        Returns:
        tuple: (sampling_rate, data_array)
        """
        if not os.path.exists(filename):
            print(f"Error: File '{filename}' not found.")
            return None, None
        
        fs, data = wavfile.read(filename)
        
        # data shape is typically (samples, channels)
        if len(data.shape) == 1:
            data = data.reshape(-1, 1)
            
        n_samples, n_channels = data.shape
        duration = n_samples / fs
        
        print(f"Successfully loaded: {filename}")
        print(f"  Sampling rate     : {fs} Hz")
        print(f"  Data shape        : {data.shape}")
        print(f"  Number of channels: {n_channels}")
        print(f"  Duration          : {duration:.2f} seconds")
        
        return fs, data
