from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generator

import numpy as np


@dataclass
class AudioChunk:
    data: np.ndarray  # shape: (frames, channels), dtype float32, range [-1.0, 1.0]
    timestamp: float  # seconds — ADC capture time (live) or sample-index time (file)


class Loader(ABC):
    @abstractmethod
    def stream(self) -> Generator[AudioChunk, None, None]: ...
