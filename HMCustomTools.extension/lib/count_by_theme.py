import unicodedata


def normalize_text(value):
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def filter_by_text(words, text):
    return [word for word in words if text in word]


def filter_by_terms(items, terms):
    normalized_terms = [normalize_text(term.strip()) for term in terms if term.strip()]
    if not normalized_terms:
        return []

    return [
        item
        for item in items
        if any(term in normalize_text(item) for term in normalized_terms)
    ]
