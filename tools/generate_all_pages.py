#!/usr/bin/env python3
"""
Generate an "All Pages" markdown index for MkDocs.

We intentionally generate this file into the REAL docs root (not the mkdocs docs_dir symlink farm),
so it is also visible via the repo symlink path.
"""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path("/home/fanzewei/docs/Runtime_Architecture_Internals_and_Developer_Guide")
OUT = ROOT / "All_Pages.md"

EXCLUDE_DIRS = {
    ".git",
    ".github",
    ".venv",
    "site",
    "__pycache__",
}

# We do not want to index generated symlink-farm directory itself; we index the real content.
EXCLUDE_TOP_LEVEL = {"docs"}


def iter_md_files(root: Path) -> list[Path]:
    res: list[Path] = []
    for p in root.rglob("*.md"):
        rel = p.relative_to(root)
        if rel.parts and rel.parts[0] in EXCLUDE_TOP_LEVEL:
            continue
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        # Skip README-like duplicates in root index? keep all for completeness.
        res.append(p)
    res.sort(key=lambda x: str(x.relative_to(root)).lower())
    return res


def to_mkdocs_link(rel: Path) -> str:
    # MkDocs/Material accepts relative links. We keep file extension for readability.
    s = str(rel).replace(os.sep, "/")
    return s


def main() -> None:
    files = iter_md_files(ROOT)
    lines: list[str] = []
    lines.append("# All Pages（全量页面索引）")
    lines.append("")
    lines.append("这个页面用于保证：**仓库内每一篇 Markdown 都能在站点里被点击访问**。")
    lines.append("")
    lines.append("提示：如果你已经知道关键词，用右上角搜索会更快。")
    lines.append("")

    # Group by top-level directory / file
    groups: dict[str, list[Path]] = {}
    for f in files:
        rel = f.relative_to(ROOT)
        key = rel.parts[0] if len(rel.parts) > 1 else "_root"
        groups.setdefault(key, []).append(rel)

    def group_title(k: str) -> str:
        return "Root Files" if k == "_root" else k

    for k in sorted(groups.keys(), key=lambda x: x.lower()):
        lines.append(f"## {group_title(k)}")
        lines.append("")
        for rel in groups[k]:
            link = to_mkdocs_link(rel)
            title = rel.stem if rel.name.lower() != "readme.md" else str(rel.parent) + "/README"
            lines.append(f"- [{title}]({link})")
        lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote: {OUT} ({len(files)} pages)")


if __name__ == "__main__":
    main()


