# PR Explanation as HTML

Normally write the PR Explanation in Markdown (`tasks/<task id>/pr-explanation.md`). Use this HTML only for pull requests whose diff is too long to read comfortably in Markdown.

Write the PR Explanation as a spec (JSON) and turn it into HTML with `scripts/render-pr-explanation.py`.
The HTML puts the code (diff) on the left and the explanation on the right. Each line range in the explanation gets a numbered chip (① L189-193), and the same range on the code side gets a badge with the same number and a vertical bar.

## Generating

`<skill dir>` is the directory containing this skill's SKILL.md.

```sh
git diff <base>...<head> > /tmp/pr.diff   # or: gh pr diff <number> > /tmp/pr.diff
python3 -I <skill dir>/scripts/render-pr-explanation.py \
  --spec tasks/<task id>/pr-explanation.json \
  --diff /tmp/pr.diff \
  --out tasks/<task id>/pr-explanation.html
```

Even if you do not explain test files, pass the diff as is. Only the files and lines specified in the spec are shown.

If a marker points to a line not shown in its step, the script stops with an error. Fix the marker or the `code` range.

## Viewing

```sh
open tasks/<task id>/pr-explanation.html
```

Take the human's questions in conversation with the agent, and fix the spec and regenerate if needed.

Do not add scripts or external resources to the HTML. It must be readable as a static page.
To change how the HTML looks, fix the script instead of hand-writing HTML per pull request.

## Spec Format

```json
{
  "title": "Pull request title",
  "eyebrow": "Pull request · owner/repo#123 · PR Explanation",
  "url": "https://github.com/owner/repo/pull/123",
  "repo": "owner/repo",
  "head_sha": "<commit SHA of the pull request's head>",
  "meta": ["12 files", "+1142 -68", "head-branch → base-branch"],
  "summary": "TL;DR (Markdown)",
  "overview": [
    {"module": "pkg/foo", "change": "Summary of the change (Markdown)"}
  ],
  "attention": [
    {"title": "Heading of a place to look at", "body": "Details (Markdown)", "warn": true}
  ],
  "tests": {
    "covered": ["What is confirmed"],
    "not_covered": ["What is not confirmed"]
  },
  "steps": [
    {
      "module": "pkg/foo",
      "title": "Step heading",
      "code": [
        {"file": "pkg/foo/foo.go", "lines": [40, 80]},
        {"file": "pkg/foo/bar.go"}
      ],
      "body": "[[45-52]] Explanation (Markdown). Other files can be pointed to like [[bar.go:10]]"
    }
  ]
}
```

- If `repo` and `head_sha` are set, a GitHub link pinned to the commit SHA is added under each step
- `overview` / `attention` / `tests` are optional. Omitted sections are not shown
- Places to look at with `warn: true` are highlighted in red. Use it for things that need a decision
- Order `steps` in the order the code is read. The table of contents is generated automatically

### code

- `file`: the path in the diff. Just the file name is fine if its suffix is unique
- `lines`: the line range on the new (head) side. If omitted, the whole diff of the file
- Deleted lines within the range are also shown. A deleted line belongs to the line right after it
- If the range spans multiple hunks, the gap is shown as `⋯`

### Markers

`[[a-b]]` / `[[a]]` / `[[<file>:a-b]]` in `body` become chips.

- Line numbers are on the new side
- If the file is omitted, the marker points to the first file in the step's `code`
- The lines pointed to must be shown in the step
- Placing a marker at the start of an explanation item makes it easy to see which code the item is about

### Markdown

Only the following can be used in `summary`, `change`, `attention[].body`, and `steps[].body`.

- Paragraphs separated by blank lines
- `- ` bullet lists and `1. ` numbered lists (no nesting)
- `` `code` `` and `[text](https://...)`
