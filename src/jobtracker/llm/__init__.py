from __future__ import annotations

from ..config import Settings
from .base import ExtractionError, Extractor

__all__ = ["ExtractionError", "Extractor", "get_extractor"]


def get_extractor(settings: Settings) -> Extractor:
    if settings.llm_provider == "ollama":
        from .ollama_extractor import OllamaExtractor

        return OllamaExtractor(settings.ollama_host, settings.ollama_model)
    if settings.llm_provider == "anthropic":
        raise NotImplementedError("LLM_PROVIDER=anthropic is not implemented in the MVP yet.")
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")
