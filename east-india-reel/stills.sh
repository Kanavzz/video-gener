#!/bin/sh
# Render stills at the given times and tile them into out/stills/sheet.png for a quick look.
set -e
cd "$(dirname "$0")"
rm -rf out/stills
node render.js build out/stills --stills "$1"
n=$(ls out/stills/*.png | wc -l)
args=""; for f in $(ls out/stills/*.png | sort -t t -k2 -g); do args="$args -i $f"; done
ffmpeg -y -loglevel error $args -filter_complex "hstack=$n,scale=$((n*360)):-1" out/sheet.png
