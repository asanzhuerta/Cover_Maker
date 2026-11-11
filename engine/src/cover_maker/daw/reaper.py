"""REAPER project (``.RPP``) writer.

RPP is REAPER's plain-text project format: nested ``<CHUNK ... >`` blocks of
space-separated lines. Only the lines a session needs are written; REAPER fills
in defaults (and GUIDs) for everything else when it opens the project.

- ``TEMPO bpm num denom`` is the base tempo; the ``TEMPOENVEX`` chunk holds the
  tempo map as square (hold) points ``PT seconds bpm 1 [signature 0 1]``, where
  the signature is ``numerator + denominator * 65536`` on points that start a bar
  in a new time signature.
- ``MARKER index seconds "name" 0 0 1`` adds a marker (flag 0: not a region).
- Each track holds one item at position 0 whose source is the stem file, given
  relative to the project folder. ``VOLPAN`` is linear volume and pan (-1..1);
  ``MUTESOLO`` starts with the mute flag.
"""

from __future__ import annotations

from .model import Session
from .tempo import signature_flags

# The oldest REAPER line every chunk below is valid for; newer versions open it silently.
WRITER_VERSION = "6.0"


def _num(value: float) -> str:
    """Shortest stable decimal for a float (no exponent, no trailing zeros)."""
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _quote(text: str) -> str:
    """Quote a string the way REAPER does: pick a quote character it does not contain."""
    clean = " ".join(text.split())
    for mark in ('"', "'", "`"):
        if mark not in clean:
            return f"{mark}{clean}{mark}"
    return '"' + clean.replace('"', "'") + '"'


def _signature(numerator: int, denominator: int = 4) -> int:
    return numerator + denominator * 65536


def write(session: Session) -> str:
    """The project file's text (UTF-8, LF line ends)."""
    lines: list[str] = [f'<REAPER_PROJECT 0.1 "{WRITER_VERSION}" 0']
    lines.append(f"  TEMPO {_num(session.bpm)} 4 4")
    lines.append(f"  SAMPLERATE {session.sample_rate} 0 0")
    lines.append("  <NOTES 0 2")
    lines.extend(f"    |{' '.join(line.split())}" for line in session.summary())
    lines.append("  >")

    lines.extend(
        [
            "  <TEMPOENVEX",
            "    ACT 1 -1",
            "    VIS 1 0 1",
            "    LANEHEIGHT 0 0",
            "    ARM 0",
            "    DEFSHAPE 1 -1 -1",
        ]
    )
    for point, starts in zip(session.tempo, signature_flags(session.tempo), strict=True):
        line = f"    PT {point.time:.12f} {point.bpm:.10f} 1"
        if starts:
            line += f" {_signature(point.numerator)} 0 1"
        lines.append(line)
    lines.append("  >")

    for index, marker in enumerate(session.markers, start=1):
        lines.append(f"  MARKER {index} {_num(marker.time)} {_quote(marker.name)} 0 0 1")

    for track in session.tracks:
        lines.extend(
            [
                "  <TRACK",
                f"    NAME {_quote(track.name)}",
                f"    VOLPAN {_num(track.gain)} {_num(track.pan)} -1 -1 1",
                f"    MUTESOLO {1 if track.muted else 0} 0 0",
                f"    NCHAN {max(2, track.channels)}",
                "    <ITEM",
                "      POSITION 0",
                f"      LENGTH {_num(track.seconds)}",
                "      LOOP 0",
                "      FADEIN 1 0 0 1 0 0 0",
                "      FADEOUT 1 0 0 1 0 0 0",
                f"      NAME {_quote(track.file)}",
                "      SOFFS 0",
                "      <SOURCE WAVE",
                f"        FILE {_quote(track.file)}",
                "      >",
                "    >",
                "  >",
            ]
        )
    lines.append(">")
    return "\n".join(lines) + "\n"
