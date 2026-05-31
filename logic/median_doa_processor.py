import logging
from collections import deque
from typing import Generator

import numpy as np

from logic.doa_processor import DoaChunk

log = logging.getLogger(__name__)


class MedianDoaProcessor:
    """Sliding-window circular median over DOA estimates.

    Parameters
    ----------
    window:
        Number of most-recent DoaChunks to include in each median.
        Default: 3.
    """

    def __init__(self, window: int = 3):
        if window < 1:
            raise ValueError("window must be >= 1")
        self._window = window
        self._buf: deque[float] = deque(maxlen=window)

    def process(self, chunks: Generator[DoaChunk, None, None]) -> Generator[DoaChunk, None, None]:
        for chunk in chunks:
            self._buf.append(chunk.azimuth_rad)

            median_rad = _circular_median(np.array(self._buf))
            median_deg = float(np.rad2deg(median_rad)) % 360

            log.debug("MedianDOA: window=%s  median=%.1f°", list(np.rad2deg(self._buf)), median_deg)

            yield DoaChunk(
                azimuth_deg=median_deg,
                azimuth_rad=float(median_rad),
                timestamp=chunk.timestamp,
            )


def _circular_median(angles_rad: np.ndarray) -> float:
    """Circular median: minimises sum of circular distances."""
    if len(angles_rad) == 1:
        return float(angles_rad[0])

    # Candidate set is the input angles themselves (optimal for circular median)
    best_angle = angles_rad[0]
    best_cost = float("inf")
    for candidate in angles_rad:
        cost = np.sum(np.abs(_wrap(angles_rad - candidate)))
        if cost < best_cost:
            best_cost = cost
            best_angle = candidate
    return float(best_angle)


def _wrap(a: np.ndarray) -> np.ndarray:
    """Wrap angles to [-π, π]."""
    return (a + np.pi) % (2 * np.pi) - np.pi
