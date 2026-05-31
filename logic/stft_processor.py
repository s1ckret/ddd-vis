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
    magnitudes: np.ndarray   # shape: (n_channels, n_freqs, n_frames) — magnitude spectrum
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
        self.noverlap = noverlap if noverlap is not None else nperseg // 2
        self.window = window
        self._carry: np.ndarray | None = None  # shape: (noverlap, channels)

    def process(self, chunks: Generator[AudioChunk, None, None]) -> Generator[StftChunk, None, None]:
        for chunk in chunks:
            # Prepend carry-over from previous chunk to maintain cross-boundary overlap
            if self._carry is not None:
                data = np.concatenate([self._carry, chunk.data.astype(np.float32)], axis=0)
            else:
                data = chunk.data.astype(np.float32)

            # Save last noverlap samples for next chunk
            self._carry = data[-self.noverlap:]

            n_channels = data.shape[1]
            per_channel: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
            for ch in range(n_channels):
                freqs, times, Zxx = stft(
                    data[:, ch],
                    fs=chunk.sampling_rate,
                    window=self.window,
                    nperseg=self.nperseg,
                    noverlap=self.noverlap,
                )
                per_channel.append((freqs, times, np.abs(Zxx)))

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
