# Runtime Architecture Internals & Developer Guide

这是一套面向 `arkcompiler/runtime_core/static_core` 的内部 Wiki：

- **概览（原 Stage1）**：每章一篇“架构主线 + 关键概念”总览，方便快速建立心智模型
- **深入（原 Stage2）**：围绕每章 README/Flows/DataStructures/FileNotes 做逐行证据链沉淀，方便新人落地排障与改代码

## 00 总览与方法论（首页）

- [总索引（概览）](00_Master_Index.md)
- [方法论 Checklist](00_Methodology_Wiki_Review_Checklist.md)
- [全量页面索引（必备）](All_Pages.md)

### 各章概览（Stage1）

- [01 Startup](01_Startup_and_Entrypoints.md)
- [02 Memory](02_Memory_Management_and_Object_Model.md)
- [03 ClassLoading](03_Class_Loading_and_Linking.md)
- [04 ExecutionEngine](04_Execution_Engine_Interpreter_JIT_AOT.md)
- [05 NativeBridge](05_Native_Bridge_ANI_and_Interop.md)
- [06 Tooling](06_Tooling_Profiling_Verification.md)
- [07 Build&Config](07_Build_and_Configuration.md)

## 本地预览（MkDocs）

在本目录（`/home/fanzewei/docs/Runtime_Architecture_Internals_and_Developer_Guide`）运行：

```bash
# 如果你本机已经有 mkdocs（例如 ~/.local/bin/mkdocs），可以直接：
mkdocs serve

# 若需要隔离环境（可能会慢/需要网络）：
python3 -m venv .venv
source .venv/bin/activate
pip install -r mkdocs-requirements.txt
mkdocs serve
```

## GitHub Pages 发布

本目录提供了 GitHub Actions workflow（见 `.github/workflows/mkdocs-gh-pages.yml`），会将 `mkdocs.yml` 构建产物发布到 `gh-pages` 分支。

发布前你需要在 GitHub 仓库里做一次设置：

- Settings → Pages → Build and deployment
  - Source: `Deploy from a branch`
  - Branch: `gh-pages` / `(root)`


