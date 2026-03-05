#!/usr/bin/env python3
"""
Compute session statistics and extract activity heat map data.

Reads the session list from $SESSION_LIST (one path per line),
then in a single pass computes:
  - Per-source session counts and token estimates
  - Per-day activity heat map data → _pf_parts/activity.json
  - Stdout summary for the agent to present

Environment:
  SESSION_LIST          – path to file listing session paths
  PF_CONTEXT_WINDOW     – context window size (default 200000)
  PF_MAX_READ_BYTES     – max bytes to read per file (default 8MB)
  PF_TOKEN_CACHE_PATH   – token estimate cache (default /tmp/promptfolio-token-estimate-cache.json)
"""

import os
import json
import re
import hashlib
from collections import defaultdict
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────

CONTEXT_WINDOW = int(os.environ.get("PF_CONTEXT_WINDOW", "200000"))
MAX_READ_BYTES = int(os.environ.get("PF_MAX_READ_BYTES", str(8 * 1024 * 1024)))
CACHE_PATH = os.environ.get(
    "PF_TOKEN_CACHE_PATH", "/tmp/promptfolio-token-estimate-cache.json"
)

# ── Load session list ─────────────────────────────────────────────────

session_list_path = os.environ.get("SESSION_LIST", "")
if not session_list_path:
    print("ERROR: SESSION_LIST environment variable not set")
    raise SystemExit(1)

with open(session_list_path, "r") as f:
    sessions = [l.strip() for l in f if l.strip()]

# ── Classifier ────────────────────────────────────────────────────────


def classify(path):
    if "/.claude/" in path:
        return "claude-code"
    if "/.cursor/" in path:
        return "cursor"
    if "/.codex/" in path:
        return "codex"
    if "/.openclaw/" in path:
        return "openclaw"
    if "/Antigravity" in path or "/.gemini/antigravity" in path:
        return "antigravity"
    if "/.codeium/" in path or "/.windsurf/" in path or "/Windsurf" in path:
        return "windsurf"
    if "chatgpt" in path.lower() or "conversations" in os.path.basename(path).lower():
        return "chatgpt"
    return "other"


# ── Cache ─────────────────────────────────────────────────────────────


def load_cache(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
            return obj if isinstance(obj, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(path, cache):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, path)


def fingerprint(path, size, mtime):
    base = f"{path}|{size}|{mtime}".encode("utf-8", errors="replace")
    return hashlib.sha256(base).hexdigest()


# ── Tokenizer ─────────────────────────────────────────────────────────

try:
    import tiktoken

    _enc = tiktoken.get_encoding("cl100k_base")
    TOKENIZER_NAME = "tiktoken(cl100k_base)"

    def count_tokens(text):
        return len(_enc.encode(text))

except Exception:
    TOKENIZER_NAME = "regex-fallback"
    _token_re = re.compile(r"\w+|[^\w\s]", re.UNICODE)

    def count_tokens(text):
        return len(_token_re.findall(text))


# ── Text extraction ───────────────────────────────────────────────────


def safe_read_text(path, max_bytes=MAX_READ_BYTES):
    with open(path, "rb") as f:
        data = f.read(max_bytes + 1)
    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]
    text = data.decode("utf-8", errors="replace")
    return text, truncated, len(data)


def extract_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(filter(None, (extract_text(v) for v in value)))
    if isinstance(value, dict):
        parts = []
        for key in ("text", "content", "value", "input", "output", "prompt", "completion"):
            if key in value:
                parts.append(extract_text(value.get(key)))
        if not parts:
            for v in value.values():
                parts.append(extract_text(v))
        return "\n".join(filter(None, parts))
    return ""


def normalize_role(role):
    if role is None:
        return None
    role = str(role).lower()
    if role in ("assistant", "model", "ai"):
        return "assistant"
    if role in ("user", "human"):
        return "user"
    if role in ("system", "developer"):
        return "system"
    if role in ("tool", "function"):
        return "tool"
    return None


def extract_message_from_obj(obj):
    role = normalize_role(obj.get("role") or obj.get("type"))
    text = extract_text(obj.get("content"))

    if not text and isinstance(obj.get("message"), dict):
        msg = obj["message"]
        if role is None:
            role = normalize_role(msg.get("role") or msg.get("type"))
        text = extract_text(msg.get("content") or msg.get("text"))

    if not text:
        text = extract_text(obj.get("text") or obj.get("parts") or obj.get("body"))

    if role and text:
        return [(role, text)]
    return []


