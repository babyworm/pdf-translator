from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class DraftElement:
    index: int
    type: str
    original: str
    translated: str | None
    page: int
    bbox: list[float]
    status: str = "accepted"
    confidence: float | None = None
    user_edit: str | None = None

    @property
    def effective_translation(self) -> str | None:
        if self.user_edit is not None:
            return self.user_edit
        return self.translated


@dataclass
class Draft:
    source_file: str
    source_lang: str
    target_lang: str
    backend: str
    elements: list[DraftElement]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    glossary_applied: list[str] = field(default_factory=list)

    def save(self, path: str | Path) -> None:
        data = {
            "source_file": self.source_file,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "backend": self.backend,
            "created_at": self.created_at,
            "glossary_applied": self.glossary_applied,
            "elements": [asdict(el) for el in self.elements],
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> Draft:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        elements = [DraftElement(**el) for el in data["elements"]]
        return cls(
            source_file=data["source_file"],
            source_lang=data["source_lang"],
            target_lang=data["target_lang"],
            backend=data["backend"],
            elements=elements,
            created_at=data.get("created_at", ""),
            glossary_applied=data.get("glossary_applied", []),
        )

    def to_translations(self) -> dict[int, str]:
        result = {}
        for el in self.elements:
            text = el.effective_translation
            if text is not None:
                result[el.index] = text
        return result

    def pending_indices(self) -> list[int]:
        return [el.index for el in self.elements if el.status == "pending" or el.translated is None]
