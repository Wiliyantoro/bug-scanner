# =========================
# scanner.py
# =========================

import requests

SQL_PAYLOAD = "' OR '1'='1"
XSS_PAYLOAD = "<script>alert(1)</script>"

def scan_url(url):
    result = {
        "url": url,
        "status_code": None,
        "issues": []
    }

    try:
        response = requests.get(url, timeout=5)
        result["status_code"] = response.status_code

        # 🔍 Detect error page
        if response.status_code >= 500:
            result["issues"].append("Server Error")

        if response.status_code == 404:
            result["issues"].append("Broken Link")

        # 🔥 SQL Injection Test
        test_url = url + "?id=" + SQL_PAYLOAD
        r = requests.get(test_url)

        if "sql" in r.text.lower() or "syntax" in r.text.lower():
            result["issues"].append("Possible SQL Injection")

        # 🔥 XSS Test
        test_url = url + "?q=" + XSS_PAYLOAD
        r = requests.get(test_url)

        if XSS_PAYLOAD in r.text:
            result["issues"].append("Possible XSS")

    except Exception as e:
        result["issues"].append(f"Error: {str(e)}")

    return result