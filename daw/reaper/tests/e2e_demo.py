"""Run the ReaScript against a running demo engine with a stubbed ``reaper`` API.

Usage (from the repository root, with ``cover-maker serve --demo`` running and
COVER_MAKER_HOME pointing at the demo data folder):

    uvx --with lupa python -I daw/reaper/tests/e2e_demo.py <script.lua> <song.wav>

It checks the real discovery file, the curl calls, the job submission and that
one track per stem is inserted at the selected item's position.
"""

import subprocess
import sys

from lupa.lua54 import LuaRuntime

script, song = sys.argv[1], sys.argv[2]
lua = LuaRuntime(unpack_returned_tuples=True)
deferred: list = []
tracks: list[dict] = []
items: list[dict] = []
messages: list[str] = []


def exec_process(cmd: str, timeout: int) -> str:
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout / 1000)
    return f"{done.returncode}\n{done.stdout}{done.stderr}"


def insert_track(index: int, _defaults: bool) -> None:
    tracks.insert(int(index), {"name": "", "items": []})


def add_item(track: dict) -> dict:
    item = {"track": track, "props": {}, "take": {"props": {}}}
    track["items"].append(item)
    items.append(item)
    return item


source_item = {"props": {"D_POSITION": 12.0}, "take": {"props": {"D_STARTOFFS": 2.0}}}
source_track = {"name": "song", "items": [source_item], "number": 1}
tracks.append(source_track)

stub = {
    "ExecProcess": exec_process,
    "ShowMessageBox": lambda text, _t, _f: messages.append(text),
    "time_precise": __import__("time").monotonic,
    "defer": deferred.append,
    "GetSelectedMediaItem": lambda _p, _i: source_item,
    "GetActiveTake": lambda item: item["take"],
    "TakeIsMIDI": lambda _t: False,
    "GetMediaItemTake_Source": lambda _t: "src",
    "GetMediaSourceParent": lambda _s: None,
    "GetMediaSourceFileName": lambda _s, _b: song,
    "GetMediaItemInfo_Value": lambda item, key: item["props"].get(key, 0.0),
    "GetMediaItemTakeInfo_Value": lambda take, key: take["props"].get(key, 0.0),
    "GetMediaItemTrack": lambda _i: source_track,
    "GetMediaTrackInfo_Value": lambda track, _k: tracks.index(track) + 1,
    "GetUserInputs": lambda _t, _n, _c, defaults: (True, defaults.replace(",n", ",y")),
    "GetCursorPosition": lambda: 0.0,
    "GetProjectPath": lambda _b: str(__import__("tempfile").mkdtemp()),
    "Undo_BeginBlock": lambda: None,
    "Undo_EndBlock": lambda _d, _f: None,
    "PreventUIRefresh": lambda _n: None,
    "CountTracks": lambda _p: len(tracks),
    "InsertTrackAtIndex": insert_track,
    "GetTrack": lambda _p, i: tracks[int(i)],
    "GetSetMediaTrackInfo_String": lambda t, _k, v, _s: t.__setitem__("name", v),
    "PCM_Source_CreateFromFile": lambda path: {"path": path},
    "GetMediaSourceLength": lambda _s: 30.0,
    "AddMediaItemToTrack": add_item,
    "AddTakeToMediaItem": lambda item: item["take"],
    "SetMediaItemTake_Source": lambda take, src: take.__setitem__("source", src),
    "GetSetMediaItemTakeInfo_String": lambda *_a: None,
    "SetMediaItemInfo_Value": lambda item, k, v: item["props"].__setitem__(k, v),
    "SetMediaItemTakeInfo_Value": lambda take, k, v: take["props"].__setitem__(k, v),
    "TrackList_AdjustWindows": lambda _b: None,
    "UpdateArrange": lambda: None,
}
lua.globals().reaper = lua.table_from(stub)
lua.execute(open(script, encoding="utf-8").read())

import time

deadline = time.monotonic() + 120
while deferred and time.monotonic() < deadline:
    callback = deferred.pop(0)
    callback()
    time.sleep(0.05)

assert not messages, messages
new = [t for t in tracks if t is not source_track]
names = [t["name"].lower() for t in new]
assert names == ["vocals", "drums", "bass", "other"], names
for track in new:
    item = track["items"][0]
    assert item["props"]["D_POSITION"] == 10.0, item["props"]
    assert item["take"]["source"]["path"].lower().endswith((".wav", ".flac", ".mp3"))
assert tracks[0] is source_track
print("e2e ok:", names, new[0]["items"][0]["take"]["source"]["path"])
