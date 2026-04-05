# =========================
# crawler.py
# =========================

import re
from collections import deque
from urllib.parse import parse_qsl, urlencode, urldefrag, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

MAX_URLS = 200
REQUEST_TIMEOUT = 5
HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
DISCOVERY_ATTRS = ("href", "src", "action", "data-url", "data-href", "data-endpoint")
SCRIPT_URL_PATTERN = re.compile(
    r"""
    (?:
        ["'](?P<quoted>/[^"'?#\s][^"'#\s]*)["']
        |
        (?P<api>/api/[^"'?#\s]+)
    )
    """,
    re.VERBOSE,
)


def crawl_website(base_url):
    start_url = _normalize_seed_url(base_url)
    if not start_url:
        return []

    origin = _origin_tuple(start_url)
    session = requests.Session()
    visited = set()
    discovered = set()
    queue = deque([start_url])

    while queue and len(visited) < MAX_URLS:
        current_url = queue.popleft()

        if current_url in visited:
            continue

        visited.add(current_url)
        discovered.add(current_url)

        try:
            response = session.get(
                current_url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            final_url = _normalize_discovered_url(response.url, start_url)
        except requests.RequestException:
            continue

        if final_url and _is_same_origin(final_url, origin):
            discovered.add(final_url)

        content_type = response.headers.get("Content-Type", "").lower()
        if not any(content_type.startswith(value) for value in HTML_CONTENT_TYPES):
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        candidates = set(_extract_candidate_urls(soup, response.text, final_url or current_url))

        for candidate in candidates:
            if not _is_same_origin(candidate, origin):
                continue

            discovered.add(candidate)

            if candidate not in visited and candidate not in queue and len(visited) + len(queue) < MAX_URLS:
                queue.append(candidate)

    return sorted(discovered)


def _extract_candidate_urls(soup, html, page_url):
    for tag in soup.find_all(True):
        for attr in DISCOVERY_ATTRS:
            value = tag.get(attr)
            if value:
                normalized = _normalize_discovered_url(value, page_url)
                if normalized:
                    yield normalized

    for form in soup.find_all("form"):
        action = form.get("action") or page_url
        action_url = _normalize_discovered_url(action, page_url)
        if action_url:
            yield action_url

        params = []
        for field in form.find_all(["input", "textarea", "select"]):
            name = field.get("name")
            if name:
                params.append((name, field.get("value", "")))

        if action_url and params:
            dynamic_url = _merge_query_params(action_url, params)
            if dynamic_url:
                yield dynamic_url

    for match in SCRIPT_URL_PATTERN.finditer(html):
        raw_url = match.group("quoted") or match.group("api")
        normalized = _normalize_discovered_url(raw_url, page_url)
        if normalized:
            yield normalized


def _normalize_seed_url(url):
    if not url:
        return None

    raw_url = url.strip()
    if not raw_url:
        return None

    if "://" not in raw_url:
        raw_url = "http://" + raw_url

    return _canonicalize_url(raw_url)


def _normalize_discovered_url(candidate, page_url):
    if not candidate:
        return None

    raw_value = candidate.strip()
    if not raw_value or raw_value.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None

    absolute_url = urljoin(page_url, raw_value)
    return _canonicalize_url(absolute_url)


def _canonicalize_url(url):
    try:
        defragmented, _ = urldefrag(url)
        parsed = urlparse(defragmented)
    except ValueError:
        return None

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None

    normalized_path = parsed.path or "/"
    normalized_query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)), doseq=True)

    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            normalized_path,
            "",
            normalized_query,
            "",
        )
    )


def _origin_tuple(url):
    parsed = urlparse(url)
    return (parsed.scheme.lower(), parsed.netloc.lower())


def _is_same_origin(url, origin):
    return _origin_tuple(url) == origin


def _merge_query_params(url, params):
    parsed = urlparse(url)
    merged = parse_qsl(parsed.query, keep_blank_values=True)
    merged.extend(params)
    query = urlencode(sorted(merged), doseq=True)

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            query,
            "",
        )
    )
