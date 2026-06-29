"""
pre_commit_doc_updater.py
=========================
Automatically generates or updates documentation for staged source files
before every git commit.

Run by the Git pre-commit hook (installed via install_hooks.py).

Mode:
  - Static (default): Uses Python AST + JS regex. No API key required.
  - AI-enhanced (optional): Set GEMINI_API_KEY env var for richer descriptions.
"""

import os
import sys
import ast
import re
import subprocess
from datetime import datetime

# Project root = one level above scripts/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(ROOT, "docs")


# ──────────────────────────────────────────────
# 1.  Git helpers
# ──────────────────────────────────────────────

def get_staged_files():
    """Return list of staged source files (.py / .js / .ts)."""
    result = subprocess.run(
        ["git", "diff", "--staged", "--name-only"],
        capture_output=True, text=True, cwd=ROOT
    )
    all_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    return [f for f in all_files if f.endswith((".py", ".js", ".ts", ".jsx", ".tsx"))]


def stage_files(paths):
    """Stage a list of absolute file paths."""
    if paths:
        subprocess.run(["git", "add"] + paths, cwd=ROOT, check=False)


def get_staged_diff(rel_path):
    result = subprocess.run(
        ["git", "diff", "--staged", rel_path],
        capture_output=True, text=True, cwd=ROOT
    )
    return result.stdout


# ──────────────────────────────────────────────
# 2.  Python extractor (AST-based)
# ──────────────────────────────────────────────

def extract_python_summary(rel_path):
    """
    Parse a Python file with the AST module and extract:
      - top-level imports
      - class definitions + docstrings
      - function / async-function definitions + args + decorators + docstrings
    Returns a dict, or None if the file cannot be parsed.
    """
    abs_path = os.path.join(ROOT, rel_path)
    if not os.path.exists(abs_path):
        return None

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception as e:
        print(f"    Could not parse {rel_path}: {e}")
        return None

    summary = {"imports": [], "classes": [], "functions": []}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                summary["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                summary["imports"].append(f"{module}.{alias.name}")
        elif isinstance(node, ast.ClassDef) and node.col_offset == 0:
            summary["classes"].append({
                "name": node.name,
                "docstring": ast.get_docstring(node) or "",
                "line": node.lineno,
            })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [arg.arg for arg in node.args.args]
            decorators = []
            for dec in node.decorator_list:
                try:
                    decorators.append(f"@{ast.unparse(dec)}")
                except Exception:
                    pass
            summary["functions"].append({
                "name": node.name,
                "args": args,
                "decorators": decorators,
                "docstring": ast.get_docstring(node) or "",
                "line": node.lineno,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
            })

    return summary


# ──────────────────────────────────────────────
# 3.  JavaScript extractor (regex-based)
# ──────────────────────────────────────────────

def extract_js_summary(rel_path):
    """
    Parse a JS/TS file with regex and extract:
      - import statements
      - named function declarations
      - arrow functions / function expressions assigned to const/let/var
    """
    abs_path = os.path.join(ROOT, rel_path)
    if not os.path.exists(abs_path):
        return None

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        print(f"    Could not read {rel_path}: {e}")
        return None

    summary = {"imports": [], "functions": []}

    for match in re.finditer(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]", source):
        summary["imports"].append(match.group(1))

    func_patterns = [
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)",
        r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>",
        r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?function\s*\(([^)]*)\)",
    ]

    seen = set()
    for pattern in func_patterns:
        for match in re.finditer(pattern, source):
            name = match.group(1)
            if name in seen:
                continue
            seen.add(name)
            args_str = match.group(2).strip()
            args = [a.strip() for a in args_str.split(",") if a.strip()]
            line = source[: match.start()].count("\n") + 1
            summary["functions"].append({"name": name, "args": args, "line": line})

    return summary


# ──────────────────────────────────────────────
# 4.  Optional AI enhancement (Gemini)
# ──────────────────────────────────────────────

