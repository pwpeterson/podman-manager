"""Interactive model selection "event" for troubleshooting.

When a PM command hits an error path that triggers AI troubleshooting, we want to:
- list available models from the local model-proxy
- show which model is currently configured as the assistant
- optionally prompt the user to select a model for this troubleshooting session

This module is intentionally UI/console-focused and should stay thin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from rich.table import Table

from core.config import console

from .model_proxy_client import ModelProxyClient, ModelProxyError, ModelProxyModel


@dataclass(frozen=True)
class ModelSelectionResult:
    """Result of an interactive selection attempt."""

    selected_model: Optional[str]
    current_assistant_model: Optional[str]
    changed: bool


def run_model_selection_event(
    *,
    client: Optional[ModelProxyClient] = None,
    title: str = "AI agent event",
    prompt_text: str = "Select a model to use for troubleshooting",
    max_attempts: int = 3,
) -> ModelSelectionResult:
    """Run an interactive model selection flow.

    Behavior:
    - If model-proxy is unavailable, returns (None, None, False).
    - If user presses Enter, keeps current assistant model (no changes).
    - If user chooses a different model, updates assistant model via model-proxy.

    Returns:
        ModelSelectionResult(selected_model, current_assistant_model, changed)
    """

    mp = client or ModelProxyClient()

    try:
        models = mp.list_models()
        assistant = mp.get_assistant_model()
    except ModelProxyError as e:
        console.print(
            f"[yellow]AI agent event unavailable (model-proxy not reachable): {e}[/yellow]"
        )
        return ModelSelectionResult(
            selected_model=None, current_assistant_model=None, changed=False
        )

    if not models:
        console.print(
            "[yellow]AI agent event unavailable: model-proxy returned no models.[/yellow]"
        )
        return ModelSelectionResult(
            selected_model=None, current_assistant_model=assistant, changed=False
        )

    console.print(f"\n[bold cyan]{title}[/bold cyan]")
    console.print(
        "[dim]A troubleshooting model will be used to analyze the failure context.[/dim]"
    )

    _print_models_table(models=models, assistant_model=assistant)

    # Build lookup
    model_ids = [m.id for m in models]
    id_set = set(model_ids)

    if assistant:
        prompt_suffix = f" (Enter to keep current: [cyan]{assistant}[/cyan])"
    else:
        prompt_suffix = " (Enter to skip)"

    for _ in range(max_attempts):
        console.print(
            f"\n[bold yellow]==>[/bold yellow] {prompt_text}{prompt_suffix}: ", end=""
        )
        try:
            raw = input().strip()
        except (KeyboardInterrupt, EOFError):
            raw = ""

        if not raw:
            # Keep current assistant model as-is.
            return ModelSelectionResult(
                selected_model=assistant,
                current_assistant_model=assistant,
                changed=False,
            )

        # Allow selecting by index (1-based) or by exact id.
        selected = _resolve_selection(raw=raw, models=models)
        if not selected:
            console.print(
                "[yellow]Invalid selection. Enter a model number (e.g. 1) or an exact model id.[/yellow]"
            )
            continue

        if selected not in id_set:
            console.print(
                "[yellow]Unknown model id. Please choose from the list shown above.[/yellow]"
            )
            continue

        if selected == assistant:
            console.print(
                f"[green]Assistant model already set to:[/green] [cyan]{selected}[/cyan]"
            )
            return ModelSelectionResult(
                selected_model=selected,
                current_assistant_model=assistant,
                changed=False,
            )

        try:
            mp.set_assistant_model(selected)
        except ModelProxyError as e:
            console.print(
                f"[yellow]Failed to set assistant model via model-proxy: {e}[/yellow]"
            )
            return ModelSelectionResult(
                selected_model=assistant,
                current_assistant_model=assistant,
                changed=False,
            )

        console.print(f"[green]Assistant model set to:[/green] [cyan]{selected}[/cyan]")
        return ModelSelectionResult(
            selected_model=selected,
            current_assistant_model=assistant,
            changed=True,
        )

    console.print(
        "[yellow]No valid selection made. Keeping current assistant model.[/yellow]"
    )
    return ModelSelectionResult(
        selected_model=assistant,
        current_assistant_model=assistant,
        changed=False,
    )


def _print_models_table(
    *, models: List[ModelProxyModel], assistant_model: Optional[str]
) -> None:
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", justify="right", no_wrap=True)
    table.add_column("Model", style="cyan")
    table.add_column("Provider", style="white")
    table.add_column("Assistant", style="bright_yellow", justify="center")

    for idx, model in enumerate(models, start=1):
        is_assistant = "*" if assistant_model and model.id == assistant_model else ""
        table.add_row(
            str(idx),
            model.id,
            model.owned_by or "",
            is_assistant,
        )

    console.print()
    console.print(table)


def _resolve_selection(*, raw: str, models: List[ModelProxyModel]) -> Optional[str]:
    # Index selection
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(models):
            return models[idx - 1].id
        return None

    # Exact model id selection
    return raw if raw else None
