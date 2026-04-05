# =========================
# reporter.py
# =========================

import json
from datetime import datetime

def generate_report(results):
    filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(filename, "w") as f:
        json.dump(results, f, indent=4)

    print(f"[+] Report disimpan: {filename}")