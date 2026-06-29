# `pre_commit_doc_updater.py`

> **Path:** `scripts/pre_commit_doc_updater.py`  
> **Last documented:** 2026-06-29 18:03

---

## Dependencies / Imports

- `ast`
- `datetime.datetime`
- `google.generativeai`
- `os`
- `re`
- `subprocess`
- `sys`

## Functions

### `get_staged_files()` — line 30

> Return list of staged source files (.py / .js / .ts).

### `stage_files(paths)` — line 40

> Stage a list of absolute file paths.

### `get_staged_diff(rel_path)` — line 46

### `extract_python_summary(rel_path)` — line 58

> Parse a Python file with the AST module and extract:
  - top-level imports
  - class definitions + docstrings
  - function / async-function definitions + args + decorators + docstrings
Returns a dict, or None if the file cannot be parsed.

### `extract_js_summary(rel_path)` — line 118

> Parse a JS/TS file with regex and extract:
  - import statements
  - named function declarations
  - arrow functions / function expressions assigned to const/let/var

### `ai_describe_change(rel_path, diff_text)` — line 166

> If GEMINI_API_KEY is set, call Gemini to produce a human-readable
summary of the code diff. Returns empty string if not configured.

### `generate_doc(rel_path, summary, ai_description)` — line 195

### `update_changelog(staged_files)` — line 254

### `main()` — line 283
