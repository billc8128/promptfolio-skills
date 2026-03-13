#!/usr/bin/env bash
# Promptfolio skill auto-updater
# Called by each SKILL.md as: bash ~/.promptfolio/update-check.sh
# This script updates itself first, then updates all skill files if needed.
set -euo pipefail

PF_DIR="$HOME/.promptfolio"
LOCAL_V=$(cat "$PF_DIR/VERSION" 2>/dev/null || echo "0")
API_URL=$(python3 -c "import json; print(json.load(open('$PF_DIR/config.json')).get('api_url','https://promptfolio.club'))" 2>/dev/null || echo "https://promptfolio.club")
REMOTE_V=$(curl -sfL --max-time 5 "$API_URL/skills/VERSION" 2>/dev/null || echo "")

# Network failure — can't check
if [ -z "$REMOTE_V" ]; then
  echo "OFFLINE v$LOCAL_V"
  exit 0
fi

# Already up to date
if [ "$LOCAL_V" = "$REMOTE_V" ]; then
  echo "UP_TO_DATE v$LOCAL_V"
  exit 0
fi

echo "UPDATING v$LOCAL_V -> v$REMOTE_V"

# 1. Update this script itself first
curl -sfL "$API_URL/skills/update-check.sh" -o "$PF_DIR/update-check.sh.tmp" 2>/dev/null && \
  mv "$PF_DIR/update-check.sh.tmp" "$PF_DIR/update-check.sh" && \
  chmod +x "$PF_DIR/update-check.sh" || true

# 2. Update all skill files
SKILLS="promptfolio-summarize promptfolio-search-people promptfolio-search-skills promptfolio-logout"
FILES="SKILL.md analysis-prompt.md device-auth.sh scripts/discover-sessions.sh scripts/compute-stats.py scripts/assemble-payload.py scripts/post-sync.sh"
FAIL=0

for SKILL in $SKILLS; do
  SKILL_DIR="$PF_DIR/skills/$SKILL"
  mkdir -p "$SKILL_DIR/scripts" 2>/dev/null || true
  for F in $FILES; do
    curl -sfL "$API_URL/skills/$SKILL/$F" -o "$SKILL_DIR/$F.tmp" 2>/dev/null && \
      mv "$SKILL_DIR/$F.tmp" "$SKILL_DIR/$F" || true
  done
  # Restore execute bits on scripts
  chmod +x "$SKILL_DIR/device-auth.sh" "$SKILL_DIR/scripts/discover-sessions.sh" "$SKILL_DIR/scripts/post-sync.sh" 2>/dev/null || true
done

# Verify at least the main SKILL.md downloaded successfully
if [ ! -s "$PF_DIR/skills/promptfolio-summarize/SKILL.md" ]; then
  FAIL=1
fi

# 3. Write new version only if update succeeded
if [ "$FAIL" -eq 0 ]; then
  echo "$REMOTE_V" > "$PF_DIR/VERSION.tmp" && mv "$PF_DIR/VERSION.tmp" "$PF_DIR/VERSION"
  echo "UPDATED v$REMOTE_V"
else
  echo "UPDATE_FAILED v$LOCAL_V"
fi
