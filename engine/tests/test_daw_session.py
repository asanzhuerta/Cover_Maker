"""DAW session export: tempo map, the three writers (golden files) and the folder.

Golden files live in ``tests/golden/daw``. After an intended change to a writer,
regenerate them with ``UPDATE_GOLDEN=1 uv run pytest tests/test_daw_session.py``
and review the diff. Everything here uses synthetic audio only.
"""

from __future__ import annotations

import io
import os
import struct
import zipfile
from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
import xmlschema
from hypothesis import given, settings
from hypothesis import strategies as st

from cover_maker.audio.analysis import Analysis
from cover_maker.daw import dawproject, midi, reaper
from cover_maker.daw.export import ORIGINAL, RESIDUAL, TrackSettings, build_session, export_session
from cover_maker.daw.model import DawFormat, Key, Marker, Session, TempoPoint, Track
from cover_maker.daw.tempo import (
    MIN_PICKUP,
    STEADY_TOLERANCE,
    beats_at,
    tempo_map,
    time_signature_changes,
)
from cover_maker.domain import JobSpec, ResidualMode, Stem
from cover_maker.pipeline.runner import MixSources
from cover_maker.store.analyses import Marker as StoredMarker

from .conftest import tone

GOLDEN = Path(__file__).parent / "golden" / "daw"
SCHEMAS = Path(__file__).parent / "schemas" / "dawproject"
# A grid that is not steady: bars of 2.4 s (100 BPM) and 2.7 s (88.9 BPM), after a one-beat pickup.
VARIABLE_DOWNBEATS = [0.6, 3.0, 5.7, 8.1, 10.8]


def sample_session() -> Session:
    tracks = (
        Track("Vocals", "Demo - Vocals.wav", 12.5, 2, gain=0.5, pan=-0.25),
        Track("Drums", "Demo - Drums.wav", 12.5, 2, gain=1.4125375446),
        Track("Bass", "Demo - Bass.wav", 12.5, 1, muted=True),
        Track(RESIDUAL, "Demo - Residual.wav", 12.5, 2),
        Track(ORIGINAL, "Demo - Original mix.wav", 12.5, 2, muted=True),
    )
    return Session(
        title="Demo",
        sample_rate=44_100,
        bpm=98.0,
        tracks=tracks,
        tempo=tempo_map(VARIABLE_DOWNBEATS, 98.0),
        markers=(Marker("Intro", 0.0), Marker('Verse "A"', 3.0), Marker("Chorus & más", 8.1)),
        key=Key("G", "major"),
        tuning_cents=-20.0,
        artist="Cover_Maker tests",
        notes=("Synthetic test session.",),
    )


