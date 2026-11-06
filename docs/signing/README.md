# Code signing setup (SignPath Foundation)

Release binaries are signed with Authenticode through the
[SignPath Foundation](https://signpath.org) programme for open-source projects
(issue #51). `release.yml` skips every signing step until the repository is
configured, so releases keep working unsigned in the meantime.

## One-time setup after the application is accepted

1. In SignPath, install the **GitHub.com trusted build system** connector and
   link it to the project.
2. Create the project with the slug **`Cover_Maker`** and a signing policy with
   the slug **`release-signing`** (manual approval by the approver role).
3. Add the two artifact configurations below, with the slugs **`installer`**
   and **`vst3-plugin`**. `actions/upload-artifact` zips what it uploads, so
   the root element is `<zip-file>`.
4. Create an API token for a user with the *submitter* role.
5. In GitHub → Settings → Secrets and variables → Actions:
   - secret **`SIGNPATH_API_TOKEN`**: the token;
   - variable **`SIGNPATH_ORGANIZATION_ID`**: the organisation id.

From then on every `v*` tag waits in the release workflow until the signing
request is approved in SignPath (up to 5 hours, the job limit).

## Artifact configuration `installer`

```xml
<?xml version="1.0" encoding="utf-8"?>
<artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
  <zip-file>
    <pe-file path="Cover_Maker_*_x64-setup.exe"
             product-name="Cover_Maker" product-version="${version}">
      <authenticode-sign />
    </pe-file>
  </zip-file>
</artifact-configuration>
```

## Artifact configuration `vst3-plugin`

```xml
<?xml version="1.0" encoding="utf-8"?>
<artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
  <zip-file>
    <pe-file path="Cover_Maker.vst3/Contents/x86_64-win/Cover_Maker.vst3">
      <authenticode-sign />
    </pe-file>
  </zip-file>
</artifact-configuration>
```

Adjust the product metadata rules to what SignPath requires for the project
(the Foundation enforces product name and version attributes).

## What is signed

Only binaries built from this repository by `release.yml`: the NSIS installer
and the VST3 plugin. The installer is signed after Tauri builds it, so the
workflow signs the signed file again with the updater key and replaces the
installer, its `.sig` and `latest.json` in the draft release. Third-party
programs downloaded on first run (uv, Python, ffmpeg, deno, Python packages)
keep their publishers' signatures and are checked by SHA-256.
