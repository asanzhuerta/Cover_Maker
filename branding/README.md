# Cover_Maker logo

`logo.svg` is the master logo: a rounded square with the violet→pink gradient
of the UI and six white bars forming a waveform, the same mark as in the app's
sidebar. `logo-1024.png` is a 1024 × 1024 export for web pages.

The app icons in `desktop/src-tauri/icons` are generated from the master:

```bash
cd desktop
pnpm tauri icon ../branding/logo.svg -o src-tauri/icons
```

Then delete the generated `android/` and `ios/` folders (Windows-only app) and
copy `src-tauri/icons/64x64.png` to `static/favicon.png`.

Colours: `#8f7bff` → `#ff5c8a` (diagonal gradient), bars `#ffffff`.
