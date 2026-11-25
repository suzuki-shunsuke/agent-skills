#!/usr/bin/env python3
"""Render a PR Explanation as one HTML page: code on the left, explanation on the right.

Usage:
    render-pr-explanation.py --spec spec.json --diff pr.diff --out pr-explanation.html

The diff is the output of `git diff <base>...<head>` (or `gh pr diff`). The spec format is
described in references/pr-explanation-html.md.

The page has no scripts and loads nothing from the network, so it works when opened
directly in a browser.
"""
import argparse
import html
import json
import re
import sys

HDR = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)")
MARK = re.compile(r"\[\[(?:([\w./-]+):)?(\d+)(?:-(\d+))?\]\]")
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚"


def fail(msg):
    sys.exit(f"render-pr-explanation: {msg}")


# ---- diff ------------------------------------------------------------------------------


def parse_diff(text):
    """Return {path: [(sign, old_no, new_no, code), ...]} for the new side of every file.

    sign is "+", "-" or " ". old_no is None for an added line, new_no is None for a deleted
    one. Lines of all hunks of a file are concatenated; a gap between hunks is marked by a
    ("@", None, None, header) row.
    """
    files, rows, o, n = {}, None, 0, 0
    for line in text.splitlines():
        if line.startswith("diff --git"):
            rows = files.setdefault(line.split(" b/", 1)[1], [])
        elif rows is None or line.startswith(("--- ", "+++ ", "index ", "new file", "deleted file", "similarity", "rename ", "old mode", "new mode", "\\ No newline")):
            continue
        elif line.startswith("@@"):
            m = HDR.match(line)
            o, n = int(m.group(1)), int(m.group(3))
            rows.append(("@", None, None, line))
        elif line.startswith("+"):
            rows.append(("+", None, n, line[1:]))
            n += 1
        elif line.startswith("-"):
            rows.append(("-", o, None, line[1:]))
            o += 1
        else:
            rows.append((" ", o, n, line[1:]))
            o += 1
            n += 1
    return files


def find_file(files, name):
    """Resolve a path or a unique path suffix (e.g. a basename) to a file in the diff."""
    if name in files:
        return name
    hits = [p for p in files if p.endswith("/" + name)]
    if len(hits) != 1:
        fail(f"{name!r} matches {len(hits)} files in the diff")
    return hits[0]


def slice_rows(rows, a, b):
    """Rows whose new line number is in [a, b], with the deletions between them.

    A deletion belongs to the line after it, so deleted lines are shown when the line that
    follows them is in the range.
    """
    out, pending = [], []
    for sign, o, n, code in rows:
        if sign == "@":
            pending = []
            continue
        if sign == "-":
            pending.append((sign, o, n, code))
            continue
        if a <= n <= b:
            out.extend(pending)
            out.append((sign, o, n, code))
        pending = []
    if not out:
        fail(f"no lines {a}-{b} in the diff")
    return out


# ---- markdown subset -------------------------------------------------------------------


def md_inline(s, marker):
    out = []
    for part in re.split(r"(`[^`]+`)", s):
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f"<code>{html.escape(part[1:-1])}</code>")
            continue
        # markers are fenced with NUL so the link pattern can't take them for a [text]
        part = MARK.sub(lambda m: "\0" + m.group(0) + "\0", part)
        esc = html.escape(part, quote=False)
        esc = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', esc)
        esc = re.sub(r"\0(\[\[.*?\]\])\0", lambda m: marker(MARK.fullmatch(m.group(1))), esc)
        out.append(esc)
    return "".join(out)


def md(text, marker=lambda m: html.escape(m.group(0))):
    """Paragraphs, "- " lists and "1. " lists, with `code`, [links](https://...) and markers."""
    blocks, html_out = re.split(r"\n\s*\n", (text or "").strip()), []
    for block in blocks:
        lines = block.split("\n")
        kind = "ul" if re.match(r"- ", lines[0]) else "ol" if re.match(r"\d+\. ", lines[0]) else "p"
        if kind == "p":
            html_out.append(f"<p>{md_inline(' '.join(l.strip() for l in lines), marker)}</p>")
            continue
        items = []
        for line in lines:
            m = re.match(r"(?:- |\d+\. )(.*)", line)
            if m:
                items.append(m.group(1))
            elif items:
                items[-1] += " " + line.strip()
        lis = "".join(f"<li>{md_inline(i, marker)}</li>" for i in items)
        html_out.append(f"<{kind}>{lis}</{kind}>")
    return "".join(html_out)


