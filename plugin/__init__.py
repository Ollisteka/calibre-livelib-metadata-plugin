from __future__ import absolute_import, division, print_function, unicode_literals


from types import SimpleNamespace


__license__ = 'GPL-3.0-only'


__copyright__ = '2026, Emin Ganbarov and contributors'


import json


import re


from datetime import datetime


from html import escape, unescape


from queue import Empty, Queue


from urllib.parse import quote, urlencode, urljoin, urlsplit


from urllib.request import Request, urlopen


from lxml import html


from calibre import as_unicode


from calibre.ebooks.metadata import check_isbn


from calibre.ebooks.metadata.book.base import Metadata


from calibre.ebooks.metadata.sources.base import Source


STRONG_MATCH_SCORE = 100


def decode_next_payload(raw):
    cleaned = clean_html(raw)
    chunks = []
    for match in re.finditer(r'self\.__next_f\.push\(\[1,"((?:\\.|[^"\\])*)"\]\)</script>', cleaned, re.DOTALL):
        try:
            chunks.append(json.loads('"%s"' % match.group(1)))
        except Exception:
            continue
    if chunks:
        return '\n'.join(chunks)
    return unescape(cleaned).replace('\\"', '"').replace('\\/', '/')


def source_rating(value):
    try:
        rating = float(as_unicode(value).replace(',', '.'))
    except Exception:
        return None
    return rating / 2 if rating > 5 else rating


def extract_livelib_json(raw):
    try:
        root = safe_html_fromstring(raw)
        for script in root.xpath('//script[@type="application/ld+json"]/text()'):
            try:
                payload = json.loads(script)
            except Exception:
                continue
            entries = payload if isinstance(payload, list) else [payload]
            for entry in entries:
                graph = entry.get('@graph') if isinstance(entry, dict) else None
                for graph_entry in graph or []:
                    if graph_entry.get('@type') == 'Book':
                        return graph_entry
                if isinstance(entry, dict) and entry.get('@type') == 'Book':
                    return entry
    except Exception:
        pass

    match = re.search(r'"(\{\\?"@context\\?":\\?"https://schema\.org\\?".*?\})"', raw)
    if not match:
        return None
    data = match.group(1).replace('\\"', '"').replace('\\/', '/')
    try:
        payload = json.loads(data)
    except Exception:
        return None
    for entry in payload.get('@graph', []):
        if entry.get('@type') == 'Book':
            return entry
    return None


def livelib_original_cover_url(url):
    if not url:
        return None
    match = re.match(r'(https?://s\d+\.livelib\.ru/boocover/\d+)/(?:\d+x\d+)/(.*?)/([^/?#]+)$', url)
    if not match:
        return None
    base, shard, filename = match.groups()
    filename = re.sub(r'\.(?:jpg|jpeg|png|webp)$', '.jpeg', filename, flags=re.IGNORECASE)
    return '%s/o/%s/%s' % (base, shard, filename)


def livelib_cover_candidates(url):
    urls = []
    original = livelib_original_cover_url(url)
    if original:
        urls.append(original)
    if url and url not in urls:
        urls.append(url)
    return urls


