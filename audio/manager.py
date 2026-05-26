import wave
import numpy as np
import sounddevice as sd
from PyQt6.QtCore import QObject, pyqtSignal

class AudioManager(QObject):
    # Signals to communicate with the UI thread
    levels_updated = pyqtSignal(list)       # Emits a list of peak levels (floats, 0.0 to 1.0) per channel
    status_changed = pyqtSignal(str, bool)   # Emits (status_message, is_error)
    playback_finished = pyqtSignal()         # Emits when file playback hits the end

    def __init__(self):
        super().__init__()
        self.stream = None
        self.input_type = "mic"  # "mic" or "file"
        
        # Microphone configuration
        self.selected_device_id = None
        
        # WAV file configuration
        self.file_path = None
        self.audio_data = None    # NumPy array shaped (frames, channels)
        self.sample_rate = 44100
        self.num_channels = 1
        self.play_index = 0
        
        # State machine flags
        self.is_playing = False
        self.is_paused = False

        # Connect playback finished to clean up on the main thread
        self.playback_finished.connect(self._handle_playback_finished)

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

    def set_input_type(self, input_type):
        """Toggle between 'mic' and 'file' mode. Safely stops current stream if active."""
        if self.input_type != input_type:
            self.stop()
            self.input_type = input_type
            if self.input_type == "mic":
                self.status_changed.emit("Switched to Microphone input.", False)
            else:
                if self.file_path:
                    self.status_changed.emit(f"Switched to WAV file input. Ready to play '{self.file_path.split('/')[-1]}'.", False)
                else:
                    self.status_changed.emit("Switched to WAV file input. Please select a WAV file.", False)

    def set_selected_device_id(self, device_id):
        """Set the active microphone device ID. Safely stops current stream if active."""
        if self.selected_device_id != device_id:
            self.stop()
            self.selected_device_id = device_id
            if device_id is not None and device_id >= 0:
                try:
                    dev_info = sd.query_devices(device_id)
                    self.status_changed.emit(f"Selected microphone: '{dev_info['name']}'", False)
                except Exception:
                    self.status_changed.emit("Selected microphone.", False)

    def load_wav(self, file_path):
        """Load and decode a PCM WAV file into memory using standard wave + numpy."""
        self.stop()
        try:
            wf = wave.open(file_path, 'rb')
            self.num_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            self.sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            
            data = wf.readframes(n_frames)
            wf.close()
            
            # Determine appropriate numpy dtype from sample width (bytes)
            if sampwidth == 1:
                dtype = np.uint8
                audio_data = np.frombuffer(data, dtype=dtype)
                # Convert 8-bit unsigned PCM to float32 normalized [-1.0, 1.0]
                audio_data = (audio_data.astype(np.float32) - 128.0) / 128.0
            elif sampwidth == 2:
                dtype = np.int16
                audio_data = np.frombuffer(data, dtype=dtype)
                # Convert 16-bit signed PCM to float32 normalized [-1.0, 1.0]
                audio_data = audio_data.astype(np.float32) / 32768.0
            elif sampwidth == 4:
                dtype = np.int32
                audio_data = np.frombuffer(data, dtype=dtype)
                # Convert 32-bit signed PCM to float32 normalized [-1.0, 1.0]
                audio_data = audio_data.astype(np.float32) / 2147483648.0
            else:
                raise ValueError(f"Unsupported WAV sample width: {sampwidth} bytes. Must be 8, 16, or 32-bit PCM.")
                
            # Reshape 1D array to (frames, channels)
            self.audio_data = audio_data.reshape(-1, self.num_channels)
            self.file_path = file_path
            self.play_index = 0
            self.is_playing = False
            self.is_paused = False
            
            filename = file_path.replace("\\", "/").split("/")[-1]
            self.status_changed.emit(f"Loaded '{filename}' ({self.num_channels} ch, {self.sample_rate}Hz)", False)
            return True
        except Exception as e:
            self.status_changed.emit(f"Failed to load WAV file: {str(e)}", True)
            self.audio_data = None
            self.file_path = None
            return False

    def play(self):
        """Start or resume audio playback / recording."""
        if self.is_playing and not self.is_paused:
            return  # Already running

        if self.input_type == "mic":
            self._start_mic_stream()
        else:
            self._start_playback_stream()

    def _start_mic_stream(self):
        """Open and start microphone stream."""
        try:
            device_id = self.selected_device_id
            if device_id is None:
                # Fallback to default input
                device_id = sd.default.device[0]

            if device_id is None or device_id < 0:
                raise ValueError("No valid input microphone detected.")

            dev_info = sd.query_devices(device_id)
            max_chans = int(dev_info['max_input_channels'])
            if max_chans <= 0:
                raise ValueError("Selected device has no audio inputs.")

            # Set up recording channel count (cap at 8 channels)
            self.num_channels = min(8, max_chans)
            self.sample_rate = int(dev_info['default_samplerate'])
            self.play_index = 0
            
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

    def _start_playback_stream(self):
        """Open and start WAV playback stream, safely capping output channels to hardware limits."""
        if self.audio_data is None:
            self.status_changed.emit("No WAV file loaded. Please select a file first.", True)
            return

        try:
            # If we were paused, resume from self.play_index. Otherwise play from start.
            if not self.is_paused:
                self.play_index = 0

            # Query default output device to see its hardware channel limits
            try:
                default_output = sd.default.device[1]
                if default_output is None or default_output < 0:
                    default_output = sd.default.device[1]
                
                dev_info = sd.query_devices(default_output)
                max_out_chans = int(dev_info['max_output_channels'])
            except Exception:
                max_out_chans = 2  # Standard stereo fallback

            # Cap the stream channels to the hardware output capacity,
            # but keep self.num_channels for parsing the full file data.
            self.stream_channels = min(self.num_channels, max_out_chans)

            self.stream = sd.OutputStream(
                device=sd.default.device[1],
                samplerate=self.sample_rate,
                channels=self.stream_channels,
                blocksize=1024,
                dtype='float32',
                callback=self._playback_callback
            )
            self.stream.start()
            self.is_playing = True
            self.is_paused = False
            
            filename = self.file_path.replace("\\", "/").split("/")[-1]
            status_msg = f"Playing '{filename}' ({self.num_channels} ch file, outputting {self.stream_channels} ch)"
            self.status_changed.emit(status_msg, False)
        except Exception as e:
            self.status_changed.emit(f"Failed to start playback: {str(e)}", True)
            self.stream = None
            self.is_playing = False
            self.is_paused = False

    def pause(self):
        """Pause playback or recording."""
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

        if self.input_type == "mic":
            self.status_changed.emit("Microphone recording paused.", False)
        else:
            self.status_changed.emit("Playback paused.", False)

    def stop(self):
        """Stop playback or recording completely, resetting file index."""
        self.is_playing = False
        self.is_paused = False
        self.play_index = 0

        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                print(f"Error closing stream on stop: {e}")
            self.stream = None

        # Emit flat/zero levels to reset the visual chart
        self.levels_updated.emit([0.0] * self.num_channels)

        if self.input_type == "mic":
            self.status_changed.emit("Microphone recording stopped.", False)
        else:
            self.status_changed.emit("Playback stopped.", False)

    def _mic_callback(self, indata, frames, time, status):
        """Non-blocking sounddevice callback for recording."""
        if status:
            print(f"Mic callback status: {status}", flush=True)

        if not self.is_playing or self.is_paused:
            return

        # Calculate peak amplitude (absolute maximum) per channel in the buffer
        # indata has shape (frames, channels)
        peaks = np.max(np.abs(indata), axis=0)
        levels = [float(p) for p in peaks]
        self.levels_updated.emit(levels)

    def _playback_callback(self, outdata, frames, time, status):
        """Non-blocking sounddevice callback for playback."""
        if status:
            print(f"Playback callback status: {status}", flush=True)

        if not self.is_playing or self.is_paused:
            outdata.fill(0)
            return

        remaining = len(self.audio_data) - self.play_index
        if remaining <= 0:
            outdata.fill(0)
            # Signal playback finished (triggers stream close and status updates on main thread)
            self.playback_finished.emit()
            return

        # Calculate standard chunk size
        chunk_size = min(frames, remaining)
        chunk = self.audio_data[self.play_index : self.play_index + chunk_size]
        
        # Copy chunk to output data buffer, capping channels to the output hardware capabilities
        # chunk is (chunk_size, self.num_channels), outdata is (frames, self.stream_channels)
        outdata[:chunk_size] = chunk[:, :self.stream_channels]
        if chunk_size < frames:
            outdata[chunk_size:].fill(0)

        # Calculate peak levels for ALL channels in the loaded WAV file (for the visualizer)
        peaks = np.max(np.abs(chunk), axis=0)
        levels = [float(p) for p in peaks]
        self.levels_updated.emit(levels)

        # Advance file pointer
        self.play_index += chunk_size

    def _handle_playback_finished(self):
        """Safely stops audio streams on the GUI thread after playback hits the end."""
        self.stop()
        if self.file_path:
            filename = self.file_path.replace("\\", "/").split("/")[-1]
            self.status_changed.emit(f"Finished playing '{filename}'", False)
        else:
            self.status_changed.emit("Finished playing WAV file", False)

    def close(self):
        """Ensure all audio resources are terminated cleanly."""
        self.stop()
