#!/usr/bin/env bash
set -euo pipefail

# Quartz builds notes under public/ (baseUrl path: /notes).
# Copy the existing HTML toolbox into the same public/ output.

copy_dir() {
  local src="$1"
  local dest="$2"
  if [ -d "$src" ]; then
    mkdir -p "$dest"
    cp -R "$src/." "$dest/"
  fi
}

copy_file() {
  local src="$1"
  local dest="$2"
  if [ -f "$src" ]; then
    cp "$src" "$dest"
  fi
}

copy_file index.html public/index.html
copy_dir out public/out
copy_dir data public/data
copy_dir blood-glucose-prompt-framework public/blood-glucose-prompt-framework
copy_dir research-daily public/research-daily

echo "bg.purpleiris.cn" > public/CNAME

echo "Merged toolbox assets into public/"
