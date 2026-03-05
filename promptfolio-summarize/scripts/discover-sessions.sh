#!/usr/bin/env bash
set -euo pipefail

# Discover AI coding session files from the last 30 days.
# Output: prints the path of a temp file containing one session path per line.
#
# Usage:
#   SESSION_LIST=$(bash discover-sessions.sh)
#
# Environment:
#   SESSION_LIST  – optional; reuse an existing temp file path instead of creating one
#   PF_DAYS       – optional; number of days to look back (default: 30)
#   PF_SOURCES    – optional; comma-separated list of sources to scan
#                   (e.g. "claude-code,cursor,codex"). If unset, scans all.

DAYS="${PF_DAYS:-30}"
SESSION_LIST="${SESSION_LIST:-$(mktemp /tmp/promptfolio-sessions.XXXXXX)}"
SOURCES="${PF_SOURCES:-all}"

should_scan() {
  [ "$SOURCES" = "all" ] && return 0
  echo ",$SOURCES," | grep -qi ",$1," && return 0
  return 1
}

# ── Find session files ────────────────────────────────────────────────

if should_scan "claude-code"; then
  find ~/.claude/projects/ -name "*.jsonl" -not -path "*/subagents/*" -type f 2>/dev/null >> "$SESSION_LIST" || true
fi

if should_scan "cursor"; then
  find ~/.cursor/projects/ -path "*/agent-transcripts/*" \( -name "*.txt" -o -name "*.jsonl" \) -type f 2>/dev/null >> "$SESSION_LIST" || true
fi

if should_scan "codex"; then
  find ~/.codex/sessions/ -name "*.jsonl" -type f 2>/dev/null >> "$SESSION_LIST" || true
  [ -f ~/.codex/history.jsonl ] && echo ~/.codex/history.jsonl >> "$SESSION_LIST"
fi

if should_scan "openclaw"; then
  find ~/.openclaw/sessions -name "*.jsonl" -type f 2>/dev/null >> "$SESSION_LIST" || true
  find ~/.openclaw/agents -name "*.jsonl" -type f 2>/dev/null >> "$SESSION_LIST" || true
fi

if should_scan "antigravity"; then
  find "$HOME/Library/Application Support/Antigravity" \
    \( -path "*/exthost/google.antigravity/*.log" -o -name "*.jsonl" -o -name "*.json" \) \
    -not -name "state.vscdb" -type f 2>/dev/null >> "$SESSION_LIST" || true
  find ~/.gemini/antigravity -type f \( -name "*.jsonl" -o -name "*.json" \) 2>/dev/null >> "$SESSION_LIST" || true
fi

if should_scan "windsurf"; then
  find ~/.codeium/windsurf ~/.windsurf \
    "$HOME/Library/Application Support/Windsurf" \
    "$HOME/Library/Application Support/Codeium/Windsurf" \
    -type f \( -name "*.jsonl" -o -name "*.json" -o -path "*/agent-transcripts/*" \) \
    -not -name "state.vscdb" 2>/dev/null >> "$SESSION_LIST" || true
fi

if should_scan "chatgpt"; then
  find ~/Desktop/chatgpt_history ~/Downloads -maxdepth 4 -type f \
    \( -name "conversations*.json" -o -name "chat.html" \) \
    2>/dev/null >> "$SESSION_LIST" || true
fi

# ── Deduplicate ───────────────────────────────────────────────────────

sort -u -o "$SESSION_LIST" "$SESSION_LIST"

# ── Filter to last N days ────────────────────────────────────────────

CUTOFF=$(date -v-${DAYS}d +%s 2>/dev/null || date -d "${DAYS} days ago" +%s)
FILTERED=$(mktemp /tmp/promptfolio-filtered.XXXXXX)
while IFS= read -r f; do
  MTIME=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null || echo 0)
  if [ "$MTIME" -ge "$CUTOFF" ] 2>/dev/null; then
    echo "$f" >> "$FILTERED"
  fi
done < "$SESSION_LIST"
mv "$FILTERED" "$SESSION_LIST"

# ── Output ────────────────────────────────────────────────────────────

TOTAL=$(wc -l < "$SESSION_LIST" | tr -d ' ')
echo "$SESSION_LIST"
echo "Found $TOTAL session files (last ${DAYS} days)" >&2
