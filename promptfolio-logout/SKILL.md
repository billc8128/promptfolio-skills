---
name: promptfolio-logout
description: Sign out this CLI device from promptfolio by clearing local credentials, with optional remote API token revocation.
allowed-tools: Bash, Read
---

# promptfolio-logout

You are helping the user log out of promptfolio from their current CLI device.

## Behavior

- Default: remove local credentials only (`~/.promptfolio/config.json`).
- Optional `--revoke`: also revoke the current API token on the server before local cleanup.

## Step 0: Auto-Update

Before anything else, run the auto-updater to ensure you have the latest skill files and data formats:

```bash
bash ~/.promptfolio/update-check.sh
```

- If output is `UPDATED v...` → tell the user: **"Skills updated to v{version}."** Then **re-read this SKILL.md file** since it may have changed, and continue from Step 1.
- If output is `UP_TO_DATE v...` → continue silently.
- If output is `OFFLINE v...` → tell the user: **"Could not check for updates (offline). Running with local v{version}."** Continue normally.

Then continue with Step 1 normally.

## Step 1: Read local config

Check if local config exists:

```bash
if [ -f ~/.promptfolio/config.json ]; then
  cat ~/.promptfolio/config.json
else
  echo "NO_CONFIG"
fi
```

If config is missing, reply: "Already logged out on this device."

## Step 2: Optional remote revoke (`--revoke`)

If the user includes `--revoke`, revoke the current API token:

```bash
API_TOKEN=$(cat ~/.promptfolio/config.json | grep api_token | cut -d'"' -f4)
API_URL=$(cat ~/.promptfolio/config.json | grep api_url | cut -d'"' -f4)

curl -s -X POST "$API_URL/api/auth/logout" \
  -H "Authorization: Bearer $API_TOKEN"
```

If revoke fails, continue local logout and tell the user: "Local logout completed, but remote token revoke failed. You can retry with /promptfolio-logout --revoke."

## Step 3: Local logout

Delete local credentials:

```bash
rm -f ~/.promptfolio/config.json
```

## Step 4: Confirm outcome

Return a concise status:

- Without `--revoke`: "Logged out on this device. Other devices stay signed in."
- With `--revoke` success: "Logged out on this device and revoked this device token."
- With `--revoke` failure: "Logged out on this device, but remote revoke failed."
