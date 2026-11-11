"""DAW session export: a separated song as a project for REAPER, DAWproject and MIDI.

Every writer is pure Python with no third-party code and takes a :class:`Session`:

- :mod:`.reaper`: REAPER's text project format (``.RPP``).
- :mod:`.dawproject`: the open DAWproject format (MIT, Bitwig), a ZIP with XML.
- :mod:`.midi`: a Standard MIDI File with the tempo map, markers and key, for any DAW.

:mod:`.export` builds the session from an item (stems, mixer settings, analysis)
and writes the folder; :mod:`.tempo` turns the beat grid into a tempo map.
"""
