from typing import Generator

import soxr

from logic.loader import AudioChunk


class ResampleProcessor:
    def __init__(self, source_rate: int, target_rate: int):
        self._source_rate = source_rate
        self._target_rate = target_rate
        self._stream: soxr.ResampleStream | None = None

    def process(self, chunks: Generator[AudioChunk, None, None]) -> Generator[AudioChunk, None, None]:
        for chunk in chunks:
            if self._source_rate == self._target_rate:
                yield chunk
                continue

            if self._stream is None:
                self._stream = soxr.ResampleStream(
                    in_rate=self._source_rate,
                    out_rate=self._target_rate,
                    num_channels=chunk.data.shape[1],
                    quality="HQ",
                    dtype="float32",
                )

            resampled = self._stream.resample_chunk(chunk.data)

            yield AudioChunk(data=resampled, timestamp=chunk.timestamp)
