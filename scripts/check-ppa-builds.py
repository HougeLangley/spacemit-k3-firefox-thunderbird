#!/usr/bin/env python3
"""Check the Firefox K3 PPA builds and report state/elapsed/log URL.

Usage: python3 check-ppa-builds.py [build-id ...]
Default: the 1.3 retry build and the old 1.1 build.
"""
import datetime
import json
import sys
import time
import urllib.error
import urllib.request

USER = "mymathersname-gmail"
PPA = "ppa"
API = f"https://api.launchpad.net/1.0/~{USER}/+archive/ubuntu/{PPA}"
DEFAULT_BUILDS = (33976658, 33975178, 33970093)


def get_json(url: str, attempts: int = 3):
    last = None
    for n in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except Exception as exc:  # Launchpad API is intermittently slow
            last = exc
            time.sleep(3 * (n + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last}")


def main(ids):
    now = datetime.datetime.now(datetime.timezone.utc)
    for bid in ids:
        try:
            d = get_json(f"{API}/+build/{bid}")
        except Exception as exc:
            print(f"{bid}: ERROR {exc}")
            continue
        state = d.get("buildstate")
        first = d.get("date_first_dispatched")
        built = d.get("datebuilt")
        elapsed = ""
        if first:
            t = datetime.datetime.fromisoformat(first)
            elapsed = f"{(now - t).total_seconds() / 3600:.2f}h"
        print(
            f"{bid}: state={state} elapsed={elapsed} "
            f"first={first} built={built} log={d.get('build_log_url')}"
        )
    try:
        b = get_json(f"{API}?ws.op=getPublishedBinaries&binary_name=firefox&exact_match=true")
        print(f"published_firefox_binaries={b.get('total_size')}")
    except Exception as exc:
        print(f"binaries: ERROR {exc}")


if __name__ == "__main__":
    ids = [int(x) for x in sys.argv[1:]] or list(DEFAULT_BUILDS)
    main(ids)
