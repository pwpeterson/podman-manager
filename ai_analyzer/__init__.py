"""AI Analyzer package for Podman Manager.

This package intentionally avoids import-time side effects (no dotenv loading,
no eager global analyzer instance). Use `get_ai_analyzer()` to obtain a shared
analyzer instance.
"""

from __future__ import annotations

from typing import Any, Optional

from .analyzer import AIAnalyzer
from .config import config

__all__ = ["AIAnalyzer", "config", "get_ai_analyzer"]

_ai_analyzer_singleton: Optional[AIAnalyzer] = None


def get_ai_analyzer(manager: Optional[Any] = None) -> AIAnalyzer:
    """Return a shared AIAnalyzer instance (lazy-initialized).

    If `manager` is provided and the singleton doesn't have one yet, it will be set.
    """
    global _ai_analyzer_singleton

    if _ai_analyzer_singleton is None:
        _ai_analyzer_singleton = AIAnalyzer(manager)
    elif manager is not None and _ai_analyzer_singleton.manager is None:
        _ai_analyzer_singleton.manager = manager

    return _ai_analyzer_singleton


def __getattr__(name: str) -> Any:
    """Soft-deprecated legacy export.

    `from ai_analyzer import ai_analyzer` will still work, but should be replaced
    with `get_ai_analyzer()` in callers.
    """
    if name == "ai_analyzer":
        return get_ai_analyzer()
    raise AttributeError(name)
