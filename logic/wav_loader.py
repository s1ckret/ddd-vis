import logging
import os
from typing import Generator

import numpy as np
from scipy.io import wavfile

from logic.loader import AudioChunk, Loader

log = logging.getLogger(__name__)


class WavLoader(Loader):
    def __init__(self, file_path: str, chunk_size: int = 1024):
        self.file_path = file_path
        self.chunk_size = chunk_size

    def stream(self) -> Generator[AudioChunk, None, None]:
        if not os.path.exists(self.file_path):
            log.error("File not found: %s", self.file_path)
            return

        try:
            sampling_rate, data = wavfile.read(self.file_path)
        except Exception as e:
            log.error("Could not load WAV file: %s", e)
            return

        if data.ndim == 1:
            data = data.reshape(-1, 1)

        # Normalise to float32 [-1.0, 1.0] regardless of source bit depth
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        elif data.dtype == np.uint8:
            data = (data.astype(np.float32) - 128.0) / 128.0
        elif data.dtype != np.float32:
            data = data.astype(np.float32)

        log.info("Streaming '%s' (%d ch, %d Hz)", os.path.basename(self.file_path), data.shape[1], sampling_rate)

        for start in range(0, len(data), self.chunk_size):
            yield AudioChunk(
                data=data[start : start + self.chunk_size],
                sampling_rate=sampling_rate,
                timestamp=start / sampling_rate,
            )
