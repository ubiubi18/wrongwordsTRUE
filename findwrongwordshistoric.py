#!/usr/bin/env python3
"""
Scan the last N finished Idena epochs and list every identity that created flips
with wrongWords == true. Writes one CSV + JSONL per epoch and a master summary.
"""

import os, sys, time, json, requests
from datetime import datetime

# ====== USER CONFIG ======
EPOCHS_BACK = 50                        # how many finished epochs to scan
LIMIT       = 100                       # page size for /Flips list
SLEEP_LIST  = 0.10                      # delay between list pages (sec)
SLEEP_FLIP  = 0.05                      # delay between per‑flip queries (sec)
OUT_DIR     = "/var/idena-wrongwords"   # where CSV/JSONL files will be stored
# ==========================

os.makedirs(OUT_DIR, exist_ok=True)
LOG = lambda m: print(f"[{datetime.utcnow().isoformat(timespec='seconds')}Z] {m}", flush=True)

def latest_epoch() -> int:
    """Return the latest epoch number (current running one)."""
    url = "https://api.idena.io/api/Epoch/Last"
    return int(requests.get(url, timeout=10).json()["result"]["epoch"])

def fetch_flip_cids(epoch: int):
    """Return a list of all flip CIDs for given epoch (handle pagination)."""
    cids, token = [], None
    while True:
        url = f"https://api.idena.io/api/Epoch/{epoch}/Flips?limit={LIMIT}"
        if token:
            url += f"&continuationToken={token}"
        js = requests.get(url, timeout=10).json()
        cids.extend([f["cid"] for f in js.get("result", []) if f.get("cid")])
        token = js.get("continuationToken")
        if not token:
            break
        time.sleep(SLEEP_LIST)
    return cids

def scan_epoch(epoch: int):
    """Scan one epoch and return dict {address: wrongWordsCount>0}."""
    LOG(f"E{epoch}: fetching flip list …")
    cids = fetch_flip_cids(epoch)
    LOG(f"E{epoch}: {len(cids)} flips, scanning …")

    counts = {}
    for idx, cid in enumerate(cids, start=1):
        try:
            info = requests.get(f"https://api.idena.io/api/Flip/{cid}", timeout=8).json().get("result", {})
            if info.get("wrongWords", False):
                addr = (info.get("author") or "").lower()
                if addr:
                    counts[addr] = counts.get(addr, 0) + 1
        except Exception as e:
            LOG(f"  {idx}/{len(cids)} ERROR {cid[:18]}… {e}")
        if idx % 50 == 0:
            LOG(f"  processed {idx}/{len(cids)} flips")
        time.sleep(SLEEP_FLIP)

    # CSV
    csv_path = os.path.join(OUT_DIR, f"wrongwords_epoch{epoch}.csv")
    with open(csv_path, "w") as f:
        f.write("address,wrongWordsCount\n")
        for a, c in sorted(counts.items(), key=lambda x: -x[1]):
            f.write(f"{a},{c}\n")

    # JSONL
    jsonl_path = os.path.join(OUT_DIR, f"wrongwords_epoch{epoch}.jsonl")
    with open(jsonl_path, "w") as f:
        for a, c in counts.items():
            f.write(json.dumps({"epoch": epoch, "address": a, "wrongWords": c}) + "\n")

    LOG(f"E{epoch}: wrote {len(counts)} addresses to {csv_path}")
    return counts

def main():
    start_epoch = latest_epoch() - 1      # current epoch still in progress
    summary = {}

    for off in range(EPOCHS_BACK):
        ep = start_epoch - off
        if ep < 0:
            break
        summary[ep] = scan_epoch(ep)

    # master CSV
    master = os.path.join(OUT_DIR, "wrongwords_summary.csv")
    with open(master, "w") as f:
        f.write("epoch,address,wrongWordsCount\n")
        for ep, m in summary.items():
            for addr, cnt in m.items():
                f.write(f"{ep},{addr},{cnt}\n")
    LOG(f"Done. Summary file: {master}")

if __name__ == "__main__":
    main()
