from typing import Generator

import numpy as np

from logic.stft_processor import StftChunk


class LogScaleProcessor:
    """Converts STFT magnitudes to decibels for display.

    Output magnitudes are real-valued dB values. Intended for spectrogram
    visualisation only — do NOT feed into DoaProcessor.

    Parameters
    ----------
    ref:
        Reference amplitude for 0 dB. Default 1.0 (normalised audio).
    eps:
        Small constant added before log to avoid log(0). Default 1e-5.
    """

    def __init__(self, ref: float = 1.0, eps: float = 1e-5):
        self._ref = ref
        self._eps = eps

    def process(self, chunks: Generator[StftChunk, None, None]) -> Generator[StftChunk, None, None]:
        for chunk in chunks:
            magnitude = np.abs(chunk.magnitudes)
            db = 20.0 * np.log10(magnitude / self._ref + self._eps)
            yield StftChunk(
                freqs=chunk.freqs,
                times=chunk.times,
                magnitudes=db,
                sampling_rate=chunk.sampling_rate,
                timestamp=chunk.timestamp,
            )
