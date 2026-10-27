#!/usr/bin/env bash
# The clips used in the current 15s cut (Pexels, fetched by ID - no API key needed).
set -euo pipefail
cd "$(dirname "$0")"
P=https://www.pexels.com/video
rm -f clips/manifest.json

python3 fetch_by_id.py 1 $P/close-up-of-watch-mechanism-11965370/ --photographer "Quang Viet Nguyen" --start 1.5
python3 fetch_by_id.py 2 $P/drone-footage-of-a-man-climbing-a-snowy-mountain-15781857/ --start 1.0 \
    --query "drone footage of a man climbing a snowy mountain"
python3 fetch_by_id.py 3 $P/deep-dive-underwater-17809337/ --start 6 --query "deep dive underwater"
python3 fetch_by_id.py 4 $P/surfer-riding-the-big-waves-of-a-sea-2873484/ --photographer "Evgenia Kirpichnikova" --start 2.5 \
    --query "surfer riding big wave"
python3 fetch_by_id.py 5 $P/big-waves-in-an-ocean-2802271/ --photographer "Sean JOHNSTON" --start 3.5
python3 fetch_by_id.py 6 $P/close-up-view-of-a-rolex-watch-6230465/ --photographer "Mitchel Durfee" --start 4 \
    --query "gold watch black background"
