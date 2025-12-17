# `plugins/ets/runtime/ets_class_linker_context.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：ETS 的 `ClassLinkerContext` 实现：把“类加载域”绑定到一个 **managed RuntimeLinker（AbcRuntimeLinker 等）**，并提供：LoadClass/枚举 panda files/链式枚举/获取 file paths。

## 1. 关键设计：context 持有 RuntimeLinker 的弱引用（L33–L39）

构造函数 `EtsClassLinkerContext(EtsRuntimeLinker *runtimeLinker)`：
- 继承 `ClassLinkerContext(SourceLang::ETS)`（L33）
- 通过 `PandaEtsVM::GetCurrent()->GetGlobalObjectStorage()` 获取全局对象存储
- 把 `runtimeLinker->GetCoreType()` 以 **WEAK 引用** 存入 object storage（L35–L38）
  - 目的：**不阻止 managed RuntimeLinker 被 GC 回收**（context 不应成为强根）
  - 后续通过 `GetRuntimeLinker()` 动态解引用取回

析构（L44）会把该 weak ref 从 object storage 移除（实现见 `.cpp`）。

## 2. 对外 override：LoadClass + panda files 枚举（L48–L67）

- `LoadClass(descriptor, needCopyDescriptor, errorHandler)` override（L48–L50）：
  - 语义：按对应 RuntimeLinker 的加载规则解析类（native 先行，必要时调用 managed 实现）。
- `EnumeratePandaFiles(cb)`（L52）：
  - 枚举当前 context 对应的 abc files（实现见 `.cpp`）。
- `EnumeratePandaFilesInChain(cb)`（L54）：
  - 链式枚举：沿 parent linker chain 向上遍历后再枚举当前 context（实现见 `.cpp`）。
- `GetPandaFilePaths()`（L56–L64）：
  - 基于 `EnumeratePandaFiles` 把 `pf.GetFilename()` 收集成列表（供 dump/AOT class context）。
- `FindAndLoadClass(descriptor, errorHandler)`（L66–L67）：
  - 在当前 context 的 panda files 中查找并直接调用 core `ClassLinker::LoadClass(pf, classId, this, handler)`。
  - 这是 native 路径“最后一步实际加载”。

## 3. GetRuntimeLinker：从 weak ref 解引用（L69–L74）

`GetRuntimeLinker()`：
- 从 global object storage 取回 `refToLinker_` 指向的 core 对象
- `EtsRuntimeLinker::FromCoreType(linker)` 转回 ETS 包装类型
- ASSERT linker 非空（意味着：context 被使用时 RuntimeLinker 必须仍然存活）

> 这套设计把“context 生命周期”与“managed RuntimeLinker 生命周期”解耦：  
> - context 不强持有 linker  
> - 但在使用时要求 linker 存活（否则属于逻辑错误）

## 4. 并发保护：abcFilesMutex_（L76–L98）

- `GetAbcFilesMutex()` 返回 `abcFilesMutex_`（递归 mutex）。
- 结合 `.cpp` 中对 `GetAbcFiles()` 的访问，可推断：  
  **abc files 列表在 ETS 侧可能并发更新，需要一个互斥量保护遍历/修改。**

## 5. 私有辅助（L81–L93）

- `TryLoadingClassFromNative(...)`：尝试沿 AbcRuntimeLinker chain 找/加载类（不调用 managed 实现）。
- `EnumeratePandaFilesImpl(cb)`：实际枚举实现，供 `EnumeratePandaFiles` 与 `FindAndLoadClass` 复用。

## 6. 字段（L96–L98）

- `abcFilesMutex_`：保护 abc files 相关访问（递归，匹配链式遍历可能的重入）。
- `refToLinker_`：weak ref 指针（object storage 条目）。


