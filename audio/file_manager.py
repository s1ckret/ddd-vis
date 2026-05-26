import wave
import numpy as np
import sounddevice as sd
from PyQt6.QtCore import QObject, pyqtSignal

class FileAudioManager(QObject):
    # Signals for UI communications
    levels_updated = pyqtSignal(list)       # List of peak levels (floats, 0.0 to 1.0)
    status_changed = pyqtSignal(str, bool)   # (message, is_error)
    playback_finished = pyqtSignal()         # Emitted on stream reaching end-of-file

    def __init__(self):
        super().__init__()
        self.stream = None
        self.file_path = None
        self.audio_data = None    # NumPy array shaped (frames, channels)
        self.sample_rate = 44100
        self.num_channels = 1
        self.stream_channels = 1   # Channels configured for physical output device
        self.play_index = 0
        
        self.is_playing = False
        self.is_paused = False

        # Connect playback finished to clean up on the main thread
        self.playback_finished.connect(self._handle_playback_finished)

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
                audio_data = (audio_data.astype(np.float32) - 128.0) / 128.0
            elif sampwidth == 2:
                dtype = np.int16
                audio_data = np.frombuffer(data, dtype=dtype)
                audio_data = audio_data.astype(np.float32) / 32768.0
            elif sampwidth == 4:
                dtype = np.int32
                audio_data = np.frombuffer(data, dtype=dtype)
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
        """Start or resume WAV file playback stream."""
        if self.is_playing and not self.is_paused:
            return  # Already playing

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
        """Pause WAV playback and release the hardware."""
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

        self.status_changed.emit("Playback paused.", False)

    def stop(self):
        """Stop WAV playback completely, resetting file index."""
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
        self.status_changed.emit("Playback stopped.", False)

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
        
        # Copy chunk to output data buffer, capping channels to what the stream expects
        # chunk has self.num_channels channels, outdata expects self.stream_channels channels
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
        """Clean up audio streams."""
        self.stop()
