"""Command-line entry point for the Cover_Maker engine."""

from typing import Annotated

import typer
from rich.console import Console

from . import __version__

app = typer.Typer(
    name="cover-maker",
    help="Local AI stem separation for your own audio files.",
    no_args_is_help=True,
)
console = Console()


def _show_version(value: bool) -> None:
    if value:
        console.print(f"cover-maker {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_show_version,
            is_eager=True,
            help="Show the engine version and exit.",
        ),
    ] = False,
) -> None:
    """Cover_Maker engine."""


@app.command()
def serve() -> None:
    """Run the local API for the desktop app (token from COVER_MAKER_TOKEN)."""
    from .api.server import serve as run_server

    run_server()


@app.command()
def doctor() -> None:
    """Check the local environment (placeholder until M3)."""
    console.print("[green]Engine installed.[/green] Hardware checks arrive in M3.")
