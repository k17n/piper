from __future__ import annotations

from typing import Protocol

from ..schema import JobEvent, RawEmail


class ExtractionError(Exception):
    """The model's output could not be parsed into a JobEvent."""


class Extractor(Protocol):
    name: str

    def extract(self, email: RawEmail) -> JobEvent: ...
