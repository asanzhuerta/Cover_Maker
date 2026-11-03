"""Command-line entry point for the Cover_Maker engine."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .domain import JobSpec, Mode, OutputFormat, ResidualMode, Stem

app = typer.Typer(
    name="cover-maker",
    help="Local AI stem separation for your own audio files.",
    no_args_is_help=True,
)
models_app = typer.Typer(help="List and install separation models.", no_args_is_help=True)
app.add_typer(models_app, name="models")
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
    """Show detected hardware, the hardware tier and the recommended preset."""
    from .audio.io import ffmpeg_path
    from .paths import Paths
    from .pipeline.runner import resolve_preset
    from .separation.hardware import Tier, detect
    from .separation.installer import separation_available

    paths = Paths.default().ensure()
    hw = detect(paths.home)
    table = Table(title="Cover_Maker doctor", show_header=False)
    table.add_row("Engine", __version__)
    table.add_row("Data folder", str(paths.home))
    table.add_row("CPU", f"{hw.cpu_name} ({hw.physical_cores} cores / {hw.logical_cores} threads)")
    table.add_row("RAM", f"{hw.ram_gb} GB")
    if hw.gpu:
        gpu = hw.gpu
        table.add_row(
            "GPU",
            f"{gpu.name}, {gpu.total_mb} MB ({gpu.free_mb} MB free), "
            f"compute {gpu.compute_capability}, driver {gpu.driver}",
        )
    else:
        table.add_row("GPU", "no NVIDIA GPU detected (CPU mode)")
    table.add_row("Hardware tier", hw.tier.value)
    table.add_row("Recommended preset", resolve_preset("auto", hw.tier is not Tier.CPU).value)
    table.add_row("Free disk", f"{hw.free_disk_gb} GB")
    table.add_row(
        "Power", "battery" if hw.on_battery else "mains" if hw.on_battery is False else "n/a"
    )
    table.add_row("Running DAWs", ", ".join(hw.daws) or "none")
    table.add_row("ffmpeg", ffmpeg_path() or "[yellow]not found[/yellow]")
    table.add_row(
        "Separation support", "installed" if separation_available() else "[yellow]missing[/yellow]"
    )
    console.print(table)


@models_app.command("list")
def models_list() -> None:
    """List catalogue models with their licence class and install state."""
    from .paths import Paths
    from .separation.catalog import Catalog, Installs
    from .store.db import connect

    paths = Paths.default().ensure()
    installs = Installs(connect(paths.db))
    table = Table(title="Separation models")
    for column in ("ID", "Name", "Stems", "Licence", "Size", "Installed"):
        table.add_column(column)
    for model in Catalog.load().models.values():
        table.add_row(
            model.id,
            model.name,
            ", ".join(sorted(stem.value for stem in model.produces)),
            model.licence_class.value,
            f"{model.size_mb} MB",
            "yes" if installs.is_installed(model) else "no",
        )
    console.print(table)


@models_app.command("install")
def models_install(
    model_id: Annotated[str, typer.Argument(help="Catalogue model id (see `models list`).")],
    accept_licence: Annotated[
        bool, typer.Option("--accept-licence", help="Accept the licence notice without prompting.")
    ] = False,
) -> None:
    """Show a model's licence notice and download it once accepted."""
    from .paths import Paths
    from .separation.catalog import Catalog, Installs
    from .separation.installer import InstallError, install
    from .store.db import connect

    paths = Paths.default().ensure()
    model = Catalog.load().get(model_id)
    console.print(f"[bold]{model.name}[/bold]\n{model.notice()}\n")
    accepted = accept_licence or typer.confirm("Do you accept this licence notice?", default=False)
    try:
        target = install(model, paths.models, Installs(connect(paths.db)), accepted=accepted)
    except InstallError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    console.print(f"[green]Installed[/green] {model.id} -> {target}")