def ai_describe_change(rel_path, diff_text):
    """
    If GEMINI_API_KEY is set, call Gemini to produce a human-readable
    summary of the code diff. Returns empty string if not configured.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key or not diff_text.strip():
        return ""

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = (
            f"You are a technical writer. Summarize the following code diff for "
            f"file `{rel_path}` in 2-3 sentences. Be concrete and mention function names.\n\n"
            f"```diff\n{diff_text[:4000]}\n```"
        )
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"    AI description skipped: {e}")
        return ""


# ──────────────────────────────────────────────
# 5.  Markdown generation
# ──────────────────────────────────────────────

def generate_doc(rel_path, summary, ai_description=""):
    filename = os.path.basename(rel_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# `{filename}`",
        "",
        f"> **Path:** `{rel_path.replace(chr(92), '/')}`  ",
        f"> **Last documented:** {now}",
        "",
        "---",
        "",
    ]

    if ai_description:
        lines += [
            "## Recent Changes",
            "",
            f"> {ai_description}",
            "",
            "---",
            "",
        ]

    if summary.get("imports"):
        lines += ["## Dependencies / Imports", ""]
        for imp in sorted(set(summary["imports"])):
            lines.append(f"- `{imp}`")
        lines.append("")

    if summary.get("classes"):
        lines += ["## Classes", ""]
        for cls in summary["classes"]:
            lines.append(f"### `{cls['name']}` — line {cls['line']}")
            if cls["docstring"]:
                lines.append(f"> {cls['docstring']}")
            lines.append("")

    if summary.get("functions"):
        lines += ["## Functions", ""]
        for fn in summary["functions"]:
            args = ", ".join(fn["args"])
            prefix = "async " if fn.get("is_async") else ""
            lines.append(f"### `{prefix}{fn['name']}({args})` — line {fn['line']}")
            if fn.get("decorators"):
                for dec in fn["decorators"]:
                    lines.append(f"**Decorator:** `{dec}`  ")
            if fn.get("docstring"):
                lines += ["", f"> {fn['docstring']}", ""]
            else:
                lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# 6.  CHANGELOG update
# ──────────────────────────────────────────────

def update_changelog(staged_files):
    changelog_path = os.path.join(DOCS_DIR, "CHANGELOG.md")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    entry = f"\n## {now}\n\n**Files changed:**\n"
    for f in staged_files:
        entry += f"- `{f}`\n"

    if os.path.exists(changelog_path):
        with open(changelog_path, "r", encoding="utf-8") as fh:
            existing = fh.read()
        split_point = existing.find("\n\n")
        if split_point == -1:
            content = existing + entry
        else:
            content = existing[:split_point] + entry + existing[split_point:]
    else:
        content = "# Changelog\n\nAuto-generated by pre-commit hook.\n" + entry

    with open(changelog_path, "w", encoding="utf-8") as fh:
        fh.write(content)

    return changelog_path


# ──────────────────────────────────────────────
# 7.  Entry point
# ──────────────────────────────────────────────

def main():
    staged_files = get_staged_files()

    if not staged_files:
        print("No source files staged - skipping doc update.")
        sys.exit(0)

    print(f"Updating docs for {len(staged_files)} staged file(s)...")
    os.makedirs(DOCS_DIR, exist_ok=True)

    updated_docs = []

    for rel_path in staged_files:
        print(f"  -> {rel_path}")

        if rel_path.endswith(".py"):
            summary = extract_python_summary(rel_path)
        else:
            summary = extract_js_summary(rel_path)

        if summary is None:
            print(f"     Skipping (could not parse).")
            continue

        diff_text = get_staged_diff(rel_path)
        ai_desc = ai_describe_change(rel_path, diff_text)

        doc_content = generate_doc(rel_path, summary, ai_desc)

        safe_name = rel_path.replace("/", "_").replace("\\", "_")
        doc_path = os.path.join(DOCS_DIR, f"{safe_name}.md")
        with open(doc_path, "w", encoding="utf-8") as fh:
            fh.write(doc_content)
        updated_docs.append(doc_path)
        print(f"     Written: docs/{safe_name}.md")

    changelog_path = update_changelog(staged_files)
    updated_docs.append(changelog_path)
    print(f"     Updated: docs/CHANGELOG.md")

    stage_files(updated_docs)
    print(f"\nDone. {len(updated_docs)} doc file(s) staged into this commit.")
    sys.exit(0)


if __name__ == "__main__":
    main()
