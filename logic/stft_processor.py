import logging
from dataclasses import dataclass
from typing import Generator

import numpy as np
from scipy.signal import ShortTimeFFT

from logic.loader import AudioChunk

log = logging.getLogger(__name__)


@dataclass
class StftChunk:
    freqs: np.ndarray        # shape: (n_freqs,)                    — frequency bin centres in Hz
    times: np.ndarray        # shape: (n_frames,)                   — global slice times in seconds
    magnitudes: np.ndarray   # shape: (n_channels, n_freqs, n_frames) — complex STFT spectrum (use np.abs() for magnitude)
    timestamp: float         # inherited from AudioChunk


class StftProcessor:
    """Per-channel STFT with cross-chunk overlap continuity (scipy ShortTimeFFT).

    Streaming model
    ---------------
    Samples are accumulated in an internal buffer. On each pass only the
    *fully-covered, non-border* window slices are emitted (slices that scipy
    would otherwise zero-pad are held back). The buffer is then advanced by
    exactly ``n_emitted * hop`` samples, so the first valid slice of the next
    pass continues the previous slice grid with no gap and no duplication. The
    overlap tail (the held-back border region) is carried over automatically.

    One audio chunk may therefore yield a StftChunk with several frames, or none
    at all if not enough samples have accumulated yet.

    Parameters
    ----------
    nperseg:
        FFT window length in samples. Must match ``nfft`` in DoaProcessor.
    noverlap:
        Overlapping samples between consecutive windows. 75% overlap =
        ``nperseg - nperseg // 4``.
    window:
        Window function name (e.g. 'hann').
    """

    def __init__(
        self,
        sampling_rate: int,
        nperseg: int = 512,
        noverlap: int | None = None,
        window: str = "hann",
    ):
        if noverlap is None:
            noverlap = nperseg - nperseg // 4  # 75% overlap

        self._sampling_rate = sampling_rate
        self.nperseg = nperseg
        self.noverlap = noverlap
        self.window = window

        self._sft = ShortTimeFFT.from_window(
            window,
            fs=sampling_rate,
            nperseg=nperseg,
            noverlap=noverlap,
            fft_mode="onesided",
        )
        self._hop = self._sft.hop                 # = nperseg - noverlap
        self._p_lo = self._sft.lower_border_end[1]  # first slice clear of left pad

        self._buffer: np.ndarray | None = None  # shape (n_buffered, n_channels)
        self._frame_count = 0                    # global emitted slice counter (for times)

    def reset(self) -> None:
        """Clear overlap buffer + slice counter. Call when starting a new stream."""
        self._buffer = None
        self._frame_count = 0

    def process(self, chunks: Generator[AudioChunk, None, None]) -> Generator[StftChunk, None, None]:
        m = self.nperseg
        hop = self._hop
        p_lo = self._p_lo

        for chunk in chunks:
            data = chunk.data.astype(np.float32)  # (frames, channels)

            if self._buffer is not None:
                data = np.concatenate([self._buffer, data], axis=0)

            n = data.shape[0]

            # Not enough samples for a single full window yet — keep buffering.
            if n < m:
                self._buffer = data
                continue

            p_hi = self._sft.upper_border_begin(n)[1]  # first slice touching right pad
            n_emit = p_hi - p_lo

            if n_emit <= 0:
                # Only border/partial slices available — wait for more data.
                self._buffer = data
                continue

            n_channels = data.shape[1]
            # ShortTimeFFT.stft → (n_freqs, n_slices); keep only clean interior slices.
            mags = np.stack(
                [self._sft.stft(data[:, ch], p0=p_lo, p1=p_hi) for ch in range(n_channels)],
                axis=0,
            )  # (n_channels, n_freqs, n_emit)

            # Advance buffer by exactly the consumed hops → next pass's p_lo == this pass's p_hi.
            advance = n_emit * hop
            self._buffer = data[advance:].copy()

            # Global, monotonic slice times.
            times = self._sft.delta_t * np.arange(self._frame_count, self._frame_count + n_emit)
            self._frame_count += n_emit

            yield StftChunk(
                freqs=self._sft.f,
                times=times,
                magnitudes=mags,
                timestamp=chunk.timestamp,
            )
