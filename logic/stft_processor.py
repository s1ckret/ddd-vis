import logging
from dataclasses import dataclass
from typing import Generator

import numpy as np
from scipy.signal import stft

from logic.loader import AudioChunk

log = logging.getLogger(__name__)


@dataclass
class StftChunk:
    freqs: np.ndarray        # shape: (n_freqs,)                    — frequency bin centres in Hz
    times: np.ndarray        # shape: (n_frames,)                   — time offsets within this chunk in seconds
    magnitudes: np.ndarray   # shape: (n_channels, n_freqs, n_frames) — complex STFT spectrum (use np.abs() for magnitude)
    timestamp: float         # inherited from AudioChunk


class StftProcessor:
    """Computes per-channel STFT with cross-chunk overlap continuity.

    Parameters
    ----------
    nperseg:
        FFT window length in samples. The chunk_size (in samples at this
        processor's sample rate) must exceed nperseg. When upstream resampling
        is applied, account for the rate change:
        chunk_size_orig >= nperseg * (orig_rate / target_rate).
        Example: nperseg=2048 at 8 kHz from a 44.1 kHz source requires
        chunk_size >= 11290 at the source rate (use 32768 for headroom).
    noverlap:
        Number of samples overlapping between consecutive windows.
        87.5% overlap = noverlap = nperseg - nperseg // 8.
    window:
        Window function name (e.g. 'hann').
    """

    def __init__(
        self,
        sampling_rate: int,
        nperseg: int = 512,
        noverlap: int | None = 256,
        window: str = "hann",
    ):
        self._sampling_rate = sampling_rate
        self.nperseg = nperseg
        self.noverlap = noverlap
        self.window = window
        self._buffer: np.ndarray | None = None  # shape (noverlap, n_channels)

    def reset(self) -> None:
        """Clear the inter-chunk overlap buffer. Call when starting a new stream."""
        self._buffer = None

    def process(self, chunks: Generator[AudioChunk, None, None]) -> Generator[StftChunk, None, None]:
        for chunk in chunks:
            # data shape: (frames, channels)
            data = chunk.data.astype(np.float32)

            # Prepend buffered tail from previous chunk so overlap spans chunk boundaries
            if self._buffer is not None and self.noverlap:
                data = np.concatenate([self._buffer, data], axis=0)

            if self.noverlap:
                self._buffer = data[-self.noverlap:].copy()

            n_channels = data.shape[1]
            per_channel: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
            for ch in range(n_channels):
                freqs, times, Zxx = stft(
                    data[:, ch],
                    fs=self._sampling_rate,
                    window=self.window,
                    nperseg=self.nperseg,
                    noverlap=self.noverlap,
                )
                per_channel.append((freqs, times, Zxx))

            freqs = per_channel[0][0]
            times = per_channel[0][1]
            # stack magnitudes → (n_channels, n_freqs, n_frames)
            magnitudes = np.stack([zxx for _, _, zxx in per_channel], axis=0)

            yield StftChunk(
                freqs=freqs,
                times=times,
                magnitudes=magnitudes,
                timestamp=chunk.timestamp,
            )
