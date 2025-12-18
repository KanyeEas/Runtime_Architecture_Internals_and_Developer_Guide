#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate mkdocs.yml nav from the real docs/ directory tree (following symlinks).

Design goals (per user requirements):
- nav lists ALL markdown documents (.md) so every page is reachable from sidebar.
- Preserve a deterministic, human-friendly order.
- Put FileNotes at the very bottom of each chapter (largest, least primary).
- Keep sidebar collapsible: we only create nested sections; we DO NOT enable navigation.expand.

This script rewrites the section between:
  # NAV_BEGIN (AUTO-GENERATED)
  # NAV_END (AUTO-GENERATED)
in mkdocs.yml. If markers are missing, it will fail fast.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


NAV_BEGIN = "# NAV_BEGIN (AUTO-GENERATED)"
NAV_END = "# NAV_END (AUTO-GENERATED)"


def _rel_posix(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def _is_md(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".md"


def _sorted_md_files(dir_path: Path) -> List[Path]:
    return sorted([p for p in dir_path.iterdir() if _is_md(p)], key=lambda p: p.name.lower())


def _sorted_md_files_recursive(dir_path: Path) -> List[Path]:
    # Follow symlinks by default because docs/ is mostly symlinks.
    files: List[Path] = []
    for root, _dirs, fnames in os.walk(dir_path, followlinks=True):
        for f in fnames:
            if f.lower().endswith(".md"):
                files.append(Path(root) / f)
    return sorted(files, key=lambda p: _rel_posix(p, dir_path).lower())


def _title_from_filename(md_path: Path) -> str:
    # Use basename without extension; keep punctuation to match file identity.
    return md_path.stem


def _emit_yaml_line(lines: List[str], indent: int, text: str) -> None:
    lines.append(" " * indent + text + "\n")


def _emit_item(lines: List[str], indent: int, title: str, rel_path: str) -> None:
    # YAML: - Title: path
    # Quote title if contains ":" or leading/trailing spaces.
    key = title
    if ":" in key or key != key.strip():
        key = f'"{key}"'
    _emit_yaml_line(lines, indent, f"- {key}: {rel_path}")


def _emit_section(lines: List[str], indent: int, title: str) -> None:
    key = title
    if ":" in key or key != key.strip():
        key = f'"{key}"'
    _emit_yaml_line(lines, indent, f"- {key}:")


@dataclass(frozen=True)
class ChapterSpec:
    key: str  # "01 Startup"
    stage1_title: str  # "概览（Stage1）"
    stage1_file: str  # "01_Startup_and_Entrypoints.md"
    chapter_dir: str  # "01_Startup"
    readme_title: str  # "深入入口（Stage2/README）"
    index_title: str  # "深入路线图（Index）"


CHAPTERS: List[ChapterSpec] = [
    ChapterSpec(
        key="01 Startup",
        stage1_title="概览（Stage1）",
        stage1_file="01_Startup_and_Entrypoints.md",
        chapter_dir="01_Startup",
        readme_title="深入入口（Stage2/README）",
        index_title="深入路线图（Index）",
    ),
    ChapterSpec(
        key="02 Memory",
        stage1_title="概览（Stage1）",
        stage1_file="02_Memory_Management_and_Object_Model.md",
        chapter_dir="02_Memory",
        readme_title="深入入口（Stage2/README）",
        index_title="深入路线图（Index）",
    ),
    ChapterSpec(
        key="03 ClassLoading",
        stage1_title="概览（Stage1）",
        stage1_file="03_Class_Loading_and_Linking.md",
        chapter_dir="03_ClassLoading",
        readme_title="深入入口（Stage2/README）",
        index_title="深入路线图（Index）",
    ),
    ChapterSpec(
        key="04 ExecutionEngine",
        stage1_title="概览（Stage1）",
        stage1_file="04_Execution_Engine_Interpreter_JIT_AOT.md",
        chapter_dir="04_ExecutionEngine",
        readme_title="深入入口（Stage2/README）",
        index_title="深入路线图（Index）",
    ),
    ChapterSpec(
        key="05 NativeBridge",
        stage1_title="概览（Stage1）",
        stage1_file="05_Native_Bridge_ANI_and_Interop.md",
        chapter_dir="05_NativeBridge",
        readme_title="深入入口（Stage2/README）",
        index_title="深入路线图（Index）",
    ),
    ChapterSpec(
        key="06 Tooling",
        stage1_title="概览（Stage1）",
        stage1_file="06_Tooling_Profiling_Verification.md",
        chapter_dir="06_Tooling_Profiling_Verification",
        readme_title="深入入口（Stage2/README）",
        index_title="深入路线图（Index）",
    ),
    ChapterSpec(
        key="07 Build&Config",
        stage1_title="概览（Stage1）",
        stage1_file="07_Build_and_Configuration.md",
        chapter_dir="07_Build_and_Configuration",
        readme_title="深入入口（Stage2/README）",
        index_title="深入路线图（Index）",
    ),
]


def _chapter_end_to_end(chapter_dir: str) -> Optional[str]:
    # Heuristic: find *EndToEnd.md under Flows.
    flows = Path(chapter_dir) / "Flows"
    if not flows.exists():
        return None
    cands = sorted([p for p in _sorted_md_files(flows) if "EndToEnd" in p.stem], key=lambda p: p.name.lower())
    if not cands:
        return None
    return _rel_posix(cands[0], Path("."))


def _maybe_file(rel: str, docs_root: Path) -> Optional[str]:
    p = docs_root / rel
    if p.exists() and p.is_file():
        return rel
    return None


def _emit_chapter_nav(lines: List[str], docs_root: Path, spec: ChapterSpec) -> None:
    _emit_section(lines, 2, spec.key + ":")
    # NOTE: we already include ":" in title above; we passed with ":"; but _emit_section will quote.
    # To keep exact display, we want "- 01 Startup:" (no double colon). We'll handle this by emitting raw.


def _emit_chapter(lines: List[str], docs_root: Path, spec: ChapterSpec) -> None:
    # Chapter header
    _emit_yaml_line(lines, 2, f"- {spec.key}:")

    # NOTE: Per user requirement, Stage1 overviews are centralized under
    # "00 总览与方法论", not repeated inside each chapter.
    #
    # README.md is still kept as the chapter landing page (MkDocs maps README.md
    # to /<chapter_dir>/). To keep it as the landing page without adding a
    # labeled nav row, we insert a *path-only* entry as the first child.
    # Then the README itself uses front matter `hide: [navigation]` to avoid
    # occupying space in the left sidebar.
    readme = _maybe_file(f"{spec.chapter_dir}/README.md", docs_root)
    if readme:
        _emit_yaml_line(lines, 6, f"- {readme}")

    # 1) EndToEnd (Flows/*EndToEnd*.md) - if exists
    flows_dir = docs_root / spec.chapter_dir / "Flows"
    if flows_dir.exists():
        end_to_end = None
        for p in _sorted_md_files(flows_dir):
            if "EndToEnd" in p.stem:
                end_to_end = _rel_posix(p, docs_root)
                break
        if end_to_end:
            _emit_item(lines, 6, "端到端主线（EndToEnd）", end_to_end)

    # 2) Newbie playbook
    playbook = _maybe_file(f"{spec.chapter_dir}/Newbie_MinDebug_Playbook.md", docs_root)
    if playbook:
        _emit_item(lines, 6, "新人最小调试手册", playbook)

    # 3) Chapter Index
    idx = _maybe_file(f"{spec.chapter_dir}/Index.md", docs_root)
    if idx:
        _emit_item(lines, 6, spec.index_title, idx)

    # 4) Completion review & Errata (if exists)
    completion = _maybe_file(f"{spec.chapter_dir}/Completion_Review.md", docs_root)
    if completion:
        _emit_item(lines, 6, "完成度验收（Checklist）", completion)
    errata = _maybe_file(f"{spec.chapter_dir}/Errata_to_Stage1.md", docs_root)
    if errata:
        _emit_item(lines, 6, "Stage1 校正（Errata）", errata)

    # 5) Any other md at chapter root (not already listed), keep stable order.
    # Keep README.md excluded to avoid duplicating a page that is already the directory index.
    chapter_root = docs_root / spec.chapter_dir
    if chapter_root.exists():
        known = {
            "README.md",
            "Index.md",
            "Newbie_MinDebug_Playbook.md",
            "Completion_Review.md",
            "Errata_to_Stage1.md",
        }
        extra_root = [p for p in _sorted_md_files(chapter_root) if p.name not in known]
        for p in extra_root:
            _emit_item(lines, 6, _title_from_filename(p), _rel_posix(p, docs_root))

    # 6) Topic indexes + all pages under subdirs.
    # Order matters, and FileNotes MUST be the last.
    subdir_order = ["Flows", "DataStructures", "Diagrams", "Manifests", "FileNotes"]
    # Only include non-empty subdirs (must contain at least one .md),
    # otherwise MkDocs will parse the nav node value as null and error out.
    rendered_subdirs: List[Tuple[str, Path]] = []
    for sub in subdir_order:
        sub_path = docs_root / spec.chapter_dir / sub
        if not sub_path.exists() or not sub_path.is_dir():
            continue
        md_any = _sorted_md_files(sub_path)
        if not md_any:
            continue
        rendered_subdirs.append((sub, sub_path))

    if rendered_subdirs:
        _emit_yaml_line(lines, 6, "- 专题索引:")

        for sub, sub_path in rendered_subdirs:
            # Section name in sidebar
            _emit_yaml_line(lines, 10, f"- {sub}:")

            # Index.md first if present
            index_md = sub_path / "Index.md"
            if index_md.exists():
                _emit_item(lines, 14, "Index", _rel_posix(index_md, docs_root))

            # Then all other md files in that subdir (non-recursive), excluding Index.md
            md_files = [p for p in _sorted_md_files(sub_path) if p.name != "Index.md"]

            # For FileNotes, keep _Glossary near the top (after Index)
            if sub == "FileNotes":
                def note_key(p: Path) -> Tuple[int, str]:
                    if p.name == "_Glossary.md":
                        return (0, p.name.lower())
                    return (1, p.name.lower())

                md_files = sorted(md_files, key=note_key)

            for p in md_files:
                _emit_item(lines, 14, _title_from_filename(p), _rel_posix(p, docs_root))


def generate_nav_yaml(docs_root: Path) -> str:
    lines: List[str] = []
    _emit_yaml_line(lines, 0, "nav:")

    # 00 section (fixed)
    _emit_yaml_line(lines, 2, "- 00 总览与方法论:")
    # Keep index.md in nav to avoid MkDocs "exists but not included in nav" noise,
    # while still NOT introducing a top-level "Home" entry.
    if _maybe_file("index.md", docs_root):
        _emit_item(lines, 6, "首页（00 总览）", "index.md")
    for title, rel in [
        ("总索引（概览）", "00_Master_Index.md"),
        ("方法论 Checklist", "00_Methodology_Wiki_Review_Checklist.md"),
        ("全量页面索引（必备）", "All_Pages.md"),
    ]:
        if _maybe_file(rel, docs_root):
            _emit_item(lines, 6, title, rel)

    # Centralized Stage1 overviews for each chapter (per user requirement)
    stage1_items: List[Tuple[str, str]] = []
    for spec in CHAPTERS:
        if _maybe_file(spec.stage1_file, docs_root):
            stage1_items.append((spec.key, spec.stage1_file))
    if stage1_items:
        _emit_yaml_line(lines, 6, "- 各章概览（Stage1）:")
        for key, rel in stage1_items:
            _emit_item(lines, 10, key, rel)

    # Chapters (fixed order)
    for spec in CHAPTERS:
        _emit_chapter(lines, docs_root, spec)

    return "".join(lines)


def rewrite_mkdocs_yml(mkdocs_yml: Path, nav_yaml: str) -> None:
    text = mkdocs_yml.read_text(encoding="utf-8")
    if NAV_BEGIN not in text or NAV_END not in text:
        raise SystemExit(
            f"mkdocs.yml missing markers. Please add:\\n{NAV_BEGIN}\\n...\\n{NAV_END}"
        )
    before, rest = text.split(NAV_BEGIN, 1)
    _mid, after = rest.split(NAV_END, 1)
    new_text = before + NAV_BEGIN + "\n" + nav_yaml + NAV_END + after
    mkdocs_yml.write_text(new_text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mkdocs-yml", default="mkdocs.yml")
    ap.add_argument("--docs-dir", default="docs")
    args = ap.parse_args()

    mkdocs_yml = Path(args.mkdocs_yml)
    docs_root = Path(args.docs_dir)
    if not mkdocs_yml.exists():
        raise SystemExit(f"mkdocs.yml not found: {mkdocs_yml}")
    if not docs_root.exists():
        raise SystemExit(f"docs dir not found: {docs_root}")

    nav_yaml = generate_nav_yaml(docs_root)
    rewrite_mkdocs_yml(mkdocs_yml, nav_yaml)


if __name__ == "__main__":
    main()


