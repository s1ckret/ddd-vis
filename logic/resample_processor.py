import math
from typing import Generator

import numpy as np
from scipy.signal import resample_poly

from logic.loader import AudioChunk


class ResampleProcessor:
    """Resamples audio to a target sample rate using polyphase filtering.

    Parameters
    ----------
    target_rate:
        Desired output sample rate in Hz.
    """

    def __init__(self, target_rate: int):
        self._target_rate = target_rate
        self._up: int | None = None
        self._down: int | None = None

    def process(self, chunks: Generator[AudioChunk, None, None]) -> Generator[AudioChunk, None, None]:
        for chunk in chunks:
            if self._up is None:
                g = math.gcd(self._target_rate, chunk.sampling_rate)
                self._up = self._target_rate // g
                self._down = chunk.sampling_rate // g

            if chunk.sampling_rate == self._target_rate:
                yield chunk
                continue

            # resample_poly expects (samples,) or (samples, channels); axis=0 for (frames, channels)
            resampled = resample_poly(chunk.data, self._up, self._down, axis=0).astype(np.float32)

            yield AudioChunk(data=resampled, sampling_rate=self._target_rate, timestamp=chunk.timestamp)
