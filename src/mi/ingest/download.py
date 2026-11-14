"""Download the authentic 84.51 Complete Journey tables from the R package maintainer's repository.

Source: https://github.com/bradleyboehmke/completejourney (DESCRIPTION: License CC0; data
originate from 84.51 Complete Journey 2.0 source files). This is the same location the R
functions get_transactions()/get_promotions() download from.

We deliberately do NOT use the unrelated Python port `completejourney_py`, which states its
content is simulated.

Writes data/raw/*.rd[a|s] plus data/raw/manifest.json (URL, bytes, sha256, retrieved_at, commit).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone

from mi.paths import RAW

REPO = "bradleyboehmke/completejourney"
# Pinned commit observed 2026-11-14 (latest master commit 2025-11-25).
COMMIT = "5b5d06192b9856edd04e4d405787af2f2e4a1fef"
FILES = [
    "transactions.rds",
    "products.rda",
    "campaigns.rda",
    "campaign_descriptions.rda",
    "coupons.rda",
    "coupon_redemptions.rda",
    "demographics.rda",
]
# promotions.rds (25 MB, store x product x week display/mailer flags) is optional context.
OPTIONAL = ["promotions.rds"]


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--with-promotions", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    files = FILES + (OPTIONAL if args.with_promotions else [])
    manifest = {"source_repo": f"https://github.com/{REPO}", "commit": COMMIT,
                "licence": "CC0 (package DESCRIPTION)", "files": []}
    for name in files:
        url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/data/{name}"
        dest = RAW / name
        if args.force or not dest.exists():
            print(f"downloading {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "course-research-client"})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as out:
                out.write(r.read())
        manifest["files"].append({
            "name": name, "url": url, "bytes": dest.stat().st_size, "sha256": sha256(dest),
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        print(f"  {name}: {dest.stat().st_size:,} bytes")
    (RAW / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"manifest -> {RAW / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
