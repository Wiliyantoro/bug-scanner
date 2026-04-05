# =========================
# crawler.py
# =========================

import posixpath
import re
from collections import defaultdict, deque
from urllib.parse import parse_qsl, urlencode, urldefrag, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

MAX_URLS = 300
MAX_DEPTH = 4
MAX_VARIANTS_PER_PATH = 8
REQUEST_TIMEOUT = 5
HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
DISCOVERY_ATTRS = (
    "href",
    "src",
    "action",
    "formaction",
    "data-url",
    "data-href",
    "data-endpoint",
    "data-action",
    "poster",
)
DANGEROUS_ROUTE_KEYWORDS = (
    "logout",
    "log-out",
    "signout",
    "sign-out",
    "delete",
    "remove",
    "destroy",
    "truncate",
    "drop",
    "reset",
    "purge",
)
JAVASCRIPT_ENDPOINT_PATTERNS = (
    re.compile(r"""fetch\(\s*["']([^"'?#\s][^"'#\s]*)["']""", re.IGNORECASE),
    re.compile(r"""open\(\s*["'](?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)["']\s*,\s*["']([^"'?#\s][^"'#\s]*)["']""", re.IGNORECASE),
    re.compile(r"""url\s*:\s*["']([^"'?#\s][^"'#\s]*)["']""", re.IGNORECASE),
    re.compile(r"""(?:api|endpoint|route|path)\s*:\s*["']([^"'?#\s][^"'#\s]*)["']""", re.IGNORECASE),
    re.compile(r"""["']((?:/|\.{1,2}/)[^"'#\s<>]+)["']"""),
)


def crawl_website(base_url):
    start_url = _normalize_seed_url(base_url)
    if not start_url:
        return []

    origin = _origin_tuple(start_url)
    session = requests.Session()
    visited = set()
    discovered = set()
    queued = {start_url}
    queue = deque([(start_url, 0)])
    path_variant_counts = defaultdict(int)

    while queue and len(visited) < MAX_URLS:
        current_url, depth = queue.popleft()
        queued.discard(current_url)

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
        except requests.RequestException:
            continue

        final_url = _normalize_discovered_url(response.url, current_url)
        if final_url and _is_same_origin(final_url, origin) and not _is_dangerous_route(final_url):
            discovered.add(final_url)
            _enqueue_candidate(
                final_url,
                depth,
                MAX_DEPTH,
                visited,
                queued,
                queue,
                path_variant_counts,
            )

        if depth >= MAX_DEPTH:
            continue

        content_type = response.headers.get("Content-Type", "").lower()
        if not any(content_type.startswith(value) for value in HTML_CONTENT_TYPES):
            continue

        page_url = final_url or current_url
        soup = BeautifulSoup(response.text, "html.parser")

        for candidate in _extract_candidate_urls(soup, response.text, page_url):
            if not _is_same_origin(candidate, origin):
                continue

            if _is_dangerous_route(candidate):
                continue

            discovered.add(candidate)
            _enqueue_candidate(
                candidate,
                depth,
                MAX_DEPTH,
                visited,
                queued,
                queue,
                path_variant_counts,
            )

    return sorted(discovered)


def _enqueue_candidate(
    candidate,
    depth,
    max_depth,
    visited,
    queued,
    queue,
    path_variant_counts,
):
    if candidate in visited or candidate in queued:
        return

    if depth + 1 > max_depth:
        return

    path_key = _path_variant_key(candidate)
    if path_variant_counts[path_key] >= MAX_VARIANTS_PER_PATH:
        return

    path_variant_counts[path_key] += 1
    queued.add(candidate)
    queue.append((candidate, depth + 1))


def _extract_candidate_urls(soup, html, page_url):
    for tag in soup.find_all(True):
        for attr in DISCOVERY_ATTRS:
            value = tag.get(attr)
            if value:
                normalized = _normalize_discovered_url(value, page_url)
                if normalized:
                    yield normalized

        srcset = tag.get("srcset")
        if srcset:
            for raw_value in _parse_srcset(srcset):
                normalized = _normalize_discovered_url(raw_value, page_url)
                if normalized:
                    yield normalized

    for form in soup.find_all("form"):
        for candidate in _extract_form_targets(form, page_url):
            yield candidate

    for candidate in _extract_javascript_urls(html, page_url):
        yield candidate


def _extract_form_targets(form, page_url):
    action = form.get("action") or page_url
    action_url = _normalize_discovered_url(action, page_url)
    if not action_url:
        return

    yield action_url

    method = (form.get("method") or "get").strip().lower()
    fields = _extract_form_fields(form)
    if not fields:
        return

    if method == "get":
        dynamic_url = _merge_query_params(action_url, fields)
        if dynamic_url:
            yield dynamic_url


def _extract_form_fields(form):
    params = []

    for field in form.find_all(["input", "textarea", "select"]):
        name = field.get("name")
        if not name:
            continue

        field_type = (field.get("type") or "").strip().lower()
        if field_type in {"submit", "button", "image", "file", "reset"}:
            continue

        value = field.get("value", "")
        if field.name == "textarea":
            value = field.text or value
        elif field.name == "select":
            selected_option = field.find("option", selected=True)
            if selected_option:
                value = selected_option.get("value", selected_option.text)
            else:
                first_option = field.find("option")
                if first_option:
                    value = first_option.get("value", first_option.text)

        params.append((name, value))

    return params


def _extract_javascript_urls(html, page_url):
    seen = set()

    for pattern in JAVASCRIPT_ENDPOINT_PATTERNS:
        for match in pattern.finditer(html):
            raw_url = match.group(1)
            normalized = _normalize_discovered_url(raw_url, page_url)
            if normalized and normalized not in seen:
                seen.add(normalized)
                yield normalized


def _parse_srcset(srcset):
    for item in srcset.split(","):
        value = item.strip().split(" ", 1)[0]
        if value:
            yield value


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
    if not raw_value:
        return None

    lowered = raw_value.lower()
    if lowered.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
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

    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return None

    port = parsed.port
    if port and not _is_default_port(scheme, port):
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname

    normalized_path = _normalize_path(parsed.path)
    normalized_query = urlencode(
        sorted(parse_qsl(parsed.query, keep_blank_values=True)),
        doseq=True,
    )

    return urlunparse((scheme, netloc, normalized_path, "", normalized_query, ""))


def _normalize_path(path):
    raw_path = path or "/"
    collapsed = re.sub(r"/{2,}", "/", raw_path)

    normalized = posixpath.normpath(collapsed)
    if not normalized.startswith("/"):
        normalized = "/" + normalized

    if collapsed.endswith("/") and normalized != "/":
        normalized += "/"

    return normalized


def _is_default_port(scheme, port):
    return (scheme == "http" and port == 80) or (scheme == "https" and port == 443)


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
            "",
            query,
            "",
        )
    )


def _path_variant_key(url):
    parsed = urlparse(url)
    return (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path)


def _is_dangerous_route(url):
    parsed = urlparse(url)
    combined = "/".join(
        piece for piece in (parsed.path, parsed.query) if piece
    ).lower()
    return any(keyword in combined for keyword in DANGEROUS_ROUTE_KEYWORDS)
