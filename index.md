# Runtime Architecture Internals & Developer Guide

这是一套面向 `arkcompiler/runtime_core/static_core` 的内部 Wiki（Stage1 架构索引 + Stage2 逐行证据链沉淀）。

## 快速入口（推荐）

- **总索引（Stage1）**：`00_Master_Index.md`
- **文档交付/验收方法论**：`00_Methodology_Wiki_Review_Checklist.md`
- **Stage2（新人建议从脊柱图开始）**：
  - ClassLoading：`03_ClassLoading/Flows/ClassLoading_EndToEnd.md`
  - ExecutionEngine：`04_ExecutionEngine/Flows/ExecutionEngine_EndToEnd.md`

## 本地预览（MkDocs）

在本目录（作为站点仓库根目录）运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r mkdocs-requirements.txt
mkdocs serve
```

## GitHub Pages 发布

本目录提供了 GitHub Actions workflow（见 `.github/workflows/mkdocs-gh-pages.yml`），会将 `mkdocs.yml` 构建产物发布到 `gh-pages` 分支。


