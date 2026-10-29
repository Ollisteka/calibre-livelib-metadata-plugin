from lxml import html
import re


def clean_html(raw):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw or '')


def safe_html_fromstring(raw):
    parser = html.HTMLParser(recover=True, huge_tree=True, encoding='utf-8')
    # Match the declared parser encoding explicitly. Passing a Unicode string
    # can fail on non-BMP characters in Calibre's bundled libxml2 on Windows.
    return html.fromstring(clean_html(raw).encode('utf-8'), parser=parser)


def extract_balanced_json(text, start):
    start = text.find('{', start)
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for pos in range(start, len(text)):
        char = text[pos]
        if in_string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[start:pos + 1]
    return None


def compact_page_text(raw):
    try:
        root = safe_html_fromstring(raw)
        text = root.text_content()
    except Exception:
        text = raw
    text = text.replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def extract_between(text, label, next_labels):
    labels = '|'.join(re.escape(label) for label in next_labels)
    match = re.search(re.escape(label) + r'\s*(.*?)\s*(?:' + labels + r')', text)
    if match:
        return match.group(1).strip(' ,;')
    return None
