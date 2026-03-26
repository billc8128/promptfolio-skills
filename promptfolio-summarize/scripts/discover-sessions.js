#!/usr/bin/env node
/**
 * Discover AI coding session files from the last N days.
 * Cross-platform replacement for discover-sessions.sh (works on Windows, macOS, Linux).
 *
 * Output: prints the path of a temp file containing one session path per line.
 *
 * Environment:
 *   SESSION_LIST  – optional; reuse an existing temp file path
 *   PF_DAYS       – optional; number of days to look back (default: 30)
 *   PF_SOURCES    – optional; comma-separated list of sources to scan
 *                   (e.g. "claude-code,cursor,codex"). If unset, scans all.
 */

const fs = require("fs");
const path = require("path");
const os = require("os");
const { execSync } = require("child_process");

// ── Config ────────────────────────────────────────────────────────────

const DAYS = parseInt(process.env.PF_DAYS || "30", 10);
const SOURCES = (process.env.PF_SOURCES || "all").toLowerCase();
const HOME = os.homedir();

const cutoffMs = Date.now() - DAYS * 24 * 60 * 60 * 1000;

function shouldScan(source) {
  return SOURCES === "all" || SOURCES.split(",").map(s => s.trim()).includes(source);
}

// ── Session list file ─────────────────────────────────────────────────

let sessionListPath = process.env.SESSION_LIST || "";
if (!sessionListPath) {
  const tmpDir = os.tmpdir();
  const suffix = Math.random().toString(36).slice(2, 8);
  sessionListPath = path.join(tmpDir, `promptfolio-sessions.${suffix}`);
}
// Ensure file exists
if (!fs.existsSync(sessionListPath)) {
  fs.writeFileSync(sessionListPath, "");
}

const results = [];

// ── Helpers ───────────────────────────────────────────────────────────

function exists(p) {
  try { return fs.existsSync(p); } catch { return false; }
}

function isDir(p) {
  try { return fs.statSync(p).isDirectory(); } catch { return false; }
}

function isFile(p) {
  try { return fs.statSync(p).isFile(); } catch { return false; }
}

/**
 * Recursively walk a directory, collecting files matching a filter function.
 * Silently skips directories/files that can't be accessed.
 */
function walk(dir, filter, opts = {}) {
  const maxDepth = opts.maxDepth ?? Infinity;
  const found = [];

  function _walk(current, depth) {
    if (depth > maxDepth) return;
    let entries;
    try { entries = fs.readdirSync(current, { withFileTypes: true }); }
    catch { return; }
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      try {
        if (entry.isDirectory()) {
          _walk(full, depth + 1);
        } else if (entry.isFile() && filter(full, entry.name)) {
          found.push(full);
        }
      } catch { /* permission denied, broken symlink, etc. */ }
    }
  }

  if (isDir(dir)) _walk(dir, 0);
  return found;
}

// Platform-aware Application Support path
function appSupport() {
  if (process.platform === "darwin") {
    return path.join(HOME, "Library", "Application Support");
  }
  if (process.platform === "win32") {
    return process.env.APPDATA || path.join(HOME, "AppData", "Roaming");
  }
  // Linux: use XDG or fallback
  return process.env.XDG_DATA_HOME || path.join(HOME, ".local", "share");
}

// ── Source scanners ───────────────────────────────────────────────────

function scanClaudeCode() {
  const dir = path.join(HOME, ".claude", "projects");
  results.push(...walk(dir, (f) => f.endsWith(".jsonl"), { maxDepth: 8 }));
}

function scanCursor() {
  const dir = path.join(HOME, ".cursor", "projects");
  results.push(...walk(dir, (f, name) => {
    if (!f.includes("agent-transcripts")) return false;
    return name.endsWith(".txt") || name.endsWith(".jsonl");
  }, { maxDepth: 8 }));
}

function scanCodex() {
  const sessionsDir = path.join(HOME, ".codex", "sessions");
  results.push(...walk(sessionsDir, (f) => f.endsWith(".jsonl"), { maxDepth: 8 }));
  const historyFile = path.join(HOME, ".codex", "history.jsonl");
  if (isFile(historyFile)) results.push(historyFile);
}

