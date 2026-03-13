#!/bin/bash
set -e

BASE_URL="https://promptfolio.club/skills"
AUTH_HELPER_URL="$BASE_URL/promptfolio-summarize/device-auth.sh"
AUTH_HELPER_PATH="$HOME/.promptfolio/device-auth.sh"
CANONICAL="$HOME/.promptfolio/skills"

install_auth_helper() {
  mkdir -p "$HOME/.promptfolio"
  curl -sfL "$AUTH_HELPER_URL" -o "$AUTH_HELPER_PATH"
  chmod +x "$AUTH_HELPER_PATH"
  curl -sfL "$BASE_URL/VERSION" -o "$HOME/.promptfolio/VERSION" 2>/dev/null || true
  curl -sfL "$BASE_URL/update-check.sh" -o "$HOME/.promptfolio/update-check.sh" 2>/dev/null || true
  chmod +x "$HOME/.promptfolio/update-check.sh" 2>/dev/null || true
}

# Download once to ~/.promptfolio/skills/
download_canonical() {
  mkdir -p "$CANONICAL/promptfolio-summarize/scripts" \
           "$CANONICAL/promptfolio-search-people" \
           "$CANONICAL/promptfolio-search-skills" \
           "$CANONICAL/promptfolio-logout"

  curl -sfL "$BASE_URL/promptfolio-summarize/SKILL.md"                    -o "$CANONICAL/promptfolio-summarize/SKILL.md"
  curl -sfL "$BASE_URL/promptfolio-summarize/analysis-prompt.md"          -o "$CANONICAL/promptfolio-summarize/analysis-prompt.md"
  curl -sfL "$BASE_URL/promptfolio-summarize/device-auth.sh"              -o "$CANONICAL/promptfolio-summarize/device-auth.sh"
  chmod +x "$CANONICAL/promptfolio-summarize/device-auth.sh"
  curl -sfL "$BASE_URL/promptfolio-summarize/scripts/discover-sessions.sh" -o "$CANONICAL/promptfolio-summarize/scripts/discover-sessions.sh"
  chmod +x "$CANONICAL/promptfolio-summarize/scripts/discover-sessions.sh"
  curl -sfL "$BASE_URL/promptfolio-summarize/scripts/compute-stats.py"    -o "$CANONICAL/promptfolio-summarize/scripts/compute-stats.py"
  curl -sfL "$BASE_URL/promptfolio-summarize/scripts/assemble-payload.py" -o "$CANONICAL/promptfolio-summarize/scripts/assemble-payload.py"
  curl -sfL "$BASE_URL/promptfolio-summarize/scripts/post-sync.sh"        -o "$CANONICAL/promptfolio-summarize/scripts/post-sync.sh"
  chmod +x "$CANONICAL/promptfolio-summarize/scripts/post-sync.sh"
  curl -sfL "$BASE_URL/promptfolio-search-people/SKILL.md"                -o "$CANONICAL/promptfolio-search-people/SKILL.md"
  curl -sfL "$BASE_URL/promptfolio-search-skills/SKILL.md"                -o "$CANONICAL/promptfolio-search-skills/SKILL.md"
  curl -sfL "$BASE_URL/promptfolio-logout/SKILL.md"                       -o "$CANONICAL/promptfolio-logout/SKILL.md"
}

SKILL_NAMES="promptfolio-summarize promptfolio-search-people promptfolio-search-skills promptfolio-logout"

# Symlink skill folders from an agent's skills dir to the canonical copy
link_to_agent() {
  local dir="$1"
  mkdir -p "$dir"
  for name in $SKILL_NAMES; do
    rm -rf "$dir/$name"
    ln -s "$CANONICAL/$name" "$dir/$name"
  done
}

# Antigravity uses flat file layout — symlink individual files
link_to_antigravity() {
  local dir="$1"
  mkdir -p "$dir" "$dir/scripts"
  ln -sf "$CANONICAL/promptfolio-summarize/SKILL.md"                     "$dir/promptfolio-summarize.md"
  ln -sf "$CANONICAL/promptfolio-summarize/analysis-prompt.md"           "$dir/analysis-prompt.md"
  ln -sf "$CANONICAL/promptfolio-summarize/device-auth.sh"               "$dir/device-auth.sh"
  ln -sf "$CANONICAL/promptfolio-summarize/scripts/discover-sessions.sh" "$dir/scripts/discover-sessions.sh"
  ln -sf "$CANONICAL/promptfolio-summarize/scripts/compute-stats.py"     "$dir/scripts/compute-stats.py"
  ln -sf "$CANONICAL/promptfolio-summarize/scripts/assemble-payload.py"  "$dir/scripts/assemble-payload.py"
  ln -sf "$CANONICAL/promptfolio-summarize/scripts/post-sync.sh"         "$dir/scripts/post-sync.sh"
  ln -sf "$CANONICAL/promptfolio-search-people/SKILL.md"                 "$dir/promptfolio-search-people.md"
  ln -sf "$CANONICAL/promptfolio-search-skills/SKILL.md"                 "$dir/promptfolio-search-skills.md"
  ln -sf "$CANONICAL/promptfolio-logout/SKILL.md"                        "$dir/promptfolio-logout.md"
}

