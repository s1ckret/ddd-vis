import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

# Import modular components and backend
from components.header import HeaderWidget
from components.body import BodyWidget
from components.footer import FooterWidget
from audio.manager import AudioManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multi-Channel Audio Visualizer")
        self.setMinimumSize(950, 500)

        # 1. Initialize Audio Manager
        self.audio_manager = AudioManager()

        # 2. Build UI Layout Components
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Header component (Controls)
        self.header = HeaderWidget(self)
        main_layout.addWidget(self.header)

        # Body component (Scrolling Chart)
        self.body = BodyWidget(self)
        # Give body chart maximum stretch priority to expand vertically
        main_layout.addWidget(self.body, 1)

        # Footer component (Status line)
        self.footer = FooterWidget(self)
        main_layout.addWidget(self.footer)

        # 3. Connect Component Signals & Controller Logic
        self._connect_signals()

        # 4. Populate microphone list on startup
        self.refresh_mic_list()

    def _connect_signals(self):
        """Bind all component signals and slots together."""
        # Header actions
        self.header.inputTypeChanged.connect(self.on_input_type_changed)
        self.header.deviceChanged.connect(self.audio_manager.set_selected_device_id)
        self.header.fileSelected.connect(self.on_file_selected)
        
        # Header playback commands
        self.header.playClicked.connect(self.audio_manager.play)
        self.header.pauseClicked.connect(self.audio_manager.pause)
        self.header.stopClicked.connect(self.audio_manager.stop)
        
        # Connect refresh button in Header
        self.header.btn_refresh.clicked.connect(self.refresh_mic_list)

        # Audio Manager feedback
        self.audio_manager.levels_updated.connect(self.body.update_levels)
        self.audio_manager.status_changed.connect(self.on_status_changed)

    def on_status_changed(self, message, is_error):
        """Handle status updates by setting the footer text and logging to the console."""
        self.footer.set_status(message, is_error)
        if is_error:
            print(f"[ERROR] {message}", file=sys.stderr, flush=True)
        else:
            print(f"[INFO] {message}", flush=True)

    def on_input_type_changed(self, input_type):
        """Wipes the chart and updates the audio manager whenever the user toggles sources."""
        self.body.reset_chart()
        self.audio_manager.set_input_type(input_type)

    def on_file_selected(self, file_path):
        """Resets chart and triggers WAV load on the audio manager."""
        self.body.reset_chart()
        self.audio_manager.load_wav(file_path)

    def refresh_mic_list(self):
        """Fetch microphones from audio manager and populate the header dropdown."""
        devices = self.audio_manager.get_input_devices()
        self.header.populate_devices(devices)
        
        if self.audio_manager.input_type == "mic":
            self.footer.set_status("Microphone list refreshed.", False)

    def closeEvent(self, event):
        """Cleanly closes background audio streams on window exit."""
        self.audio_manager.close()
        event.accept()

def main():
    app = QApplication(sys.argv)
    
    # Optional: Apply native window styles adjustments if any
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
