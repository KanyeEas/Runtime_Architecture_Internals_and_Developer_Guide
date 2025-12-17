# `plugins/ets/runtime/ets_class_linker.h`（逐行精读｜ETS façade：把 ClassLinker 变成 EtsClass API）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件规模：75 行  
> 目标：解释 ETS 为何需要一个“门面（façade）类”包裹 `ClassLinker`：对外暴露 `EtsClass*` 语义、隐藏 `ClassLinkerExtension` 转换，并补充 ETS 特有的 async 注解解析入口（实现见 `.cpp`）。

## 0. include 与前置声明（L19–L29）

- 引入 `ets_class_root.h`（ETS 自己的 root 枚举）。
- 引入 panda smart pointers/string/containers（Expected/PandaUniquePtr/PandaString 等）。
- 前置声明 core runtime 类型：`Method/ClassLinker/ClassLinkerContext/ClassLinkerErrorHandler`。

## 1. `EtsClassLinker`：对外 API（L37–L55）

- **L39**：`Create(ClassLinker*) -> Expected<PandaUniquePtr<EtsClassLinker>, PandaString>`
  - 采用 Expected 返回，便于未来扩展错误路径（当前实现基本不会失败）。
- **L42–L43**：`Initialize()`：把 `classLinker_` 中 ETS extension 缓存到 `ext_`（见 cpp）。
- **L44**：`InitializeClass(EtsCoroutine*, EtsClass*)`：对外把 runtime `InitializeClass` 暴露给 ETS。
- **L45**：`GetClassRoot(EtsClassRoot)`：返回 `EtsClass*`。
- **L46–L53**：两种 GetClass（按 name 或按 pf+id）与 `GetMethod`（按 pf+id）。
- **L54**：`GetAsyncImplMethod(Method*, EtsCoroutine*)`：ETS async 注解解析入口（非常 ETS-specific）。

## 2. 内部状态与语义（L64–L71）

- `classLinker_`：底层 runtime `ClassLinker*`（不 owned）。
- `ext_`：`EtsClassLinkerExtension*`（不 owned），由 `Initialize()` 解析得到。
- `friend class mem::Allocator`：允许 `MakePandaUnique`/allocator 构造。

## 结论

`EtsClassLinker` 不是 ClassLinker 的“替代品”，而是 **ETS 的类型系统视角**：
- 输入/输出尽可能是 `EtsClass*`，把 `Class*` 的细节藏到 extension 转换里。
- 提供一个额外的 ETS-specific 工具入口：async 注解 → impl method。

## 证据链

- 实现：[FileNotes/plugins_ets_runtime_ets_class_linker.cpp](plugins_ets_runtime_ets_class_linker.cpp.md)
- ETS extension：[FileNotes/plugins_ets_runtime_ets_class_linker_extension.cpp](plugins_ets_runtime_ets_class_linker_extension.cpp.md)


