#!/bin/sh
# Installed locally after the initial configuration has passed validation.
set -eu
umask 077
base=/etc/openclash/custom/unified-rules
exec 9> /tmp/lock/unified-rules.lock
flock -n 9 || exit 0
repository=$(cat "$base/repository")
profile=$(cat "$base/profile")
case "$repository" in *[!a-zA-Z0-9_./-]*|'') exit 2;; esac
case "$profile" in *[!a-zA-Z0-9_.-]*|'') exit 2;; esac
[ "$(uci -q get openclash.config.config_path)" = "/etc/openclash/config/$profile" ] || exit 0
runtime="/etc/openclash/$profile"
next=$(mktemp -d "$base/.update.XXXXXX")
trap 'rm -r "$next"' EXIT
curl -q -fsSL --retry 2 --retry-delay 3 --connect-timeout 10 --max-time 45 --max-filesize 20000000 \
  "https://raw.githubusercontent.com/$repository/release/OpenClash.yaml" > "$next/overlay.yaml"
if cmp -s "$next/overlay.yaml" "$base/overlay.yaml"; then exit 0; fi
cp "$runtime" "$next/candidate.yaml"
ruby "$base/merge.rb" "$next/candidate.yaml" "$next/overlay.yaml"
SAFE_PATHS=/usr/share/openclash:/etc/ssl /etc/openclash/clash -t -d /etc/openclash \
  -f "$next/candidate.yaml" > "$next/validation.log" 2>&1
cp -p "$base/overlay.yaml" "$base/previous.yaml"
mv "$next/overlay.yaml" "$base/overlay.yaml"
rm -f /tmp/openclash.change
/etc/init.d/openclash restart > "$next/restart.log" 2>&1 || true
attempt=0
while [ "$attempt" -lt 20 ]; do
  if /etc/init.d/openclash status | grep -qx running &&
     ruby -ryaml -e 'a,b=ARGV.map{|p| YAML.safe_load(File.read(p),aliases:true)}; abort unless b.all?{|k,v| a[k]==v}' "$runtime" "$base/overlay.yaml" 2>/dev/null; then
    logger -t unified-rules 'Applied new OpenClash routing configuration'
    exit 0
  fi
  attempt=$((attempt + 1))
  sleep 2
done
cp "$base/previous.yaml" "$next/restore.yaml"
mv "$next/restore.yaml" "$base/overlay.yaml"
rm -f /tmp/openclash.change
/etc/init.d/openclash restart > "$next/restore.log" 2>&1 || true
logger -t unified-rules 'Update failed; restored previous routing configuration'
exit 1
