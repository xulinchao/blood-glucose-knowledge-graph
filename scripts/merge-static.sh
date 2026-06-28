#!/usr/bin/env bash
set -euo pipefail

# Quartz builds into public/ with baseUrl path /notes.
# Move the notes site under public/notes/, then add toolbox assets at root.

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

mkdir -p _site
mv public _site/notes

copy_file index.html _site/index.html
copy_dir site _site/site
copy_dir data _site/data
copy_dir reports _site/reports
copy_dir research-daily _site/research-daily

echo "bg.purpleiris.cn" > _site/CNAME

rm -rf public
mv _site public

echo "Merged toolbox + Quartz notes into public/"
