# Cover_Maker logo

The mark is a tape reel whose flange opens into a **C**; the tape leaving
through the gap is the underscore of `Cover_Maker` (Tape & Console identity,
ADR-009 in the Architecture document).

| File | Use |
|---|---|
| `logo.svg` | Master: the mark on a round, dark chassis (app icon, web pages). |
| `logo-1024.png` | 1024 × 1024 export of `logo.svg` with a transparent corner area. |
| `logo-mark.svg` | The mark alone on a transparent background, for light pages and print. |

In the app the mark is drawn by `desktop/src/lib/components/Logo.svelte`
in the current text colour, so it follows the dark and light themes.

The app icons in `desktop/src-tauri/icons` are generated from the master:

```bash
cd desktop
pnpm tauri icon ../branding/logo.svg -o src-tauri/icons
```

Then delete the generated `android/` and `ios/` folders (Windows-only app) and
copy `src-tauri/icons/64x64.png` to `static/favicon.png`.

Colours: chassis `#15130f` with a `#29251f` rim, reel cream `#f1e9dc`
(`#1d1a16` in `logo-mark.svg`), tape signal orange `#ff6a3d`.

Descriptor: "the cover musician's studio" (Spanish: "el estudio del músico de
covers").
