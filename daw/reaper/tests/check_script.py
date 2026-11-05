import sys

from lupa.lua54 import LuaRuntime

src = open(sys.argv[1], encoding="utf-8").read()
assert src.rstrip().endswith("main()")
src = src.rstrip()[: -len("main()")] + "return {json=json, split=split, valid_stems=valid_stems}"
lua = LuaRuntime(unpack_returned_tuples=True)
mod = lua.execute(src)
j = mod.json
doc = '{"job_id": 7, "items": 1, "a": [1, 2.5, -3e2], "s": "x\\"y\\\\z\\u00e9\\n", "t": true, "f": false, "n": null, "o": {}}'
v = j.decode(doc)
assert v.job_id == 7 and v.a[2] == 2.5 and v.a[3] == -300, v
assert v.s == 'x"y\\zé\n', repr(v.s)
assert v.t is True and v.f is False and v.n is None
enc = j.encode(lua.eval('{inputs={"C:\\\\a b.wav"}, stems={"vocals","bass"}, rights_confirmed=false}'))
import json
back = json.loads(enc)
assert back == {"inputs": ["C:\\a b.wav"], "stems": ["vocals", "bass"], "rights_confirmed": False}, back
stems = mod.split(" Vocals, bass ,drums")
assert list(stems.values()) == ["vocals", "bass", "drums"]
ok, bad = mod.valid_stems(lua.eval('{"vocals","kazoo"}'))
assert ok is False and bad == "kazoo"
print("lua ok", enc)
