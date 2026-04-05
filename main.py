# =========================
# main.py
# =========================

from crawler import crawl_website
from scanner import scan_url
from reporter import generate_report

def main():
    print("=== OpenSID Bug Scanner ===")
    target = input("Masukkan URL target: ").strip()

    print("\n[+] Crawling website...")
    urls = crawl_website(target)

    print(f"[+] Ditemukan {len(urls)} URL")

    results = []

    for url in urls:
        print(f"[SCAN] {url}")
        result = scan_url(url)
        results.append(result)

    print("\n[+] Generate report...")
    generate_report(results)

    print("\n[✔] Selesai!")

if __name__ == "__main__":
    main()