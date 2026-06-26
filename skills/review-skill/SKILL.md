---
name: review-skill
description: Reviews an agent skill's SKILL.md against authoring best practices and reports findings by severity. Use when the user asks to review, audit, or check the quality of an agent skill or a SKILL.md.
---

# Review a skill

Review the target agent skill against the best practices, then report findings.

The argument identifies the target skill. Resolve it to the skill directory:

- A `SKILL.md` file path (e.g. `skills/pr/SKILL.md`) → use its parent directory.
- A directory path (e.g. `skills/pr`) → use it directly.
- A bare skill name (e.g. `pr`) → locate its directory, e.g. `find . -type d -name <name>` or check `skills/<name>`. If it matches more than one or none, ask the user which skill to review.

Then read every file under that directory, with `SKILL.md` as the primary subject.

## Workflow

1. Get the best practices (see below).
2. Read the target skill's files.
3. Evaluate the skill against the best practices and the checklist below.
4. Report findings using the output format below.

## Get the best practices

1. Pull the repository:

   ```sh
   test -d "$(ghq root)/github.com/agentskills/agentskills" || ghq get agentskills/agentskills
   git -C "$(ghq root)/github.com/agentskills/agentskills" pull
   ```

   If the command is denied, tell the user.

2. Read the first best practice in full: `~/repos/src/github.com/agentskills/agentskills/docs/skill-creation/best-practices.mdx`

   If the file doesn't exist, tell the user.

3. Download the second best practice, then read the downloaded file in full. Don't use the `WebFetch` tool — it doesn't necessarily read all the content.

   ```sh
   tempdir=$(mktemp -d)
   temppath=${tempdir}/best-practices.md
   curl -Lq -o "$temppath" https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices.md
   echo "$temppath"
   ```

   If the URL is 404 or the download is denied, tell the user.

## What to check

Compare the skill against the best practices. Pay particular attention to:

- **`description`**: includes both *what* the skill does and *when* to use it, written in third person, with discovery keywords.
- **`name`**: valid (≤64 chars, lowercase/numbers/hyphens, no reserved words). A short, well-understood abbreviation is fine — do not force a long gerund name at the cost of invocation convenience.
- **Conciseness**: adds only what the agent wouldn't already know; no filler.
- **Degrees of freedom**: fragile/exact steps are prescriptive; flexible steps are not over-specified.
- **Workflow**: steps are clear, correctly ordered, and numbered without gaps.
- **Progressive disclosure**: `SKILL.md` under ~500 lines; references one level deep; large content split into separate files.
- **Consistency**: one term per concept; consistent capitalization.
- **Output templates / gotchas**: present where they add value.

## Output format

Group findings by severity and end with prioritized actions:

```markdown
## Review: <skill path>

### 🔴 High
- <finding, with current vs. suggested>

### 🟡 Medium
- <finding>

### 🟢 Low
- <finding>

### Good points
- <what the skill already does well>

### Recommended actions (by priority)
1. <most impactful fix first>
```

After reporting, offer to create a revised `SKILL.md`.
