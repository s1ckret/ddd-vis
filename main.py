import sys
import numpy as np
import sounddevice as sd
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QComboBox, QPushButton, QProgressBar, QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer

class AudioPortSelectorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("8-Channel Microphone Reader")
        self.setMinimumSize(550, 420)
        
        # Audio stream and state variables
        self.stream = None
        self.selected_device_id = None
        self.num_channels = 8
        self.current_peaks = [0.0] * 8
        
        # Central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # --- Selector Control Bar ---
        selector_layout = QHBoxLayout()
        selector_layout.setSpacing(10)
        
        self.input_label = QLabel("Select microphone:")
        self.device_dropdown = QComboBox()
        self.device_dropdown.setMinimumWidth(250)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.populate_devices)
        
        selector_layout.addWidget(self.input_label)
        selector_layout.addWidget(self.device_dropdown, 1)
        selector_layout.addWidget(self.refresh_btn)
        main_layout.addLayout(selector_layout)
        
        # --- Action Buttons ---
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(15)
        
        self.start_btn = QPushButton("Start Reading")
        self.start_btn.clicked.connect(self.start_audio)
        
        self.stop_btn = QPushButton("Stop Reading")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_audio)
        
        actions_layout.addWidget(self.start_btn)
        actions_layout.addWidget(self.stop_btn)
        main_layout.addLayout(actions_layout)
        
        # --- Real-Time Level Meters ---
        self.levels_group = QGroupBox("8-Channel Level Indicators")
        levels_layout = QGridLayout(self.levels_group)
        levels_layout.setContentsMargins(15, 15, 15, 15)
        levels_layout.setSpacing(10)
        
        self.progress_bars = []
        self.channel_labels = []
        
        for i in range(8):
            label = QLabel(f"Channel {i+1}:")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            
            # Grid layout: Row i, Column 0: Label, Column 1: Progress Bar
            levels_layout.addWidget(label, i, 0)
            levels_layout.addWidget(bar, i, 1)
            
            self.channel_labels.append(label)
            self.progress_bars.append(bar)
            
        main_layout.addWidget(self.levels_group)
        
        # --- Status Label ---
        self.status_label = QLabel("Select an input device and click 'Start Reading'.")
        self.status_label.setWordWrap(True)
        main_layout.addWidget(self.status_label)
        
        # --- Timer for UI updates ---
        self.ui_timer = QTimer()
        self.ui_timer.setInterval(30) # Poll every ~33ms (30 FPS)
        self.ui_timer.timeout.connect(self.update_levels_ui)
        
        # Listen for dropdown changes
        self.device_dropdown.currentIndexChanged.connect(self.on_device_changed)
        
        # Populate initially
        self.populate_devices()

    def populate_devices(self):
        """Query and load audio input devices."""
        self.device_dropdown.clear()
        
        try:
            devices = sd.query_devices()
        except Exception as e:
            self.status_label.setText(f"Error querying audio devices: {e}")
            return
            
        input_devices = []
        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                input_devices.append((i, d))
                
        if not input_devices:
            self.device_dropdown.addItem("No input devices detected")
            self.device_dropdown.setEnabled(False)
            self.start_btn.setEnabled(False)
            self.status_label.setText("No microphone detected. Please plug in a microphone and refresh.")
        else:
            self.device_dropdown.setEnabled(True)
            self.start_btn.setEnabled(True)
            for idx, dev in input_devices:
                name = dev['name']
                chans = dev['max_input_channels']
                display_text = f"{name} ({chans} input ch)"
                self.device_dropdown.addItem(display_text, idx)
                
            self.status_label.setText("Input devices refreshed successfully.")

    def on_device_changed(self, index):
        """Fires when the user selects a different input device."""
        if index < 0 or not self.device_dropdown.isEnabled():
            self.selected_device_id = None
            return
        self.selected_device_id = self.device_dropdown.itemData(index)

    def audio_callback(self, indata, frames, time, status):
        """Sounddevice non-blocking audio stream callback."""
        if status:
            # We print PortAudio buffer status warnings if any (e.g. input overflow)
            print(f"PortAudio status: {status}", flush=True)
            
        # indata has shape (frames, channels)
        # Calculate peak amplitude (0.0 to 1.0) along the frames axis for each channel
        peaks = np.max(np.abs(indata), axis=0)
        
        # Fill in active channels, zero out the rest
        for ch in range(8):
            if ch < len(peaks):
                self.current_peaks[ch] = float(peaks[ch])
            else:
                self.current_peaks[ch] = 0.0

    def start_audio(self):
        """Initialize and start the 8-channel input stream."""
        if self.selected_device_id is None:
            self.status_label.setText("Please select a valid input device first.")
            return
            
        # Close any existing stream first
        if self.stream is not None:
            self.stop_audio()
            
        try:
            device_info = sd.query_devices(self.selected_device_id)
            samplerate = int(device_info['default_samplerate'])
            max_chans = int(device_info['max_input_channels'])
        except Exception as e:
            self.status_label.setText(f"Failed to query device details: {e}")
            return

        self.current_peaks = [0.0] * 8
        self.status_label.setText("Starting audio stream...")
        
        # We try to open 8 channels. If the hardware supports fewer channels,
        # we open as many channels as possible up to 8 and zero out the inactive meters.
        target_chans = 8
        opened_chans = target_chans
        
        try:
            self.stream = sd.InputStream(
                device=self.selected_device_id,
                channels=target_chans,
                samplerate=samplerate,
                callback=self.audio_callback
            )
            self.stream.start()
            self.status_label.setText(f"Reading 8 channels successfully at {samplerate}Hz.")
        except Exception as e:
            # Fallback block: try opening the maximum supported channels (capped at 8)
            opened_chans = min(8, max_chans)
            try:
                self.stream = sd.InputStream(
                    device=self.selected_device_id,
                    channels=opened_chans,
                    samplerate=samplerate,
                    callback=self.audio_callback
                )
                self.stream.start()
                self.status_label.setText(
                    f"Warning: Hardware does not support 8 channels. "
                    f"Opened with fallback: Reading {opened_chans} channel(s)."
                )
            except Exception as err:
                self.status_label.setText(f"Failed to open audio: {err}")
                self.stream = None
                return

        # Update button states and start UI timer
        self.start_btn.setEnabled(False)
        self.device_dropdown.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.ui_timer.start()

    def stop_audio(self):
        """Stop and close the audio stream cleanly."""
        self.ui_timer.stop()
        
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                print(f"Error closing stream: {e}")
            self.stream = None
            
        # Reset level indicators
        self.current_peaks = [0.0] * 8
        for bar in self.progress_bars:
            bar.setValue(0)
            
        # Re-enable inputs
        self.start_btn.setEnabled(True)
        self.device_dropdown.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Audio reading stopped.")

    def update_levels_ui(self):
        """Update progress bars in the main GUI thread from audio thread peak values."""
        for ch in range(8):
            # Scale absolute amplitude peak (0.0 to 1.0) to standard percentage (0 to 100)
            val = int(self.current_peaks[ch] * 100)
            # Clip between 0 and 100 just to be safe
            val = max(0, min(100, val))
            self.progress_bars[ch].setValue(val)

    def closeEvent(self, event):
        """Make sure to stop audio stream when closing the application."""
        self.stop_audio()
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    
    window = AudioPortSelectorApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