# ---- code ------------------------------------------------------------------------------

KEYWORDS = r"func|return|if|else|for|range|type|struct|interface|var|const|package|import|nil|defer|continue|break|switch|case|default|map|true|false|go|chan|select|def|class|from|None|True|False|let|function|async|await|export|new|this|self|fn|pub|impl|use|mut|match"
TOK = re.compile(r'(?P<cm>(?://|#).*$)|(?P<str>"(?:\\.|[^"\\])*"|`[^`]*`|\'(?:\\.|[^\'\\])*\')|(?P<kw>\b(?:' + KEYWORDS + r")\b)")


def highlight(code):
    out, pos = [], 0
    for m in TOK.finditer(code):
        out.append(html.escape(code[pos : m.start()]))
        out.append(f'<span class="{m.lastgroup}">{html.escape(m.group())}</span>')
        pos = m.end()
    out.append(html.escape(code[pos:]))
    return "".join(out)


def slug(s):
    return re.sub(r"[^A-Za-z0-9]", "_", s)


def render_code(sid, path, rows, marks):
    trs, prev_o, prev_n = [], None, None
    for sign, o, n, code in rows:
        # a gap in the line numbers means lines were skipped: show it like a hunk header
        if prev_n is not None and ((n is not None and n != prev_n + 1) or (o is not None and prev_o is not None and o != prev_o + 1)):
            trs.append('<tr class="gap"><td></td><td></td><td></td><td></td><td>⋯</td></tr>')
        if o is not None:
            prev_o = o
        if n is not None:
            prev_n = n
        if sign == "-":
            trs.append(f'<tr class="del"><td>{o}</td><td></td><td class="mkc"></td><td class="sg">-</td><td>{highlight(code)}</td></tr>')
            continue
        cls = (["add"] if sign == "+" else []) + (["ref"] if n in marks["in"] else [])
        badges = "".join(f'<span class="mk">{CIRCLED[k % len(CIRCLED)]}</span>' for k in marks["start"].get(n, []))
        cls_attr = f' class="{" ".join(cls)}"' if cls else ""
        trs.append(
            f'<tr id="{sid}-{n}"{cls_attr}>'
            f'<td>{"" if o is None else o}</td><td>{n}</td><td class="mkc">{badges}</td>'
            f'<td class="sg">{"+" if sign == "+" else ""}</td><td>{highlight(code)}</td></tr>'
        )
    return (
        f'<div class="diff"><div class="diff-path">{html.escape(path)}</div>'
        f'<div class="diff-scroll"><table>{"".join(trs)}</table></div></div>'
    )


# ---- page ------------------------------------------------------------------------------


