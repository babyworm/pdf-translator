from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class OCRResult:
    text: str
    bbox: list[float]
    confidence: float


@runtime_checkable
class OCREngine(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def extract(self, page_image: bytes, lang: str = "en") -> list[OCRResult]: ...
