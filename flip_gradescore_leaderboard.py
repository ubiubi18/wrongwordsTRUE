#!/usr/bin/env python3
"""
Idena flip leaderboards by gradeScore for one epoch.

Outputs 2 CSVs:
1) flips leaderboard (each flip row, sorted by gradeScore desc)
2) identities leaderboard (sum of gradeScore per author, sorted desc)

Excludes authors that are "bad authors" with reason == "WrongWords"
(or wrongWords == true) from /Epoch/{epoch}/Authors/Bad.

Endpoints used (from your swagger doc.json):
- GET /Epoch/Last
- GET /Epoch/{epoch}/Authors/Bad   (paged)
- GET /Epoch/{epoch}/Flips         (paged)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


BASE_URL_DEFAULT = "https://api.idena.io/api"


@dataclass
class FlipRow:
    rank: int
    cid: str
    author: str
    grade_score: float
    grade: Optional[int]
    status: str
    wrong_words_votes: Optional[int]
    short_resp: Optional[int]
    long_resp: Optional[int]
    with_private_part: Optional[bool]
    word1: str
    word2: str


def _safe_float(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        return float(v)
    except Exception:
        return 0.0


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def _get_words(flip: Dict[str, Any]) -> Tuple[str, str]:
    words = flip.get("words") or {}
    w1 = (words.get("word1") or {}).get("name") or ""
    w2 = (words.get("word2") or {}).get("name") or ""
    return w1, w2


class IdenaApi:
    def __init__(self, base_url: str, timeout: int = 30, retries: int = 6, backoff_sec: float = 1.5):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.backoff_sec = backoff_sec
        self.sess = requests.Session()
        self.sess.headers.update({"Accept": "application/json"})

    def get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_err: Optional[Exception] = None

        for attempt in range(1, self.retries + 1):
            try:
                r = self.sess.get(url, params=params, timeout=self.timeout)
                if r.status_code == 429:
                    sleep_s = self.backoff_sec * attempt
                    time.sleep(sleep_s)
                    continue
                r.raise_for_status()
                js = r.json()

                # API responses are typically { "result": ..., "error": ... }
                err = js.get("error")
                if isinstance(err, dict) and err.get("message"):
                    raise RuntimeError(f"API error at {path}: {err.get('message')}")

                return js
            except Exception as e:
                last_err = e
                sleep_s = self.backoff_sec * attempt
                time.sleep(sleep_s)

        raise RuntimeError(f"GET failed after {self.retries} retries: {url} ({last_err})")

    def paged(self, path: str, limit: int, sleep_per_page: float = 0.0) -> Iterable[Dict[str, Any]]:
        token: Optional[str] = None
        page = 0
        while True:
            page += 1
            params: Dict[str, Any] = {"limit": limit}
            if token:
                params["continuationToken"] = token

            js = self.get_json(path, params=params)
            items = js.get("result") or []
            if not isinstance(items, list):
                raise RuntimeError(f"Unexpected result type at {path}: {type(items)}")

            for it in items:
                if isinstance(it, dict):
                    yield it

            token = js.get("continuationToken")
            if not token:
                break

            if sleep_per_page > 0:
                time.sleep(sleep_per_page)

    def last_epoch_number(self) -> int:
        js = self.get_json("/Epoch/Last")
        res = js.get("result")
        if isinstance(res, int):
            return res
        if isinstance(res, dict):
            # be tolerant if schema changes
            for k in ("epoch", "Epoch", "number", "Number"):
                if k in res and isinstance(res[k], int):
                    return res[k]
        raise RuntimeError(f"Unexpected /Epoch/Last result: {res}")


def fetch_wrongwords_bad_authors(api: IdenaApi, epoch: int, page_size: int, sleep_per_page: float) -> set[str]:
    bad = set()
    for row in api.paged(f"/Epoch/{epoch}/Authors/Bad", limit=page_size, sleep_per_page=sleep_per_page):
        addr = (row.get("address") or "").lower()
        reason = row.get("reason")
        wrong_words_flag = row.get("wrongWords")
        if not addr:
            continue
        if reason == "WrongWords" or wrong_words_flag is True:
            bad.add(addr)
    return bad


def fetch_flips(api: IdenaApi, epoch: int, page_size: int, sleep_per_page: float) -> Iterable[Dict[str, Any]]:
    yield from api.paged(f"/Epoch/{epoch}/Flips", limit=page_size, sleep_per_page=sleep_per_page)


def write_csv(path: str, header: List[str], rows: Iterable[List[Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def main() -> int:
    ap = argparse.ArgumentParser(description="Idena flip leaderboards by gradeScore (excluding wrongWords bad authors).")
    ap.add_argument("--base-url", default=BASE_URL_DEFAULT, help="Idena API base URL (default: https://api.idena.io/api)")
    ap.add_argument("--epoch", type=int, default=0, help="Epoch number. If 0, uses (LastEpoch - 1).")
    ap.add_argument("--page-size", type=int, default=100, help="Pagination page size (limit=). Max allowed by API is 100.")
    ap.add_argument("--sleep-per-page", type=float, default=0.0, help="Sleep seconds after each page fetch.")
    ap.add_argument("--top", type=int, default=100, help="How many top rows to print to console per leaderboard.")
    ap.add_argument("--out-dir", default="./out_flip_leaderboards", help="Output directory for CSV/JSON.")
    ap.add_argument("--include-zero", action="store_true", help="Include flips with gradeScore <= 0.")
    ap.add_argument(
        "--status",
        action="append",
        default=[],
        help="Filter by flip status (repeatable). Example: --status Qualified --status WeaklyQualified",
    )
    args = ap.parse_args()

    api = IdenaApi(base_url=args.base_url)

    epoch = args.epoch
    if epoch == 0:
        last_epoch = api.last_epoch_number()
        epoch = max(0, last_epoch - 1)

    print(f"[i] Epoch: {epoch}")
    print("[i] Fetching bad authors (WrongWords)...")
    bad_authors = fetch_wrongwords_bad_authors(api, epoch=epoch, page_size=args.page_size, sleep_per_page=args.sleep_per_page)
    print(f"[i] wrongWords bad authors: {len(bad_authors)}")

    allowed_status = set(args.status) if args.status else None

    print("[i] Fetching flips and building leaderboards...")
    flips_min: List[Dict[str, Any]] = []
    sums = defaultdict(lambda: {"total": 0.0, "count": 0, "max": 0.0})

    total_seen = 0
    total_kept = 0

    for fl in fetch_flips(api, epoch=epoch, page_size=args.page_size, sleep_per_page=args.sleep_per_page):
        total_seen += 1

        author = (fl.get("author") or "").lower()
        if not author or author in bad_authors:
            continue

        status = fl.get("status") or ""
        if allowed_status is not None and status not in allowed_status:
            continue

        grade_score = _safe_float(fl.get("gradeScore"))
        if (not args.include_zero) and grade_score <= 0:
            continue

        # Keep only what we need (do not keep icon to save RAM)
        w1, w2 = _get_words(fl)
        kept = {
            "cid": fl.get("cid") or "",
            "author": author,
            "gradeScore": grade_score,
            "grade": _safe_int(fl.get("grade")),
            "status": status,
            "wrongWordsVotes": _safe_int(fl.get("wrongWordsVotes")),
            "shortRespCount": _safe_int(fl.get("shortRespCount")),
            "longRespCount": _safe_int(fl.get("longRespCount")),
            "withPrivatePart": fl.get("withPrivatePart"),
            "word1": w1,
            "word2": w2,
        }
        if not kept["cid"]:
            continue

        flips_min.append(kept)
        total_kept += 1

        sums[author]["total"] += grade_score
        sums[author]["count"] += 1
        if grade_score > sums[author]["max"]:
            sums[author]["max"] = grade_score

        if total_seen % 2000 == 0:
            print(f"[i] processed flips: seen={total_seen} kept={total_kept}")

    print(f"[i] Done. flips: seen={total_seen} kept={total_kept} (after filters)")

    # Flip leaderboard
    flips_sorted = sorted(flips_min, key=lambda x: (x["gradeScore"], x["cid"]), reverse=True)
    flip_rows: List[FlipRow] = []
    for i, fl in enumerate(flips_sorted, start=1):
        flip_rows.append(
            FlipRow(
                rank=i,
                cid=fl["cid"],
                author=fl["author"],
                grade_score=float(fl["gradeScore"]),
                grade=fl.get("grade"),
                status=fl.get("status") or "",
                wrong_words_votes=fl.get("wrongWordsVotes"),
                short_resp=fl.get("shortRespCount"),
                long_resp=fl.get("longRespCount"),
                with_private_part=fl.get("withPrivatePart"),
                word1=fl.get("word1") or "",
                word2=fl.get("word2") or "",
            )
        )

    # Identity leaderboard
    id_rows = []
    for addr, agg in sums.items():
        total = float(agg["total"])
        count = int(agg["count"])
        max_gs = float(agg["max"])
        avg = total / count if count else 0.0
        id_rows.append({"address": addr, "totalGradeScore": total, "flipCount": count, "avgGradeScore": avg, "maxFlipGradeScore": max_gs})
    id_sorted = sorted(id_rows, key=lambda x: (x["totalGradeScore"], x["flipCount"], x["address"]), reverse=True)

    # Print top to console
    top = max(0, int(args.top))
    if top:
        print("\n=== TOP FLIPS (by gradeScore) ===")
        for r in flip_rows[:top]:
            print(f"{r.rank:4d}  {r.grade_score:10.4f}  grade={r.grade}  status={r.status:16s}  {r.author}  {r.cid}")

        print("\n=== TOP IDENTITIES (sum gradeScore) ===")
        for i, r in enumerate(id_sorted[:top], start=1):
            print(f"{i:4d}  {r['totalGradeScore']:12.4f}  flips={r['flipCount']:3d}  avg={r['avgGradeScore']:8.4f}  max={r['maxFlipGradeScore']:8.4f}  {r['address']}")

    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)

    flips_csv = os.path.join(out_dir, f"epoch_{epoch}_flip_leaderboard.csv")
    ids_csv = os.path.join(out_dir, f"epoch_{epoch}_identity_leaderboard.csv")
    meta_json = os.path.join(out_dir, f"epoch_{epoch}_meta.json")

    write_csv(
        flips_csv,
        header=[
            "rank",
            "gradeScore",
            "grade",
            "status",
            "wrongWordsVotes",
            "shortRespCount",
            "longRespCount",
            "withPrivatePart",
            "author",
            "cid",
            "word1",
            "word2",
            "scan_url",
        ],
        rows=[
            [
                r.rank,
                f"{r.grade_score:.8f}",
                r.grade if r.grade is not None else "",
                r.status,
                r.wrong_words_votes if r.wrong_words_votes is not None else "",
                r.short_resp if r.short_resp is not None else "",
                r.long_resp if r.long_resp is not None else "",
                "true" if r.with_private_part is True else ("false" if r.with_private_part is False else ""),
                r.author,
                r.cid,
                r.word1,
                r.word2,
                f"https://scan.idena.io/flip/{r.cid}",
            ]
            for r in flip_rows
        ],
    )

    write_csv(
        ids_csv,
        header=["rank", "totalGradeScore", "flipCount", "avgGradeScore", "maxFlipGradeScore", "address", "scan_url"],
        rows=[
            [
                i,
                f"{r['totalGradeScore']:.8f}",
                r["flipCount"],
                f"{r['avgGradeScore']:.8f}",
                f"{r['maxFlipGradeScore']:.8f}",
                r["address"],
                f"https://scan.idena.io/address/{r['address']}",
            ]
            for i, r in enumerate(id_sorted, start=1)
        ],
    )

    with open(meta_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "epoch": epoch,
                "baseUrl": args.base_url,
                "excludedWrongWordsAuthorsCount": len(bad_authors),
                "excludedWrongWordsAuthors": sorted(list(bad_authors)),
                "filters": {
                    "includeZero": bool(args.include_zero),
                    "status": sorted(list(allowed_status)) if allowed_status is not None else None,
                },
                "counts": {"flipsSeen": total_seen, "flipsKept": total_kept, "uniqueAuthorsKept": len(sums)},
            },
            f,
            indent=2,
        )

    print("\n[i] Wrote:")
    print(f"[i] {flips_csv}")
    print(f"[i] {ids_csv}")
    print(f"[i] {meta_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
