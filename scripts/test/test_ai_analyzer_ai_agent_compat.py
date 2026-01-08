#!/usr/bin/env python3
# ruff: noqa: E402
"""Regression test: AIAnalyzer.ai_analyze backward-compat for legacy ai_agent kwarg.

This repo appears to use simple executable smoke tests (not pytest). This script validates:
- ai_agent is accepted (no TypeError)
- ai_agent is treated as an alias for ai_model when ai_model is not provided
- ai_model takes precedence when both are provided

Usage:
  python scripts/test/test_ai_analyzer_ai_agent_compat.py
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure repo root is on sys.path when running as a script
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _install_fake_model_proxy_client_module(*, expected_model: str) -> None:
    """Install a fake ai_system.model_proxy_client module into sys.modules.

    AIAnalyzer imports ModelProxyClient inside ai_analyze(), so we provide a stub here
    to avoid any real network/system dependencies during the test.
    """
    module_name = "ai_system.model_proxy_client"

    fake_mod = types.ModuleType(module_name)

    class ModelProxyError(Exception):
        pass

    class ModelProxyClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._assistant_model: Optional[str] = None

        def set_assistant_model(self, model_id: str) -> None:
            # Simulate success; also validate what the analyzer tried to set.
            assert (
                model_id == expected_model
            ), f"expected assistant model {expected_model!r}, got {model_id!r}"
            self._assistant_model = model_id

        def get_assistant_model(self) -> Optional[str]:
            return self._assistant_model

        def chat_completion_text(
            self,
            *,
            model: str,
            messages: list[dict[str, str]],
            max_tokens: int,
            temperature: float,
        ) -> str:
            _ = messages, max_tokens, temperature
            return f"ok:{model}"

    setattr(fake_mod, "ModelProxyClient", ModelProxyClient)
    setattr(fake_mod, "ModelProxyError", ModelProxyError)

    sys.modules[module_name] = fake_mod


def _remove_fake_model_proxy_client_module() -> None:
    sys.modules.pop("ai_system.model_proxy_client", None)


class _NoOpFormatter:
    def set_collected_data(self, data: Dict[str, Any]) -> None:
        _ = data

    def display(
        self, analysis_type: str, target: str, result: str, verbose: bool
    ) -> None:
        _ = analysis_type, target, result, verbose

    def set_context(self, prompt: str, result: str) -> None:
        _ = prompt, result


class _NoOpInteractive(_NoOpFormatter):
    def start_session(self, analysis_type: str, target: str, verbose: bool) -> None:
        _ = analysis_type, target, verbose


def _make_test_analyzer() -> Any:
    # Import after sys.path manipulation
    from ai_analyzer.analyzer import AIAnalyzer

    class TestAIAnalyzer(AIAnalyzer):
        def _setup_collectors(self) -> None:
            # Disable collectors for unit-level test
            self.collectors = {}

        def _setup_formatters(self) -> None:
            self.markdown_formatter = _NoOpFormatter()
            self.basic_formatter = _NoOpFormatter()
            self.interactive_handler = _NoOpInteractive()

        def _collect_context_data(
            self,
            analysis_type: str,
            target: str,
            context_data: Dict[str, Any],
            verbose: bool = False,
        ) -> Dict[str, Any]:
            _ = analysis_type, target, context_data, verbose
            return {"ok": True}

        def _generate_prompt(
            self, analysis_type: str, target: str, data: Dict[str, Any]
        ) -> str:
            _ = analysis_type, target, data
            return "prompt"

        def _analyze_with_fallback(
            self,
            prompt: str,
            verbose: bool = False,
            target: Optional[str] = None,
            selected_model: Optional[str] = None,
        ) -> Optional[str]:
            _ = prompt, verbose, target
            # Record what model selection the parent method produced.
            self._selected_model_seen = selected_model
            return f"ok:{selected_model}"

    return TestAIAnalyzer(manager=None)


def _assert(condition: bool, msg: str) -> None:
    if not condition:
        raise AssertionError(msg)


def main() -> int:
    analyzer = _make_test_analyzer()

    # 1) ai_agent aliases to ai_model when ai_model is not provided
    expected = "model-from-ai-agent"
    _install_fake_model_proxy_client_module(expected_model=expected)
    try:
        result = analyzer.ai_analyze(
            analysis_type="logs",
            target="dummy",
            context_data={},
            ai_agent=expected,
            verbose=True,
        )
        _assert(result == f"ok:{expected}", f"unexpected result: {result!r}")
        _assert(
            getattr(analyzer, "_selected_model_seen", None) == expected,
            f"selected_model mismatch: {getattr(analyzer, '_selected_model_seen', None)!r}",
        )
    finally:
        _remove_fake_model_proxy_client_module()

    # 2) ai_model takes precedence over ai_agent if both are provided
    analyzer = _make_test_analyzer()
    expected = "model-from-ai-model"
    _install_fake_model_proxy_client_module(expected_model=expected)
    try:
        result = analyzer.ai_analyze(
            analysis_type="logs",
            target="dummy",
            context_data={},
            ai_model=expected,
            ai_agent="ignored-legacy-model",
            verbose=True,
        )
        _assert(result == f"ok:{expected}", f"unexpected result: {result!r}")
        _assert(
            getattr(analyzer, "_selected_model_seen", None) == expected,
            f"selected_model mismatch: {getattr(analyzer, '_selected_model_seen', None)!r}",
        )
    finally:
        _remove_fake_model_proxy_client_module()

    print("PASS: ai_agent backward-compat verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
