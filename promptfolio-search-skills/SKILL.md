---
name: promptfolio-search-skills
description: Search the promptfolio platform for reusable AI interaction techniques and skills. Find proven prompting patterns, problem-solving tricks, and workflow techniques shared by other users.
allowed-tools: Bash, Read, AskUserQuestion
---


# promptfolio-search-skills

You are helping the user search the promptfolio platform for reusable skills — proven techniques for interacting with AI agents that other users have developed and shared.

## Step 0: Auto-Update

Before anything else, run the auto-updater to ensure you have the latest skill files and data formats:

```bash
bash ~/.promptfolio/update-check.sh
```

- If output is `UPDATED v...` → tell the user: **"Skills updated to v{version}."** Then **re-read this SKILL.md file** since it may have changed, and continue from Step 1.
- If output is `UP_TO_DATE v...` → continue silently.
- If output is `OFFLINE v...` → tell the user: **"Could not check for updates (offline). Running with local v{version}."** Continue normally.

Then continue with Step 1 normally.

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
- `/promptfolio-search-skills how to debug failing CI pipelines with AI`
- `/promptfolio-search-skills structured requirement description techniques`
- `/promptfolio-search-skills prompt templates for code review`

If no arguments provided, ask the user what kind of skill or technique they're looking for using AskUserQuestion.

## Step 3: Execute Search

```bash
API_TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.promptfolio/config.json'))['api_token'])")
API_URL=$(python3 -c "import json; print(json.load(open('$HOME/.promptfolio/config.json'))['api_url'])")

curl -s -X POST "$API_URL/api/search/skills" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"THE_SEARCH_QUERY","limit":10}'
```

## Step 4: Present Results

Format each skill result clearly. The API returns `skill`, `author`, `shareSlug`, and `similarity` for each result.

For each skill:

```
### [skill.title]
**Match:** [similarity as percentage, e.g. 87%] · **Category:** [skill.category] · **Proficiency:** [skill.proficiency]
**By:** [author.name] ([API_URL]/p/[shareSlug])

[skill.skillContent — the complete skill document including When to Use, How It Works, Examples, and Why It Works]

---
```

If `skillContent` is null or empty for a result, show `skill.description` only and note that the full document is not yet available.

**Similarity display:** Convert the raw similarity float (0-1) to a percentage. Only show results with similarity > 30%.

If no results found:
- Suggest broadening or rephrasing the search terms
- Example: "No matches for 'Kubernetes RBAC automation'. Try 'Kubernetes debugging' or 'infrastructure automation'?"

## Step 5: Follow-up Actions

After presenting results, offer these options via AskUserQuestion:

1. **Leave a thank-you note** — "Found a skill useful? Leave the author a thank-you note."
2. **Find the author** — "Want to see the full profile of any skill author?"
3. **Show more results** — "Want to see more results or try a different search?"
4. **Done** — Exit

### If leaving a thank-you note:

First, ask which skill they want to thank, and what they want to say (1-1000 chars). Then record the skill call and submit the thank-you note:

```bash
API_TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.promptfolio/config.json'))['api_token'])")
API_URL=$(python3 -c "import json; print(json.load(open('$HOME/.promptfolio/config.json'))['api_url'])")

# Step 1: Record the skill call (required before thank-you)
curl -s -o /dev/null -X POST "$API_URL/api/plaza/skills/SKILL_ID/call" \
  -H "Authorization: Bearer $API_TOKEN" -H "Content-Type: application/json" -d '{}'

# Step 2: Submit the thank-you note
curl -s -X POST "$API_URL/api/plaza/skills/SKILL_ID/thank-you" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":"THE_MESSAGE","isAiGenerated":false,"taskCompleted":true}'
```

Replace `SKILL_ID` with the skill's `id` from search results. Handle errors:
- `self_thank_forbidden`: "You can't thank your own skill."
- `duplicate_thank_you`: "You already left a thank-you note for this skill."

Confirm: "Thank-you note sent to [author.name] for '[skill.title]'!"

### If showing more results:

Re-run the search with `limit:20` (or higher, up to 50), or let the user refine their query.

### If finding the author:

Ask which author, then show their profile URL: `[API_URL]/p/[shareSlug]`