def extract_livelib_page_details(raw):
    text = compact_page_text(raw)
    details = {}
    field_specs = [
        ('publisher', 'Издательство:', ['Серия:', 'ISBN:', 'Год издания:', 'Язык:', 'Подробная информация']),
        ('series', 'Серия:', ['ISBN:', 'Год издания:', 'Язык:', 'Тип обложки', 'Количество страниц', 'Подробная информация']),
        ('isbn', 'ISBN:', ['Год издания:', 'Язык:', 'Подробная информация']),
        ('year', 'Год издания:', ['Язык:', 'Тип обложки', 'Тип бумаги', 'Количество страниц', 'Возрастные ограничения:', 'Содержание', 'Подробная информация']),
        ('age', 'Возрастные ограничения:', ['Содержание', 'Награды', 'Подробная информация', 'Рейтинг LiveLib']),
        ('weight', 'Вес:', ['Размер:', 'Возрастные ограничения:', 'Подробная информация']),
        ('size', 'Размер:', ['Возрастные ограничения:', 'Подробная информация']),
        ('cover_type', 'Тип обложки -', ['Тип бумаги', 'Количество страниц', 'Возрастные ограничения:', 'Содержание', 'Награды', 'Подробная информация']),
        ('paper_type', 'Тип бумаги в книге -', ['Количество страниц', 'Возрастные ограничения:', 'Содержание', 'Награды', 'Подробная информация']),
    ]
    for key, label, next_labels in field_specs:
        value = extract_between(text, label, next_labels)
        if value:
            details[key] = value

    physical = re.search(r'((?:Мягкий|Твердый|Твёрдый|Кожаный|Интегральный|Электронная|Аудио)[^:]{0,80}?\d+\s*стр\.)', text)
    if physical:
        details['physical'] = physical.group(1).strip()
        pages = re.search(r'(\d+)\s*стр\.', details['physical'])
        if pages:
            details['pages'] = pages.group(1)

    pages = re.search(r'Количество страниц\s*-\s*(\d+)', text)
    if pages:
        details['pages'] = pages.group(1)

    if not details.get('physical'):
        physical_parts = []
        if details.get('cover_type'):
            physical_parts.append(details['cover_type'])
        if details.get('pages'):
            physical_parts.append('%s стр.' % details['pages'])
        if physical_parts:
            details['physical'] = ', '.join(physical_parts)

    language = extract_between(text, 'Язык:', [
        'Исполнитель:', 'Длительность:', 'Редактирование звука:', 'Корректор:',
        'Постер:', 'кодек / битрейт:', 'Вес:', 'Размер:',
        'Возрастные ограничения:', 'Содержание', 'Подробная информация'
    ])
    if language:
        language = re.sub(r'((?:Мягкий|Твердый|Твёрдый|Кожаный|Интегральный|Электронная|Аудио).*)$', '', language).strip(' ,;')
        if 'Русский' in language:
            language = 'Русский'
        if language:
            details['language'] = language

    if details.get('year'):
        year = re.search(r'\d{4}', details['year'])
        if year:
            details['year'] = year.group(0)
    if details.get('age'):
        age = re.search(r'\d+\+', details['age'])
        if age:
            details['age'] = age.group(0)
    return details


from .constants import BASE_URL


from .constants import BETA_BASE_URL


from .constants import FANTLAB_BASE_URL


from .constants import FANTLAB_API_BASE_URL


from .constants import LITRES_API_BASE


from .constants import LITRES_WEB_BASE


from .constants import IDENTIFIER_TYPE_LITRES


from .constants import IDENTIFIER_TYPE_LIVELIB


from .constants import IDENTIFIER_TYPE_FANTLAB


from .constants import IDENTIFIER_TYPE_ISBN


from .constants import FANTLAB_IDENTIFIER_PATTERN


from .constants import USER_AGENT


from .matching import norm


from .matching import score_match


from .matching import title_match_enough


from .identifiers import livelib_id_from_url


from .identifiers import fantlab_identifier_from_url


from .identifiers import livelib_beta_url


from .identifiers import get_book_url


from .identifiers import id_from_url


from .identifiers import get_book_url_name


from .html_utils import clean_html


from .html_utils import safe_html_fromstring


from .html_utils import extract_balanced_json


from .html_utils import compact_page_text


from .html_utils import extract_between


from .transport import Transport


from .providers.livelib.formatting import append_edition_details


from .providers.litres import LitresProvider


from .providers.fantlab import FantlabProvider