def render(spec, files):
    repo, sha = spec.get("repo"), spec.get("head_sha")
    esc = html.escape

    def src_link(path, a, b):
        label = f"{esc(path)}#L{a}-L{b}"
        if repo and sha:
            return f'<a class="srclink" href="https://github.com/{repo}/blob/{sha}/{path}#L{a}-L{b}">{label}</a>'
        return f'<span class="srclink">{label}</span>'

    steps_html, toc = [], []
    for i, step in enumerate(spec["steps"], 1):
        blocks = []  # (sid, path, rows, a, b)
        for ref in step["code"]:
            path = find_file(files, ref["file"])
            rows = files[path]
            if "lines" in ref:
                a, b = ref["lines"]
                rows = slice_rows(rows, a, b)
            else:
                rows = [r for r in rows if r[0] != "@"]
            nums = [r[2] for r in rows if r[2] is not None]
            blocks.append((f"s{i}-{slug(path)}", path, rows, min(nums) if nums else 0, max(nums) if nums else 0))

        marks, counter = {}, [0]

        def marker(m, blocks=blocks, marks=marks, counter=counter, i=i):
            name, a = m.group(1), int(m.group(2))
            b = int(m.group(3) or a)
            if name:
                path = find_file({p: None for _, p, _, _, _ in blocks}, name)
            else:
                path = blocks[0][1]
            sid = f"s{i}-{slug(path)}"
            shown = {r[2] for s, p, rows, _, _ in blocks if s == sid for r in rows if r[2] is not None}
            missing = [x for x in range(a, b + 1) if x not in shown]
            if missing:
                fail(f"step {i}: {m.group(0)} points at lines not shown in the step: {missing}")
            k = counter[0]
            counter[0] += 1
            fm = marks.setdefault(sid, {"start": {}, "in": set()})
            fm["start"].setdefault(a, []).append(k)
            fm["in"].update(range(a, b + 1))
            label = f"L{a}" if a == b else f"L{a}-{b}"
            if name:
                label = f"{esc(name)}:{label}"
            return f'<span class="ln"><b>{CIRCLED[k % len(CIRCLED)]}</b> {label}</span>'

        body = md(step["body"], marker)
        empty = {"start": {}, "in": set()}
        left = "".join(render_code(s, p, rows, marks.get(s, empty)) for s, p, rows, _, _ in blocks)
        links = "<br>".join(src_link(p, a, b) for _, p, _, a, b in blocks)
        module = esc(step.get("module", ""))
        steps_html.append(f"""
<section class="step" id="step{i}">
  <div class="code-col">{left}</div>
  <aside class="explain">
    <span class="step-no">{i:02d}</span><span class="pkg">{module}</span>
    <h3>{esc(step["title"])}</h3>
    {body}
    <div class="links">{links}</div>
  </aside>
</section>""")
        toc.append(f'<li><a href="#step{i}"><span class="pkg">{module}</span> {esc(step["title"])}</a></li>')

    sec = [0]

    def section(title, content):
        if not content:
            return ""
        sec[0] += 1
        return f'<section class="block"><div class="section-header"><span class="section-number">{sec[0]:02d}</span><h2>{esc(title)}</h2></div>{content}</section>'

    overview = ""
    if spec.get("overview"):
        trs = "".join(f"<tr><td><code>{esc(o['module'])}</code></td><td>{md(o['change'])}</td></tr>" for o in spec["overview"])
        overview = f'<table class="overview"><tr><th>Module</th><th>Changes</th></tr>{trs}</table>'

    attention = ""
    if spec.get("attention"):
        items = "".join(
            f'<div class="focus-item{" warn" if a.get("warn") else ""}"><span class="focus-number">{k}</span>'
            f'<div><h4>{md_inline(a["title"], lambda m: esc(m.group(0)))}</h4>{md(a.get("body", ""))}</div></div>'
            for k, a in enumerate(spec["attention"], 1)
        )
        attention = f'<div class="focus-list">{items}</div>'

    tests = ""
    if spec.get("tests"):
        t = spec["tests"]
        lis = lambda xs: "".join(f"<li>{md_inline(x, lambda m: esc(m.group(0)))}</li>" for x in xs)
        tests = (
            f'<div class="two-col"><div class="panel done"><div class="label">Confirmed</div><ul>{lis(t.get("covered", []))}</ul></div>'
            f'<div class="panel todo"><div class="label">Not confirmed</div><ul>{lis(t.get("not_covered", []))}</ul></div></div>'
        )

    meta = "".join(f"<span>{esc(str(x))}</span>" for x in spec.get("meta", []))
    if spec.get("url"):
        meta += f'<span><a href="{esc(spec["url"])}">GitHub</a></span>'
    summary = f'<div class="tldr"><h3>TL;DR</h3>{md(spec["summary"])}</div>' if spec.get("summary") else ""

    head = f"""
<div class="narrow">
<header>
  <span class="eyebrow">{esc(spec.get("eyebrow", "PR Explanation"))}</span>
  <h1>{esc(spec["title"])}</h1>
  <div class="pr-meta">{meta}</div>
</header>
{summary}
{section("Summary of Changes", overview)}
{section("Places to Look At", attention)}
{section("Tests", tests)}
{section("Reading Order", '<ol class="toc">' + "".join(toc) + "</ol>")}
</div>
{section("Code Walkthrough", "".join(steps_html))}"""
    return PAGE.replace("%%TITLE%%", esc(spec.get("page_title", spec["title"]))).replace("%%BODY%%", head)


