#!/usr/bin/env bash
set -euo pipefail

# Keep MkDocs docs_dir as a child directory (./docs), but keep the "real" content at repo root.
# This script rebuilds ./docs as a symlink farm pointing to the real content.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

rm -rf docs
mkdir -p docs

for item in 00_* 01_* 02_* 03_* 04_* 05_* 06_* 07_* assets index.md All_Pages.md; do
  if [ -e "$item" ]; then
    ln -s "../$item" "docs/$item"
  fi
done

echo "Synced MkDocs symlinks into: $ROOT/docs"