def _parse_stems(value: str) -> list[Stem]:
    try:
        return [Stem(part.strip().lower()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        valid = ", ".join(stem.value for stem in Stem)
        raise typer.BadParameter(f"stems must be a comma-separated list of: {valid}") from exc


@app.command()
def separate(
    files: Annotated[list[Path], typer.Argument(help="Audio files to process.", exists=True)],
    stems: Annotated[
        str, typer.Option(help="Comma-separated stems, e.g. vocals,guitar.")
    ] = "vocals",
    mode: Annotated[
        Mode, typer.Option(help="extract the stems, or render the song without them.")
    ] = Mode.EXTRACT,
    residual: Annotated[
        ResidualMode, typer.Option(help="For 'without': keep or drop the residual.")
    ] = ResidualMode.KEEP,
    preset: Annotated[str, typer.Option(help="auto, fast, balanced or max.")] = "auto",
    output: Annotated[Path, typer.Option("--output", "-o", help="Output folder.")] = Path("stems"),
    fmt: Annotated[
        OutputFormat, typer.Option("--format", help="Output format.")
    ] = OutputFormat.WAV,
    allow_cpu: Annotated[
        bool, typer.Option("--allow-cpu", help="Fall back to CPU if the GPU runs out of memory.")
    ] = False,
    low_impact: Annotated[
        bool, typer.Option("--low-impact", help="Use fewer CPU threads (when a DAW is running).")
    ] = False,
) -> None:
    """Separate files into stems, or render them without the selected stems."""
    from .paths import Paths
    from .pipeline.runner import JobRunner, ModelNotInstalled, resolve_preset
    from .separation.catalog import Catalog
    from .separation.hardware import Tier, detect
    from .separation.installer import separation_available
    from .separation.service import NeedsCpuFallback, WorkerService
    from .store.db import connect

    if not separation_available():
        console.print(
            "[red]Error:[/red] separation support is missing (uv sync --extra separation)."
        )
        raise typer.Exit(1)
    paths = Paths.default().ensure()
    hw = detect(paths.home)
    use_gpu = hw.tier is not Tier.CPU
    if hw.daws and not low_impact:
        console.print(f"[yellow]{', '.join(hw.daws)} is running; consider --low-impact.[/yellow]")
    threads = max(1, hw.physical_cores // 2) if low_impact else max(1, hw.physical_cores - 1)

    spec = JobSpec(
        inputs=[file.resolve() for file in files],
        stems=_parse_stems(stems),
        mode=mode,
        residual=residual,
        preset=resolve_preset(preset, use_gpu),
        output_dir=output.resolve(),
        output_format=fmt,
        allow_cpu_fallback=allow_cpu,
    )
    service = WorkerService(threads=threads)
    runner = JobRunner(paths, connect(paths.db), Catalog.load(), service, use_gpu=use_gpu)
    runner.recover()

    def show(event: dict[str, object]) -> None:
        kind = event["type"]
        if kind == "item.step":
            console.print(f"  [cyan]{event['step']}[/cyan]")
        elif kind == "separation.metrics":
            console.print(
                f"  model {event['model']}: {event['seconds']} s on {event['device']} "
                f"({event['precision']}, chunk {event['chunk_s'] or 'default'})"
            )
        elif kind == "separation.retry":
            console.print(f"  [yellow]{event['message']}[/yellow]")
        elif kind == "item.done":
            outputs = event["outputs"]
            assert isinstance(outputs, dict)
            for path in outputs.values():  # pyright: ignore[reportUnknownVariableType]
                console.print(f"  [green]saved[/green] {path}")
        elif kind == "item.failed":
            console.print(f"  [red]failed:[/red] {event['error']}")

    runner.events.subscribe(show)
    console.print(f"Preset [bold]{spec.preset.value}[/bold] on {'GPU' if use_gpu else 'CPU'}")
    try:
        job_id = runner.submit(spec)
        for item in runner.items(job_id):
            console.print(f"[bold]{Path(item['input_path']).name}[/bold]")
        status = runner.run(job_id)
    except (ModelNotInstalled, NeedsCpuFallback) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    finally:
        service.close()
    if status != "done":
        raise typer.Exit(1)
