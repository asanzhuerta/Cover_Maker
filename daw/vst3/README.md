# Cover_Maker VST3 plugin

A VST3 effect that separates songs into stems with the Cover_Maker app running
on the same computer, previews each stem through the track and lets you drag
the stem files into your DAW's tracks. VST3 plugins cannot create tracks, so the
files are offered for drag and drop (or *Show in folder*).

**Licence:** GPL-3.0-or-later (see `COPYING`), because the VST3 bindings used
by [NIH-plug](https://github.com/robbert-vdh/nih-plug) (`vst3-sys`) are GPLv3.
The rest of Cover_Maker is MIT. Source code:
<https://github.com/asanzhuerta/Cover_Maker/tree/main/daw/vst3>. VST is a
registered trademark of Steinberg Media Technologies GmbH.

## Install

Copy `Cover_Maker.vst3` to `C:\Program Files\Common Files\VST3` and rescan
plugins in your DAW. Open the Cover_Maker app before using the plugin.

## How it finds the app

The engine writes `%LOCALAPPDATA%\Cover_Maker\run\engine.json` with its port
and a client token while it runs; only your Windows account can read it
(ADR-008 in the Architecture document). The plugin only talks to
`127.0.0.1`, never follows redirects and sends the token in a header.

## Build

```bash
cargo test
cargo xtask bundle cover_maker_vst3 --release
```

The bundle is written to `target/bundled/Cover_Maker.vst3`.

Only separate audio you have the right to use.
