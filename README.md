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
LitRes automatically prefers text and paper editions over audio editions with the same
normalized title and authors. Matching audio candidates are removed before fetching details,
selecting covers, and merging metadata, so they cannot cause an ambiguous LitRes ID.
If only audio editions are found for a book, they remain available as fallback results.
This requires no setting. An explicit `litres:ID` is always fetched directly, including an
audiobook ID. Multiple non-audio editions remain separate candidates; ambiguous IDs are
still not borrowed when enriching another source's result.
When a known ID resolves to a result, that result anchors the lookup; other sources supply
matching IDs and missing metadata rather than unrelated alternative books.

## Source settings

Open **Preferences → Metadata download**, select **LiveLib Metadata**, and click
**Configure selected source**.

- **Sources:** LitRes, LiveLib, and FantLab are enabled by default. Uncheck any source
  you don't want to use for metadata or covers.
- **Имя пользователя LiveLib** (optional): enter your username — the `LOGIN` part of
  `livelib.ru/reader/LOGIN` — to import your personal rating and read date from your public
  **«Прочитал»** shelf. No password is needed. Leave it blank to use regular book ratings.
- **Если личная оценка LiveLib не найдена:** choose **Не переносить оценку** (default)
  or **Использовать общую оценку книги** to fall back to the public rating from the
  enabled sources. A personal rating always takes priority when found.
- **Fields:** enable **Rating** and **Comments** to receive your personal rating and
  reading details. The read date appears in the book's comments.

Reading history requires LiveLib to be enabled and matches the exact book edition.
The fallback setting also applies when the profile is unavailable or the lookup times out.
With **Не переносить оценку**, the plugin returns no rating if no personal rating is found.
For large shelves, you may
need to download metadata again to find your reading details.

Settings apply to all libraries in your Calibre profile.

The plugin takes reading dates from your public **«Прочитал»** shelf on LiveLib.
If LiveLib shows the exact day, you get a date such as **02.11.2026**. If it only shows
a month or year, that is what appears in the book's comments. The date you added a book
to the shelf is never treated as the date you read it.
If the current shelf page is unavailable, the plugin tries the older page, which may
only show the month and year. For rereads, it uses the most recent shelf entry.

### Save read dates in a custom column

To keep reading dates in their own column, install **LiveLib.ReadingDates.zip** through
**Preferences → Plugins → Load plugin from file**, then restart Calibre.
You also need **LiveLib Metadata 0.5.0 or newer**. Dates are loaded with a separate toolbar
button because Calibre's regular metadata download cannot fill custom columns.

1. In **Preferences → Add your own columns**, create a column with type **Date**, if needed.
2. In **Preferences → Toolbars & menus**, add **Загрузить даты прочтения LiveLib** to the main toolbar.
3. Select your books and click the new button. Choose the column to fill and click **Загрузить даты**.

Before you start, enter your LiveLib username in the LiveLib Metadata settings and make sure
LiveLib is enabled there. Each book needs a LiveLib ID in its Calibre metadata so the plugin
can find the right edition. This command does not search by book title.

Your column choice and the option to replace existing dates are remembered for each library.
Dates you already have are kept unless you check **Обновлять уже заполненные даты**.
If a date cannot be found or understood, the existing value stays unchanged.
Your ratings and comments stay unchanged too.

A Date column needs a day, month, and year. If LiveLib only gives **Ноябрь 2026 г.**, the
plugin saves **01.11.2026**. If it only gives **2026**, it saves **01.01.2026**.
Exact dates are saved as they are. For rereads, the most recent shelf entry is used.
You can still see the date as LiveLib wrote it in the comments loaded by LiveLib Metadata.

You can keep using Calibre while dates load. Each attempt runs for up to two minutes.
If you cancel, no dates are changed. If some books were not reached, run the command again
within five minutes to continue where it left off. When it finishes, you will see how many
books were updated or skipped, with a log you can check for details.
To replace dates previously saved as the first of the month with exact dates now available
on LiveLib, check **Обновлять уже заполненные даты** and load the dates again.

For developers: `python scripts/build_plugin.py` builds both plugin ZIP files.
To test the reading-date plugin in Calibre, first set `CALIBRE_CONFIG_DIRECTORY` to a separate
test profile, then run `calibre-debug -e scripts/check_reading_plugin.py`.
The check uses a temporary library and sample data instead of contacting LiveLib.

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

Plugins are released independently:

| Tag | Version file | Release notes | Asset |
| --- | --- | --- | --- |
| `metadata-v0.6.0` | `plugin/__init__.py` | `RELEASE_NOTES.md` | `LiveLib.Metadata.zip` |
| `reading-dates-v0.1.0` | `reading_plugin/__init__.py` | `RELEASE_NOTES_READING_DATES.md` | `LiveLib.ReadingDates.zip` |

Update the selected plugin's version and release notes, commit and push the changes,
then create and push its tag (for example, `git tag metadata-v0.6.0` followed by
`git push origin metadata-v0.6.0`). Use a new version/tag for each subsequent release.
The workflow validates the tag against the version, runs the offline tests, builds
only the selected ZIP and publishes it with the corresponding notes. Old `v*` tags
no longer trigger releases. Manual runs require an existing tag and check out that tag.
Independent releases are not marked as the repository-wide Latest release; use the
releases list to find the desired plugin.

For a local single-plugin build, use `python scripts/build_plugin.py --plugin metadata`
or `python scripts/build_plugin.py --plugin reading-dates`. Without arguments, both are built.
Reading Dates still requires a compatible installed Metadata plugin.

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
