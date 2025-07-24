#!/usr/bin/env python3
import requests
import time

# ========== CONFIG ==========
EPOCH = 166         # ← change epoch here or override via CLI (see below)
LIMIT = 100         # page size for /Flips list
SLEEP_LIST = 0.10   # pause between list‑page requests
SLEEP_FLIP = 0.05   # pause between per‑flip queries
# ============================

def fetch_flip_cids(epoch: int):
    """Return a list of all flip CIDs for the given epoch (handles pagination)."""
    cids, token = [], None
    while True:
        url = f"https://api.idena.io/api/Epoch/{epoch}/Flips?limit={LIMIT}"
        if token:
            url += f"&continuationToken={token}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        js = r.json()
        cids.extend([flt.get("cid") for flt in js.get("result", []) if flt.get("cid")])
        token = js.get("continuationToken")
        if not token:
            break
        time.sleep(SLEEP_LIST)
    return cids

def main(epoch: int):
    print(f"[1/3] Fetching flip list for epoch {epoch} …")
    cids = fetch_flip_cids(epoch)
    if not cids:
        print("No flips returned – is the epoch too old?")
        return
    print(f"[2/3] {len(cids)} flips found. Scanning for wrongWords …")

    counts = {}
    for i, cid in enumerate(cids, start=1):
        try:
            info = requests.get(f"https://api.idena.io/api/Flip/{cid}", timeout=8).json()
            result = info.get("result") or {}
            author = (result.get("author") or "").lower()
            wrong = result.get("wrongWords", False)
            if author:
                counts[author] = counts.get(author, 0) + (1 if wrong else 0)
            print(f"{i:>4}/{len(cids)}  {author or 'N/A'}  wrongWords={wrong}")
        except Exception as e:
            print(f"{i:>4}/{len(cids)}  ERROR fetching {cid[:18]}…  {e}")
        time.sleep(SLEEP_FLIP)

    print(f"\n[3/3] Summary for epoch {epoch}")
    print("address                                wrongWordsCount")
    print("-" * 50)
    for addr, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        flag = "  **>1**" if cnt > 1 else ""
        print(f"{addr}  {cnt}{flag}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 2 and sys.argv[1].isdigit():
        EPOCH = int(sys.argv[1])
    main(EPOCH)
