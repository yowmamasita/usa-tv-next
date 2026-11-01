#!/usr/bin/env bash
# Daily stream refresh on ben@zen (crontab, 05:00 UTC, under flock).
# Prunes dead streams, harvests and injects working ones, gates on the tests, then pushes main
# with the repository's deploy key. NO_PUSH=1 commits locally only, for a supervised run.
set -euo pipefail
cd "$(dirname "$0")/.."
# The router sends all port-53 DNS to NextDNS, which blocks some stream hosts, and prune counts
# an unresolvable host as dead. Re-run in a private mount namespace whose /etc/resolv.conf points
# at unbound on 127.0.0.2 (DNS over TLS, see CLAUDE.md); the rest of zen keeps NextDNS.
if [ -z "${USATV_DNS_NS:-}" ]; then
    export USATV_DNS_NS=1
    exec unshare --user --map-root-user --mount bash -c \
        'mount --bind deploy/resolv.conf /etc/resolv.conf && exec deploy/daily.sh'
fi
export PATH="$HOME/.local/bin:$PATH" NO_COLOR=1
step() { echo "== $(date -Is) $1"; }

step pull; git pull -q --ff-only origin main
step sync; uv sync -q
step prune; uv run python -m harvester prune
step harvest+inject; uv run python -m harvester run --no-resume
step tests; uv run python -m unittest discover -s tests

if [ -z "$(git status --porcelain -- catalog meta stream)" ]; then echo "No stream changes"; exit 0; fi
step commit
git add -- catalog meta stream
git commit -q -m "feat: daily refresh - prune dead and inject working streams"
if [ "${NO_PUSH:-}" = 1 ]; then echo "Committed $(git rev-parse --short HEAD), not pushed"; exit 0; fi
step push; git push -q origin HEAD:main
echo "Pushed $(git rev-parse --short HEAD)"
