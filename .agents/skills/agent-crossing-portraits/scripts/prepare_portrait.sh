#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 INPUT OUTPUT [--checkerboard] [--force]" >&2
  exit 2
}

[[ $# -ge 2 ]] || usage

input=$1
output=$2
shift 2
checkerboard=false
force=false

for option in "$@"; do
  case "$option" in
    --checkerboard) checkerboard=true ;;
    --force) force=true ;;
    *) usage ;;
  esac
done

command -v magick >/dev/null 2>&1 || {
  echo "ImageMagick 'magick' is required." >&2
  exit 1
}
[[ -f "$input" ]] || {
  echo "Input does not exist: $input" >&2
  exit 1
}
if [[ -e "$output" && "$force" != true ]]; then
  echo "Output already exists; pass --force only for an approved replacement: $output" >&2
  exit 1
fi

mkdir -p "$(dirname "$output")"

if [[ "$checkerboard" == true ]]; then
  magick "$input" \
    -alpha on -fuzz 5% -fill none -draw 'color 0,0 floodfill' \
    -filter point -resize 512x512 \
    -define png:compression-level=9 "$output"
else
  magick "$input" \
    -alpha on -filter point -resize 512x512 \
    -define png:compression-level=9 "$output"
fi

dimensions=$(magick "$output" -format '%wx%h' info:)
alpha_range=$(magick "$output" -alpha extract -format '%[fx:minima],%[fx:maxima]' info:)
if [[ "$dimensions" != "512x512" || "$alpha_range" != "0,1" ]]; then
  echo "Invalid portrait: dimensions=$dimensions alpha_range=$alpha_range" >&2
  exit 1
fi

echo "Prepared $output (512x512 RGBA, transparent background)"
