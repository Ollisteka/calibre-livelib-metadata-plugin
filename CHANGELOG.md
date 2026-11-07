# Changelog

## v0.6.0 - Unreleased

- Read precise calendar dates from the new public LiveLib shelf, preserving the day in comments and the companion date column. Keep month/year precision when that is all LiveLib provides; use legacy shelf headings only when the new source is unavailable. Log each requested book's date and source.
- Added optional **LiveLib Reading Dates** companion command for selected books, with a
  library-specific date-column picker and opt-in overwrite. Partial dates use the first
  day/month; cancellation and missing values do not change existing dates. Rating settings
  remain in the metadata source.

## v0.5.1

- Fix direct LiveLib lookups crashing on books with multiple JSON-LD authors; preserve all coauthors in page metadata and direct-lookup fallback results.

## v0.5.0 - Unreleased
- Add a setting for missing LiveLib personal ratings: use the public book rating from enabled sources or return no rating (default). Personal ratings always take priority; the setting also covers unavailable profiles and lookup timeouts.
- Prefer non-audio LitRes editions with matching normalized titles and authors before fetching and merging results. Retain audio-only matches and explicit audio IDs; no additional setting is needed.
- Fix ratings passed to Calibre's metadata download API: return 0..5 values, since Calibre converts these to its internal 0..10 scale when applying a result. Previously personal ratings such as 4/5 could display as five stars.
- Add an optional LiveLib username: read personal ratings and reading dates from the public read shelf. Use the personal rating in Calibre and append both values to LiveLib edition details. Preserve date precision; handle pagination, short-lived caching, cancellation, and unavailable profiles. Cover-only lookups skip reading history.

## v0.4.0 - Unreleased

- Reload the plugin's submodules when replacing an installed ZIP so an update from 0.3.3 does not mix old and new code in a running Calibre.
- Automatically collect LitRes, LiveLib, and FantLab IDs for matching results, including lookups that already have a service ID.
- Fill only missing metadata fields; preserve populated comments, ratings, tags, and existing identifiers. Skip ambiguous additional IDs.
- Add three source switches through Calibre's native metadata source configuration; disabled sources are excluded from metadata and cover requests.
- Return all service links through `get_book_urls` and recognize URLs from all three services.
- Support direct FantLab work/edition lookup and separate cover cache entries by source.
- Preserve the original provider scoring and acceptance rules.

## v0.3.4

- Fix LiveLib cover downloads crashing when JSON-LD `image` is an ImageObject instead of a URL string.
- Extract `contentUrl` or `url`, support image lists, and ignore missing or malformed image values before caching.
- Add regression coverage from direct LiveLib lookup through the cover downloader handoff.

## v0.3.3 - 2026-07-09

- Fix missing LitRes covers: `download_cover` now aggregates covers from every matched source (LitRes, LiveLib, FantLab) instead of only the single top-scoring result.
- Speed up identify by no longer downloading cover image bytes during identification; Calibre fetches covers separately from the cached URLs.
- Skip the slow, ddos-guard-prone legacy `www.livelib.ru/find` search when LitRes or the beta search already produced a strong title/author match.

## v0.3.2 - 2026-06-28

- Fix a Calibre 9.10 cover-search crash when LiveLib search HTML triggers an `lxml` parser error.
- Parse LiveLib beta search results from the embedded Next.js `searchData` payload before falling back to DOM parsing.
- Keep returning LiveLib candidates when DOM parsing fails, including the exact `Битва за рейтинг (Альфа-6)` result.
- Harden LiveLib HTML parsing with recover/huge-tree mode and invalid-control-character cleanup.

## v0.3.1 - 2026-06-28

- Prefer high-resolution LiveLib cover URLs using the `/o/...jpeg` form.
- Fall back to preview cover URLs when the original image is unavailable.
- Preserve direct LiveLib identifiers when LiveLib schema points to a canonical/alternate edition.
- Add release-ready project documentation.

## v0.3.0 - 2026-06-28

- Add `beta.livelib.ru` search and book-page support.
- Parse LiveLib `application/ld+json` Book schema.
- Import ISBN, publisher, publication year, rating, vote count, and Russian tags.
- Append edition details to comments: series, pages, binding, paper type, weight, size, and age rating.
- Prefer LiveLib beta pages over the older ddos-guard-prone LiveLib surface.

## v0.2.0 - 2026-06-28

- Add LitRes public API search and detail lookup.
- Add FantLab fallback.
- Improve Russian matching and reject same-author/wrong-title LitRes results.
- Fix cover download behavior.

## v0.1.0 - 2026-06-28

- Initial local LiveLib metadata source.
