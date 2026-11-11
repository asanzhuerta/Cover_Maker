# Translating Cover_Maker

Cover_Maker is made for musicians, and many of them would rather not read
English. Translations are one of the most useful contributions you can make,
and you do not need to know Rust, Python or Svelte to make one.

| Language | Code | Kept up to date by |
|---|---|---|
| English | `en` | the maintainers (source language) |
| Spanish | `es` | the maintainers |
| Portuguese (Brazil) | `pt-BR` | the community |
| French | `fr` | the community |
| German | `de` | the community |
| Italian | `it` | the community |

Portuguese (Portugal) users get `pt-BR` until someone contributes a separate
`pt-PT`. Issues and pull requests about translations carry the
[`translation`](https://github.com/asanzhuerta/Cover_Maker/labels/translation)
label.

## What is translated, and where

| What | File |
|---|---|
| Every text of the interface | `desktop/src/lib/i18n/<code>.ts`, one file per language |
| About page (author bio, app description, credit roles) | `desktop/src/lib/about.json` |
| Installer language list | `desktop/src-tauri/tauri.conf.json` (`bundle.windows.nsis.languages`) |
| Installer language → app language | `desktop/src-tauri/src/locale.rs` |

These stay in English: the LaTeX documentation, the engine's log and command
line, model licence notices (legal texts are shown as their authors wrote
them), and the names of products and documents (Cover_Maker, ccMixter,
Internet Archive, yt-dlp, ffmpeg, PyTorch, CUDA, CREDITS.txt, *Installation
Guide › Troubleshooting*).

`desktop/src/lib/i18n/en.ts` is the source: it defines every key. Each other
file has the type `Dictionary`, so a missing, misspelt or extra key is a type
error.

## Improve an existing translation

1. Fork the repository and edit `desktop/src/lib/i18n/<code>.ts`. Change only
   the text on the right of each key.
2. Check it (see [Check your work](#check-your-work)).
3. Open a pull request with the `translation` label. Say which language you
   speak and, for larger changes, why the new wording is better.

You can also open an issue with the `translation` label that quotes the key,
the current text and your suggestion.

## Add a new language

Use a [BCP 47](https://www.rfc-editor.org/info/bcp47) code: the language
alone (`nl`, `pl`) unless the regional variants differ enough to matter
(`pt-BR`). The examples below use Dutch, `nl`.

1. **Strings.** Copy `desktop/src/lib/i18n/en.ts` to `nl.ts`. Replace the
   header and the declaration with:

   ```ts
   /** Dutch. Community-maintained. */
   import type { Dictionary } from "./en";

   export const nl: Dictionary = {
   ```

   Remove `as const` and the two `export type` lines at the end, then
   translate every value.
2. **Register it** in `desktop/src/lib/i18n.svelte.ts`: import `nl`, add
   `nl: "Nederlands"` to `LOCALES` (each language under its own name), and add
   it to `dictionaries`.
3. **About page.** Add an `"nl"` text next to every `"en"` one in
   `desktop/src/lib/about.json`.
4. **Installer.** Add the NSIS language name (`"Dutch"`; see the
   [NSIS language files](https://github.com/kichik/nsis/tree/master/Contrib/Language%20files))
   to `languages` in `desktop/src-tauri/tauri.conf.json`. In
   `desktop/src-tauri/src/locale.rs`, map the primary language id from
   [`winnt.h`](https://learn.microsoft.com/en-us/windows/win32/intl/language-identifier-constants-and-strings)
   (`LANG_DUTCH` is `0x13`) to `"nl"` and add a line to the test. If you
   cannot run Rust, leave this step to a maintainer and say so in the pull
   request.
5. **Docs.** Add the language to the table at the top of this file, to the
   "Languages" paragraph of the User Manual
   (`docs/latex/user-manual/main.tex`) and to the `Unreleased` section of
   `CHANGELOG.md`.
6. Check your work and open a pull request with the `translation` label.

The system language is detected automatically: a Dutch Windows starts in
`nl` once it is registered, and `nl-BE` falls back to `nl`.

## Style guide

- **Write for musicians.** Use the words that guitarists, singers and home
  producers use in your language, not a literal translation. Keep English
  terms where musicians do (*stem*, *loop*, *solo*, *preset*).
- **Address the user the way good software in your language does**:
  informal in Spanish (*tú*), German (*du*) and Italian (*tu*), *você* in
  Brazilian Portuguese, *vous* in French.
- **Keep it short.** Page names appear as tooltips next to a 64 px icon rail,
  many strings are buttons, and the display tags (`lcd.key`, `lcd.tuning`,
  `lcd.engine`) must stay at about six letters: abbreviate with a full stop
  (*Afin.*, *Diap.*). Check long words in the app.
- **Same words for the same things.** When a sentence names a button or a
  page ("press *Retry*", "the *Models* page", "*Settings* › *Check for yt-dlp
  update*"), use exactly the label of that button or page in your language.
  The display light is called RUNTIME in every language.
- **Placeholders.** Keep `{db}`, `{mb}` and any other `{name}` exactly as they
  are; you may move them within the sentence.
- **Legal texts** (`welcome.legal`, `new.rights`, `catalog.note`,
  `catalog.ndWarning`, `models.accept`, `quick.accept`): translate the meaning
  faithfully, without softening or adding anything. For Creative Commons terms
  (`catalog.nc`, `catalog.nd`), use the official names of the licence
  elements in your language.
- **Typography.** Use the quotation marks, ellipsis (…) and number formats of
  your language. French puts a non-breaking space (U+00A0) before `:` `;` `?`
  and `!`; the checks reject an ordinary space there.

### Glossary

| English | es | pt-BR | fr | de | it |
|---|---|---|---|---|---|
| stem | stem | stem | stem | Stem | stem |
| backing track (the song without the selected stems) | pista | base | piste d'accompagnement | Playback | base |
| song | canción | música | morceau | Song | brano |
| job | trabajo | tarefa | tâche | Auftrag | lavoro |
| queue | cola | fila | file d'attente | Warteschlange | coda |
| mixer | mezclador | mixer | table de mixage | Mixer | mixer |
| mute / solo | silenciar / solo | mudo / solo | muet / solo | stumm / Solo | muto / solo |
| loop | bucle | loop | boucle | Loop | loop |
| click (metronome) | clic | click | clic | Klick | click |
| count-in | claqueta | contagem | décompte | Einzähler | conteggio |
| pitch (shift) | tono | tom | hauteur | Tonhöhe | trasposizione |
| separate | separar | separar | séparer | trennen | separare |
| engine | motor | motor | moteur | Engine | motore |
| separation runtime | runtime de separación | runtime de separação | runtime de séparation | Trenn-Runtime | runtime di separazione |
| quality preset | calidad | qualidade | qualité | Qualität | qualità |
| Retry | Reintentar | Tentar de novo | Réessayer | Erneut versuchen | Riprova |

## Check your work

From `desktop/`, with the [development setup](../CONTRIBUTING.md#development-setup-windows):

```bash
pnpm check:i18n
pnpm check
pnpm lint
```

`pnpm check:i18n` reports, for each language, the keys that are missing or
unknown, empty strings and changed `{placeholders}`. CI runs the same checks
on every pull request.

To see your translation, run `pnpm dev`, open <http://localhost:1420> and
pick your language in *Settings*. Without the engine most pages still show
their texts; `pnpm tauri dev` runs the whole app.

## When new strings are added

New features add keys to `en.ts` and `es.ts` first. The pull request that adds
them must also add them to every other language, so that CI stays green: the
author either translates them or copies the English text and opens an issue
with the `translation` label that lists the keys. Community translators then
replace the English text.
