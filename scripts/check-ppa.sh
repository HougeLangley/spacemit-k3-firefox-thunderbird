#!/bin/bash
# Check whether the Launchpad account has the GPG key and PPA ready.
set -euo pipefail
user="mymathersname-gmail"
ppa="firefox-k3"
api="https://api.launchpad.net/1.0/~${user}"
echo "== account =="
curl -s "$api" | python3 -c 'import sys,json; d=json.load(sys.stdin); print({k:d.get(k) for k in ("name","display_name","is_probationary","karma")})'
echo "== gpg keys =="
curl -s "$api/gpg_keys" | python3 -c 'import sys,json; d=json.load(sys.stdin); print("count",d["total_size"]); [print(e.get("keyid"), e.get("fingerprint")) for e in d["entries"]]'
echo "== ppas =="
curl -s "$api/ppas" | python3 -c 'import sys,json; d=json.load(sys.stdin); print("count",d["total_size"]); [print(e.get("name"), e.get("web_link")) for e in d["entries"]]'
echo "== target ppa =="
curl -s "$api/+archive/ubuntu/${ppa}" | python3 -c 'import sys,json; d=json.load(sys.stdin); print({k:d.get(k) for k in ("name","displayname","authorized_size","web_link")})' 2>/dev/null || echo "PPA not found (create it first)"
