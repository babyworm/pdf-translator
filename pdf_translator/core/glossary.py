from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)
_DATA_DIR = Path(__file__).parent.parent / "data" / "glossaries"


@dataclass
class Glossary:
    entries: dict[str, str] = field(default_factory=dict)
    keep_terms: list[str] = field(default_factory=list)

    def get(self, term: str) -> str | None:
        return self.entries.get(term)

    def to_prompt_dict(self) -> dict[str, str]:
        return dict(self.entries)

    @classmethod
    def from_csv(cls, path: str | Path) -> Glossary:
        entries = {}
        keep_terms = []
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                source = row.get("source", "").strip()
                target = row.get("target", "").strip()
                rule = row.get("rule", "").strip().lower()
                if not source:
                    continue
                entries[source] = target or source
                if rule == "keep" or (not rule and source.lower() == target.lower()):
                    keep_terms.append(source)
        return cls(entries=entries, keep_terms=keep_terms)

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> Glossary:
        keep_terms = [k for k, v in d.items() if k.lower() == v.lower()]
        return cls(entries=dict(d), keep_terms=keep_terms)

    @classmethod
    def merge(cls, *glossaries: Glossary) -> Glossary:
        merged_entries = {}
        merged_keep = []
        for g in glossaries:
            merged_entries.update(g.entries)
            for k in g.keep_terms:
                if k not in merged_keep:
                    merged_keep.append(k)
        final_keep = [k for k in merged_keep if merged_entries.get(k, "").lower() == k.lower()]
        return cls(entries=merged_entries, keep_terms=final_keep)


def load_builtin_pack(name: str) -> Glossary | None:
    path = _DATA_DIR / f"{name}.csv"
    if not path.exists():
        return None
    return Glossary.from_csv(path)


def load_glossary(source: str | dict | Path | None) -> Glossary | None:
    if source is None:
        return None
    if isinstance(source, dict):
        return Glossary.from_dict(source)
    path = Path(source)
    if path.exists():
        return Glossary.from_csv(path)
    return load_builtin_pack(str(source))
