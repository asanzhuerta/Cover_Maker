"""Command-line entry point for the Cover_Maker engine."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .domain import JobSpec, Mode, OutputFormat, ResidualMode, Stem

if TYPE_CHECKING:
    from .library.collections import Library

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
def serve(
    demo: Annotated[
        bool, typer.Option("--demo", help="Use a fake separator and a separate data folder.")
    ] = False,
) -> None:
    """Run the local API for the desktop app (token from COVER_MAKER_TOKEN)."""
    from .api.server import serve as run_server

    run_server(demo=demo)


@app.command()
def openapi() -> None:
    """Print the OpenAPI schema of the local API (used to generate TypeScript types)."""
    import json

    from .api.app import create_app
    from .api.security import AccessPolicy

    schema = create_app(AccessPolicy(token="x" * 32, host="127.0.0.1:0")).openapi()
    typer.echo(json.dumps(schema, indent=2, sort_keys=True))


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


from .sources.expand import RIGHTS_NOTICE, expand_inputs  # noqa: E402


def _parse_stems(value: str) -> list[Stem]:
    try:
        return [Stem(part.strip().lower()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        valid = ", ".join(stem.value for stem in Stem)
        raise typer.BadParameter(f"stems must be a comma-separated list of: {valid}") from exc


@app.command()
def separate(
    inputs: Annotated[
        list[str], typer.Argument(help="Audio files, folders, or video/playlist links you pasted.")
    ],
    stems: Annotated[
        str, typer.Option(help="Comma-separated stems, e.g. vocals,guitar.")
    ] = "vocals",
    mode: Annotated[
        Mode, typer.Option(help="extract the stems, render the song without them, or both.")
    ] = Mode.EXTRACT,
    residual: Annotated[
        ResidualMode, typer.Option(help="For 'without' and 'both': keep or drop the residual.")
    ] = ResidualMode.KEEP,
    preset: Annotated[str, typer.Option(help="auto, fast, balanced or max.")] = "auto",
    output: Annotated[Path, typer.Option("--output", "-o", help="Output folder.")] = Path("stems"),
    fmt: Annotated[
        OutputFormat, typer.Option("--format", help="Output format.")
    ] = OutputFormat.WAV,
    allow_cpu: Annotated[
        bool, typer.Option("--allow-cpu", help="Fall back to CPU if the GPU runs out of memory.")
    ] = False,
    confirm_rights: Annotated[
        bool,
        typer.Option(
            "--confirm-rights", help="Confirm you own or may use the online content you pasted."
        ),
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
    from .sources.links import UnsupportedInput
    from .sources.youtube import DownloadError
    from .store.db import connect

    if not separation_available():
        console.print(
            "[red]Error:[/red] separation support is missing (uv sync --extra separation --extra cu128, or --extra cpu)."
        )
        raise typer.Exit(1)
    paths = Paths.default().ensure()
    hw = detect(paths.home)
    use_gpu = hw.tier is not Tier.CPU
    if hw.daws and not low_impact:
        console.print(f"[yellow]{', '.join(hw.daws)} is running; consider --low-impact.[/yellow]")
    threads = max(1, hw.physical_cores // 2) if low_impact else max(1, hw.physical_cores - 1)

    try:
        expanded, online = expand_inputs(inputs)
    except (UnsupportedInput, DownloadError, FileNotFoundError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    if not expanded:
        console.print("[yellow]No audio found in the given inputs.[/yellow]")
        raise typer.Exit(1)
    if online and not confirm_rights:
        console.print(f"[bold]{online} online item(s).[/bold] {RIGHTS_NOTICE}")
        confirm_rights = typer.confirm("Do you confirm you have these rights?", default=False)
        if not confirm_rights:
            raise typer.Exit(1)

    spec = JobSpec(
        inputs=expanded,
        stems=_parse_stems(stems),
        mode=mode,
        residual=residual,
        preset=resolve_preset(preset, use_gpu),
        output_dir=output.resolve(),
        output_format=fmt,
        allow_cpu_fallback=allow_cpu,
        rights_confirmed=confirm_rights,
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
        elif kind == "item.progress" and isinstance(event.get("fraction"), float):
            console.print(f"  download {event['fraction']:.0%}", end="\r")
        elif kind == "item.failed":
            console.print(f"  [red]failed:[/red] {event['error']}")

    runner.events.subscribe(show)
    console.print(f"Preset [bold]{spec.preset.value}[/bold] on {'GPU' if use_gpu else 'CPU'}")
    try:
        job_id = runner.submit(spec)
        for item in runner.items(job_id):
            raw = str(item["input_path"])
            console.print(f"[bold]{raw if raw.startswith('http') else Path(raw).name}[/bold]")
        status = runner.run(job_id)
    except (ModelNotInstalled, NeedsCpuFallback) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    finally:
        service.close()
    if status != "done":
        raise typer.Exit(1)


library_app = typer.Typer(
    help="Watched folders, video playlists and imported playlists.", no_args_is_help=True
)
app.add_typer(library_app, name="library")


def _library() -> Library:
    from .library.collections import Library
    from .paths import Paths
    from .store.db import connect

    return Library(connect(Paths.default().ensure().db))


@library_app.command("ls")
def library_ls(
    collection: Annotated[int | None, typer.Argument(help="Collection id.")] = None,
) -> None:
    """List collections, or the items of one collection."""
    library = _library()
    if collection is None:
        table = Table(title="Library")
        for column in ("ID", "Kind", "Title", "Items", "Last sync"):
            table.add_column(column)
        for row in library.collections():
            table.add_row(
                str(row["id"]),
                row["kind"],
                row["title"],
                str(row["items"]),
                row["synced_at"] or "never",
            )
        console.print(table)
        return
    table = Table(title=library.collection(collection)["title"])
    for column in ("Item", "#", "Artist", "Title", "Status", "Score", "Input"):
        table.add_column(column)
    for row in library.items(collection):
        score = f"{row['score']:.2f}" if row["score"] is not None else ""
        table.add_row(
            str(row["id"]), str(row["position"] + 1), row["artist"] or "", row["title"],
            row["status"], score, row["input"] or "",
        )  # fmt: skip
    console.print(table)


@library_app.command("add-folder")
def library_add_folder(
    folder: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
) -> None:
    """Watch a folder: new or changed audio files are processed on sync."""
    console.print(f"Collection {_library().add_folder(folder)} -> {folder.resolve()}")


@library_app.command("add-playlist")
def library_add_playlist(link: Annotated[str, typer.Argument(help="Video playlist link.")]) -> None:
    """Follow a video playlist: new videos are processed on sync."""
    from .sources.links import InputKind, parse_input

    parsed = parse_input(link, prefer_playlist=True)
    if parsed.kind is not InputKind.PLAYLIST:
        console.print("[red]Error:[/red] that link is not a playlist.")
        raise typer.Exit(1)
    console.print(f"Collection {_library().add_video_playlist(parsed.value)} -> {parsed.url}")


@library_app.command("import")
def library_import(
    playlist_file: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, help="JSON, CSV, JSPF or M3U file.")
    ],
    search: Annotated[
        list[Path], typer.Option("--search", "-s", help="Folders that hold your audio files.")
    ],
) -> None:
    """Import a playlist file and match its entries against your own audio files."""
    library = _library()
    for collection_id in library.import_playlist_file(playlist_file, search):
        result = library.sync(collection_id)
        title = library.collection(collection_id)["title"]
        console.print(
            f"Collection {collection_id} '{title}': {len(result.ready)} matched, "
            f"{result.needs_review} to review, {result.unavailable} not found"
        )


@library_app.command("sync")
def library_sync(collection: Annotated[int, typer.Argument(help="Collection id.")]) -> None:
    """Refresh a collection and report what changed (processing only redoes new work)."""
    result = _library().sync(collection)
    console.print(
        f"+{result.added} new, -{result.removed} removed, {result.unchanged} unchanged; "
        f"{len(result.ready)} ready, {result.needs_review} to review, {result.unavailable} not found"
    )


@library_app.command("match")
def library_match(
    item: Annotated[int, typer.Argument(help="Item id from `library ls <collection>`.")],
    file: Annotated[Path | None, typer.Argument(exists=True, dir_okay=False)] = None,
    unavailable: Annotated[
        bool, typer.Option("--unavailable", help="Mark as not available.")
    ] = False,
) -> None:
    """Correct the file matched to an imported playlist entry."""
    if file is None and not unavailable:
        console.print("[red]Error:[/red] give a file or --unavailable.")
        raise typer.Exit(1)
    _library().set_match(item, None if unavailable else file)
    console.print("[green]Match updated.[/green]")