class LiveLibMetadata(Source):
    name = 'LiveLib Metadata'
    description = 'Downloads Russian metadata and covers from LitRes, LiveLib, and FantLab'
    author = 'OpenAI Codex for Emin'
    version = (0, 3, 3)
    minimum_calibre_version = (6, 0, 0)

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset([
        'title', 'authors',
        'identifier:' + IDENTIFIER_TYPE_LITRES,
        'identifier:' + IDENTIFIER_TYPE_LIVELIB,
        'identifier:' + IDENTIFIER_TYPE_FANTLAB,
        'identifier:' + IDENTIFIER_TYPE_ISBN,
        'comments', 'publisher', 'pubdate', 'tags', 'rating', 'languages'
    ])
    has_html_comments = True
    supports_gzip_transfer_encoding = True
    can_get_multiple_covers = True


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transport = Transport()
        provider_transport = SimpleNamespace(fetch_url=lambda *a: self.fetch_url(*a), fetch_json=lambda *a: self.fetch_json(*a))
        self.litres = LitresProvider(provider_transport, self.cache_identifier_to_cover_url)
        self.fantlab = FantlabProvider(provider_transport, self.cache_identifier_to_cover_url)


    def fetch_url(self, *args, **kwargs):
        return self.transport.fetch_url(*args, **kwargs)


    def fetch_json(self, *args, **kwargs):
        return self.transport.fetch_json(*args, **kwargs)


    def absolutize_litres_cover(self, *args, **kwargs):
        return self.litres.absolutize_litres_cover(*args, **kwargs)


    def attach_cover_data(self, mi, cover_url, timeout):
        if not cover_url:
            return
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
            'Referer': BASE_URL + '/',
        }
        raw = None
        downloaded_url = cover_url
        for candidate_url in livelib_cover_candidates(cover_url):
            try:
                raw = urlopen(Request(candidate_url, headers=headers), timeout=timeout).read()
                downloaded_url = candidate_url
                break
            except Exception:
                continue
        if raw is None:
            raw = urlopen(Request(cover_url, headers=headers), timeout=timeout).read()
        fmt = 'jpeg'
        lowered = downloaded_url.lower()
        if lowered.endswith('.png'):
            fmt = 'png'
        elif lowered.endswith('.webp'):
            fmt = 'webp'
        mi.cover_data = (fmt, raw)
        mi.has_cover = True


    def get_book_url(self, *args, **kwargs):
        return get_book_url(*args, **kwargs)


    def get_book_url_name(self, idtype, idval, url):
        return get_book_url_name(idtype, self.name)


    def id_from_url(self, *args, **kwargs):
        return id_from_url(*args, **kwargs)


    def identify(self, log, result_queue, abort, title=None, authors=None,
                 identifiers=None, timeout=30):
        identifiers = identifiers or {}
        direct_id = identifiers.get(IDENTIFIER_TYPE_LIVELIB)
        candidates = []

        litres_id = identifiers.get(IDENTIFIER_TYPE_LITRES)
        if litres_id:
            candidates.append({
                'source': 'litres',
                'score': 1000,
                'id': litres_id,
                'title': title or '',
                'authors': authors or [],
            })
        elif direct_id:
            candidates.append({
                'source': 'livelib',
                'score': 1000,
                'url': BETA_BASE_URL + '/book/' + direct_id,
                'title': title or '',
                'author': (authors or [''])[0],
            })
        else:
            query = ' '.join([title or ''] + list(authors or [])).strip()
            if not query:
                return
            candidates = self.search_litres(log, title, authors, timeout)
            # Always run the fast beta search; only fall back to the slow legacy
            # livelib.ru/find search when nothing strong has been found yet.
            search_urls = [BETA_BASE_URL + '/search?q=' + quote(query)]
            for url in search_urls:
                log.info('LiveLib search: ' + url)
                try:
                    raw = self.fetch_url(url, timeout)
                except Exception as err:
                    log.exception('LiveLib search failed: %s' % as_unicode(err))
                    raw = None
                if raw:
                    candidates.extend(self.parse_search_results(raw, title, authors))
            if not any(c['score'] >= STRONG_MATCH_SCORE for c in candidates):
                legacy_url = BASE_URL + '/find/' + quote(query)
                log.info('LiveLib search: ' + legacy_url)
                try:
                    raw = self.fetch_url(legacy_url, timeout)
                except Exception as err:
                    log.exception('LiveLib search failed: %s' % as_unicode(err))
                    raw = None
                if raw:
                    candidates.extend(self.parse_search_results(raw, title, authors))
            candidates.extend(self.search_fantlab(log, title, authors, timeout))
            candidates.sort(key=lambda row: row['score'], reverse=True)

        for candidate in candidates[:6]:
            if abort.is_set():
                return
            if candidate.get('source') == 'litres':
                try:
                    mi = self.fetch_litres_book(log, candidate, timeout)
                except Exception as err:
                    log.exception('LitRes detail failed for %s: %s' % (candidate.get('id'), as_unicode(err)))
                    mi = self.metadata_from_litres_candidate(candidate)
            elif candidate.get('source') == 'fantlab':
                mi = self.metadata_from_fantlab_candidate(candidate)
            else:
                try:
                    mi = self.fetch_book(log, candidate['url'], timeout)
                except Exception as err:
                    log.exception('LiveLib detail failed for %s: %s' % (candidate['url'], as_unicode(err)))
                    mi = self.metadata_from_search_candidate(candidate)
                if mi is not None and candidate.get('cover_url'):
                    livelib_id = (mi.identifiers or {}).get(IDENTIFIER_TYPE_LIVELIB) or livelib_id_from_url(candidate.get('url'))
                    if livelib_id:
                        self.cache_identifier_to_cover_url(livelib_id, candidate['cover_url'])
                        mi.has_cover = True
            if mi is None:
                continue
            # Cover bytes are intentionally NOT downloaded here. Calibre fetches
            # covers separately via download_cover() using the URLs cached above,
            # so downloading them during identify would only duplicate the work.
            mi.source_relevance = -candidate['score']
            result_queue.put(mi)


    def search_litres(self, *args, **kwargs):
        return self.litres.search_litres(*args, **kwargs)


    def metadata_from_litres_candidate(self, *args, **kwargs):
        return self.litres.metadata_from_litres_candidate(*args, **kwargs)


    def fetch_litres_book(self, *args, **kwargs):
        return self.litres.fetch_litres_book(*args, **kwargs)


    def parse_beta_search_payload(self, raw, query_title, query_authors):
        decoded = decode_next_payload(raw)
        candidates = []
        seen = set()
        pos = 0
        marker = '"searchData":'
        while True:
            pos = decoded.find(marker, pos)
            if pos < 0:
                break
            json_text = extract_balanced_json(decoded, pos + len(marker))
            pos += len(marker)
            if not json_text:
                continue
            try:
                data = json.loads(json_text)
            except Exception:
                continue
            rows = ((data.get('payload') or {}).get('data') or [])
            for row in rows:
                if row.get('type') != 'art_editions':
                    continue
                item = row.get('instance') or {}
                href = item.get('url') or ''
                if '/book/' not in href or href in seen:
                    continue
                author_names = [
                    author.get('full_name') for author in item.get('authors') or []
                    if author.get('full_name')
                ]
                result_author = ', '.join(author_names)
                result_title = item.get('title') or ''
                score = score_match(query_title, query_authors, result_title, result_author)
                if score < 50:
                    continue
                seen.add(href)
                cover_url = item.get('cover_url')
                if cover_url and cover_url.startswith('/'):
                    cover_url = BETA_BASE_URL + cover_url
                stats = item.get('stats') or {}
                rating = source_rating(stats.get('rating'))
                candidates.append({
                    'source': 'livelib',
                    'score': score + 8,
                    'url': urljoin(BETA_BASE_URL, href),
                    'title': result_title,
                    'author': result_author or (query_authors or ['Unknown'])[0],
                    'cover_url': cover_url,
                    'rating': as_unicode(rating) if rating is not None else None,
                })
        return candidates


    def parse_search_results(self, raw, query_title, query_authors):
        candidates = self.parse_beta_search_payload(raw, query_title, query_authors)
        seen = {candidate['url'] for candidate in candidates}
        try:
            root = safe_html_fromstring(raw)
        except Exception:
            candidates.sort(key=lambda row: row['score'], reverse=True)
            return candidates
        for block in root.xpath('//div[contains(@class, "object-edition")]'):
            link = block.xpath('.//div[contains(@class, "brow-title")]/a[contains(@class, "title")]')
            author = block.xpath('.//a[contains(@class, "description")]/text()')
            if not link or not author:
                continue
            href = link[0].get('href') or ''
            if not href.startswith('/book/'):
                continue
            url = urljoin(BASE_URL, href)
            if href in seen or url in seen:
                continue
            seen.add(href)
            seen.add(url)
            result_title = unescape(' '.join(link[0].xpath('.//text()'))).strip()
            result_author = unescape(author[0]).strip()
            score = score_match(query_title, query_authors, result_title, result_author)
            if score < 50:
                continue
            cover_url = None
            cover_style = block.xpath('.//span[contains(@class, "object-cover")]/@style')
            if cover_style:
                match = re.search(r'background:url\((.*?)\)', cover_style[0])
                if match:
                    cover_url = match.group(1)

            rating = None
            rating_text = block.xpath('.//span[@itemprop="ratingValue"]/text()')
            if rating_text:
                rating = rating_text[0].strip()

            candidates.append({
                'source': 'livelib',
                'score': score,
                'url': url,
                'title': result_title,
                'author': result_author,
                'cover_url': cover_url,
                'rating': rating,
            })

        for link in root.xpath('//a[contains(@href, "/book/") and normalize-space()]'):
            href = link.get('href') or ''
            url = urljoin(BETA_BASE_URL, href)
            if '/book/' not in href or href in seen or url in seen:
                continue
            result_title = unescape(' '.join(link.xpath('.//text()'))).strip()
            if not result_title:
                continue
            card = link
            author_names = []
            cover_url = None
            rating = None
            for _ in range(6):
                card = card.getparent()
                if card is None:
                    break
                author_names = [
                    unescape(' '.join(a.xpath('.//text()'))).strip()
                    for a in card.xpath('.//a[contains(@href, "/author/")]')
                    if unescape(' '.join(a.xpath('.//text()'))).strip()
                ]
                covers = card.xpath('.//img[contains(@src, "boocover")]/@src')
                if covers:
                    cover_url = covers[0]
                text = re.sub(r'\s+', ' ', card.text_content()).strip()
                match = re.search(r'(\d+(?:[,.]\d+)?)\s*\(\s*([\dKКkк,.\s]+)\s*\)', text)
                if match:
                    rating = match.group(1).replace(',', '.')
                if author_names or cover_url:
                    break
            result_author = ', '.join(dict.fromkeys(author_names)) if author_names else ''
            score = score_match(query_title, query_authors, result_title, result_author)
            if score < 50:
                continue
            seen.add(href)
            seen.add(url)
            if cover_url and cover_url.startswith('/'):
                cover_url = BETA_BASE_URL + cover_url
            candidates.append({
                'source': 'livelib',
                'score': score,
                'url': url,
                'title': result_title,
                'author': result_author or (query_authors or ['Unknown'])[0],
                'cover_url': cover_url,
                'rating': rating,
            })
        candidates.sort(key=lambda row: row['score'], reverse=True)
        return candidates


    def search_fantlab(self, *args, **kwargs):
        return self.fantlab.search_fantlab(*args, **kwargs)


    def metadata_from_search_candidate(self, candidate):
        title = candidate.get('title') or ''
        author = candidate.get('author') or 'Unknown'
        if not title:
            return None
        mi = Metadata(title, [author])
        mi.language = 'rus'
        livelib_id = livelib_id_from_url(candidate.get('url'))
        if livelib_id:
            mi.set_identifier(IDENTIFIER_TYPE_LIVELIB, livelib_id)
        # Do not overwrite an existing annotation with a bare source link.
        if candidate.get('summary'):
            mi.comments = '<p>%s</p>' % as_unicode(candidate.get('summary')).strip()
        try:
            if candidate.get('rating'):
                mi.rating = float(candidate['rating']) * 2
        except Exception:
            pass
        cover_url = candidate.get('cover_url')
        if cover_url and livelib_id:
            self.cache_identifier_to_cover_url(livelib_id, cover_url)
        return mi


    def metadata_from_fantlab_candidate(self, *args, **kwargs):
        return self.fantlab.metadata_from_fantlab_candidate(*args, **kwargs)


    def fetch_book(self, log, url, timeout):
        url = livelib_beta_url(url)
        raw = self.fetch_url(url, timeout)
        data = extract_livelib_json(raw)
        if not data:
            return None

        author_data = data.get('author') or {}
        author_name = author_data.get('name') if isinstance(author_data, dict) else author_data
        title = data.get('name') or ''
        authors = [author_name] if author_name else ['Unknown']
        mi = Metadata(title, authors)
        mi.language = 'rus'

        livelib_id = livelib_id_from_url(url) or livelib_id_from_url(data.get('url'))
        if livelib_id:
            mi.set_identifier(IDENTIFIER_TYPE_LIVELIB, livelib_id)

        details = extract_livelib_page_details(raw)

        isbn = check_isbn(data.get('isbn') or details.get('isbn'))
        if isbn:
            mi.isbn = isbn

        publisher = details.get('publisher')
        if not publisher:
            publisher_data = data.get('publisher') or {}
            if isinstance(publisher_data, dict):
                publisher = publisher_data.get('name')
            elif publisher_data:
                publisher = as_unicode(publisher_data)
        if publisher:
            mi.publisher = publisher

        year = details.get('year')
        if year:
            match = re.search(r'\d{4}', year)
            if match:
                try:
                    mi.pubdate = datetime(int(match.group(0)), 1, 1)
                except Exception:
                    pass

        description = data.get('description')
        comments = None
        if description:
            comments = '<p>%s</p>' % escape(description).replace('\n', '<br/>')

        genres = data.get('genre') or []
        if isinstance(genres, str):
            genres = [genres]
        mi.tags = [g for g in genres if g]

        rating = ((data.get('aggregateRating') or {}).get('ratingValue'))
        rating_count = ((data.get('aggregateRating') or {}).get('ratingCount'))
        try:
            # Calibre ratings are on a 0..10 scale.
            mi.rating = float(rating) * 2
        except Exception:
            pass

        mi.comments = append_edition_details(comments, details, rating_count=rating_count)

        image = data.get('image')
        if image and livelib_id:
            self.cache_identifier_to_cover_url(livelib_id, image)
            mi.has_cover = True

        return mi


    def get_cached_cover_url(self, identifiers):
        litres_id = (identifiers or {}).get(IDENTIFIER_TYPE_LITRES)
        if litres_id:
            return self.cached_identifier_to_cover_url(litres_id)
        livelib_id = (identifiers or {}).get(IDENTIFIER_TYPE_LIVELIB)
        if livelib_id:
            return self.cached_identifier_to_cover_url(livelib_id)
        fantlab_id = (identifiers or {}).get(IDENTIFIER_TYPE_FANTLAB)
        if fantlab_id:
            return self.cached_identifier_to_cover_url(fantlab_id)
        return None


    def find_cover_url_direct(self, log, title=None, authors=None, timeout=30):
        for candidate in self.search_litres(log, title, authors, timeout):
            if candidate.get('cover_url'):
                return candidate['cover_url']
        query = ' '.join([title or ''] + list(authors or [])).strip()
        if query:
            for url in (
                    BETA_BASE_URL + '/search?q=' + quote(query),
                    BASE_URL + '/find/' + quote(query),
            ):
                try:
                    raw = self.fetch_url(url, timeout)
                    for candidate in self.parse_search_results(raw, title, authors):
                        if candidate.get('cover_url'):
                            return candidate['cover_url']
                except Exception as err:
                    log.exception('Direct LiveLib cover search failed: %s' % as_unicode(err))
        for candidate in self.search_fantlab(log, title, authors, timeout):
            if candidate.get('cover_url'):
                return candidate['cover_url']
        return None


    def find_all_cover_urls(self, log, result_queue_abort, title, authors, identifiers, timeout):
        """Collect cover URLs from every matched source, ordered by relevance."""
        urls = []
        seen = set()

        def add(url):
            if url and url not in seen:
                seen.add(url)
                urls.append(url)

        add(self.get_cached_cover_url(identifiers))
        if title or authors:
            q = Queue()
            self.identify(log, q, result_queue_abort, title=title, authors=authors,
                          identifiers=identifiers, timeout=timeout)
            # Drain the whole queue so covers from every matched source (LitRes,
            # LiveLib, FantLab) are gathered, not just the single top-scoring hit.
            while True:
                try:
                    mi = q.get_nowait()
                except Empty:
                    break
                add(self.get_cached_cover_url(mi.identifiers))
        if not urls and (title or authors):
            add(self.find_cover_url_direct(log, title=title, authors=authors, timeout=timeout))
        return urls


    def download_cover(self, log, result_queue, abort, title=None, authors=None,
                       identifiers=None, timeout=30, get_best_cover=False):
        identifiers = identifiers or {}
        urls = self.find_all_cover_urls(log, abort, title, authors, identifiers, timeout)
        if not urls:
            return
        # Expand each source URL into its resolution variants (e.g. the LiveLib
        # original /o/...jpeg plus the preview) and download them all together.
        candidates = []
        seen = set()
        for url in urls:
            for candidate in livelib_cover_candidates(url):
                if candidate and candidate not in seen:
                    seen.add(candidate)
                    candidates.append(candidate)
        if candidates:
            self.download_multiple_covers(title, authors, candidates, get_best_cover,
                                          timeout, result_queue, abort, log,
                                          prefs_name=None)
