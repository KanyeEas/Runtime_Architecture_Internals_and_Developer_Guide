# `plugins/ets/runtime/ets_native_library.cpp`（逐行精读）

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：实现 `EtsNativeLibrary::Load` 与构造函数，基本是对 `os::library_loader::Load` 的异常/错误包装。

## 1. `EtsNativeLibrary::Load`（L19–L27）

- **L21**：`auto handle = os::library_loader::Load(name)`：尝试加载动态库。
- **L22–L24**：失败则 `Unexpected(handle.Error())`：把 OS 错误原样上抛。
- **L26**：成功则构造 `EtsNativeLibrary(name, std::move(handle.Value()))`。

> 上层 `NativeLibraryProvider` 会把这个 `os::Error` 转为 string，并进一步决定是否需要 namespace fallback。

## 2. 构造函数：移动 name 与 handle（L29–L32）

- `name_` 与 `handle_` 都采用 move 语义，确保 `EtsNativeLibrary` 是一个“拥有 handle 所有权”的值类型。



