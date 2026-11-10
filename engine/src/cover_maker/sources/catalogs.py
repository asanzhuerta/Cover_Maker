# pyright: basic
# (The catalogue APIs answer untyped JSON; this module only adapts it.)
"""Creative Commons music catalogues: ccMixter and the Internet Archive.

Only openly licensed audio is offered (Creative Commons or public domain).
Every download keeps its attribution in a ``<file>.credits.json`` sidecar,
which the export turns into a ``CREDITS.txt`` next to the stems.
"""

from __future__ import annotations

import http.client
import json
import re
import shutil
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .. import __version__

SOURCES = ("ccmixter", "archive")
USER_AGENT = f"Cover_Maker/{__version__} (+https://github.com/asanzhuerta/Cover_Maker)"
TIMEOUT_S = 30
# The app downloads only from the Internet Archive, which allows it (and never
# acts as an open proxy). ccMixter blocks automated downloads of its files, so
# the user downloads those on its site and attaches the file (`attach`).
DOWNLOAD_HOSTS = ("archive.org",)
# Hosts the catalogue searches may query.
CATALOG_HOSTS = ("ccmixter.org", "archive.org")
DIRECT_DOWNLOAD = ("archive",)
# Internet Archive formats, best first: lossless, then common lossy ones.
ARCHIVE_FORMATS = ("Flac", "WAVE", "VBR MP3", "MP3", "128Kbps MP3", "Ogg Vorbis")
MAX_DOWNLOAD_BYTES = 1024 * 1024 * 1024
# ccMixter repeats the whole JSON answer in an `X-JSON` response header, which
# exceeds http.client's 64 KB header-line limit; allow up to 4 MB.
http.client._MAXLINE = max(http.client._MAXLINE, 4 * 1024 * 1024)  # pyright: ignore[reportPrivateUsage, reportAttributeAccessIssue]


class CatalogError(RuntimeError):
    pass


@dataclass(frozen=True)
class CatalogFile:
    name: str
    url: str
    title: str
    size_bytes: int | None = None


@dataclass(frozen=True)
class CatalogEntry:
    source: str
    id: str
    title: str
    artist: str
    licence_name: str
    licence_url: str
    page_url: str
    files: list[CatalogFile] = field(default_factory=list[CatalogFile])

    @property
    def restrictions(self) -> list[str]:
        return licence_restrictions(self.licence_url)


def licence_restrictions(url: str) -> list[str]:
    """`NC` (non-commercial) and `ND` (no derivatives) from a CC licence URL."""
    path = urllib.parse.urlparse(url).path.lower()
    match = re.search(r"/licenses/([a-z+-]+)/", path)
    parts = match.group(1).split("-") if match else []
    return [flag.upper() for flag in ("nc", "nd") if flag in parts]


def is_open_licence(url: str | None) -> bool:
    if not url:
        return False
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc.endswith("creativecommons.org") and (
        parsed.path.startswith("/licenses/") or parsed.path.startswith("/publicdomain/")
    )


def licence_name_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path.strip("/").split("/")
    if len(path) >= 3 and path[0] == "licenses":
        return f"CC {path[1].upper()} {path[2]}"
    if len(path) >= 2 and path[0] == "publicdomain":
        return "CC0 / public domain" if path[1] == "zero" else "Public domain"
    return url


def _https_opener() -> urllib.request.OpenerDirector:
    """An opener that only speaks HTTPS: no ``file:``, ``ftp:`` or plain ``http:`` URLs."""
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler(),
        urllib.request.HTTPSHandler(),
        urllib.request.HTTPRedirectHandler(),
        urllib.request.HTTPDefaultErrorHandler(),
        urllib.request.HTTPErrorProcessor(),
    ):
        opener.add_handler(handler)
    return opener


_OPENER = _https_opener()


def _on_hosts(url: str, hosts: tuple[str, ...]) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""
    return parsed.scheme == "https" and any(
        host == allowed or host.endswith(f".{allowed}") for allowed in hosts
    )