def iter_messages(value):
    out = []
    if isinstance(value, dict):
        out.extend(extract_message_from_obj(value))
        for key in ("messages", "conversation", "items", "turns", "mapping"):
            child = value.get(key)
            if isinstance(child, dict):
                for v in child.values():
                    out.extend(iter_messages(v))
            elif isinstance(child, list):
                for v in child:
                    out.extend(iter_messages(v))
    elif isinstance(value, list):
        for v in value:
            out.extend(iter_messages(v))
    return out


def parse_messages(path, size):
    ext = os.path.splitext(path)[1].lower()
    messages = []

    if ext == ".jsonl":
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    messages.extend(iter_messages(obj))
        except OSError:
            return []
        return messages

    if ext == ".json":
        if size > 20 * 1024 * 1024:
            return []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                obj = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []
        return iter_messages(obj)

    if ext == ".txt":
        try:
            text, _, _ = safe_read_text(path)
        except OSError:
            return []
        for m in re.finditer(
            r"(?im)^(user|assistant|system|tool)\s*[:：]\s*(.+)$", text
        ):
            role = normalize_role(m.group(1))
            content = m.group(2).strip()
            if role and content:
                messages.append((role, content))
        return messages

    return []


# ── Token estimation ──────────────────────────────────────────────────


def estimate_tokens_from_messages(messages):
    if not messages:
        return 0, 0

    context_tokens = 0
    total_billed = 0
    assistant_turns = 0

    for role, text in messages:
        tok = count_tokens(text)
        if tok <= 0:
            continue
        if role == "assistant":
            total_billed += min(context_tokens, CONTEXT_WINDOW)
            total_billed += tok
            assistant_turns += 1
            context_tokens = min(context_tokens + tok, CONTEXT_WINDOW)
        else:
            context_tokens = min(context_tokens + tok, CONTEXT_WINDOW)

    if assistant_turns == 0:
        return sum(count_tokens(t) for _, t in messages), 0

    return total_billed, assistant_turns


def estimate_tokens_from_text(path, size):
    try:
        text, truncated, used_bytes = safe_read_text(path)
    except OSError:
        return 0
    if not text:
        return 0
    base = count_tokens(text)
    if truncated and used_bytes > 0:
        base = int(base * (size / used_bytes))
    return base


def extract_claude_code_tokens(path):
    total = 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("type") == "assistant":
                        msg = obj.get("message", {})
                        if isinstance(msg, dict) and "usage" in msg:
                            u = msg["usage"]
                            total += u.get("input_tokens", 0)
                            total += u.get("output_tokens", 0)
                            total += u.get("cache_creation_input_tokens", 0)
                            total += u.get("cache_read_input_tokens", 0)
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError:
        return 0
    return total


# ── Timestamp extraction (for activity heat map) ─────────────────────


def extract_timestamps(path):
    timestamps = []
    ext = os.path.splitext(path)[1].lower()

    if ext == ".jsonl":
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = obj.get("timestamp")
                    if ts:
                        if isinstance(ts, str):
                            try:
                                dt = datetime.fromisoformat(
                                    ts.replace("Z", "+00:00")
                                )
                                timestamps.append(dt)
                            except (ValueError, TypeError):
                                pass
                        elif isinstance(ts, (int, float)):
                            try:
                                if ts > 1e12:
                                    ts = ts / 1000
                                timestamps.append(
                                    datetime.fromtimestamp(ts, tz=timezone.utc)
                                )
                            except (ValueError, OSError):
                                pass
                    ts2 = obj.get("ts")
                    if ts2 and isinstance(ts2, (int, float)):
                        try:
                            if ts2 > 1e12:
                                ts2 = ts2 / 1000
                            timestamps.append(
                                datetime.fromtimestamp(ts2, tz=timezone.utc)
                            )
                        except (ValueError, OSError):
                            pass
        except OSError:
            pass

    if not timestamps:
        try:
            mtime = os.path.getmtime(path)
            timestamps.append(datetime.fromtimestamp(mtime, tz=timezone.utc))
        except OSError:
            pass

    return timestamps


# ══════════════════════════════════════════════════════════════════════
# Main: single pass over all sessions
# ══════════════════════════════════════════════════════════════════════

cache = load_cache(CACHE_PATH)
next_cache = {}

by_source = defaultdict(
    lambda: {
        "count": 0,
        "tokens": 0,
        "bytes": 0,
        "exact": 0,
        "replayEstimate": 0,
        "tokenizerEstimate": 0,
        "bytesEstimate": 0,
        "cacheHits": 0,
    }
)
total_tokens = 0
calibration_pairs = []
replay_adjust = []

# Activity heat map data
try:
    local_tz = datetime.now().astimezone().tzinfo
except Exception:
    local_tz = timezone.utc

