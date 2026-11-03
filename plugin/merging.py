"""Enrich results without replacing their populated fields or source IDs.

Providers retain their original candidate acceptance rules. Only candidates with
the same normalized title/authors share data; no new edition evidence is fetched.
"""
from copy import deepcopy

from .matching import norm


FIELDS = ('title', 'authors', 'languages', 'language', 'comments', 'tags',
          'rating', 'publisher', 'pubdate', 'isbn')


def missing(mi, field):
    value = getattr(mi, field, None)
    if field in ('title', 'authors'):
        values = value if isinstance(value, list) else [value]
        if not values or all(not v or norm(v) == 'unknown' for v in values):
            return True
    if hasattr(mi, 'is_null'):
        return mi.is_null(field)
    return not value


def match_key(mi):
    if missing(mi, 'title') or missing(mi, 'authors'):
        return None
    title = norm(getattr(mi, 'title', ''))
    authors = tuple(sorted(norm(a) for a in (getattr(mi, 'authors', None) or []) if norm(a)))
    if not title or not authors or authors == ('unknown',):
        return None
    return title, authors


def enrich_results(rows, identifiers, log, blocked_sources=()):
    """Each row is (source, metadata); ambiguous source IDs are not borrowed."""
    originals = [(source, mi.deepcopy_metadata()) for source, mi in rows]
    groups = {}
    for kind, original in originals:
        key = match_key(original)
        if key is not None:
            groups.setdefault((key, kind), []).append(original)
    for source, mi in rows:
        key = match_key(mi)
        own_ids = {original.identifiers.get(source)
                   for original in groups.get((key, source), [])} - {None, ''}
        for kind in ('litres', 'livelib', 'fantlab'):
            if (kind == source or source in blocked_sources or kind in blocked_sources
                    or len(own_ids) > 1):
                continue
            matches = groups.get((key, kind), [])
            ids = {donor.identifiers.get(kind) for donor in matches} - {None, ''}
            if len(ids) != 1:
                if len(ids) > 1:
                    log.info('Ambiguous %s IDs: enrichment skipped' % kind)
                continue
            identifier = next(iter(ids))
            if identifiers.get(kind) and identifiers[kind] != identifier:
                log.info('Existing %s ID conflicts: enrichment skipped' % kind)
                continue
            donor = next(donor for donor in matches if donor.identifiers.get(kind) == identifier)
            mi.set_identifier(kind, identifier)
            for field in FIELDS:
                if missing(mi, field) and not missing(donor, field):
                    setattr(mi, field, deepcopy(getattr(donor, field)))
            mi.has_cover = mi.has_cover or donor.has_cover
        # Input identifiers belong to the user's record, including disabled sources.
        for kind, value in identifiers.items():
            if value:
                mi.set_identifier(kind, value)
    return [mi for _, mi in rows]
