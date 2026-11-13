# Packaging

Cover_Maker is published as an NSIS installer on
[GitHub Releases](https://github.com/asanzhuerta/Cover_Maker/releases) by
[`release.yml`](../.github/workflows/release.yml). Each release carries:

| Asset | Use |
|---|---|
| `Cover_Maker_<version>_x64-setup.exe` (+ `.sig`) | Versioned installer, used by the in-app updater, winget and Scoop. |
| `Cover_Maker_x64-setup.exe` | The same file under a stable name, for links that never change. |
| `latest.json` | Updater manifest (signed update). |
| `SHA256SUMS.txt` | SHA-256 of both installers; Scoop's `autoupdate` reads it. |

The stable download link always serves the newest published (non-draft,
non-pre-release) installer:

<https://github.com/asanzhuerta/Cover_Maker/releases/latest/download/Cover_Maker_x64-setup.exe>

## winget

The `winget` job of `release.yml` runs when a draft release is published by
hand as a full release (not a pre-release). It runs `wingetcreate update`
(pinned version, checked by SHA-256), which opens a pull request on
[microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs) with the new
version. Without a `WINGET_TOKEN` secret it only logs a notice.

One-time setup:

1. Submit the first version by hand, because `wingetcreate update` only
   updates a package that already exists:
   `wingetcreate new https://github.com/asanzhuerta/Cover_Maker/releases/download/v0.4.0/Cover_Maker_0.4.0_x64-setup.exe`
   with the package identifier `asanzhuerta.CoverMaker` (change `WINGET_ID` in
   `release.yml` if you pick another one).
2. Create a classic personal access token with the `public_repo` scope and
   save it as the repository secret `WINGET_TOKEN`.

## Scoop

[`scoop/cover-maker.json`](scoop/cover-maker.json) is a manifest for the
[Extras bucket](https://github.com/ScoopInstaller/Extras). It extracts the
NSIS installer with 7-Zip (`#/dl.7z`) instead of running it, as Scoop expects,
and keeps itself current with `checkver` (GitHub releases) and `autoupdate`
(hash from `SHA256SUMS.txt`).

To submit it once v0.4.0 is published:

1. Fork ScoopInstaller/Extras, copy the manifest to `bucket/cover-maker.json`.
2. Run `.\bin\checkver.ps1 cover-maker -u` there; it adds the hash.
3. Test with `scoop install .\bucket\cover-maker.json`, then open the pull
   request. The bucket's bot updates later versions on its own.

The app keeps its runtime and data in `%LOCALAPPDATA%\Cover_Maker` whichever
way it is installed. A Scoop copy should be updated with `scoop update`; the
in-app updater would install a second, per-user copy.