activity_days = defaultdict(
    lambda: {
        "sessions": 0,
        "tokens": 0,
        "earliest": None,
        "latest": None,
        "timestamps": [],
    }
)

for path in sessions:
    try:
        size = os.path.getsize(path)
        mtime = int(os.path.getmtime(path))
    except OSError:
        continue

    source = classify(path)
    by_source[source]["count"] += 1
    by_source[source]["bytes"] += size

    # ── Token estimation ──────────────────────────────────────────

    fp = fingerprint(path, size, mtime)
    cached = cache.get(path)
    if (
        isinstance(cached, dict)
        and cached.get("fp") == fp
        and isinstance(cached.get("tokens"), int)
    ):
        est = max(0, int(cached["tokens"]))
        method = cached.get("method", "cache")
        total_tokens += est
        by_source[source]["tokens"] += est
        by_source[source]["cacheHits"] += 1
        if method == "exact":
            by_source[source]["exact"] += 1
            if source == "claude-code":
                raw_replay = cached.get("rawReplay")
                if isinstance(raw_replay, int) and raw_replay > 0:
                    calibration_pairs.append((est, raw_replay))
        elif method == "replay":
            by_source[source]["replayEstimate"] += 1
            if source != "claude-code":
                replay_adjust.append((source, est))
        elif method == "tokenizer":
            by_source[source]["tokenizerEstimate"] += 1
        else:
            by_source[source]["bytesEstimate"] += 1
        next_cache[path] = cached
    else:
        if source == "claude-code":
            exact = extract_claude_code_tokens(path)
            if exact > 0:
                est = exact
                method = "exact"
                messages = parse_messages(path, size)
                replay_est, turns = estimate_tokens_from_messages(messages)
                raw_replay = replay_est if replay_est > 0 and turns > 0 else 0
                if raw_replay > 0:
                    calibration_pairs.append((exact, raw_replay))
                next_cache[path] = {
                    "fp": fp,
                    "tokens": int(est),
                    "method": method,
                    "rawReplay": raw_replay,
                }
                by_source[source]["tokens"] += est
                total_tokens += est
                by_source[source]["exact"] += 1
            else:
                messages = parse_messages(path, size)
                replay_est, turns = estimate_tokens_from_messages(messages)
                if replay_est > 0 and turns > 0:
                    est = replay_est
                    method = "replay"
                else:
                    tok_est = estimate_tokens_from_text(path, size)
                    if tok_est > 0:
                        est = tok_est
                        method = "tokenizer"
                    else:
                        est = size // 3
                        method = "bytes"
                by_source[source]["tokens"] += est
                total_tokens += est
                if method == "replay":
                    by_source[source]["replayEstimate"] += 1
                    replay_adjust.append((source, est))
                elif method == "tokenizer":
                    by_source[source]["tokenizerEstimate"] += 1
                else:
                    by_source[source]["bytesEstimate"] += 1
                next_cache[path] = {"fp": fp, "tokens": int(est), "method": method}
        else:
            messages = parse_messages(path, size)
            replay_est, turns = estimate_tokens_from_messages(messages)
            if replay_est > 0 and turns > 0:
                est = replay_est
                method = "replay"
            else:
                tok_est = estimate_tokens_from_text(path, size)
                if tok_est > 0:
                    est = tok_est
                    method = "tokenizer"
                else:
                    est = size // 3
                    method = "bytes"

            by_source[source]["tokens"] += est
            total_tokens += est
            if method == "exact":
                by_source[source]["exact"] += 1
            elif method == "replay":
                by_source[source]["replayEstimate"] += 1
                if source != "claude-code":
                    replay_adjust.append((source, est))
            elif method == "tokenizer":
                by_source[source]["tokenizerEstimate"] += 1
            else:
                by_source[source]["bytesEstimate"] += 1
            next_cache[path] = {"fp": fp, "tokens": int(est), "method": method}

    # ── Activity timestamps ───────────────────────────────────────

    timestamps = extract_timestamps(path)
    if timestamps:
        local_timestamps = []
        for ts_dt in timestamps:
            try:
                lt = ts_dt.astimezone(local_tz)
                local_timestamps.append(lt)
            except Exception:
                local_timestamps.append(ts_dt)

        if local_timestamps:
            # Group timestamps by their actual calendar day, not session start
            ts_by_day = defaultdict(list)
            for lt in local_timestamps:
                ts_by_day[lt.strftime("%Y-%m-%d")].append(lt)

            num_days = len(ts_by_day)
            tokens_per_day = est // num_days if num_days > 0 else est

            for day_key, day_ts in ts_by_day.items():
                day = activity_days[day_key]
                day["sessions"] += 1
                day["tokens"] += tokens_per_day
                day["timestamps"].extend(day_ts)
                day_earliest = min(day_ts)
                day_latest = max(day_ts)
                if day["earliest"] is None or day_earliest < day["earliest"]:
                    day["earliest"] = day_earliest
                if day["latest"] is None or day_latest > day["latest"]:
                    day["latest"] = day_latest

