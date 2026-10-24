from __future__ import annotations

import ollama
from pydantic import ValidationError

from ..schema import JobEvent, RawEmail
from .base import ExtractionError
from .prompt import build_messages


class OllamaExtractor:
    def __init__(self, host: str, model: str) -> None:
        self.client = ollama.Client(host=host)
        self.model = model
        self.name = model

    def extract(self, email: RawEmail) -> JobEvent:
        messages = build_messages(email)
        error: Exception | None = None
        for _ in range(2):  # one retry on invalid output
            resp = self.client.chat(
                model=self.model,
                messages=messages,
                format=JobEvent.model_json_schema(),
                options={"temperature": 0},
            )
            try:
                return JobEvent.model_validate_json(resp.message.content or "")
            except ValidationError as exc:
                error = exc
        raise ExtractionError(str(error))
