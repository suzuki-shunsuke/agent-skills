---
name: create-skill
description: Creates agent skills from an OSS project's documentation. Splits the documentation other than README.md into per-topic skills/<oss>-<topic>/*.md files, and has README.md and SKILL.md reference them, so human-facing documentation and skills share the same body and avoid double maintenance. Use when turning an OSS project's documentation into skills, or restructuring existing documentation into a skill-based layout.
---

## Overview

This skill restructures a project's existing documentation while creating skills, so the human-facing documentation and the skills share one body instead of being maintained twice.

## Assumptions

Assume the existing documentation is structured so that the repository-root README.md or INSTALL.md references other documentation such as docs/*.md.

## Goal

Modify the existing documentation and create the skills so the final layout looks like this:

```
README.md # Content you want humans to read first (a concise description of the OSS, catchy info, screenshot, Features, Getting Started, etc.) plus only a summary of each topic; link to skills/*/*.md for the details
skills/
  <oss>-<topic>/ # Split skills per topic
    SKILL.md # Refers to *.md for the details
    *.md # Documentation shared between README.md and SKILL.md
  ...
```

Name *.md `reference.md` when it fits in a single file.
When splitting it into multiple files, use snake_case file names based on the content.
When a SKILL.md references multiple `*.md` files, annotate each link with when to read it (for example, "Read `config.md` to change configuration") so the agent loads each file on demand instead of all at once.

## Example

https://github.com/suzuki-shunsuke/ghtkn/tree/v0.3.3

```
README.md # refers to skills/*/reference.md
skills/ # 9 skills
  ghtkn-backend/
    SKILL.md # refers to reference.md
    reference.md
  ghtkn-configuration/
    SKILL.md # refers to reference.md
    reference.md
  ...
```

## Workflow

1. Explore the repository's documentation. Understand which files contain which documentation.
2. Decide which skills to create (how to split them).
   1. Write each name and description so the agent can select the right skill: state both what the skill does and when to use it, include distinguishing keywords, and avoid reusing similar keywords across skills.
   2. Discuss the granularity of the skills with the user and confirm before proceeding.
3. Move the documentation other than README.md into skills/*/*.md, and fix the links from README.md.
4. Create skills/*/SKILL.md, and have it refer to *.md for the details.
