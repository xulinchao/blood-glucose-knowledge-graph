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

# Generate reports.json for dynamic daily report listing
node -e "
const fs = require('fs');
const path = require('path');

const htmlDir = '_site/research-daily';
const quartzDir = '_site/notes/research-daily';

const scanDir = (dir, urlPrefix) => {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter(f => f.endsWith('-日报.html'))
    .map(f => {
      const date = f.replace('-日报.html', '');
      return { date, title: '血糖控糖热点监控日报', url: urlPrefix + f };
    })
    .sort((a, b) => b.date.localeCompare(a.date));
};

const htmlReports = scanDir(htmlDir, 'research-daily/');
const quartzReports = scanDir(quartzDir, 'notes/research-daily/');

fs.writeFileSync(
  '_site/reports.json',
  JSON.stringify({ html_reports: htmlReports, quartz_reports: quartzReports }, null, 2)
);
console.log('Generated reports.json with', htmlReports.length, 'HTML reports and', quartzReports.length, 'Quartz reports');
"

rm -rf public
mv _site public

echo "Merged toolbox + Quartz notes into public/"
