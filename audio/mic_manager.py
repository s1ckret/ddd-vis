import numpy as np
import sounddevice as sd
from PyQt6.QtCore import QObject, pyqtSignal

class MicAudioManager(QObject):
    # Signals for UI communications
    levels_updated = pyqtSignal(list)       # List of peak levels (floats, 0.0 to 1.0)
    status_changed = pyqtSignal(str, bool)   # (message, is_error)

    def __init__(self):
        super().__init__()
        self.stream = None
        self.selected_device_id = None
        self.num_channels = 1
        self.sample_rate = 44100
        
        self.is_playing = False
        self.is_paused = False

    def get_input_devices(self):
        """Query and return all active audio input devices."""
        devices = []
        try:
            devs = sd.query_devices()
            for idx, dev in enumerate(devs):
                if dev['max_input_channels'] > 0:
                    devices.append((idx, dev['name'], dev['max_input_channels']))
        except Exception as e:
            self.status_changed.emit(f"Failed to query input devices: {e}", True)
        return devices

    def set_selected_device_id(self, device_id):
        """Set the active microphone device ID. Safely stops stream if running."""
        if self.selected_device_id != device_id:
            self.stop()
            self.selected_device_id = device_id
            if device_id is not None and device_id >= 0:
                try:
                    dev_info = sd.query_devices(device_id)
                    self.status_changed.emit(f"Selected microphone: '{dev_info['name']}'", False)
                except Exception:
                    self.status_changed.emit("Selected microphone.", False)

    def play(self):
        """Start or resume microphone capture stream."""
        if self.is_playing and not self.is_paused:
            return  # Already running

        try:
            device_id = self.selected_device_id
            if device_id is None:
                device_id = sd.default.device[0]

            if device_id is None or device_id < 0:
                raise ValueError("No valid input microphone detected.")

            dev_info = sd.query_devices(device_id)
            max_chans = int(dev_info['max_input_channels'])
            if max_chans <= 0:
                raise ValueError("Selected device has no audio inputs.")

            # Set up recording parameters (capped at 8 channels)
            self.num_channels = min(8, max_chans)
            self.sample_rate = int(dev_info['default_samplerate'])
            
            self.stream = sd.InputStream(
                device=device_id,
                channels=self.num_channels,
                samplerate=self.sample_rate,
                blocksize=1024,
                dtype='float32',
                callback=self._mic_callback
            )
            self.stream.start()
            self.is_playing = True
            self.is_paused = False
            self.status_changed.emit(f"Recording: {self.num_channels} ch from '{dev_info['name']}'", False)
        except Exception as e:
            self.status_changed.emit(f"Failed to start mic stream: {str(e)}", True)
            self.stream = None
            self.is_playing = False
            self.is_paused = False

    def pause(self):
        """Pause recording and release the hardware."""
        if not self.is_playing or self.is_paused:
            return

        self.is_paused = True
        
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                print(f"Error closing stream on pause: {e}")
            self.stream = None

        self.status_changed.emit("Microphone recording paused.", False)

    def stop(self):
        """Stop recording completely, resetting buffers."""
        self.is_playing = False
        self.is_paused = False

        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                print(f"Error closing stream on stop: {e}")
            self.stream = None

        # Emit flat/zero levels to reset the visual chart
        self.levels_updated.emit([0.0] * self.num_channels)
        self.status_changed.emit("Microphone recording stopped.", False)

    def _mic_callback(self, indata, frames, time, status):
        """Non-blocking sounddevice callback for recording."""
        if status:
            print(f"Mic callback status: {status}", flush=True)

        if not self.is_playing or self.is_paused:
            return

        # Calculate peak amplitude (absolute maximum) per channel in the buffer
        peaks = np.max(np.abs(indata), axis=0)
        levels = [float(p) for p in peaks]
        self.levels_updated.emit(levels)

    def close(self):
        """Clean up audio streams."""
        self.stop()
