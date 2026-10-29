from ...constants import BASE_URL
from ...constants import BETA_BASE_URL
from ...html_utils import clean_html
from ...html_utils import compact_page_text
from ...html_utils import extract_balanced_json
from ...html_utils import extract_between
from ...html_utils import safe_html_fromstring
from ...matching import score_match
from calibre import as_unicode
from html import unescape
from urllib.parse import urljoin
import json
import re


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


def parse_beta_search_payload(raw, query_title, query_authors):
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


def parse_search_results(raw, query_title, query_authors):
    candidates = parse_beta_search_payload(raw, query_title, query_authors)
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
