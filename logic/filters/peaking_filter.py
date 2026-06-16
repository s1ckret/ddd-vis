import logging
from typing import Generator

import numpy as np
from scipy.signal import sosfilt, sosfilt_zi

from logic.loader import AudioChunk
from logic.filters.base import AudioFilter

log = logging.getLogger(__name__)


def _peaking_sos(center_hz: float, gain_db: float, q: float, sampling_rate: int) -> np.ndarray:
    """Build a single biquad peaking EQ section using the Audio EQ Cookbook."""
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * center_hz / sampling_rate
    alpha = np.sin(w0) / (2 * q)

    b0 =  1 + alpha * A
    b1 = -2 * np.cos(w0)
    b2 =  1 - alpha * A
    a0 =  1 + alpha / A
    a1 = -2 * np.cos(w0)
    a2 =  1 - alpha / A

    # Normalise and pack as one SOS section: [b0/a0, b1/a0, b2/a0, 1, a1/a0, a2/a0]
    sos = np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]])
    return sos


class PeakingFilter(AudioFilter):
    """Parametric peaking (bell) EQ filter.

    Parameters
    ----------
    center_hz:
        Centre frequency in Hz.
    gain_db:
        Boost (+) or cut (−) in dB.
    q:
        Quality factor controlling bandwidth. Q=0.71 ≈ one-octave bandwidth.
    sampling_rate:
        Audio sampling rate in Hz.
    """

    def __init__(self, center_hz: float, gain_db: float, q: float, sampling_rate: int):
        self._sos = _peaking_sos(center_hz, gain_db, q, sampling_rate)
        self._zi: np.ndarray | None = None  # (n_sections, 2, channels)

    def process(self, chunks: Generator[AudioChunk, None, None]) -> Generator[AudioChunk, None, None]:
        for chunk in chunks:
            n_channels = chunk.data.shape[1]
            data = chunk.data.astype(np.float32)

            if self._zi is None:
                # Scale zi by first sample to pre-charge the filter — eliminates startup transient
                zi_proto = sosfilt_zi(self._sos)                                                    # (1, 2)
                self._zi = np.stack([zi_proto * data[0, ch] for ch in range(n_channels)], axis=-1) # (1, 2, channels)

            filtered = np.empty_like(data)
            for ch in range(n_channels):
                filtered[:, ch], self._zi[:, :, ch] = sosfilt(
                    self._sos, data[:, ch], zi=self._zi[:, :, ch]
                )

            yield AudioChunk(
                data=filtered,
                timestamp=chunk.timestamp,
            )
