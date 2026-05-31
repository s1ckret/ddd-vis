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
    sampling_rate: int
    timestamp: float         # inherited from AudioChunk


class StftProcessor:
    def __init__(
        self,
        nperseg: int = 512,
        noverlap: int | None = 256,
        window: str = "hann",
    ):
        self.nperseg = nperseg
        self.noverlap = noverlap
        self.window = window

    def process(self, chunks: Generator[AudioChunk, None, None]) -> Generator[StftChunk, None, None]:
        for chunk in chunks:
            # data shape: (frames, channels)
            n_channels = chunk.data.shape[1]

            per_channel: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
            for ch in range(n_channels):
                signal = chunk.data[:, ch].astype(np.float32)
                freqs, times, Zxx = stft(
                    signal,
                    fs=chunk.sampling_rate,
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
                sampling_rate=chunk.sampling_rate,
                timestamp=chunk.timestamp,
            )