echo "Installing promptfolio skills..."
install_auth_helper
echo "  Installed auth helper -> $AUTH_HELPER_PATH"

echo "  Downloading skills -> $CANONICAL"
download_canonical

INSTALLED=""

# Claude Code
if [ -d "$HOME/.claude" ]; then
  link_to_agent "$HOME/.claude/skills"
  INSTALLED="Claude Code"
  echo "  Linked to Claude Code"
fi

# Cursor
if [ -d "$HOME/.cursor" ]; then
  link_to_agent "$HOME/.cursor/skills"
  [ -n "$INSTALLED" ] && INSTALLED="$INSTALLED + Cursor" || INSTALLED="Cursor"
  echo "  Linked to Cursor"
fi

# Codex
if [ -d "$HOME/.codex" ]; then
  link_to_agent "$HOME/.codex/skills"
  [ -n "$INSTALLED" ] && INSTALLED="$INSTALLED + Codex" || INSTALLED="Codex"
  echo "  Linked to Codex"
fi

# OpenClaw
if [ -d "$HOME/.openclaw" ]; then
  link_to_agent "$HOME/.openclaw/skills"
  [ -n "$INSTALLED" ] && INSTALLED="$INSTALLED + OpenClaw" || INSTALLED="OpenClaw"
  echo "  Linked to OpenClaw"
fi

# Trae / Trae CN
if [ -d "$HOME/.trae" ] || [ -d "$HOME/.trae-cn" ] || [ -d "$HOME/Library/Application Support/Trae" ] || [ -d "$HOME/Library/Application Support/Trae CN" ]; then
  link_to_agent "$HOME/.trae/skills"
  [ -d "$HOME/.trae-cn" ] && link_to_agent "$HOME/.trae-cn/skills"
  [ -n "$INSTALLED" ] && INSTALLED="$INSTALLED + Trae" || INSTALLED="Trae"
  echo "  Linked to Trae"
fi

# Windsurf
if [ -d "$HOME/.windsurf" ] || [ -d "$HOME/.codeium/windsurf" ] || [ -d "$HOME/Library/Application Support/Windsurf" ]; then
  link_to_agent "$HOME/.windsurf/skills"
  [ -n "$INSTALLED" ] && INSTALLED="$INSTALLED + Windsurf" || INSTALLED="Windsurf"
  echo "  Linked to Windsurf"
fi

# Gemini CLI
if [ -d "$HOME/.gemini/tmp" ]; then
  link_to_agent "$HOME/.gemini/skills"
  [ -n "$INSTALLED" ] && INSTALLED="$INSTALLED + Gemini CLI" || INSTALLED="Gemini CLI"
  echo "  Linked to Gemini CLI"
fi

# OpenCode
if [ -f "$HOME/.local/share/opencode/opencode.db" ] || [ -d "$HOME/.opencode" ]; then
  link_to_agent "$HOME/.opencode/skills"
  [ -n "$INSTALLED" ] && INSTALLED="$INSTALLED + OpenCode" || INSTALLED="OpenCode"
  echo "  Linked to OpenCode"
fi

# Antigravity (workflow-based, experimental)
if [ -d "$HOME/.gemini/antigravity" ] || [ -d "$HOME/Library/Application Support/Antigravity" ]; then
  link_to_antigravity "$HOME/.gemini/antigravity/global_workflows"
  [ -n "$INSTALLED" ] && INSTALLED="$INSTALLED + Antigravity" || INSTALLED="Antigravity"
  echo "  Linked to Antigravity (global workflows)"
fi

# No known client found — link to common default locations
if [ -z "$INSTALLED" ]; then
  link_to_agent "$HOME/.claude/skills"
  link_to_agent "$HOME/.cursor/skills"
  link_to_agent "$HOME/.codex/skills"
  link_to_agent "$HOME/.openclaw/skills"
  link_to_agent "$HOME/.trae/skills"
  link_to_agent "$HOME/.windsurf/skills"
  link_to_agent "$HOME/.gemini/skills"
  link_to_agent "$HOME/.opencode/skills"
  link_to_antigravity "$HOME/.gemini/antigravity/global_workflows"
  INSTALLED="Claude Code + Cursor + Codex + OpenClaw + Trae + Windsurf + Gemini CLI + OpenCode + Antigravity"
  echo "  Linked to all supported agents"
fi

echo ""
echo "Done! ($INSTALLED)"
echo ""
printf "\033[1;32m🔒 All analysis runs 100%% locally on your machine. Your raw conversations are NEVER uploaded.\033[0m\n"
echo ""
echo "Run /promptfolio-summarize to build your AI-verified skill profile."
echo "For Antigravity, open ~/.gemini/antigravity/global_workflows/promptfolio-summarize.md."
echo "Token usage is now counted automatically during /promptfolio-summarize."
