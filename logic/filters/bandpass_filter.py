from typing import Generator

import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

from logic.loader import AudioChunk
from logic.filters.base import AudioFilter


class BandpassFilter(AudioFilter):
    """Butterworth bandpass filter.

    Parameters
    ----------
    low_hz:
        Lower cutoff frequency in Hz.
    high_hz:
        Upper cutoff frequency in Hz.
    sampling_rate:
        Audio sampling rate in Hz.
    order:
        Filter order per edge (total roll-off is 2× order).
    """

    def __init__(self, low_hz: float, high_hz: float, sampling_rate: int, order: int = 4):
        self._sos = butter(order, [low_hz, high_hz], btype="bandpass", fs=sampling_rate, output="sos")
        self._zi: np.ndarray | None = None  # shape: (n_sections, 2, channels) — carried across chunks

    def process(self, chunks: Generator[AudioChunk, None, None]) -> Generator[AudioChunk, None, None]:
        for chunk in chunks:
            n_channels = chunk.data.shape[1]
            data = chunk.data.astype(np.float32)

            if self._zi is None:
                zi_proto = sosfilt_zi(self._sos)  # (n_sections, 2)
                self._zi = np.stack([zi_proto * data[0, ch] for ch in range(n_channels)], axis=-1)

            filtered = np.empty_like(data)
            for ch in range(n_channels):
                filtered[:, ch], self._zi[:, :, ch] = sosfilt(
                    self._sos, data[:, ch], zi=self._zi[:, :, ch]
                )

            yield AudioChunk(data=filtered, sampling_rate=chunk.sampling_rate, timestamp=chunk.timestamp)
