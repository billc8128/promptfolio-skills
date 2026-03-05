---
name: promptfolio-search-people
description: Search the promptfolio platform for people with specific skills or expertise. Find collaborators, mentors, or experts based on their AI-verified skill profiles.
allowed-tools: Bash, Read, AskUserQuestion
---


# promptfolio-search-people

You are helping the user search the promptfolio platform for people with specific skills or expertise.

## Step 0: Version Check

Before anything else, check if a newer version is available:

```bash
LOCAL_V=$(cat ~/.promptfolio/VERSION 2>/dev/null || echo "0")
REMOTE_V=$(curl -sfL --max-time 3 https://promptfolio.club/skills/VERSION 2>/dev/null || echo "$LOCAL_V")
if [ "$LOCAL_V" != "$REMOTE_V" ]; then
  echo "UPDATE_AVAILABLE"
else
  echo "UP_TO_DATE"
fi
```

If `UPDATE_AVAILABLE`, show this before proceeding (do NOT block):

> **Update available!** Run `curl -sfL promptfolio.club/install.sh | bash` to update.

Then continue with Step 1.

## Step 1: Authentication

Validate the existing token first:
```bash
if [ -f ~/.promptfolio/config.json ]; then
  API_TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.promptfolio/config.json'))['api_token'])")
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $API_TOKEN" https://promptfolio.club/api/profile/me || true)
  echo "HTTP_CODE=$HTTP_CODE"
fi
```

If HTTP 200, proceed to Step 2. If config missing or HTTP is not 200, run device auth:

```bash
bash "SKILL_DIR/../scripts/device-auth.sh"
```

Replace `SKILL_DIR` with the directory containing this SKILL.md file. The script handles everything: requesting a device code, opening the browser, polling until authorized, and saving `~/.promptfolio/config.json`.

**IMPORTANT:** Run the script as-is. Do NOT reimplement the auth flow yourself.

If the script fails, tell the user authorization timed out and to try again.

## Step 2: Parse the Query

The user's search query comes from the arguments. Examples:
- `/promptfolio-search-people someone good at building AI agents`
- `/promptfolio-search-people Rust developer with systems programming`
- `/promptfolio-search-people product manager who understands growth`

If no arguments provided, ask the user what they're looking for using AskUserQuestion.

## Step 3: Execute Search

```bash
API_TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.promptfolio/config.json'))['api_token'])")
API_URL=$(python3 -c "import json; print(json.load(open('$HOME/.promptfolio/config.json'))['api_url'])")

curl -s -X POST "$API_URL/api/search/people" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"THE_SEARCH_QUERY","limit":10}'
```

## Step 4: Present Results

The API returns `user`, `profile`, `matchedSkills`, and `similarity` for each result. Format clearly:

For each person:

```
### [user.name]  ·  Match [similarity as percentage]%
[profile.thinkingStyle — if available, this is their AI-generated cognitive portrait]
[profile.summary — fallback if thinkingStyle is null]

**Matching Skills:**
- [skill.title] ([skill.proficiency]) — [skill.description]
- [skill.title] ([skill.proficiency]) — [skill.description]

**Domains:** [profile.topDomains joined with " · "]
**Profile:** [API_URL]/p/[profile.shareSlug]
```

**Similarity display:** Convert the raw similarity float (0-1) to a percentage. Only show results with similarity > 30%.

If `thinkingStyle` and `summary` are both null, omit the portrait line.

If no results found:
- Suggest broadening the search terms
- Try rephrasing: "No exact matches for 'Kubernetes security expert'. Try 'DevOps security' or 'Kubernetes' separately?"

## Step 5: Follow-up Actions

After presenting results, offer these options via AskUserQuestion:

1. **Connect with someone** — "Send a connection request to someone in the results."
2. **View their skills** — "Want to search for a specific person's reusable techniques? Try `/promptfolio-search-skills`."
3. **Show more results** — "Want to see more results or try a different search?"
4. **Done** — Exit

### If connecting:

Ask which person, and optionally a short message:
```bash
API_TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.promptfolio/config.json'))['api_token'])")
API_URL=$(python3 -c "import json; print(json.load(open('$HOME/.promptfolio/config.json'))['api_url'])")

curl -s -X POST "$API_URL/api/connections" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"toUserId":"USER_UUID","message":"OPTIONAL_MESSAGE"}'
```

Replace `USER_UUID` with `user.id` from the search results. Handle errors:
- `400` "Cannot connect to yourself": "That's you!"
- `409` "Connection already exists": "You already have a connection with [name]."

Confirm: "Connection request sent to [name]! They'll be notified on the promptfolio platform."

### If showing more results:

Re-run the search with `limit:20` (or higher, up to 50), or let the user refine their query.
