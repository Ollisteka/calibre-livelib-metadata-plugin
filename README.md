# LiveLib Metadata for Calibre

**LiveLib Metadata** is a [Calibre](https://calibre-ebook.com/) metadata source plugin for
Russian-language books. It fills the gap left by Calibre's default (mostly English) sources by
pulling titles, authors, descriptions, tags, ratings, publication details, and covers from the
biggest Russian book services — **LitRes**, **LiveLib**, and **FantLab**.

If you keep a Russian-language library and Calibre's built-in sources return English metadata,
poor matches, or no cover at all, this plugin is for you.

---

## Features

- **Three Russian sources in one plugin.** Queries LitRes (public API), LiveLib (beta pages), and
  FantLab, then merges and ranks the results by how well title and author match your book.
- **Multiple covers from returned candidates.** The cover picker receives available cached covers
  from up to six ranked candidates. Known IDs are fetched for each enabled source, and missing
  IDs are searched with a candidate slot reserved for each source within the result limit.
- **High-resolution covers.** Prefers the original LiveLib `/o/...jpeg` image and falls back to a
  preview automatically if the original is unavailable.
- **Rich Russian metadata.** Imports Russian descriptions, genre tags, rating and vote count, ISBN,
  publisher, and publication year.
- **Edition details in comments.** Series, page count, binding type, paper type, weight, size, and
  age rating are appended to the book's comments under **«Детали издания LiveLib»**, since Calibre
  has no native fields for most of these.
- **Accurate matching.** Rejects weak title/author matches so a book is not overwritten by a
  same-title work from a different author.
- **Identifiers.** Stores `litres`, `livelib`, and `fantlab` identifiers so repeat lookups and cover downloads are fast and exact. FantLab identifiers retain the resource path returned by its API (for example, `work123`) so links use the correct FantLab page type. Numeric-only FantLab IDs saved by older plugin versions need to be refreshed to recover that page type.
- **Multiple identifiers per result.** Adds IDs from other enabled sources when their accepted candidates have the same normalized title and authors. Each result keeps its populated fields; other sources fill only missing fields. Ambiguous IDs from the same source are skipped. The original search scoring and acceptance thresholds are unchanged; no additional edition verification is introduced.
- **Choose your sources.** Native Calibre settings let you independently disable LitRes, LiveLib, or FantLab for metadata and covers.
- **Your LiveLib reading history.** Set your username to import your personal rating into
  Calibre's rating field and append both the rating and read date to **«Детали издания LiveLib»**.

---

## Search order

The plugin queries enabled sources and searches for missing IDs even when a book already has
an ID from another service:

1. Known `litres:`, `livelib:`, and `fantlab:` IDs are used directly for enabled sources. FantLab direct lookup supports `work…` and `edition…` IDs.
2. **LitRes** public API search, if its ID is missing.
3. **LiveLib** fast beta search (`beta.livelib.ru/search`), if its ID is missing.
4. **LiveLib** legacy search (`www.livelib.ru/find`) — only when the current search candidates contain no strong match.
5. **FantLab** public API search, if its ID is missing.

Skipping the slow legacy LiveLib search on a strong match keeps a typical lookup fast.
When a known ID resolves to a result, that result anchors the lookup; other sources supply
matching IDs and missing metadata rather than unrelated alternative books.

## Source settings

Open **Preferences → Metadata download**, select **LiveLib Metadata**, and click
**Configure selected source**. Calibre's standard configuration dialog provides:

- **Использовать LitRes**
- **Использовать LiveLib**
- **Использовать FantLab**
- **Имя пользователя LiveLib** — optional login from `livelib.ru/reader/LOGIN` (not the full URL).

All three are enabled by default. Disabling a source prevents searches, direct ID lookups,
fallback requests, and cover downloads from that source, including cached covers. Existing IDs
and their clickable book links remain available. Disabling all sources is allowed and makes
the plugin perform no network requests.

Settings are saved in the Calibre profile and shared across its libraries. Saved changes apply
to subsequent operations. The standard selection of metadata fields remains in the same dialog.

Enrichment does not replace populated annotations, ratings, tags, or other fields in a plugin
result. It does not append extra tags or edition details to populated comments. Applying a result
to an existing library record still follows Calibre's metadata download settings.

With a LiveLib username set, the plugin additionally reads that user's **public «Прочитал» shelf**.
For an exact LiveLib edition ID, the personal rating overrides the result's service rating
(4/5 appears as four stars; Calibre stores it as 8/10 internally). Both the personal rating and read date are appended to the
comments, including results whose description comes from another source. This is an explicit
exception to the general enrichment rule above. If no personal rating is available, the service
rating remains. Ensure **Rating** and **Comments** are enabled in Calibre's downloaded fields.

Dates keep the precision LiveLib provides, such as `Октябрь 2026 г.`; a day is never invented.
For repeat readings, the first (newest) shelf entry is used. Different editions are not matched
by title. There is no custom read-date column yet. Personal reviews/impressions are not imported:
the biglist response contains the publisher's annotation, which is not a personal review.

Leave the username empty to disable personal requests. Disabling LiveLib also disables this
feature; cover-only downloads do not request reading history. No password or login is required.
Private/unavailable profiles and network errors do not prevent normal metadata downloads.
The shelf is scanned in pages of 100 within the remaining lookup time. An incomplete scan resumes
on a subsequent lookup in the same plugin instance; the in-memory cache expires after five minutes
and resets when the username changes. Large shelves may require another lookup. The approach uses
the public endpoint described in [livelib-backup](https://github.com/Chimildic/livelib-backup/blob/main/src/gs/livelib-client.js).

---

## Installation

1. Download `LiveLib.Metadata.zip` from the [latest release](https://github.com/GanbarovEmin/calibre-livelib-metadata-plugin/releases/latest).
2. Open Calibre.
3. Go to **Preferences → Plugins → Load plugin from file**.
4. Select the downloaded `LiveLib.Metadata.zip`.
5. Restart Calibre.
6. Go to **Preferences → Metadata download** and make sure **LiveLib Metadata** is enabled (and,
   optionally, drag it above other sources to prioritise it).

## Updating

Download the newest `LiveLib.Metadata.zip` from the releases page and install it again through
**Load plugin from file**. Calibre replaces the previous version after a restart.

---

## Usage

1. Select a book (or several) in Calibre.
2. Click **Edit metadata → Download metadata and covers** (or right-click → *Edit metadata*).
3. Pick the best match and cover from the results.

**Tips**

- Better input gives better matches. A clean Russian title plus the author name in the book's fields
  produces the most accurate results.
- If you already know the book on LitRes, LiveLib, or FantLab, add its `litres:`, `livelib:`, or
  `fantlab:` identifier in Calibre. The plugin uses that ID directly and looks for missing IDs
  in the other enabled sources.
- Use **Download only covers** if you just want artwork; the plugin returns covers from all matched
  sources so you can compare.

---

## How it works

Calibre calls the plugin in two phases:

- **Identify** — searches the sources, builds candidate matches, and caches each source's cover URL.
  Cover *images* are intentionally **not** downloaded during this phase, which keeps identification
  fast.
- **Download cover** — collects the cached cover URLs from returned candidates, expands each into
  its resolution variants, de-duplicates, and hands them all to Calibre's cover picker.

Physical edition details that Calibre cannot store natively are written into the book's comments
under **«Детали издания LiveLib»**.

---

## Building locally

```bash
./scripts/build-plugin.sh
```

On Windows, run from the project root in PowerShell with Python installed:

```powershell
py scripts/build_plugin.py
```

If you use the project's virtual environment, run `.\.venv\Scripts\python.exe scripts/build_plugin.py` instead. 
No additional packages are required to build the ZIP.

The build writes the installable archive to:

```text
dist/LiveLib.Metadata.zip
```

## Running tests

Use Python 3.11. Tests run without Calibre or network access; testing in Calibre is a separate manual step.

Windows (PowerShell):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```

Linux:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

The real-Calibre ZIP and native settings check uses synthetic service responses and a separate
test profile. After building the ZIP, run on Windows:

```powershell
$env:CALIBRE_CONFIG_DIRECTORY = Join-Path (Get-Location) 'local-notes/calibre-check-profile'
$env:QT_QPA_PLATFORM = 'offscreen'
calibre-debug -e scripts/check_calibre_plugin.py -- dist/LiveLib.Metadata.zip
Remove-Item Env:CALIBRE_CONFIG_DIRECTORY, Env:QT_QPA_PLATFORM
```

## Releasing

Releases are automated. Pushing a tag like `v0.3.3` triggers the GitHub Actions workflow
(`.github/workflows/release.yml`), which builds a fresh plugin zip and publishes a GitHub release
with `RELEASE_NOTES.md` as the body.

---

## Troubleshooting

- **No results / no cover.** LiveLib and LitRes occasionally change their HTML and API responses.
  Update to the latest release, which usually ships updated parsers.
- **Wrong book returned.** Make sure the title and author in Calibre are correct; the plugin
  deliberately rejects weak matches, so a slightly wrong title can leave it with nothing to return.
- **Network / access issues.** The plugin talks to third-party Russian services; regional blocking or
  rate limiting on their side can cause empty results.

## Notes

Calibre has no native page-count or binding fields, so physical edition details are appended to
comments rather than stored as columns.

LiveLib, LitRes, and FantLab are third-party services. Their HTML/API behaviour can change at any
time, so releases may update parsers and matching rules as needed.

## Contributing

Issues and pull requests are welcome. When reporting a matching or cover problem, please include the
book title and author, and the plugin log from Calibre's job window — it makes the failure much
easier to reproduce.

## License

[GPL-3.0-only](LICENSE).