def check_golden(name: str, actual: bytes) -> None:
    path = GOLDEN / name
    if os.environ.get("UPDATE_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(actual)
    assert path.exists(), f"missing golden file {name}; run with UPDATE_GOLDEN=1"
    assert actual == path.read_bytes(), f"{name} differs from the golden file"


# ---------------------------------------------------------------- tempo map


def test_steady_grid_gets_one_tempo_after_a_pickup_bar() -> None:
    downbeats = [1.2 + 2.4 * i for i in range(20)]  # 100 BPM, first bar at 1.2 s (two beats)

    tempo = tempo_map(downbeats, 100.0)

    assert tempo == (
        TempoPoint(0.0, 100.0, numerator=2),
        TempoPoint(1.2, 100.0),
    )
    assert beats_at(tempo, downbeats[-1]) == pytest.approx(2 + 4 * 19)


def test_variable_grid_puts_a_bar_line_on_every_downbeat() -> None:
    tempo = tempo_map(VARIABLE_DOWNBEATS, 98.0)

    first = beats_at(tempo, VARIABLE_DOWNBEATS[0])
    assert first == pytest.approx(1.0)  # one-beat pickup
    for index, time in enumerate(VARIABLE_DOWNBEATS):
        assert beats_at(tempo, time) == pytest.approx(first + 4 * index, abs=1e-4)
    assert [p.numerator for p in time_signature_changes(tempo)] == [1, 4]


def test_a_pickup_too_short_for_a_bar_joins_the_first_bar() -> None:
    downbeats = [0.03 + 2.0 * i for i in range(8)]  # 120 BPM, 30 ms of silence first

    tempo = tempo_map(downbeats, 120.0)

    assert tempo[0].time == 0.0 and tempo[0].numerator == 4
    assert [p.numerator for p in time_signature_changes(tempo)] == [4]
    for index, time in enumerate(downbeats[1:], start=1):
        assert beats_at(tempo, time) == pytest.approx(4 * index, abs=1e-3)


@pytest.mark.parametrize(("bpm", "expected"), [(0.0, 120.0), (87.5, 87.5), (5000.0, 960.0)])
def test_without_downbeats_the_song_tempo_holds(bpm: float, expected: float) -> None:
    assert tempo_map([], bpm) == (TempoPoint(0.0, expected),)


@settings(max_examples=150, deadline=None)
@given(
    anchor=st.floats(0.0, 6.0),
    bars=st.lists(st.floats(1.0, 4.0), min_size=1, max_size=12),
)
def test_every_downbeat_lands_on_a_bar_line(anchor: float, bars: list[float]) -> None:
    downbeats = [anchor]
    for length in bars:
        downbeats.append(downbeats[-1] + length)

    tempo = tempo_map(downbeats, 100.0)

    assert tempo[0].time == 0.0
    assert all(a.time < b.time for a, b in pairwise(tempo))
    reference = beats_at(tempo, downbeats[1])
    for index, time in enumerate(downbeats[1:]):
        # Within the steady-grid tolerance (in beats at the local tempo), never further.
        local = max(p.bpm for p in tempo)
        slack = 2 * STEADY_TOLERANCE * local / 60.0 + 1e-3
        assert abs(beats_at(tempo, time) - reference - 4 * index) <= slack
    if anchor >= MIN_PICKUP + STEADY_TOLERANCE:
        whole = beats_at(tempo, downbeats[0])
        assert abs(whole - round(whole)) <= 2 * STEADY_TOLERANCE * tempo[0].bpm / 60.0 + 1e-3


@pytest.mark.parametrize(
    ("tonic", "mode", "fifths"),
    [("C", "major", 0), ("G", "major", 1), ("E", "minor", 1), ("F", "major", -1),
     ("D", "minor", -1), ("Bb", "major", -2), ("F#", "major", 6), ("Ab", "major", -4)],
)  # fmt: skip
def test_key_signature_counts_sharps_and_flats(tonic: str, mode: str, fifths: int) -> None:
    assert Key(tonic, mode).fifths() == fifths


# ---------------------------------------------------------------- writers


def test_reaper_project_matches_the_golden_file() -> None:
    text = reaper.write(sample_session())

    check_golden("demo.RPP", text.encode("utf-8"))
    assert "  MARKER 2 3 'Verse \"A\"' 0 0 1" in text.splitlines()
    assert "    MUTESOLO 1 0 0" in text.splitlines()


def test_dawproject_xml_matches_the_golden_files() -> None:
    session = sample_session()

    check_golden("demo.project.xml", dawproject.project_xml(session, "test"))
    check_golden("demo.metadata.xml", dawproject.metadata_xml(session))


def test_dawproject_xml_is_valid_against_the_official_schema() -> None:
    session = sample_session()
    project = xmlschema.XMLSchema(str(SCHEMAS / "Project.xsd"))
    metadata = xmlschema.XMLSchema(str(SCHEMAS / "MetaData.xsd"))

    project.validate(dawproject.project_xml(session).decode("utf-8"))
    metadata.validate(dawproject.metadata_xml(session).decode("utf-8"))
    bare = Session("Bare", 44_100, 120.0, (), tempo_map([], 0.0))
    project.validate(dawproject.project_xml(bare).decode("utf-8"))


def test_dawproject_container_is_reproducible_and_holds_both_documents() -> None:
    session = sample_session()

    data = dawproject.container(session, "test")

    assert data == dawproject.container(session, "test")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.namelist() == ["project.xml", "metadata.xml"]
        assert archive.read("project.xml") == dawproject.project_xml(session, "test")


def _midi_events(data: bytes) -> list[tuple[int, int, bytes]]:
    """(absolute tick, meta type, payload) of a format 0 file with meta events only."""
    assert data[:4] == b"MThd"
    _size, fmt, tracks, division = struct.unpack(">IHHH", data[4:14])
    assert (fmt, tracks, division) == (0, 1, midi.TICKS_PER_QUARTER)
    assert data[14:18] == b"MTrk"
    (length,) = struct.unpack(">I", data[18:22])
    body, pos, now, events = data[22 : 22 + length], 0, 0, []

    def vlq() -> int:
        nonlocal pos
        value = 0
        while True:
            byte = body[pos]
            pos += 1
            value = (value << 7) | (byte & 0x7F)
            if byte < 0x80:
                return value

    while pos < len(body):
        now += vlq()
        assert body[pos] == 0xFF
        kind = body[pos + 1]
        pos += 2
        size = vlq()
        events.append((now, kind, body[pos : pos + size]))
        pos += size
    return events


def test_midi_tempo_map_matches_the_golden_file_and_the_grid() -> None:
    session = sample_session()

    data = midi.write(session)

    check_golden("demo.mid", data)
    events = _midi_events(data)
    assert events[-1][1] == 0x2F  # end of track
    signatures = [(t, p[0]) for t, k, p in events if k == 0x58]
    assert signatures == [(0, 1), (midi.TICKS_PER_QUARTER, 4)]
    assert (0, 0x59, struct.pack(">bB", 1, 0)) in events  # G major: one sharp
    markers = [(t, p.decode("utf-8")) for t, k, p in events if k == 0x06]
    assert markers[2] == (13 * midi.TICKS_PER_QUARTER, "Chorus & más")


def test_names_with_every_quote_character_stay_one_token_in_rpp() -> None:
    session = Session(
        "Q", 44_100, 120.0, (), tempo_map([], 0.0), markers=(Marker("a\"b'c`d\nnext", 1.0),)
    )

    line = next(x for x in reaper.write(session).splitlines() if "MARKER" in x)

    assert line == "  MARKER 1 1 \"a'b'c`d next\" 0 0 1"


# ---------------------------------------------------------------- export folder


def _sources(tmp_path: Path, seconds: float = 1.0) -> MixSources:
    library = tmp_path / "library"
    library.mkdir()
    vocals = tone(seconds, freq=440.0) * np.float32(0.5)
    drums = tone(seconds, freq=110.0) * np.float32(0.25)
    mix = vocals + drums + tone(seconds, freq=880.0) * np.float32(0.1)
    files = {}
    for name, audio in (("mix", mix), ("vocals", vocals), ("drums", drums)):
        files[name] = library / f"{name}.wav"
        sf.write(str(files[name]), audio, 44_100, subtype="FLOAT")
    spec = JobSpec(inputs=["x.wav"], stems=[Stem.VOCALS], output_dir=tmp_path / "out")
    return MixSources(
        title="Demo",
        mix=files["mix"],
        stems={Stem.VOCALS: files["vocals"], Stem.DRUMS: files["drums"]},
        spec=spec,
    )


ANALYSIS = Analysis(
    tuning_cents=-20.0, key="G", mode="major", key_confidence=0.2, bpm=120.0,
    beats=[0.25, 0.5, 0.75], downbeats=[0.25],
)  # fmt: skip


def test_export_writes_aligned_stems_and_every_project(tmp_path: Path) -> None:
    sources = _sources(tmp_path)

    files = export_session(
        sources,
        {Stem.VOCALS: TrackSettings(gain=0.5, pan=0.3), Stem.DRUMS: TrackSettings(muted=True)},
        ResidualMode.DROP,
        ANALYSIS,
        [StoredMarker("Verse", 0.5), StoredMarker("After the end", 99.0)],
    )

    assert files.folder == tmp_path / "out" / "Demo - DAW session"
    assert files.tracks == ["Vocals", "Drums", RESIDUAL, ORIGINAL]
    assert set(files.projects) == set(DawFormat)
    names = sorted(p.name for p in files.folder.iterdir())
    assert names == sorted(
        ["Demo.RPP", "Demo.dawproject", "Demo - tempo map.mid", "Demo - Vocals.wav",
         "Demo - Drums.wav", "Demo - Residual.wav", "Demo - Original mix.wav"]
    )  # fmt: skip
    lengths = {sf.info(str(p)).frames for p in files.folder.glob("*.wav")}
    assert lengths == {44_100}  # every file starts at 0 and has the song's length
    vocals, _ = sf.read(str(files.folder / "Demo - Vocals.wav"), dtype="float32")
    assert np.array_equal(vocals, sf.read(str(sources.stems[Stem.VOCALS]), dtype="float32")[0])
    rest, _ = sf.read(str(files.folder / "Demo - Residual.wav"), dtype="float32")
    expected = tone(1.0, freq=880.0) * np.float32(0.1)
    assert np.allclose(rest, expected, atol=1e-5)

    rpp = (files.folder / "Demo.RPP").read_text("utf-8")
    assert "    VOLPAN 0.5 0.3 -1 -1 1" in rpp
    tracks = rpp.split("  <TRACK")[1:]
    muted = [t.splitlines()[1].split(" ", 5)[-1] for t in tracks if "MUTESOLO 1" in t]
    assert muted == ['"Drums"', '"Residual"', '"Original mix"']
    assert '"Verse"' in rpp and "After the end" not in rpp
    assert "|Key: G major" in rpp
    for line in rpp.splitlines():
        if line.strip().startswith("FILE "):
            assert (files.folder / line.split('"')[1]).is_file()
    with zipfile.ZipFile(files.projects[DawFormat.DAWPROJECT]) as archive:
        xmlschema.XMLSchema(str(SCHEMAS / "Project.xsd")).validate(
            archive.read("project.xml").decode("utf-8")
        )


def test_export_never_overwrites_and_writes_only_chosen_formats(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    first = export_session(sources, {}, ResidualMode.KEEP, None)

    second = export_session(sources, {}, ResidualMode.KEEP, None, formats={DawFormat.REAPER})

    assert second.folder.name == "Demo - DAW session (2)"
    assert list(second.projects) == [DawFormat.REAPER]
    assert not (second.folder / "Demo.dawproject").exists()
    assert (first.folder / "Demo.dawproject").exists()
    rpp = second.projects[DawFormat.REAPER].read_text("utf-8")
    assert "TEMPO 120 4 4" in rpp  # no analysis: the default tempo, no key
    assert "Key:" not in rpp


def test_a_failed_export_leaves_no_folder_behind(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    sources.stems[Stem.DRUMS].unlink()

    with pytest.raises(OSError):
        export_session(sources, {}, ResidualMode.KEEP, None)

    assert list((tmp_path / "out").iterdir()) == []


def test_session_without_a_confident_key_leaves_it_out() -> None:
    unsure = Analysis(tuning_cents=0.0, key="C", mode="major", key_confidence=0.0, bpm=0.0)

    session = build_session("S", [Track("Vocals", "S - Vocals.wav", 3.0, 2)], unsure)

    assert session.key is None
    assert session.tempo == (TempoPoint(0.0, 120.0),)
