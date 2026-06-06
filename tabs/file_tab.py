import logging
import os
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft
import pyqtgraph as pg
import pyqtgraph.opengl as gl  # Import 3D Open GL modules
import sounddevice as sd

from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLineEdit, QPushButton, 
    QWidget, QVBoxLayout, QLabel, QSlider, QComboBox, QSplitter
)
from PyQt6.QtCore import Qt, QTimer

class FileTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # --- Microphone Geometry Configuration ---
        # Outer ring: 34 cm square (4 channels)
        L_outer = np.array([
            [-0.17,  0.17, -0.17,  0.17], # X
            [-0.17, -0.17,  0.17,  0.17]  # Y
        ])

        # Inner ring: 15 cm square (4 channels)
        L_inner = np.array([
            [-0.075,  0.075, -0.075,  0.075], # X
            [-0.075, -0.075,  0.075,  0.075]  # Y
        ])

        # 1. Combine both rings horizontally into an 8-channel array setup
        L_2d = np.hstack((L_outer, L_inner))

        # 2. Add the Z-axis (Z = 0) to make it fully compliant with 3D space tracking
        z_axis = np.zeros((1, L_2d.shape[1]))
        self.mic_locs = np.vstack((L_2d, z_axis))

        # State Variables
        self.fs = None
        self.data = None
        self.duration = 0.0
        self.current_sample_idx = 0
        self.stream = None
        
        # Historial tracking for 3D trajectory
        self.scatter_points = [] 

        # Timer for UI + DOA calculation (runs every 100ms / 0.1s)
        self.ui_timer = QTimer()
        self.ui_timer.setInterval(100)  
        self.ui_timer.timeout.connect(self.process_and_update_ui)

        # Setup Layouts
        main_layout = QVBoxLayout(self)
        
        # 1. File Selector
        file_container = QWidget()
        file_layout = QHBoxLayout(file_container)
        self.line_file = QLineEdit()
        self.line_file.setReadOnly(True)
        self.btn_browse = QPushButton("Browse...")
        file_layout.addWidget(QLabel("WAV File:"))
        file_layout.addWidget(self.line_file)
        file_layout.addWidget(self.btn_browse)
        main_layout.addWidget(file_container)
        
        # 2. Charts Container (Splitter for 2D Plot and 3D Sphere)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side: 2D Waveform
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.playback_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('k', width=2, style=Qt.PenStyle.DashLine))
        splitter.addWidget(self.plot_widget)
        
        # Right side: 3D Sphere View
        self.gl_widget = gl.GLViewWidget()
        self.gl_widget.setCameraPosition(distance=3)
        
        # Create Wireframe Reference Sphere
        sphere_mesh = gl.MeshData.sphere(rows=15, cols=15, radius=1.0)
        self.sphere_item = gl.GLMeshItem(meshdata=sphere_mesh, smooth=True, color=(0.8, 0.8, 0.8, 0.2), shader='shaded', glOptions='translucent')
        self.gl_widget.addItem(self.sphere_item)
        
        # Container for tracking dots
        self.scatter_item = gl.GLScatterPlotItem()
        self.gl_widget.addItem(self.scatter_item)
        
        # --- Add Azimuth Degree Labels ---
        # Labels positioned at a radius of 1.2 (just outside the 1.0 sphere)
        labels = [
            {"text": "0°",   "pos": (1.2, 0.0, 0.0)},
            {"text": "90°",  "pos": (0.0, 1.2, 0.0)},
            {"text": "180°", "pos": (-1.2, 0.0, 0.0)},
            {"text": "270°", "pos": (0.0, -1.2, 0.0)}
        ]
        
        for label in labels:
            text_item = gl.GLTextItem(
                pos=label["pos"], 
                text=label["text"], 
                color=(0, 0, 0, 255) # Crisp black text
            )
            # You can also adjust font if needed: text_item.setFont(QtGui.QFont('Helvetica', 12))
            self.gl_widget.addItem(text_item)
            
        splitter.addWidget(self.gl_widget)
        
        main_layout.addWidget(splitter)
        
        # 3. Timeline Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderMoved.connect(self.on_slider_moved)
        main_layout.addWidget(self.slider)
        
        # 4. Controls Toolbar
        controls_container = QWidget()
        controls_layout = QHBoxLayout(controls_container)
        self.btn_play = QPushButton("Play")
        self.btn_pause = QPushButton("Pause")
        self.btn_reset = QPushButton("Reset")
        self.channel_selector = QComboBox()
        self.channel_selector.addItem("All Channels (Mixed Mono)")
        
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.btn_pause)
        controls_layout.addWidget(self.btn_reset)
        controls_layout.addWidget(QLabel("Play Channel:"))
        controls_layout.addWidget(self.channel_selector)
        controls_layout.addStretch()
        main_layout.addWidget(controls_container)
        
        # Connections
        self.btn_browse.clicked.connect(self.on_browse_file)
        self.btn_play.clicked.connect(self.start_audio)
        self.btn_pause.clicked.connect(self.pause_audio)
        self.btn_reset.clicked.connect(self.reset_audio)

    # --- Signal and Event Handling ---
    def on_browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Audio File", "", "WAV Audio Files (*.wav)")
        if file_path:
            self.stop_stream()
            self.line_file.setText(file_path)
            self.fs, self.data = FileTab.load_wav(file_path)
            
            if self.data is not None:
                n_samples, n_channels = self.data.shape
                self.duration = n_samples / self.fs
                self.reset_audio()
                
                self.channel_selector.clear()
                self.channel_selector.addItem("All Channels (Mixed Mono)")
                for i in range(n_channels):
                    self.channel_selector.addItem(f"Channel {i+1}")
                
                self.plot_data()

    def plot_data(self):
        self.plot_widget.clear()
        self.plot_widget.addLegend()
        time = np.arange(self.data.shape[0]) / self.fs
        colors = ['r', 'b', 'g', 'c', 'm', 'y']
        for i in range(self.data.shape[1]):
            self.plot_widget.plot(time, self.data[:, i], pen=pg.mkPen(color=colors[i % len(colors)]), name=f"Ch {i+1}")
        self.plot_widget.addItem(self.playback_line)

    def process_and_update_ui(self):
        """Runs every 0.1s to move UI playback tracker and process a 0.2s DOA window."""
        if self.data is None:
            return
            
        current_time = self.current_sample_idx / self.fs
        self.playback_line.setValue(current_time)
        
        # Update Slider
        self.slider.blockSignals(True)
        self.slider.setValue(int((current_time / self.duration) * 1000) if self.duration > 0 else 0)
        self.slider.blockSignals(False)

        # --- Sliding Window Extraction ---
        # 0.2 seconds window size = 0.2 * fs
        window_size = int(0.2 * self.fs)
        start_idx = self.current_sample_idx - window_size
        end_idx = self.current_sample_idx
        
        if start_idx >= 0 and end_idx <= self.data.shape[0]:
            chunk = self.data[start_idx:end_idx, :]
            
            # Execute DOA Core Algorithms
            try:
                stft_feats = self.compute_stft(chunk, self.fs)
                azimuth_deg = self.detect_doa(stft_feats, self.mic_locs, self.fs)
                
                # Assume horizontal plane configuration (Colatitude = 90 degrees)
                colatitude_deg = 90.0 
                
                # Convert spherical coordinates to 3D positions
                az_rad = np.deg2rad(azimuth_deg)
                co_rad = np.deg2rad(colatitude_deg)
                
                x = np.cos(az_rad) * np.sin(co_rad)
                y = np.sin(az_rad) * np.sin(co_rad)
                z = np.cos(co_rad)
                
                # Store and draw tracking trajectory point
                self.scatter_points.append([x, y, z])
                pos_array = np.array(self.scatter_points)
                
                # Color code mapping (Newer points are brighter red)
                colors = np.zeros((pos_array.shape[0], 4))
                colors[:, 0] = 1.0  # Red
                colors[:, 3] = np.linspace(0.2, 1.0, pos_array.shape[0])  # Dynamic alpha trail
                
                self.scatter_item.setData(pos=pos_array, color=colors, size=6)
            except Exception as e:
                logging.error(f"DOA calculation failed at index {self.current_sample_idx}: {e}")

    # --- Core DSP & DOA Algorithms ---
    def compute_stft(self, data, fs, nfft=256):
        # Adjusted smaller default nfft (256) since 0.2s chunk has limited samples
        signals = data.T
        _, _, stft_data = stft(signals, fs=fs, nperseg=min(nfft, data.shape[0]), noverlap=0, boundary=None)
        return stft_data

    def detect_doa(self, stft_data, mic_locs, fs, nfft=256, algo_name="NormMUSIC"):
        from pyroomacoustics import doa
        azimuth_grid = np.deg2rad(np.arange(360))
        num_channels = stft_data.shape[0]
        L = mic_locs[:, :num_channels]
        
        # Verify block matches constraints
        nfft_actual = min(nfft, stft_data.shape[1] * 2 - 2)
        
        if algo_name == "NormMUSIC":
            detector = doa.normmusic.NormMUSIC(L=L, fs=fs, nfft=nfft_actual, azimuth=azimuth_grid)
        elif algo_name == "MUSIC":
            detector = doa.music.MUSIC(L=L, fs=fs, nfft=nfft_actual, azimuth=azimuth_grid)
        else:
            raise ValueError(f"Unknown: {algo_name}")
            
        detector.locate_sources(stft_data)
        return np.rad2deg(detector.azimuth_recon[0]) % 360

    # --- Playback Logic ---
    def start_audio(self):
        if self.data is None: return
        if self.stream is None or not self.stream.active:
            idx = self.channel_selector.currentIndex()
            mono_data = np.mean(self.data, axis=1) if idx <= 0 else self.data[:, idx - 1]
            
            def callback(outdata, frames, time, status):
                start = self.current_sample_idx
                end = start + frames
                if start >= len(mono_data):
                    outdata.fill(0)
                    self.ui_timer.stop()
                    return
                if end > len(mono_data):
                    outdata[:len(mono_data)-start, 0] = mono_data[start:]
                    outdata[len(mono_data)-start:, 0] = 0
                    self.current_sample_idx = len(mono_data)
                else:
                    outdata[:, 0] = mono_data[start:end]
                    self.current_sample_idx = end

            self.stream = sd.OutputStream(samplerate=self.fs, channels=1, dtype=self.data.dtype, callback=callback)
            self.stream.start()
            self.ui_timer.start()

    def pause_audio(self):
        self.stop_stream()

    def reset_audio(self):
        self.stop_stream()
        self.current_sample_idx = 0
        self.scatter_points = []
        
        # FIX: Reset the scatter data by passing empty arrays/lists
        self.scatter_item.setData(pos=np.empty((0, 3)), color=np.empty((0, 4)))
        
        self.playback_line.setValue(0)
        self.slider.setValue(0)

    def on_slider_moved(self, value):
        if self.data is None: return
        self.current_sample_idx = int((value / 1000.0) * len(self.data))
        self.process_and_update_ui()

    def stop_stream(self):
        self.ui_timer.stop()
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    @staticmethod
    def load_wav(filename):
        try:
            fs, data = wavfile.read(filename)
            if len(data.shape) == 1: data = data.reshape(-1, 1)
            return fs, data
        except Exception as e:
            logging.error(f"Error: {e}")
            return None, None