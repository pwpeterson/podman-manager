#!/usr/bin/env python3
"""
Rich Text Colors and Styles Reference Module

This module provides functions to display comprehensive examples of Rich text colors,
styles, and formatting options. Can be used standalone or imported into other projects.
"""

from typing import Optional

from rich.console import Console


def print_colors_and_styles(console: Optional[Console] = None):
    """Print comprehensive Rich text colors and styles with examples."""
    if console is None:
        console = Console()

    console.print("\n[bold cyan]Rich Text Colors and Styles Reference[/bold cyan]\n")

    console.print("[bold]Basic Colors:[/bold]")
    console.print(
        "  [red]red[/red] - [green]green[/green] - [blue]blue[/blue] - [yellow]yellow[/yellow]"
    )
    console.print(
        "  [magenta]magenta[/magenta] - [cyan]cyan[/cyan] - [white]white[/white] - [black on white]black[/black on white]"
    )

    console.print("\n[bold]Bright Colors:[/bold]")
    console.print(
        "  [bright_red]bright_red[/bright_red] - [bright_green]bright_green[/bright_green] - [bright_blue]bright_blue[/bright_blue] - [bright_yellow]bright_yellow[/bright_yellow]"
    )
    console.print(
        "  [bright_magenta]bright_magenta[/bright_magenta] - [bright_cyan]bright_cyan[/bright_cyan] - [bright_white]bright_white[/bright_white] - [bright_black on white]bright_black[/bright_black on white]"
    )

    console.print("\n[bold]Dim Colors:[/bold]")
    console.print(
        "  [dim red]dim red[/dim red] - [dim green]dim green[/dim green] - [dim blue]dim blue[/dim blue] - [dim yellow]dim yellow[/dim yellow]"
    )
    console.print(
        "  [dim magenta]dim magenta[/dim magenta] - [dim cyan]dim cyan[/dim cyan] - [dim white]dim white[/dim white]"
    )

    console.print("\n[bold]Text Styles:[/bold]")
    console.print(
        "  [bold]bold[/bold] - [italic]italic[/italic] - [underline]underline[/underline] - [strike]strikethrough[/strike]"
    )
    console.print("  [reverse]reverse[/reverse] - [blink]blink[/blink]")

    console.print("\n[bold]Combined Styles:[/bold]")
    console.print(
        "  [bold red]bold red[/bold red] - [italic cyan]italic cyan[/italic cyan] - [underline bright_green]underline bright_green[/underline bright_green]"
    )
    console.print(
        "  [bold italic yellow]bold italic yellow[/bold italic yellow] - [dim underline magenta]dim underline magenta[/dim underline magenta]"
    )

    console.print("\n[bold]Background Colors:[/bold]")
    console.print(
        "  [white on red]white on red[/white on red] - [black on yellow]black on yellow[/black on yellow] - [white on blue]white on blue[/white on blue]"
    )
    console.print(
        "  [black on cyan]black on cyan[/black on cyan] - [white on magenta]white on magenta[/white on magenta] - [black on green]black on green[/black on green]"
    )

    console.print("\n[bold]Extended Colors (256-color):[/bold]")
    console.print(
        "  [color(196)]color(196) - red[/color(196)] - [color(46)]color(46) - green[/color(46)] - [color(21)]color(21) - blue[/color(21)]"
    )
    console.print(
        "  [color(226)]color(226) - yellow[/color(226)] - [color(201)]color(201) - magenta[/color(201)] - [color(51)]color(51) - cyan[/color(51)]"
    )

    console.print("\n[bold]RGB Colors:[/bold]")
    console.print(
        "  [rgb(255,0,0)]rgb(255,0,0) - red[/rgb(255,0,0)] - [rgb(0,255,0)]rgb(0,255,0) - green[/rgb(0,255,0)] - [rgb(0,0,255)]rgb(0,0,255) - blue[/rgb(0,0,255)]"
    )
    console.print(
        "  [rgb(255,165,0)]rgb(255,165,0) - orange[/rgb(255,165,0)] - [rgb(128,0,128)]rgb(128,0,128) - purple[/rgb(128,0,128)]"
    )

    console.print("\n[bold]Hex Colors:[/bold]")
    console.print(
        "  [#ff0000]#ff0000 - red[/#ff0000] - [#00ff00]#00ff00 - green[/#00ff00] - [#0000ff]#0000ff - blue[/#0000ff]"
    )
    console.print(
        "  [#ffa500]#ffa500 - orange[/#ffa500] - [#800080]#800080 - purple[/#800080] - [#ff69b4]#ff69b4 - hot pink[/#ff69b4]"
    )

    console.print("\n[bold]Usage Examples:[/bold]")
    console.print("  [cyan]\\[cyan]text\\[/cyan][/cyan] → [cyan]text[/cyan]")
    console.print(
        "  [bold red]\\[bold red]text\\[/bold red][/bold red] → [bold red]text[/bold red]"
    )
    console.print(
        "  [white on blue]\\[white on blue]text\\[/white on blue][/white on blue] → [white on blue]text[/white on blue]"
    )
    console.print(
        "  [rgb(255,100,50)]\\[rgb(255,100,50)]text\\[/rgb(255,100,50)][/rgb(255,100,50)] → [rgb(255,100,50)]text[/rgb(255,100,50)]"
    )

    console.print()


def print_compact_color_examples(console: Optional[Console] = None):
    """Print compact color and style examples for help displays."""
    if console is None:
        console = Console()

    console.print("[bold]Rich Text Colors and Styles Examples:[/bold]")
    console.print(
        "  [red]red[/red] - [green]green[/green] - [blue]blue[/blue] - [yellow]yellow[/yellow] - [magenta]magenta[/magenta] - [cyan]cyan[/cyan]"
    )
    console.print(
        "  [bright_red]bright_red[/bright_red] - [bright_green]bright_green[/bright_green] - [bright_cyan]bright_cyan[/bright_cyan]"
    )
    console.print(
        "  [bold]bold[/bold] - [italic]italic[/italic] - [underline]underline[/underline] - [strike]strikethrough[/strike]"
    )
    console.print(
        "  [bold red]bold red[/bold red] - [italic cyan]italic cyan[/italic cyan] - [underline bright_green]underline bright_green[/underline bright_green]"
    )
    console.print(
        "  [white on red]white on red[/white on red] - [black on yellow]black on yellow[/black on yellow] - [white on blue]white on blue[/white on blue]"
    )
    console.print(
        "  [rgb(255,0,0)]rgb(255,0,0)[/rgb(255,0,0)] - [#00ff00]#00ff00[/#00ff00] - [color(196)]color(196)[/color(196)]"
    )
    console.print()


def main():
    """Main function for standalone usage."""
    console = Console()
    print_colors_and_styles(console)


if __name__ == "__main__":
    main()
