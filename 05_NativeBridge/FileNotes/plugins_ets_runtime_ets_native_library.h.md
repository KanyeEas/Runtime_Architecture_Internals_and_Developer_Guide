# `plugins/ets/runtime/ets_native_library.h`（逐行精读）

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：对 `dlopen/dlsym`（通过 `os::library_loader`）的薄封装：`EtsNativeLibrary`。  
> `NativeLibraryProvider` 用它作为 `libraries_` 集合元素，实现：
> - 加载 so（`Load`）
> - 解析符号（`FindSymbol`）
> - 以 `LibraryHandle` 的 native handle 做严格排序（用于 `PandaSet` 去重/稳定存储）

## 0. includes（L19–L20）

- **L19**：`PandaString`：库名与符号名使用 runtime 自有字符串类型。
- **L20**：`library_loader.h`：跨平台动态库加载与符号解析封装。

## 1. `Load`：返回 `Expected<Library, os::Error>`（L25）

- 与 `NativeLibraryProvider` 的错误处理风格一致：失败返回 `os::Error`，上层转成 string 或继续处理。

## 2. 核心状态：name + handle（L27–L51）

- **L27**：构造函数接收 `name` 与 `LibraryHandle`（右值引用）以转移所有权。
- **L38–L41**：`FindSymbol`：调用 `os::library_loader::ResolveSymbol(handle_, name)`。
- **L43–L46**：`operator<`：按 `handle_.GetNativeHandle()` 排序。  
  这意味着 `PandaSet<EtsNativeLibrary>` 的“唯一性/排序”是基于**真实的 OS handle**，而不是库名；同名库若被不同方式加载可能仍是不同 handle（但 provider 上层会按 name 做一次幂等去重）。



