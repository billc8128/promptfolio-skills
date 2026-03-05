# promptfolio-skills

Open-source CLI skills for [promptfolio](https://promptfolio.club) — your AI-verified skill profile.

These skills run **locally on your machine** inside AI coding agents (Claude Code, Cursor, etc.). They analyze your conversation history, extract interaction patterns, and sync structured results to the platform.

**No raw conversation data is ever uploaded.** All analysis happens locally. Only structured results (framework sentences, activity stats, portrait) are sent after your explicit confirmation. The code is fully auditable here.

## Skills

| Skill | Description |
|-------|-------------|
| `promptfolio-summarize` | Analyze AI conversation history, extract framework sentences, build your portrait |
| `promptfolio-search-people` | Search the platform for people by skill or expertise |
| `promptfolio-search-skills` | Search for reusable AI interaction techniques and skills |
| `promptfolio-logout` | Sign out this CLI device |

## Install

```bash
curl -fsSL https://promptfolio.club/install.sh | bash
```

## How it works

1. Skills are installed to `~/.promptfolio/skills/` on your machine
2. Your AI agent (Claude Code, Cursor, etc.) loads the skill when you invoke it
3. `promptfolio-summarize` reads your local conversation logs, analyzes them with AI, and shows you the results
4. You review everything before anything is uploaded
5. Only the structured analysis (visible to you) is synced to the platform

## Data flow (auditable)

```
Local conversation files
  -> discover-sessions.sh    (finds session files, no network calls)
  -> compute-stats.py        (computes token counts + activity data locally)
  -> AI agent analyzes        (runs in your local AI editor)
  -> You review results
  -> assemble-payload.py     (packages only the structured analysis)
  -> Upload to platform       (only after your confirmation)
```

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE)