save_cache(CACHE_PATH, next_cache)

# ── Overhead calibration ──────────────────────────────────────────────

if calibration_pairs:
    sum_exact = sum(e for e, _ in calibration_pairs)
    sum_replay = sum(r for _, r in calibration_pairs)
    overhead_ratio = sum_exact / sum_replay if sum_replay > 0 else 1.0
    overhead_ratio = max(1.0, min(overhead_ratio, 5.0))
else:
    overhead_ratio = 1.0

if overhead_ratio > 1.0 and replay_adjust:
    for source, raw in replay_adjust:
        adjustment = int(raw * (overhead_ratio - 1.0))
        by_source[source]["tokens"] += adjustment
        total_tokens += adjustment

# ── Build activity heat map ───────────────────────────────────────────

activity_result = {"days": [], "summary": {}}
act_total_sessions = 0
most_active_day = None
most_active_sessions = 0
latest_night = None
latest_night_date = None
latest_night_time = None
longest_day = None
longest_hours = 0

for day_key in sorted(activity_days.keys()):
    d = activity_days[day_key]
    all_ts = d["timestamps"]
    if not all_ts:
        continue

    earliest = min(all_ts)
    latest = max(all_ts)
    active_hours = round((latest - earliest).total_seconds() / 3600, 1)
    latest_time = latest.strftime("%H:%M")

    entry = {
        "date": day_key,
        "sessions": d["sessions"],
        "tokens": d["tokens"],
        "activeHours": active_hours,
        "latestTime": latest_time,
    }
    activity_result["days"].append(entry)

    act_total_sessions += d["sessions"]

    if d["sessions"] > most_active_sessions:
        most_active_sessions = d["sessions"]
        most_active_day = day_key

    hour = latest.hour
    late_score = hour if hour >= 18 else (hour + 24 if hour < 6 else 0)
    if latest_night is None or late_score > latest_night:
        latest_night = late_score
        latest_night_date = day_key
        latest_night_time = latest_time

    if active_hours > longest_hours:
        longest_hours = active_hours
        longest_day = day_key

activity_result["summary"] = {
    "totalDays": len(activity_result["days"]),
    "totalSessions": act_total_sessions,
    "totalTokens": total_tokens,
    "mostActiveDay": (
        {"date": most_active_day, "sessions": most_active_sessions}
        if most_active_day
        else None
    ),
    "latestNight": (
        {"date": latest_night_date, "time": latest_night_time}
        if latest_night_date
        else None
    ),
    "longestDay": (
        {"date": longest_day, "hours": longest_hours} if longest_day else None
    ),
}

# ── Save activity.json & meta.json ────────────────────────────────────

os.makedirs("_pf_parts", exist_ok=True)
with open("_pf_parts/activity.json", "w") as f:
    json.dump(activity_result, f, ensure_ascii=False, default=str)

with open("_pf_parts/meta.json", "w") as f:
    json.dump({"sessionsAnalyzed": len(sessions), "totalTokens": total_tokens}, f)

# ── Print summary ─────────────────────────────────────────────────────

print(f"=== Session Discovery ===")
print(f"Total sessions: {len(sessions)}")
print(f"Total tokens: {total_tokens:,}")
print(f"Tokenizer: {TOKENIZER_NAME}")
print(
    f"Overhead ratio: {overhead_ratio:.2f}x "
    f"(from {len(calibration_pairs)} claude-code calibration sessions)"
)
print()
for source in sorted(by_source):
    info = by_source[source]
    label = (
        f"exact={info['exact']}, replay_est={info['replayEstimate']}, "
        f"tokenizer_est={info['tokenizerEstimate']}, bytes_est={info['bytesEstimate']}, "
        f"cache_hits={info['cacheHits']}"
    )
    print(f"  {source}: {info['count']} sessions, {info['tokens']:,} tokens ({label})")

print()
print(f"=== Activity Heat Map ===")
print(f"Days with activity: {len(activity_result['days'])}")
if most_active_day:
    print(f"Most active day: {most_active_day} ({most_active_sessions} sessions)")
if latest_night_date:
    print(f"Latest night: {latest_night_date} until {latest_night_time}")
if longest_day:
    print(f"Longest day: {longest_day} ({longest_hours}h)")