PAGE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%TITLE%%</title>
<style>
:root {
  --background: oklch(0.97 0.005 260); --foreground: oklch(0.18 0.02 260); --card: oklch(1 0 0);
  --primary: oklch(0.50 0.25 280); --primary-foreground: oklch(1 0 0); --muted: oklch(0.92 0.01 260);
  --muted-foreground: oklch(0.40 0.02 260); --destructive: oklch(0.50 0.25 25); --success: oklch(0.45 0.20 150);
  --warning: oklch(0.55 0.18 85); --border: oklch(0.88 0.01 260);
  --font-sans: 'Inter', system-ui, -apple-system, 'Hiragino Sans', sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
  --font-display: ui-serif, Georgia, 'Hiragino Mincho ProN', serif; --radius: 0.625rem;
}
@media (prefers-color-scheme: dark) {
  :root {
    --background: oklch(0.18 0.01 260); --foreground: oklch(0.93 0.01 260); --card: oklch(0.22 0.01 260);
    --primary: oklch(0.72 0.17 280); --primary-foreground: oklch(0.15 0.02 260); --muted: oklch(0.28 0.01 260);
    --muted-foreground: oklch(0.72 0.02 260); --destructive: oklch(0.68 0.19 25); --success: oklch(0.72 0.17 150);
    --warning: oklch(0.78 0.15 85); --border: oklch(0.34 0.01 260);
  }
}
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: var(--font-sans); background: var(--background); color: var(--foreground); line-height: 1.65; font-size: 15px; -webkit-font-smoothing: antialiased; }
.container { max-width: 1480px; margin: 0 auto; padding: 56px 24px; }
.narrow { max-width: 900px; }
a { color: var(--primary); }
code { font-family: var(--font-mono); font-size: 0.84em; background: var(--muted); padding: 1px 5px; border-radius: 4px; }
p + p, p + ul, p + ol, ul + p, ol + p { margin-top: 8px; }
ul, ol { margin: 6px 0 0 20px; }
.eyebrow { font-family: var(--font-mono); font-size: 0.72rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted-foreground); }
header h1 { font-family: var(--font-display); font-size: 2rem; font-weight: 500; margin: 8px 0; line-height: 1.25; }
.pr-meta { display: flex; flex-wrap: wrap; gap: 16px; font-family: var(--font-mono); font-size: 0.78rem; color: var(--muted-foreground); }
.tldr { background: var(--card); border: 1.5px solid var(--border); border-left: 4px solid var(--primary); border-radius: var(--radius); padding: 20px 24px; margin: 28px 0; }
.tldr h3, .label { font-family: var(--font-mono); font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--primary); margin-bottom: 8px; }
.tldr p { color: var(--muted-foreground); }
section.block { margin-top: 56px; }
.section-header { display: flex; align-items: baseline; gap: 16px; margin-bottom: 20px; padding-bottom: 8px; border-bottom: 1.5px solid var(--border); }
.section-number { font-family: var(--font-mono); font-size: 0.75rem; font-weight: 600; color: var(--primary); }
.section-header h2 { font-family: var(--font-display); font-size: 1.4rem; font-weight: 500; }
table.overview { width: 100%; border-collapse: collapse; font-size: 0.9rem; background: var(--card); border: 1.5px solid var(--border); }
.overview th, .overview td { text-align: left; padding: 10px 16px; border-bottom: 1px solid var(--border); vertical-align: top; }
.overview th { font-family: var(--font-mono); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted-foreground); }
.focus-list { display: flex; flex-direction: column; gap: 12px; }
.focus-item { background: var(--card); border: 1.5px solid var(--border); border-radius: var(--radius); padding: 16px 20px; display: flex; gap: 16px; align-items: flex-start; }
.focus-item.warn { border-left: 4px solid var(--destructive); }
.focus-number { font-family: var(--font-mono); font-size: 0.78rem; font-weight: 600; color: var(--primary-foreground); background: var(--primary); width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.focus-item.warn .focus-number { background: var(--destructive); }
.focus-item h4 { font-size: 0.95rem; font-weight: 600; margin-bottom: 4px; }
.focus-item p, .focus-item li { font-size: 0.88rem; color: var(--muted-foreground); }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.panel { background: var(--card); border: 1.5px solid var(--border); border-radius: var(--radius); padding: 16px 20px; }
.panel ul { margin-left: 18px; font-size: 0.88rem; }
.panel.done .label { color: var(--success); } .panel.todo .label { color: var(--warning); }
.toc { columns: 2; column-gap: 32px; list-style: none; font-size: 0.88rem; margin: 0; }
.toc li { break-inside: avoid; padding: 3px 0; }
.toc a { color: var(--foreground); text-decoration: none; }
.pkg { font-family: var(--font-mono); font-size: 0.72rem; color: var(--muted-foreground); }
.step { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(0, 1fr); gap: 28px; padding: 28px 0; border-bottom: 1px dashed var(--border); }
.code-col { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.explain { position: sticky; top: 16px; align-self: start; background: var(--card); border: 1.5px solid var(--border); border-radius: var(--radius); padding: 18px 22px; max-height: calc(100vh - 32px); overflow-y: auto; }
.explain .step-no { font-family: var(--font-mono); font-size: 0.75rem; font-weight: 600; color: var(--primary); margin-right: 10px; }
.explain h3 { font-family: var(--font-display); font-size: 1.15rem; font-weight: 500; margin: 4px 0 10px; }
.explain p, .explain li { font-size: 0.9rem; }
.explain .links { margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--border); font-family: var(--font-mono); font-size: 0.7rem; word-break: break-all; }
.srclink { color: var(--muted-foreground); }
span.ln { display: inline-block; font-family: var(--font-mono); font-size: 0.7rem; font-weight: 600; color: var(--primary); background: color-mix(in oklab, var(--primary) 12%, transparent); border: 1px solid color-mix(in oklab, var(--primary) 35%, transparent); border-radius: 4px; padding: 0 5px; margin-right: 4px; line-height: 1.5; white-space: nowrap; }
.diff { border: 1.5px solid var(--border); border-radius: var(--radius); overflow: hidden; background: var(--card); }
.diff-path { font-family: var(--font-mono); font-size: 0.72rem; color: var(--muted-foreground); padding: 8px 14px; border-bottom: 1px solid var(--border); background: var(--muted); }
.diff-scroll { overflow-x: auto; }
.diff table { border-collapse: collapse; font-family: var(--font-mono); font-size: 0.78rem; line-height: 1.5; width: max-content; min-width: 100%; }
.diff td { padding: 0 8px; white-space: pre; vertical-align: top; tab-size: 4; -moz-tab-size: 4; }
.diff td:nth-child(1), .diff td:nth-child(2) { color: var(--muted-foreground); text-align: right; user-select: none; min-width: 3.2em; opacity: 0.7; }
.diff td.mkc { padding: 0 2px 0 4px; width: 1.6em; user-select: none; }
.diff td.sg { user-select: none; width: 1em; padding: 0 4px; }
.diff tr.add { background: color-mix(in oklab, var(--success) 14%, transparent); }
.diff tr.add td.sg { color: var(--success); }
.diff tr.del { background: color-mix(in oklab, var(--destructive) 14%, transparent); }
.diff tr.del td.sg { color: var(--destructive); }
.diff tr.gap td { color: var(--primary); background: color-mix(in oklab, var(--primary) 8%, transparent); }
.diff tr.ref td.mkc { box-shadow: inset 3px 0 0 var(--primary); }
.diff tr.ref td:nth-child(2) { color: var(--primary); opacity: 1; }
.diff .mk { display: inline-block; font-family: var(--font-sans); font-size: 0.72rem; font-weight: 700; color: var(--primary-foreground); background: var(--primary); border-radius: 9px; padding: 0 5px; line-height: 1.35; }
.diff .kw { color: var(--primary); } .diff .str { color: var(--success); } .diff .cm { color: var(--muted-foreground); font-style: italic; }
@media (max-width: 900px) {
  .step, .two-col { grid-template-columns: 1fr; }
  .explain { position: static; max-height: none; order: -1; }
  .toc { columns: 1; }
  .container { padding: 32px 16px; }
}
</style>
</head>
<body>
<div class="container">
%%BODY%%
</div>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True, help="spec JSON (see references/pr-explanation-html.md)")
    ap.add_argument("--diff", required=True, help="output of git diff <base>...<head>")
    ap.add_argument("--out", required=True, help="HTML file to write")
    args = ap.parse_args()
    with open(args.spec) as f:
        spec = json.load(f)
    with open(args.diff) as f:
        files = parse_diff(f.read())
    page = render(spec, files)
    with open(args.out, "w") as f:
        f.write(page)
    print(f"{len(spec['steps'])} steps -> {args.out}")


if __name__ == "__main__":
    main()
