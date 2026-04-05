# =========================
# utils.py
# =========================

def normalize_url(url):
    if not url.startswith("http"):
        return "http://" + url
    return url