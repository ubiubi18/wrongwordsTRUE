#!/usr/bin/env python3

import os
import csv

folder = "/var/idena-wrongwords/"

print("Epoch Summary: One vs. Multiple Reported Flips\n")

for filename in sorted(os.listdir(folder)):
    if not filename.endswith(".csv") or not filename.startswith("wrongwords_epoch"):
        continue

    epoch = filename.split("epoch")[1].split(".")[0]
    path = os.path.join(folder, filename)

    one_count = 0
    multi_count = 0
    multi_addresses = []

    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            addr = row["address"].strip()
            try:
                count = int(row["wrongWordsCount"])
            except:
                continue

            if count == 1:
                one_count += 1
            elif count > 1:
                multi_count += 1
                multi_addresses.append((addr, count))

    print(f"Epoch {epoch}:")
    print(f"  One reported flip: {one_count}")
    print(f"  Multiple reported flips: {multi_count}")

    if multi_addresses:
        print("  Addresses with 2+ reported flips:")
        for addr, cnt in multi_addresses:
            print(f"    - {addr} ({cnt} flips) → https://scan.idena.io/address/{addr}")
    print("-" * 60)
