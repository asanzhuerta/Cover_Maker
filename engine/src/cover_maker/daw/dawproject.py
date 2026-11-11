"""DAWproject (``.dawproject``) writer.

DAWproject is an open exchange format by Bitwig (specification and schema under
the MIT licence, https://github.com/bitwig/dawproject), read by Bitwig Studio,
Studio One and Cubase among others. A project is a ZIP container with
``project.xml`` (validated by ``Project.xsd``) and ``metadata.xml``
(``MetaData.xsd``).

Choices for Cover_Maker sessions (ADR-011):

- The arrangement is on a **seconds** timeline (``timeUnit="seconds"``), so the
  clips, markers and tempo points sit exactly where the audio has them, whatever
  the tempo map does.
- Audio is **referenced**, not embedded (``external="true"``, relative to the
  ``.dawproject`` file), so the stems are shared with the other project formats
  in the same folder instead of being stored twice.
- There is no key signature element, so the key goes in the metadata comment.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from .. import __version__
from .model import Session
from .tempo import time_signature_changes

FORMAT_VERSION = "1.0"
# A fixed timestamp keeps the container byte-for-byte reproducible.
_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_VOLUME_MAX = 2.0  # +6 dB, the mixer's highest fader position


def _num(value: float) -> str:
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _xml(root: ET.Element) -> bytes:
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True) + b"\n"


def project_xml(session: Session, application_version: str = __version__) -> bytes:
    project = ET.Element("Project", version=FORMAT_VERSION)
    ET.SubElement(project, "Application", name=session.generator, version=application_version)

    transport = ET.SubElement(project, "Transport")
    ET.SubElement(
        transport, "Tempo", id="tempo", name="Tempo", unit="bpm", value=_num(session.bpm),
        min="20", max="960",
    )  # fmt: skip
    # The song's time signature; a pickup bar is in the time signature automation.
    ET.SubElement(
        transport, "TimeSignature", id="time-signature", name="Time Signature", numerator="4",
        denominator="4",
    )  # fmt: skip

    structure = ET.SubElement(project, "Structure")
    master = ET.SubElement(
        structure, "Track", id="track-master", name="Master", contentType="audio", loaded="true"
    )
    master_channel = ET.SubElement(
        master, "Channel", id="channel-master", role="master", audioChannels="2"
    )
    ET.SubElement(master_channel, "Mute", value="false")
    ET.SubElement(master_channel, "Pan", unit="normalized", value="0.5", min="0", max="1")
    ET.SubElement(
        master_channel, "Volume", unit="linear", value="1", min="0", max=_num(_VOLUME_MAX)
    )
    for index, track in enumerate(session.tracks, start=1):
        element = ET.SubElement(
            structure, "Track", id=f"track-{index}", name=track.name, contentType="audio",
            loaded="true",
        )  # fmt: skip
        channel = ET.SubElement(
            element, "Channel", id=f"channel-{index}", role="regular",
            audioChannels=str(track.channels), destination="channel-master",
        )  # fmt: skip
        # Schema order inside a channel: Mute, Pan, Volume.
        ET.SubElement(channel, "Mute", value=_bool(track.muted))
        pan = (min(1.0, max(-1.0, track.pan)) + 1.0) / 2.0
        ET.SubElement(channel, "Pan", unit="normalized", value=_num(pan), min="0", max="1")
        volume = min(_VOLUME_MAX, max(0.0, track.gain))
        ET.SubElement(
            channel, "Volume", unit="linear", value=_num(volume), min="0", max=_num(_VOLUME_MAX)
        )

    arrangement = ET.SubElement(project, "Arrangement", id="arrangement")
    lanes = ET.SubElement(arrangement, "Lanes", timeUnit="seconds")
    for index, track in enumerate(session.tracks, start=1):
        lane = ET.SubElement(lanes, "Lanes", track=f"track-{index}")
        clips = ET.SubElement(lane, "Clips")
        clip = ET.SubElement(
            clips, "Clip", time="0", duration=_num(track.seconds), playStart="0",
            contentTimeUnit="seconds", name=track.name,
        )  # fmt: skip
        audio = ET.SubElement(
            clip, "Audio", channels=str(track.channels), duration=_num(track.seconds),
            sampleRate=str(session.sample_rate),
        )  # fmt: skip
        ET.SubElement(audio, "File", path=track.file, external="true")
    if session.markers:
        markers = ET.SubElement(arrangement, "Markers", timeUnit="seconds")
        for marker in session.markers:
            ET.SubElement(markers, "Marker", time=_num(marker.time), name=marker.name)
    tempo = ET.SubElement(arrangement, "TempoAutomation", unit="bpm", timeUnit="seconds")
    ET.SubElement(tempo, "Target", parameter="tempo")
    for point in session.tempo:
        ET.SubElement(
            tempo, "RealPoint", time=_num(point.time), value=_num(point.bpm), interpolation="hold"
        )
    signatures = ET.SubElement(arrangement, "TimeSignatureAutomation", timeUnit="seconds")
    ET.SubElement(signatures, "Target", parameter="time-signature")
    for point in time_signature_changes(session.tempo):
        ET.SubElement(
            signatures, "TimeSignaturePoint", time=_num(point.time),
            numerator=str(point.numerator), denominator="4",
        )  # fmt: skip
    return _xml(project)


def metadata_xml(session: Session) -> bytes:
    metadata = ET.Element("MetaData")
    ET.SubElement(metadata, "Title").text = session.title
    if session.artist:
        ET.SubElement(metadata, "Artist").text = session.artist
    ET.SubElement(metadata, "Comment").text = "\n".join(session.summary())
    return _xml(metadata)


def container(session: Session, application_version: str = __version__) -> bytes:
    """The ``.dawproject`` file's bytes (a ZIP with both XML documents)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in (
            ("project.xml", project_xml(session, application_version)),
            ("metadata.xml", metadata_xml(session)),
        ):
            info = zipfile.ZipInfo(name, date_time=_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return buffer.getvalue()


def write(session: Session, target: Path) -> Path:
    target.write_bytes(container(session))
    return target
