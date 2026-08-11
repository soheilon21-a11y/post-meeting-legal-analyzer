from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.shared.validation import ensure_not_blank
from app.domain.shared.value_object import ValueObject


@dataclass(frozen=True, slots=True)
class FileName(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.value, "file_name")
        if len(normalized) > 500 or normalized in {".", ".."}:
            raise ValueError("file_name is invalid")
        if "\x00" in normalized or "/" in normalized or "\\" in normalized:
            raise ValueError("file_name must not contain path separators")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value,)


@dataclass(frozen=True, slots=True)
class MimeType(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.value, "mime_type").lower()
        if not re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+", normalized):
            raise ValueError("mime_type is invalid")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value,)


@dataclass(frozen=True, slots=True)
class ContentHash(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.value, "content_hash").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise ValueError("content_hash must be a SHA-256 hexadecimal digest")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value,)


@dataclass(frozen=True, slots=True)
class StorageKey(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.value, "storage_key")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError("storage_key must be a relative safe path")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value,)


@dataclass(frozen=True, slots=True)
class SectionPath(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.value, "section_path")
        if len(normalized) > 1000:
            raise ValueError("section_path must not exceed 1000 characters")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value,)
