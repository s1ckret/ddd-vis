from typing import Generator

import numpy as np

from logic.loader import AudioChunk
from logic.filters.base import AudioFilter


class DcOffsetFilter(AudioFilter):
    """Removes DC offset by subtracting per-channel mean of each chunk.

    Eliminates the artificial 0 Hz spike caused by a non-zero signal mean.
    """

    def process(self, chunks: Generator[AudioChunk, None, None]) -> Generator[AudioChunk, None, None]:
        for chunk in chunks:
            data = chunk.data.astype(np.float32)
            data -= data.mean(axis=0)
            yield AudioChunk(data=data, timestamp=chunk.timestamp)