def _open(url: str, hosts: tuple[str, ...]) -> Any:
    """Open ``url`` over HTTPS after checking it points at one of ``hosts``."""
    if not _on_hosts(url, hosts):
        raise CatalogError(f"refusing to contact {urllib.parse.urlparse(url).hostname or url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    # Scheme and host are checked above and the opener has no file or ftp handler.
    # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
    return _OPENER.open(request, timeout=TIMEOUT_S)


def _get_json(url: str) -> Any:
    try:
        with _open(url, CATALOG_HOSTS) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise CatalogError(f"could not reach the catalogue: {exc}") from exc


def _size(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- ccMixter


def parse_ccmixter(uploads: list[dict[str, Any]]) -> list[CatalogEntry]:
    entries: list[CatalogEntry] = []
    for upload in uploads:
        licence_url = str(upload.get("license_url") or "")
        if not is_open_licence(licence_url):
            continue
        title = str(upload.get("upload_name") or upload.get("upload_id"))
        files = [
            CatalogFile(
                name=str(f.get("file_name")),
                url=str(f.get("download_url")),
                title=title,
                size_bytes=_size(f.get("file_rawsize")),
            )
            for f in upload.get("files") or []
            if (f.get("file_format_info") or {}).get("media-type") == "audio"
            and f.get("download_url")
        ]
        if not files:
            continue
        entries.append(
            CatalogEntry(
                source="ccmixter",
                id=str(upload.get("upload_id")),
                title=title,
                artist=str(upload.get("user_real_name") or upload.get("user_name") or ""),
                licence_name=str(upload.get("license_name") or licence_name_from_url(licence_url)),
                licence_url=licence_url,
                page_url=str(upload.get("file_page_url") or ""),
                files=files,
            )
        )
    return entries


def _search_ccmixter(query: str, limit: int) -> list[CatalogEntry]:
    params = urllib.parse.urlencode({"f": "json", "search": query, "limit": limit, "sort": "rank"})
    data = _get_json(f"https://ccmixter.org/api/query?{params}")
    return parse_ccmixter(data if isinstance(data, list) else [])


# -------------------------------------------------------- Internet Archive


def parse_archive_search(data: dict[str, Any]) -> list[CatalogEntry]:
    entries: list[CatalogEntry] = []
    for doc in (data.get("response") or {}).get("docs") or []:
        licence_url = str(doc.get("licenseurl") or "")
        if not is_open_licence(licence_url) or not doc.get("identifier"):
            continue
        creator = doc.get("creator")
        if isinstance(creator, list):
            creator = ", ".join(str(c) for c in creator)
        identifier = str(doc["identifier"])
        entries.append(
            CatalogEntry(
                source="archive",
                id=identifier,
                title=str(doc.get("title") or identifier),
                artist=str(creator or ""),
                licence_name=licence_name_from_url(licence_url),
                licence_url=licence_url,
                page_url=f"https://archive.org/details/{identifier}",
            )
        )
    return entries


def _search_archive(query: str, limit: int) -> list[CatalogEntry]:
    q = f"({query}) AND mediatype:(audio) AND licenseurl:(*creativecommons.org*)"
    params = urllib.parse.urlencode(
        [("q", q), ("fl[]", "identifier"), ("fl[]", "title"), ("fl[]", "creator"),
         ("fl[]", "licenseurl"), ("rows", str(limit)), ("output", "json")]
    )  # fmt: skip
    return parse_archive_search(_get_json(f"https://archive.org/advancedsearch.php?{params}"))


def parse_archive_files(identifier: str, metadata: dict[str, Any]) -> list[CatalogFile]:
    """One file per track, in the best available format."""
    licence_url = (metadata.get("metadata") or {}).get("licenseurl")
    if not is_open_licence(licence_url):
        raise CatalogError("this item has no Creative Commons or public-domain licence")
    best: dict[str, tuple[int, dict[str, Any]]] = {}
    for f in metadata.get("files") or []:
        fmt = f.get("format")
        if fmt not in ARCHIVE_FORMATS:
            continue
        name = str(f.get("name"))
        track = name.rsplit(".", 1)[0]
        rank = ARCHIVE_FORMATS.index(fmt)
        if track not in best or rank < best[track][0]:
            best[track] = (rank, f)
    files: list[CatalogFile] = []
    for track, (_, f) in sorted(best.items()):
        name = str(f["name"])
        quoted = urllib.parse.quote(name)
        files.append(
            CatalogFile(
                name=name,
                url=f"https://archive.org/download/{identifier}/{quoted}",
                title=str(f.get("title") or track),
                size_bytes=_size(f.get("size")),
            )
        )
    return files


def archive_files(identifier: str) -> list[CatalogFile]:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", identifier):
        raise CatalogError("invalid Internet Archive identifier")
    return parse_archive_files(
        identifier,
        _get_json(f"https://archive.org/metadata/{urllib.parse.quote(identifier, safe='')}"),
    )


# ---------------------------------------------------------------- shared


def search(source: str, query: str, limit: int = 20) -> list[CatalogEntry]:
    query = query.strip()
    if not query:
        return []
    if source == "ccmixter":
        return _search_ccmixter(query, limit)
    if source == "archive":
        return _search_archive(query, limit)
    raise CatalogError(f"unknown catalogue: {source}")


def allowed_download(url: str) -> bool:
    return _on_hosts(url, DOWNLOAD_HOSTS)


@dataclass(frozen=True)
class Credits:
    title: str
    artist: str
    licence_name: str
    licence_url: str
    page_url: str
    source: str

    def text(self) -> str:
        lines = [
            f"{self.title} - {self.artist}" if self.artist else self.title,
            f"Source: {self.page_url}",
            f"Licence: {self.licence_name} ({self.licence_url})",
        ]
        restrictions = licence_restrictions(self.licence_url)
        if "ND" in restrictions:
            lines.append("Note: no-derivatives licence; do not share stems or mixes made from it.")
        if "NC" in restrictions:
            lines.append("Note: non-commercial licence.")
        return "\n".join(lines)


def safe_name(text: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text).strip(" .")
    return cleaned[:120] or "track"


def credits_path(audio: Path) -> Path:
    return audio.with_name(f"{audio.name}.credits.json")


def read_credits(audio: Path) -> Credits | None:
    sidecar = credits_path(audio)
    if not sidecar.is_file():
        return None
    try:
        return Credits(**json.loads(sidecar.read_text(encoding="utf-8")))
    except (ValueError, TypeError):
        return None


def _target(credits: Credits, target_dir: Path, suffix: str) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    stem = safe_name(f"{credits.artist} - {credits.title}" if credits.artist else credits.title)
    return target_dir / f"{stem}{suffix.lower() or '.mp3'}"


def attach(source: Path, credits: Credits, target_dir: Path) -> Path:
    """Copy a file the user downloaded from a catalogue into the library with its credits."""
    if not is_open_licence(credits.licence_url):
        raise CatalogError("only Creative Commons or public-domain audio can be added")
    if not source.is_file():
        raise CatalogError(f"file not found: {source}")
    target = _target(credits, target_dir, source.suffix)
    shutil.copy2(source, target)
    credits_path(target).write_text(json.dumps(asdict(credits), indent=2), encoding="utf-8")
    return target


def download(file: CatalogFile, credits: Credits, target_dir: Path) -> Path:
    """Download one audio file into ``target_dir`` with its credits sidecar."""
    if not allowed_download(file.url):
        raise CatalogError("the app downloads only from the Internet Archive")
    if not is_open_licence(credits.licence_url):
        raise CatalogError("only Creative Commons or public-domain audio can be downloaded")
    target = _target(credits, target_dir, Path(urllib.parse.urlparse(file.url).path).suffix)
    partial = target.with_name(f"{target.name}.partial")
    try:
        with (
            _open(file.url, DOWNLOAD_HOSTS) as response,
            partial.open("wb") as out,
        ):
            written = 0
            while chunk := response.read(1 << 16):
                written += len(chunk)
                if written > MAX_DOWNLOAD_BYTES:
                    raise CatalogError("the file is larger than 1 GB")
                out.write(chunk)
    except CatalogError:
        partial.unlink(missing_ok=True)
        raise
    except Exception as exc:
        partial.unlink(missing_ok=True)
        raise CatalogError(f"download failed: {exc}") from exc
    partial.replace(target)
    credits_path(target).write_text(json.dumps(asdict(credits), indent=2), encoding="utf-8")
    return target


def write_credits(output_dir: Path, credits: Credits) -> Path:
    """Add a track's attribution to CREDITS.txt in an output folder (once)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "CREDITS.txt"
    block = credits.text()
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if block not in existing:
        header = (
            ""
            if existing
            else (
                "Credits for the Creative Commons audio used in this folder.\n"
                "Stems and mixes were made with Cover_Maker from the original recordings.\n\n"
            )
        )
        path.write_text(existing + header + block + "\n\n", encoding="utf-8")
    return path
