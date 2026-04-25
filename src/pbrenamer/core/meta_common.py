"""Shared types for audio, image, and video metadata modules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FieldType(Enum):
    DATETIME = "datetime"
    DATE = "date"
    STRING = "string"
    INTEGER = "integer"
    RATIONAL = "rational"


@dataclass(frozen=True)
class FieldInfo:
    description: str
    type: FieldType
