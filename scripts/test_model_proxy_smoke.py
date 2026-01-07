#!/usr/bin/env python3
# ruff: noqa: E402
"""Smoke test for local model-proxy integration.

Validates:
- /health reachable
- /v1/models returns models
- /v1/assistant/model readable
- /v1/chat/completions works for a chosen model

Optional:
- temporarily set assistant model (restore after)

Usage:
  python scripts/test_model_proxy_smoke.py
  python scripts/test_model_proxy_smoke.py --model <model-id>
  python scripts/test_model_proxy_smoke.py --set-assistant --model <model-id>

Notes:
- By default this script does NOT modify the assistant model.
- If you pass --set-assistant, the script will restore the previous assistant model.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

# Ensure repo root is on sys.path when running as a script
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ai_system.model_proxy_client import ModelProxyClient, ModelProxyError
from core.config import console


def _pick_default_model(
    *,
    requested_model: Optional[str],
    assistant_model: Optional[str],
    first_available_model: Optional[str],
) -> Optional[str]:
    if requested_model:
        return requested_model
    if assistant_model:
        return assistant_model
    return first_available_model


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test for model-proxy")
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override model-proxy base URL (default: MODEL_PROXY_URL env or http://localhost:8002)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model id to use for chat completion (default: assistant model, else first in /v1/models)",
    )
    parser.add_argument(
        "--set-assistant",
        action="store_true",
        help="Temporarily set assistant model to --model (or the chosen default model) and restore after",
    )
    parser.add_argument(
        "--prompt",
        default="Reply with a single word: ok",
        help="Prompt to send to /v1/chat/completions",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=32,
        help="max_tokens for /v1/chat/completions",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="temperature for /v1/chat/completions",
    )
    args = parser.parse_args()

    mp = ModelProxyClient(base_url=args.base_url)

    try:
        health = mp.health()
        console.print(f"[green]✓[/green] model-proxy health: {health}")

        models = mp.list_models()
        if not models:
            console.print("[red]✗[/red] /v1/models returned no models")
            return 2

        console.print(f"[green]✓[/green] /v1/models count: {len(models)}")

        assistant_before = mp.get_assistant_model()
        console.print(
            f"[cyan]assistant model (before):[/cyan] {assistant_before if assistant_before else '(none)'}"
        )

        first_model = models[0].id if models else None
        chosen_model = _pick_default_model(
            requested_model=args.model,
            assistant_model=assistant_before,
            first_available_model=first_model,
        )

        if not chosen_model:
            console.print("[red]✗[/red] Could not determine a model to test")
            return 2

        # Optional assistant swap
        changed = False
        try:
            if args.set_assistant and chosen_model != assistant_before:
                mp.set_assistant_model(chosen_model)
                changed = True
                console.print(
                    f"[green]✓[/green] set assistant model to: [cyan]{chosen_model}[/cyan]"
                )

            # Completion
            console.print(f"[cyan]testing completion model:[/cyan] {chosen_model}")
            text = mp.chat_completion_text(
                model=chosen_model,
                messages=[{"role": "user", "content": args.prompt}],
                max_tokens=args.max_tokens,
                temperature=args.temperature,
            )

            if not text:
                console.print("[red]✗[/red] completion returned empty response")
                return 1

            console.print("[green]✓[/green] completion response:")
            console.print(text)

        finally:
            if args.set_assistant and changed:
                # Restore assistant model to previous state
                if assistant_before:
                    mp.set_assistant_model(assistant_before)
                    console.print(
                        f"[green]✓[/green] restored assistant model to: [cyan]{assistant_before}[/cyan]"
                    )
                else:
                    mp.clear_assistant_model()
                    console.print(
                        "[green]✓[/green] cleared assistant model (restored to none)"
                    )

        return 0

    except ModelProxyError as e:
        console.print(f"[red]✗[/red] model-proxy error: {e}")
        return 1
    except Exception as e:
        console.print(f"[red]✗[/red] unexpected error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
