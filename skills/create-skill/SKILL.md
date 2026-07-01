---
name: create-skill
description: Creates agent skills from an OSS project's documentation. Splits the docs other than README.md into per-topic skills/<oss>-<topic>/*.md files, and has README.md and SKILL.md reference them, so human-facing docs and skills share the same body and avoid double maintenance. Use when turning an OSS project's documentation into skills, or restructuring existing docs into a skill-based layout.
---

## Overview

Generate skills from an OSS project's documentation.
The goal is to share the body between the human-facing docs and the agent-facing docs (skills) to reduce double maintenance.
To do this, restructure the existing documentation as part of creating the skills.

## Assumptions

Assume the existing documentation is structured so that the repository-root README.md or INSTALL.md references other docs such as docs/*.md.

## Goal

Modify the existing documentation and create the skills so the final layout looks like this:

```
README.md # Content you want humans to read first (a concise description of the OSS, catchy info, screenshot, Features, Getting Started, etc.) plus only a summary of each topic; link to skills/*/*.md for the details
skills/
  <oss>-<topic>/ # Split skills per topic
    SKILL.md # Refers to *.md for the details
    *.md # Documentation shared between the docs and the skill
  ...
```

Name *.md `reference.md` when it fits in a single file.
When splitting it into multiple files, use snake_case file names based on the content.

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

1. Explore the repository's documentation. Understand which files contain which docs.
1. Decide which skills to create (how to split them).
    1. Make the skill's name and description let the agent select the right skill. Avoid using similar keywords across multiple skills.
    1. Include keywords in the SKILL.md description that identify what the skill covers.
    1. The granularity of the skills needs discussion with the user. Confirm with the user.
1. Move the docs other than README.md into skills/*/*.md, and fix the links from README.md.
1. Create skills/*/SKILL.md, and have it refer to *.md for the details.
