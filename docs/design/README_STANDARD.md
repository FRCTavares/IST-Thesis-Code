# Folder README standard

Last reviewed: 2026-09-09

## Purpose

An architectural folder's README should let a new developer understand the
folder in about 30 seconds. It names what lives there and points to the deep
documentation — it does not reproduce it.

## Required structure

```
# <folder path>            e.g. `# tools/experiments`

Last reviewed: YYYY-MM-DD

## Purpose
1–2 sentences: what belongs here and why the folder exists.

## Contents
| Path | Role | Why it exists |     (immediate meaningful children only;
                                     | Path | Role | is fine for small folders)

## Rules
2–5 short folder-specific rules or invariants.

## See also          (optional)
Links to the authoritative deep docs for this folder's work.
```

## Content rules

Belongs in a folder README:

- names and one-line roles of the folder's immediate children;
- the folder's purpose and local invariants;
- pointers to the authoritative deep documents.

Does not belong (put it in `docs/`, or a tool's own docstring):

- issue diaries, audit history, changelogs;
- experiment conclusions and scientific methodology;
- operating runbooks, field procedures, command tutorials;
- implementation essays;
- material already authoritative elsewhere.

## Coverage

A README is required for every folder that is a deliberate architectural or
domain boundary. It is not required for obvious asset children such as
`static/`, `templates/`, `fixtures/` or `systemd/` when the parent README
already names and explains them. If the parent can cover a child in one table
row, the child gets no README.

## "Last reviewed"

The date the folder's structure and contents were last deliberately checked
against this standard — not the date a file last changed.

## Enforcement

`tools/tests/test_tools_layout.py` asserts that each `tools/` domain folder has
a README whose first heading is its path and which carries a `Last reviewed:`
line. It does not check the date value, prose, line count or table shape.
Markdown link integrity is covered by
`tools/tests/test_documentation_references.py`.
