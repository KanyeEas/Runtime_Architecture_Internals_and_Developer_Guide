# `compiler/aot/aot_manager.cpp`（逐行精读｜加载与一致性校验实现）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：实现 `AotManager`：加载 `.an`、构建 panda file 映射、维护 snapshot，并在 CHA 开启时校验 class context。

## 1) `AddFile`：加载 `.an` 并注册其中的 panda files

关键步骤：

- **去重**：已存在则直接返回
- **打开 `.an`**：`AotFile::Open(fileName, gcType)`
- **patch/GOT 初始化**：若 `runtime != nullptr`：
  - `PatchTable(runtime)`
  - `InitializeGot(runtime)`
- **注册文件**：
  - 把 `AotFile` 放入 `aotFiles_`
  - 遍历 `FileHeaders()`，把每个 `pfName` 注册到 `filesMap_`（`pfName -> AotPandaFile`）
  - `force` 为 true 时允许覆盖（用于“强制必须有 .an”的场景）

> 这给新同学一个明确结论：**runtime 加载 `.an` 的本质，就是把 `.an` 当作动态库加载，然后完成“intrinsic/entrypoints patch + panda file 映射注册”。**

## 2) `UpdatePandaFilesSnapshot(pf, ctx, isArkAot)`：把已加载文件纳入 snapshot

- ArkAot 模式：把 `<fileName, (pf,ctx)>` 直接 push 进 `pandaFilesSnapshot_`
- 非 ArkAot：先记入 `pandaFilesLoaded_`，再调用 `UpdatePandaFilesSnapshot(isArkAot, true, true)` 用 class context 生成 snapshot

## 3) `UpdatePandaFilesSnapshot(isArkAot, ...)`：从 class context 生成 snapshot

实现提供了一个重要细节：class context 是一个“用 delimiter 分隔的字符串”，同时还包含 `HASH_DELIMETER`：

- `parseClassContext` 会在每个条目里找到 `HASH_DELIMETER`，取其前半段作为文件名 key
- snapshot 中每个条目会绑定到 loadedFiles 中已存在的 `(pf, ctx)`，否则绑定 `(nullptr, nullptr)`

> 这就是为什么 class context 错了会导致 AOT 无法启用：snapshot index 空间建立在这个字符串的解析之上。

## 4) `GetPandaFileSnapshotIndex` / `GetPandaFileBySnapshotIndex`

这俩函数提供了“string -> index -> pf”的双向映射，供 compiler/runtime 共用。

## 5) `VerifyClassHierarchy`：AOT context 校验（失败直接终止）

- 合并 boot/app context，形成 runtime 的“complete context”
- 对每个 `.an`：
  - 若 `withCha`：要求 `aotFile->GetClassContext()` 是 runtime context 的前缀
  - 否则：要求 AOT context 被 runtime context 包含
- 失败会打印 runtime context 与 aot context 并 `LOG(FATAL)` 终止




