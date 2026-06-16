import logging
from dataclasses import dataclass, field
from typing import Generator

import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

from logic.loader import AudioChunk
from logic.filters.base import AudioFilter

log = logging.getLogger(__name__)


class HighPassFilter(AudioFilter):
    """Butterworth high-pass filter.

    Parameters
    ----------
    cutoff_hz:
        Cutoff frequency in Hz.
    sampling_rate:
        Audio sampling rate in Hz.
    order:
        Filter order. 24 dB/Oct = 4th order, 12 dB/Oct = 2nd order.
    """

    def __init__(self, cutoff_hz: float, sampling_rate: int, order: int = 4):
        self._sos = butter(order, cutoff_hz, btype="high", fs=sampling_rate, output="sos")
        self._zi: np.ndarray | None = None  # shape: (n_sections, 2, channels) — carried across chunks

    def process(self, chunks: Generator[AudioChunk, None, None]) -> Generator[AudioChunk, None, None]:
        for chunk in chunks:
            n_channels = chunk.data.shape[1]
            data = chunk.data.astype(np.float32)

            if self._zi is None:
                # Scale zi by first sample to pre-charge the filter — eliminates startup transient
                zi_proto = sosfilt_zi(self._sos)              # (n_sections, 2)
                self._zi = np.stack([zi_proto * data[0, ch] for ch in range(n_channels)], axis=-1)

            filtered = np.empty_like(data)
            for ch in range(n_channels):
                filtered[:, ch], self._zi[:, :, ch] = sosfilt(
                    self._sos, data[:, ch], zi=self._zi[:, :, ch]
                )

            yield AudioChunk(
                data=filtered,
                timestamp=chunk.timestamp,
            )
