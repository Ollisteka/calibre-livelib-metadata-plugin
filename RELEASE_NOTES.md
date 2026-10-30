# LiveLib Metadata for Calibre v0.5.0

Feature release of `LiveLib Metadata`, a Calibre metadata source plugin for Russian-language book libraries.

## Highlights

- Set **Имя пользователя LiveLib** to import your rating into Calibre and add your rating and read date to **«Детали издания LiveLib»**. Uses your public read shelf and exact edition IDs; reviews and a custom date column are not included yet.
- Fixes the rating scale passed to Calibre: a personal rating of 4/5 now displays as four stars instead of five.
- Preserves the read date's original precision, including month-only or year-only dates. Uses the newest shelf entry for repeat readings.
- Loads reading history in pages, with a five-minute in-memory cache and support for cancellation and lookup time limits.
- Keeps normal metadata downloads working if the public profile is unavailable. Leaving the username empty or disabling LiveLib turns off personal requests; cover-only downloads skip them.

## Install

Download `LiveLib.Metadata.zip` from the release assets and install it in Calibre:

`Preferences -> Plugins -> Load plugin from file`

Restart Calibre after installation.

## Update

For future releases, download the newest `LiveLib.Metadata.zip` and install it through the same Calibre plugin dialog. Calibre will replace the older plugin after restart.
