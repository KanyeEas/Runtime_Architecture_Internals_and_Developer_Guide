# `compiler/aot/aot_manager.h`（逐行精读｜AOT 文件集合与 snapshot/index）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：`AotManager` 管理一组已加载的 `.an` 文件，并提供：按文件名查找、按 class context 校验、维护 panda files snapshot（供 compiler/runtime 共享索引空间）、以及 AOT string roots 的 GC 访问接口。

## 1) `AotManager` 的职责边界

可以把它理解为三件事：

- **文件级**：加载/保存多个 `AotFile`
- **映射级**：把 `panda file name -> AotPandaFile` 做成快速 map
- **一致性级**：维护 class context 与 snapshot index，保证 runtime 与 compiler 对“文件集合”的认知一致

## 2) `.an` 文件管理：`AddFile/GetFile/FindPandaFile`

- `AddFile(fileName, runtime, gcType, force)`：加载 `.an` 并把其包含的 panda files 注册进 map
- `GetFile(fileName)`：按 `.an` 文件名查找已加载文件
- `FindPandaFile(fileName)`：按 `.abc` 文件名查找它在 AOT 中对应的 `AotPandaFile`

## 3) class context：为什么它是 AOT 能否启用的“地基”

### 3.1 `SetBootClassContext/SetAppClassContext`

两者都会：

- 存下字符串（`bootClassContext_` / `appClassContext_`）
- 解析 context 到内部集合（`ParseClassContextToFile`）
- 调 `UpdatePandaFilesSnapshot(isArkAot, ...)` 让 snapshot 与当前 context 对齐

### 3.2 `VerifyClassHierarchy()`

用于校验 AOT 文件的 class context 与运行时当前 context 是否匹配：

- 若 AOT 是 `withCha`：要求 AOT context 必须是 runtime context 的前缀（更严格）
- 否则：要求 AOT context 被 runtime context 包含（较宽松）

失败时会打印两边 context 并 `LOG(FATAL)` 终止（这是正确的：错 context 会导致类型解析/虚方法分派假设失效）。

## 4) snapshot/index：compiler 与 runtime 的“共同语言”

### 4.1 `UpdatePandaFilesSnapshot(pf, ctx, isArkAot)`

- 用于同步“已加载 panda files”的可见集合（`pandaFilesLoaded_` / `pandaFilesSnapshot_`）；
- 在非 ArkAot 模式下，会把 loaded 文件集合与 boot/app class context 合并生成 snapshot。

### 4.2 `GetPandaFileSnapshotIndex(fileName)` / `GetPandaFileBySnapshotIndex(index)`

这是把“文件名”映射到一个稳定整数 index 的关键 API，供 `runtime/compiler.cpp` 暴露给 compiler 使用。

> 重要：这也是 03→04 的典型交界——class loading 决定“有哪些 panda files 在当前 context”，AOT/编译器需要把它们编号成可缓存的索引空间。

## 5) AOT string roots：让 GC 能访问 AOT 里的字符串引用

- `RegisterAotStringRoot(ObjectHeader **slot, bool isYoung)`
- `VisitAotStringRoots(cb, visitOnlyYoung)`
- `UpdateAotStringRoots(cb, predicate)`

这里用 bitset（`aotStringYoungSet_`）记录“young roots”，并用 atomic counter（`aotStringGcRootsCount_`）减少锁竞争。




