from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QGroupBox, QRadioButton,
    QComboBox, QPushButton, QLineEdit, QLabel, QFileDialog, QButtonGroup
)
from PyQt6.QtCore import pyqtSignal

class HeaderWidget(QWidget):
    # Signals for parent main window connection
    inputTypeChanged = pyqtSignal(str)   # "mic" or "file"
    deviceChanged = pyqtSignal(int)      # Emits selected audio device ID
    fileSelected = pyqtSignal(str)       # Emits selected WAV filepath
    playClicked = pyqtSignal()
    pauseClicked = pyqtSignal()
    stopClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        # Native horizontal layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # 1. Audio Source Switcher
        self.source_group = QGroupBox("Audio Source")
        source_layout = QHBoxLayout(self.source_group)
        source_layout.setContentsMargins(10, 5, 10, 5)
        
        self.btn_group = QButtonGroup(self)
        self.radio_mic = QRadioButton("Record from Mic")
        self.radio_file = QRadioButton("Open WAV File")
        self.radio_mic.setChecked(True)
        
        self.btn_group.addButton(self.radio_mic)
        self.btn_group.addButton(self.radio_file)
        
        source_layout.addWidget(self.radio_mic)
        source_layout.addWidget(self.radio_file)
        main_layout.addWidget(self.source_group)

        # 2. Dynamic Input Fields Layout
        # A: Microphone input controls
        self.mic_container = QWidget()
        mic_layout = QHBoxLayout(self.mic_container)
        mic_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_mic = QLabel("Microphone:")
        self.combo_mic = QComboBox()
        self.combo_mic.setMinimumWidth(250)
        self.btn_refresh = QPushButton("Refresh")
        
        mic_layout.addWidget(self.lbl_mic)
        mic_layout.addWidget(self.combo_mic)
        mic_layout.addWidget(self.btn_refresh)
        main_layout.addWidget(self.mic_container)

        # B: WAV File input controls
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
        main_layout.addWidget(self.file_container)
        
        # Hide the file container initially (since mic is selected by default)
        self.file_container.setVisible(False)

        # 3. Add spacing before media buttons to align them to the right-hand side
        main_layout.addStretch(1)

        # 4. Media Action Buttons
        self.btn_play = QPushButton("Play")
        self.btn_pause = QPushButton("Pause")
        self.btn_stop = QPushButton("Stop")
        
        # Make buttons standard sizes
        self.btn_play.setMinimumWidth(75)
        self.btn_pause.setMinimumWidth(75)
        self.btn_stop.setMinimumWidth(75)
        
        main_layout.addWidget(self.btn_play)
        main_layout.addWidget(self.btn_pause)
        main_layout.addWidget(self.btn_stop)

        # Event connections
        self.radio_mic.toggled.connect(self.on_source_toggled)
        self.btn_browse.clicked.connect(self.on_browse_file)
        self.combo_mic.currentIndexChanged.connect(self.on_device_changed)
        
        # Media key bubble-ups
        self.btn_play.clicked.connect(self.playClicked.emit)
        self.btn_pause.clicked.connect(self.pauseClicked.emit)
        self.btn_stop.clicked.connect(self.stopClicked.emit)

    def populate_devices(self, devices):
        """Populates the microphone combo box with detected system inputs."""
        self.combo_mic.blockSignals(True)
        self.combo_mic.clear()
        
        if not devices:
            self.combo_mic.addItem("No input devices found", -1)
            self.combo_mic.setEnabled(False)
            self.combo_mic.blockSignals(False)
            return

        self.combo_mic.setEnabled(True)
        for idx, name, chans in devices:
            self.combo_mic.addItem(f"{name} ({chans} ch)", idx)
            
        self.combo_mic.blockSignals(False)
        
        # Trigger an initial selection signal if devices are present
        if self.combo_mic.count() > 0:
            self.on_device_changed(self.combo_mic.currentIndex())

    def on_source_toggled(self):
        """Switches the visibility of UI containers depending on selected radio button."""
        if self.radio_mic.isChecked():
            self.mic_container.setVisible(True)
            self.file_container.setVisible(False)
            self.inputTypeChanged.emit("mic")
        else:
            self.mic_container.setVisible(False)
            self.file_container.setVisible(True)
            self.inputTypeChanged.emit("file")

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
            self.fileSelected.emit(file_path)

    def on_device_changed(self, index):
        """Bubble up device selection modifications."""
        if index >= 0:
            device_id = self.combo_mic.itemData(index)
            self.deviceChanged.emit(device_id)
