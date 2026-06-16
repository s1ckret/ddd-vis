import cffi
import logging
import queue
from typing import Generator

import numpy as np
import sounddevice as sd

from logic.loader import AudioChunk, Loader

log = logging.getLogger(__name__)

_ffi = cffi.FFI()


class LiveLoader(Loader):
    def __init__(
        self,
        sampling_rate: int = 44100,
        channels: int = 1,
        chunk_size: int = 8192,
        device: str | None = None,
    ):
        self.sampling_rate = sampling_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.device = device
        self.audio_queue: queue.Queue[AudioChunk] = queue.Queue()

    def stream(self) -> Generator[AudioChunk, None, None]:
        def callback(
            indata: np.ndarray,
            frames: int,
            time: cffi.FFI.CData,
            status: sd.CallbackFlags,
        ) -> None:
            if status:
                log.warning("Stream status: %s", status)
            self.audio_queue.put(
                AudioChunk(data=indata.copy(), timestamp=time.inputBufferAdcTime)
            )

        stream = sd.InputStream(
            samplerate=self.sampling_rate,
            channels=self.channels,
            dtype="float32",
            blocksize=self.chunk_size,
            device=self.device,
            callback=callback,
        )

        with stream:
            log.info("Real-time stream started.")
            while True:
                yield self.audio_queue.get()
