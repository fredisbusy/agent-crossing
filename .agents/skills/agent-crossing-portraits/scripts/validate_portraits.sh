#!/usr/bin/env bash
set -euo pipefail

portrait_dir=${1:-packages/frontend/public/portraits}

command -v magick >/dev/null 2>&1 || {
  echo "ImageMagick 'magick' is required." >&2
  exit 1
}
[[ -d "$portrait_dir" ]] || {
  echo "Portrait directory does not exist: $portrait_dir" >&2
  exit 1
}

shopt -s nullglob
portraits=("$portrait_dir"/*.png)
(( ${#portraits[@]} > 0 )) || {
  echo "No PNG portraits found in $portrait_dir" >&2
  exit 1
}

for portrait in "${portraits[@]}"; do
  dimensions=$(magick "$portrait" -format '%wx%h' info:)
  alpha_range=$(magick "$portrait" -alpha extract -format '%[fx:minima],%[fx:maxima]' info:)
  if [[ "$dimensions" != "512x512" ]]; then
    echo "Expected 512x512: $portrait ($dimensions)" >&2
    exit 1
  fi
  if [[ "$alpha_range" != "0,1" ]]; then
    echo "Expected transparent and opaque pixels: $portrait ($alpha_range)" >&2
    exit 1
  fi
  echo "OK $portrait"
done
