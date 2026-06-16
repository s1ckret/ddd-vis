import math
from typing import Generator

import numpy as np
from scipy.signal import resample_poly

from logic.loader import AudioChunk


class ResampleProcessor:
    """Resamples audio to a target sample rate using polyphase filtering.

    Parameters
    ----------
    source_rate:
        Input sample rate in Hz.
    target_rate:
        Desired output sample rate in Hz.
    """

    def __init__(self, source_rate: int, target_rate: int):
        self._passthrough = source_rate == target_rate
        g = math.gcd(target_rate, source_rate)
        self._up = target_rate // g
        self._down = source_rate // g

    def process(self, chunks: Generator[AudioChunk, None, None]) -> Generator[AudioChunk, None, None]:
        for chunk in chunks:
            if self._passthrough:
                yield chunk
                continue

            # resample_poly expects (samples,) or (samples, channels); axis=0 for (frames, channels)
            resampled = resample_poly(chunk.data, self._up, self._down, axis=0).astype(np.float32)

            yield AudioChunk(data=resampled, timestamp=chunk.timestamp)