function scanOpenclaw() {
  results.push(...walk(path.join(HOME, ".openclaw", "sessions"), (f) => f.endsWith(".jsonl"), { maxDepth: 8 }));
  results.push(...walk(path.join(HOME, ".openclaw", "agents"), (f) => f.endsWith(".jsonl"), { maxDepth: 8 }));
}

function scanAntigravity() {
  // macOS Application Support
  const asDir = path.join(appSupport(), "Antigravity");
  results.push(...walk(asDir, (f, name) => {
    if (name === "state.vscdb") return false;
    if (f.includes("exthost") && f.includes("google.antigravity") && name.endsWith(".log")) return true;
    return name.endsWith(".jsonl") || name.endsWith(".json");
  }, { maxDepth: 8 }));
  // ~/.gemini/antigravity
  results.push(...walk(path.join(HOME, ".gemini", "antigravity"), (f, name) =>
    name.endsWith(".jsonl") || name.endsWith(".json")
  , { maxDepth: 8 }));
}

function scanWindsurf() {
  const dirs = [
    path.join(HOME, ".codeium", "windsurf"),
    path.join(HOME, ".windsurf"),
    path.join(appSupport(), "Windsurf"),
    path.join(appSupport(), "Codeium", "Windsurf"),
  ];
  for (const dir of dirs) {
    results.push(...walk(dir, (f, name) => {
      if (name === "state.vscdb") return false;
      if (name.endsWith(".jsonl") || name.endsWith(".json")) return true;
      if (f.includes("agent-transcripts")) return true;
      return false;
    }, { maxDepth: 8 }));
  }
}

function scanChatgpt() {
  const dirs = [
    path.join(HOME, "Desktop", "chatgpt_history"),
    path.join(HOME, "Downloads"),
  ];
  for (const dir of dirs) {
    results.push(...walk(dir, (f, name) => {
      return name.startsWith("conversations") && name.endsWith(".json")
        || name === "chat.html";
    }, { maxDepth: 4 }));
  }
}

function scanGeminiCli() {
  const dir = path.join(HOME, ".gemini", "tmp");
  results.push(...walk(dir, (f, name) => {
    return f.includes("chats") && name.startsWith("session-") && name.endsWith(".json");
  }, { maxDepth: 6 }));
}

function scanTrae() {
  let found = 0;
  // Known export locations
  const exports = [
    path.join(HOME, ".trae-cn", "chat-export.json"),
    path.join(HOME, ".trae", "chat-export.json"),
    path.join(HOME, "Desktop", "trae-chat-export.json"),
    path.join(HOME, "Downloads", "trae-chat-export.json"),
  ];
  for (const f of exports) {
    if (isFile(f)) { results.push(f); found++; }
  }
  // Scan for exported files
  for (const dir of [path.join(HOME, ".trae-cn"), path.join(HOME, ".trae")]) {
    const files = walk(dir, (f, name) => /chat.*export.*\.json/i.test(name), { maxDepth: 2 });
    results.push(...files);
    found += files.length;
  }
  // Detection marker if installed but no exports
  if (found === 0) {
    const traeDirs = [
      path.join(HOME, ".trae-cn"),
      path.join(HOME, ".trae"),
      path.join(appSupport(), "Trae CN"),
      path.join(appSupport(), "Trae"),
    ];
    for (const d of traeDirs) {
      if (isDir(d)) {
        process.stderr.write("TRAE_DETECTED_NO_EXPORT\n");
        break;
      }
    }
  }
}

