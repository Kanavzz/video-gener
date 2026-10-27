#!/usr/bin/env bash
# The clips used in the current cut (Pexels, fetched by ID - no API key needed).
set -euo pipefail
cd "$(dirname "$0")"
P=https://www.pexels.com/video

python3 fetch_by_id.py 1 $P/close-up-of-watch-mechanism-11965370/ --photographer "Quang Viet Nguyen" --start 1.5
python3 fetch_by_id.py 2 $P/drone-footage-of-a-man-climbing-a-snowy-mountain-15781857/ --start 1.0 \
    --query "drone footage of a man climbing a snowy mountain"
python3 fetch_by_id.py 3 $P/elderly-man-fixing-a-pocket-watch-8321913/ --photographer "Tima Miroshnichenko" --start 16 --zoom 1.15 --anchor-x 0.85 \
    --query "elderly man fixing a pocket watch"
python3 fetch_by_id.py 4 $P/deep-dive-underwater-17809337/ --start 6 --query "deep dive underwater"
python3 fetch_by_id.py 5 $P/close-up-view-of-a-rolex-oyster-perpetual-watch-17197593/ --photographer "Quang Viet Nguyen" --start 2
python3 fetch_by_id.py 6 $P/big-waves-in-an-ocean-2802271/ --photographer "Sean JOHNSTON" --start 3
python3 fetch_by_id.py 7 $P/male-hands-showing-watch-12178371/ --photographer "utopia 36" --start 0.5 \
    --query "man adjusting watch"
python3 fetch_by_id.py 8 $P/close-up-view-of-a-rolex-watch-6230465/ --photographer "Mitchel Durfee" --start 3.5 \
    --query "gold watch black background"
