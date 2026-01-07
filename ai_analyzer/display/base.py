"""Shared display interfaces for AI analyzer output."""

from __future__ import annotations

from abc import ABC, abstractmethod


class DisplayFormatter(ABC):
    """Abstract base class for display formatters."""

    @abstractmethod
    def display(
        self, analysis_type: str, target: str, result: str, verbose: bool = False
    ) -> None:
        """Display analysis results."""
        raise NotImplementedError