function scanOpencode() {
  const dbPath = path.join(HOME, ".local", "share", "opencode", "opencode.db");
  if (!isFile(dbPath)) return;

  // Extract sessions from SQLite using Python (cross-platform, sqlite3 built-in)
  // Paths passed via env vars to avoid shell injection risks with execSync -c
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "promptfolio-opencode-"));
  const pyScript = path.join(tmpDir, "_extract.py");
  fs.writeFileSync(pyScript, `
import sqlite3, json, os, sys, re
db = sqlite3.connect(os.environ['PF_OC_DB'])
out = os.environ['PF_OC_DIR']
def table_exists(name):
    return db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None
if not table_exists('session') or not table_exists('message'):
    sys.exit(0)
_safe_re = re.compile(r'[^a-zA-Z0-9_-]')
has_part = table_exists('part')
for sid, tc in db.execute('SELECT id, time_created FROM session'):
    safe_sid = _safe_re.sub('_', str(sid))[:200]
    if not safe_sid: continue
    msgs = []
    for mid, mdata, mtc in db.execute('SELECT id, data, time_created FROM message WHERE session_id=? ORDER BY time_created', (sid,)):
        try: md = json.loads(mdata)
        except: md = {}
        parts = []
        if has_part:
            for (pd,) in db.execute('SELECT data FROM part WHERE message_id=? ORDER BY time_created', (mid,)):
                try: parts.append(json.loads(pd))
                except: pass
        role = md.get('role', 'unknown')
        texts = []
        for p in parts:
            if isinstance(p, dict):
                t = p.get('text','') or p.get('content','')
                if isinstance(t, str) and t: texts.append(t)
        if not texts and 'content' in md:
            t = md['content']
            if isinstance(t, str): texts.append(t)
        if texts:
            msgs.append({'role': role, 'content': chr(10).join(texts), 'timestamp': mtc})
    if not msgs: continue
    fp = os.path.join(out, safe_sid + '.json')
    with open(fp, 'w') as f: json.dump({'messages': msgs}, f)
    print(fp)
db.close()
`);

  const env = { ...process.env, PF_OC_DB: dbPath, PF_OC_DIR: tmpDir };

  // Try python3 first, then python
  for (const py of ["python3", "python"]) {
    try {
      const output = execSync(`${py} ${JSON.stringify(pyScript)}`, {
        encoding: "utf-8",
        timeout: 30000,
        stdio: ["pipe", "pipe", "pipe"],
        env,
      }).trim();
      if (output) {
        results.push(...output.split("\n").filter(Boolean));
      }
      return;
    } catch { /* try next */ }
  }
  process.stderr.write("opencode: python not found, skipping opencode extraction\n");
}

// ── Windows: also scan AppData for Cursor/Windsurf ────────────────────

function scanWindowsExtra() {
  if (process.platform !== "win32") return;
  // Cursor on Windows may store in AppData
  const cursorAppData = path.join(process.env.APPDATA || "", "Cursor", "User");
  if (isDir(cursorAppData)) {
    results.push(...walk(cursorAppData, (f, name) => {
      if (!f.includes("agent-transcripts")) return false;
      return name.endsWith(".txt") || name.endsWith(".jsonl");
    }));
  }
}

// ── Run scanners ──────────────────────────────────────────────────────

const scanners = {
  "claude-code": scanClaudeCode,
  "cursor": scanCursor,
  "codex": scanCodex,
  "openclaw": scanOpenclaw,
  "antigravity": scanAntigravity,
  "windsurf": scanWindsurf,
  "chatgpt": scanChatgpt,
  "gemini-cli": scanGeminiCli,
  "trae": scanTrae,
  "opencode": scanOpencode,
};

for (const [name, fn] of Object.entries(scanners)) {
  if (shouldScan(name)) {
    try { fn(); } catch { /* scanner failed, continue */ }
  }
}

// Windows-specific extra locations
try { scanWindowsExtra(); } catch {}

// ── Deduplicate ───────────────────────────────────────────────────────

const unique = [...new Set(results.map(f => path.resolve(f)))];

// ── Filter to last N days ─────────────────────────────────────────────

const filtered = unique.filter(f => {
  try {
    const stat = fs.statSync(f);
    return stat.mtimeMs >= cutoffMs;
  } catch { return false; }
});

// ── Write output ──────────────────────────────────────────────────────

fs.writeFileSync(sessionListPath, filtered.join("\n") + (filtered.length ? "\n" : ""));

console.log(sessionListPath);
process.stderr.write(`Found ${filtered.length} session files (last ${DAYS} days)\n`);
