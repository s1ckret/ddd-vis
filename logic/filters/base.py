from abc import ABC, abstractmethod
from typing import Generator

from logic.loader import AudioChunk


class AudioFilter(ABC):
    @abstractmethod
    def process(self, chunks: Generator[AudioChunk, None, None]) -> Generator[AudioChunk, None, None]: ...
