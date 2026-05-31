import logging
from dataclasses import dataclass
from typing import Generator

import numpy as np
import pyroomacoustics.doa as pra_doa

from logic.stft_processor import StftChunk

log = logging.getLogger(__name__)


@dataclass
class DoaChunk:
    azimuth_deg: float       # predicted azimuth in degrees [0, 360)
    azimuth_rad: float       # predicted azimuth in radians
    timestamp: float         # inherited from AudioChunk


class DoaProcessor:
    """Direction-of-arrival estimator using NormMUSIC from pyroomacoustics.

    Parameters
    ----------
    mic_locs:
        Microphone array positions, shape (3, n_mics) in metres.
    sampling_rate:
        Audio sampling rate in Hz.
    nfft:
        Must match the nperseg used in StftProcessor.
    n_sources:
        Number of sound sources to locate.
    algorithm:
        One of 'NormMUSIC' (recommended) or 'MUSIC'.
    freq_range:
        ``[fmin_hz, fmax_hz]`` frequency band used for DOA estimation.
        Choose a range below the spatial aliasing limit of the mic array.
        For the outer ring (48 cm diagonal) that is ≤ 357 Hz; for the inner
        ring (21 cm diagonal) with an HP filter applied it is [400, 808] Hz.
        Default: ``[200, 4000]`` (pyroomacoustics default).
    """

    def __init__(
        self,
        mic_locs: np.ndarray,
        sampling_rate: int,
        nfft: int = 512,
        n_sources: int = 1,
        algorithm: str = "NormMUSIC",
        freq_range: list[float] | None = None,
    ):
        self.n_sources = n_sources
        # freq_range is passed to locate_sources; default matches pyroomacoustics default
        self._freq_range = freq_range if freq_range is not None else [200.0, 4000.0]

        algo_cls = getattr(pra_doa, algorithm, None)
        if algo_cls is None:
            raise ValueError(f"Unknown DOA algorithm '{algorithm}'. Choose 'MUSIC' or 'NormMUSIC'.")

        self._algo = algo_cls(
            L=mic_locs,
            fs=sampling_rate,
            nfft=nfft,
            azimuth=np.deg2rad(np.arange(360)),  # 1° resolution grid
        )

    def process(self, chunks: Generator[StftChunk, None, None]) -> Generator[DoaChunk, None, None]:
        for chunk in chunks:
            try:
                self._algo.locate_sources(chunk.magnitudes, num_src=self.n_sources, freq_range=self._freq_range)
                azimuth_rad = float(self._algo.azimuth_recon[0])
            except Exception as e:
                log.warning("DOA estimation failed: %s", e)
                continue

            azimuth_deg = float(np.rad2deg(azimuth_rad)) % 360
            log.debug("DOA estimate: %.1f°", azimuth_deg)

            yield DoaChunk(azimuth_deg=azimuth_deg, azimuth_rad=azimuth_rad, timestamp=chunk.timestamp)
