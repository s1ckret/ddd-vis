from typing import Generator

import numpy as np

from logic.stft_processor import StftChunk


class StftSliceProcessor:
    """Slices STFT output to a frequency band of interest.

    Reduces memory and downstream compute when only a sub-band is needed
    (e.g. for spectrogram display). Do NOT feed the output into DoaProcessor —
    NormMUSIC requires the full complex spectrum.

    Parameters
    ----------
    freq_min_hz:
        Lower bound of the frequency slice in Hz (inclusive).
    freq_max_hz:
        Upper bound of the frequency slice in Hz (inclusive).
    """

    def __init__(self, sampling_rate: int, freq_min_hz: float, freq_max_hz: float):
        self._sampling_rate = sampling_rate
        self._freq_min = freq_min_hz
        self._freq_max = freq_max_hz

    def process(self, chunks: Generator[StftChunk, None, None]) -> Generator[StftChunk, None, None]:
        for chunk in chunks:
            mask = (chunk.freqs >= self._freq_min) & (chunk.freqs <= self._freq_max)
            yield StftChunk(
                freqs=chunk.freqs[mask],
                times=chunk.times,
                magnitudes=chunk.magnitudes[:, mask, :],
                timestamp=chunk.timestamp,
            )
