# =========================
# crawler.py
# =========================

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def crawl_website(base_url):
    visited = set()
    to_visit = [base_url]

    while to_visit:
        url = to_visit.pop()

        if url in visited:
            continue

        visited.add(url)

        try:
            response = requests.get(url, timeout=5)
            soup = BeautifulSoup(response.text, "html.parser")

            for link in soup.find_all("a", href=True):
                full_url = urljoin(base_url, link["href"])

                if base_url in full_url:
                    if full_url not in visited:
                        to_visit.append(full_url)

        except:
            continue

    return list(visited)