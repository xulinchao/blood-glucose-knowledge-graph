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
mkdir -p _site/site
for entry in site/*; do
  base="$(basename "$entry")"
  if [ "$base" = "local" ]; then
    continue
  fi
  if [ -d "$entry" ]; then
    copy_dir "$entry" "_site/site/$base"
  else
    copy_file "$entry" "_site/site/$base"
  fi
done
copy_dir data _site/data
copy_dir reports _site/reports
copy_dir research-daily _site/research-daily

echo "bg.purpleiris.cn" > _site/CNAME

# Generate reports.json（与 scripts/generate-reports-json.py 同源，含精选/采集）
python3 scripts/generate-reports-json.py \
  --html-dir _site/research-daily \
  --quartz-dir _site/notes/research-daily \
  --out _site/reports.json || copy_file reports.json _site/reports.json
test -f _site/reports.json || copy_file reports.json _site/reports.json

rm -rf public
mv _site public

echo "Merged toolbox + Quartz notes into public/"
