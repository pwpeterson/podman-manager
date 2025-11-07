"""Spinner management utility to prevent Rich Live display conflicts"""

from contextlib import contextmanager
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner


class SpinnerManager:
    """Manages Rich Live spinners to prevent conflicts"""

    _active_spinner: Optional[Live] = None

    @classmethod
    @contextmanager
    def spinner(cls, text: str = "Processing...", console: Optional[Console] = None):
        """Context manager for safe spinner usage

        Args:
            text: Text to display with spinner
            console: Rich console instance (optional)

        Usage:
            with SpinnerManager.spinner("Analyzing...") as spinner:
                # Do work here
                pass
        """
        # Stop any existing spinner first
        cls.stop_active_spinner()

        spinner_obj = Spinner("dots", text=f"[green]{text}[/green]")
        live_spinner = Live(spinner_obj, console=console, refresh_per_second=10)

        try:
            live_spinner.start()
            cls._active_spinner = live_spinner
            yield live_spinner
        except Exception as e:
            # Re-raise the exception after cleanup
            raise e
        finally:
            # Always clean up
            cls._stop_spinner(live_spinner)
            if cls._active_spinner == live_spinner:
                cls._active_spinner = None

    @classmethod
    def stop_active_spinner(cls) -> None:
        """Stop any currently active spinner"""
        if cls._active_spinner is not None:
            cls._stop_spinner(cls._active_spinner)
            cls._active_spinner = None

    @classmethod
    def _stop_spinner(cls, spinner: Live) -> None:
        """Safely stop a spinner instance"""
        try:
            if spinner.is_started:
                spinner.stop()
        except Exception:
            # Ignore errors when stopping spinner
            pass


@contextmanager
def safe_spinner(
    text: str = "Processing...",
    console: Optional[Console] = None,
    verbose: bool = False,
):
    """Convenience function for safe spinner usage

    Args:
        text: Text to display with spinner
        console: Rich console instance (optional)
        verbose: If True, no spinner is shown

    Usage:
        with safe_spinner("Analyzing...", verbose=verbose):
            # Do work here
            pass
    """
    if verbose:
        # In verbose mode, just yield None (no spinner)
        yield None
    else:
        with SpinnerManager.spinner(text, console) as spinner:
            yield spinner
