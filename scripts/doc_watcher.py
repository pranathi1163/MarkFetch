"""
Document watcher for new/updated spec files.

When a new document is added under docs/specs, this script reads the file,
creates a short implementation note in docs/generated, and prints a summary.

Run in VS Code as a long-running task while editing.
"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCH_DIR = ROOT / "docs" / "specs"
OUTPUT_DIR = ROOT / "docs" / "generated"
SUPPORTED_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml"}
POLL_INTERVAL = 2.0


def clean_name(path: Path) -> str:
    return path.stem.replace(" ", "_").replace("/", "_").replace("\\", "_")


def summarize_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "(empty document)"

    if lines[0].startswith("{") or lines[0].startswith("["):
        return "JSON/YAML spec detected. First line: {}".format(lines[0][:120])

    if len(lines) == 1:
        return lines[0][:200]

    bullets = [line for line in lines if line.startswith(('-', '*', '1.', '2.', '3.', '4.', '5.'))]
    if bullets:
        return " / ".join(bullets[:3])

    return " ".join(lines[:3])[:300]


def build_implementation_note(file_path: Path, content: str) -> str:
    summary = summarize_text(content)
    safe_name = clean_name(file_path)
    lines = [
        f"# Implementation note for `{file_path.name}`",
        "",
        f"> **Source spec:** `{file_path.relative_to(ROOT).as_posix()}`",
        f"> **Detected:** {summary}",
        "",
        "---",
        "",
        "## Suggested actions",
        "",
        "- Review the spec and map the requirements to the relevant code area.",
        "- Add or update backend routes / services if the spec affects API behavior.",
        "- Add or update frontend UI or interaction if the spec describes UI behavior.",
        "- Include or refresh tests for any new or changed functionality.",
        "",
        "## Generated tasks",
        "",
    ]

    keywords = {"api": False, "service": False, "route": False, "button": False, "form": False, "input": False, "file": False}
    lower = content.lower()
    for key in keywords:
        keywords[key] = key in lower

    if keywords["api"] or keywords["route"] or keywords["service"]:
        lines.append("- Target backend implementation under `backend/`.")
    if keywords["button"] or keywords["form"] or keywords["input"]:
        lines.append("- Target frontend UI or page behavior under `frontend/`.")
    if keywords["file"]:
        lines.append("- Confirm file upload/download flow, request handling, and validations.")

    if len(lines) == 10:
        lines.append("- Create a focused implementation task and update docs before commit.")

    lines += ["", "## Raw spec excerpt", "", "```", content[:1600], "```", ""]
    return "\n".join(lines)


def write_note_for(path: Path) -> None:
    content = path.read_text(encoding="utf-8", errors="ignore")
    note = build_implementation_note(path, content)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    note_path = OUTPUT_DIR / f"{clean_name(path)}.md"
    note_path.write_text(note, encoding="utf-8")
    print(f"[{time.strftime('%H:%M:%S')}] Generated: {note_path.relative_to(ROOT)}")


def find_files(directory: Path):
    return {
        file for file in directory.glob("**/*")
        if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS
    }


def main() -> int:
    WATCH_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Watching {WATCH_DIR.relative_to(ROOT)} for new/changed doc files...")
    seen = find_files(WATCH_DIR)

    for path in sorted(seen):
        write_note_for(path)

    while True:
        try:
            current = find_files(WATCH_DIR)
            added = current - seen
            modified = {path for path in current & seen if path.stat().st_mtime > time.time() - POLL_INTERVAL * 2}
            for path in sorted(added | modified):
                write_note_for(path)
            seen = current
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print("Stopped watcher.")
            return 0
        except Exception as exc:
            print(f"Watcher error: {exc}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
