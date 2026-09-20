"""Validate Agent-reviewed links between a Node HTTP backend and source HTML.

The Agent follows routes from the backend entry. This module checks the recorded
paths and source excerpts, rather than guessing JavaScript data flow from regexes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from create_project_archive import SKIP_DIRS as ARCHIVE_SKIP_DIRS


def project_file(root: Path, value: Any) -> Path:
    if (not isinstance(value, str) or not value or "\\" in value
            or any(c in value for c in "\r\n\x00") or Path(value).is_absolute()
            or ".." in Path(value).parts):
        raise ValueError("backend HTML review paths must be project-relative")
    path = root / value
    if any(part.is_symlink() for part in [path, *path.parents] if part != root and root in part.parents):
        raise ValueError(f"backend HTML review path traverses a symlink: {value}")
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"backend HTML review file is missing: {value}")
    return path


def validate_html_pages(root: Path | None, pages: Any) -> list[dict[str, Any]]:
    if not isinstance(pages, list) or not pages:
        raise ValueError("backend HTML review must be a non-empty array")
    seen: set[str] = set()
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("backend HTML review page must be an object")
        target = page.get("Path")
        if (not isinstance(target, str) or Path(target).suffix.lower() not in {".html", ".htm"}
                or Path(target).is_absolute() or ".." in Path(target).parts or "\\" in target
                or any(c in target for c in "\r\n\x00") or target in seen):
            raise ValueError("backend HTML review requires unique relative HTML source paths")
        if any(part in ARCHIVE_SKIP_DIRS | {"_tmp"} for part in Path(target).parts):
            raise ValueError("backend HTML review must reference deliverable source, not generated files")
        seen.add(target)
        if not isinstance(page.get("Reason"), str) or not page["Reason"].strip():
            raise ValueError("backend HTML review requires a route-to-HTML explanation")
        evidence = page.get("Evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("backend HTML review requires backend source evidence")
        if root is not None:
            project_file(root, target)
        for item in evidence:
            if (not isinstance(item, dict) or not isinstance(item.get("File"), str)
                    or Path(item["File"]).suffix not in {".js", ".cjs", ".mjs", ".ts", ".tsx", ".jsx"}
                    or type(item.get("Line")) is not int or item["Line"] < 1
                    or not isinstance(item.get("Text"), str) or not item["Text"].strip()):
                raise ValueError("backend HTML evidence requires File, Line and exact source Text")
            if root is not None:
                lines = project_file(root, item["File"]).read_text(encoding="utf-8").splitlines()
                line = item["Line"]
                if line > len(lines) or lines[line - 1].strip() != item["Text"].strip():
                    raise ValueError(f"backend HTML evidence is stale: {item['File']}:{line}")
    return sorted(pages, key=lambda page: page["Path"])


def load_html_pages(root: Path, path: Path) -> list[dict[str, Any]]:
    return validate_html_pages(root, json.loads(path.read_text(encoding="utf-8")))
