# `runtime/interpreter/templates/irtoc_interpreter_utils.h.erb`（逐行精读｜IRTOC/LLVM dispatch table 生成）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 本文件角色：生成 `irtoc_interpreter_utils.h`，提供：
> - `SetupDispatchTableImpl()`：IRTOC fast interpreter 的 dispatch table
> - `SetupLLVMDispatchTableImpl()`：LLVM interpreter 的 dispatch table
>
> 它被 `runtime/interpreter/interpreter_impl.cpp` 在 `PANDA_WITH_IRTOC` 下包含，用于把“fast handler 地址数组”传给 IRTOC/LLVM 的执行入口。

## 1. fast handler 符号声明（L23–L61）

- **L24–L42**：特殊的 GN build/amd64 配置下（`PANDA_TARGET_AMD64 && !PANDA_COMPILER_TARGET_X86_64`），把所有 `HANDLE_FAST_*` 定义成 `nullptr`。  
  含义：在某些构建矩阵里 fast interpreter 可能被禁用或不可用，仍需满足链接/编译通过。
- **L44–L60**：正常路径：为每条指令与 prefix 生成 `extern "C" void HANDLE_FAST_<name>()`（以及 `_LLVM` 版本）声明，并补上 `INVALID/EXCEPTION`。

> “FAST handler”通常由 IRTOC/汇编/生成代码提供，而非 C++ `InstructionHandler`。

## 2. `SetupDispatchTableImpl`：返回 `void*` 给 fast 解释器（L63–L79）

- **L66–L77**：生成一个 `static const std::array<void(*)(), N>`：
  - 元素为 `&HANDLE_FAST_<name>`（或某些配置下不取地址）
  - 最后一个元素是 `HANDLE_FAST_EXCEPTION`
- **L78**：返回 `dispatch_table.data()`（强转 `void*`）：匹配 fast interpreter ABI。

## 3. `SetupLLVMDispatchTableImpl`：LLVM 版本（L81–L97）

- 与上同理，只是符号名使用 `_LLVM` 后缀，异常入口为 `HANDLE_FAST_EXCEPTION_LLVM`。




