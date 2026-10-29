import re


def norm(value):
    value = (value or '').casefold().replace('ё', 'е')
    value = re.sub(r'[\W_]+', ' ', value, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', value).strip()


def score_match(query_title, query_authors, title, author):
    qt = norm(query_title)
    qa = norm(' '.join(query_authors or []))
    rt = norm(title)
    ra = norm(author)
    score = 0
    if qt and rt:
        if qt == rt:
            score += 80
        elif qt in rt or rt in qt:
            score += 45
        elif all(token in rt for token in qt.split()[:3]):
            score += 30
    if qa and ra:
        if qa == ra:
            score += 60
        elif qa in ra or ra in qa:
            score += 35
        else:
            q_tokens = set(qa.split())
            r_tokens = set(ra.split())
            score += 10 * len(q_tokens & r_tokens)
    return score


def title_match_enough(query_title, result_title):
    qt = norm(query_title)
    rt = norm(result_title)
    if not qt or not rt:
        return False
    if qt == rt or qt in rt or rt in qt:
        return True
    q_tokens = [token for token in qt.split() if len(token) > 1]
    r_tokens = set(rt.split())
    return len(set(q_tokens) & r_tokens) >= min(2, len(q_tokens))
