# `build/runtime/include/irtoc_interpreter_utils.h`（逐行精读｜生成的 dispatch table（IRTOC vs LLVM））

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件属性：**build 生成物**（由 `runtime/interpreter/templates/irtoc_interpreter_utils.h.erb` 等模板生成）  
> 本文件角色：
> - 声明所有 `HANDLE_FAST_*` 与 `HANDLE_FAST_*_LLVM` 符号（`extern "C"`）
> - 提供两个构造函数：
>   - `SetupDispatchTableImpl()`：IRTOC backend 表
>   - `SetupLLVMDispatchTableImpl()`：LLVM backend 表
> - 两张表的规模固定为 **392**，并返回 `dispatch_table.data()`（给 `ExecuteImplFast*` 使用）

## 1. `HANDLE_FAST_*` 声明（大量）

文件上半部分基本是：

- `extern "C" void HANDLE_FAST_<OPNAME>();`
- `extern "C" void HANDLE_FAST_<OPNAME>_LLVM();`

不同平台会有 `#if defined(PANDA_TARGET_AMD64) && !defined(PANDA_COMPILER_TARGET_X86_64)` 等 guard；在某些组合下会把 handler 定义为 `static constexpr ... = nullptr;`（用于“构建了头，但本配置不提供实现”的占位）。

## 2. `SetupDispatchTableImpl()`：IRTOC backend dispatch table（约 L1387 起）

核心结构：

- `static const std::array<void (*)(), 392> dispatch_table { ... };`
- 按 opcode 顺序依次填入 `HANDLE_FAST_*`
- 最后返回：`(void*)dispatch_table.data()`

> 这意味着 fast interpreter 的 dispatch 只需要 `opc` 做索引，就能获得 `HANDLE_FAST_*` 的入口地址。

### 2.1 重要细节：最后一个 slot 是异常入口

表尾部可以看到：

- `..., &HANDLE_FAST_EXCEPTION`

这与 `interpreter.irt` 的 `move_to_exception` 完全对齐：它用 `Load(table, handler_names.size * 8)` 取“最后一项”，再 tail-call 到异常 handler。

## 3. `SetupLLVMDispatchTableImpl()`：LLVM backend dispatch table（约 L2181 起）

结构与 IRTOC backend 相同，但每个符号都带 `_LLVM` 后缀：

- `HANDLE_FAST_MOV_V4_V4_LLVM`
- ...
- 表尾部同样是 `HANDLE_FAST_EXCEPTION_LLVM`

运行时选型见：`runtime/interpreter/interpreter_impl.cpp::ExecuteImplType`：

- `--interpreter-type=irtoc` → `SetupDispatchTableImpl()`
- `--interpreter-type=llvm` → `SetupLLVMDispatchTableImpl()`

## 4. 这份生成物与 build/irtoc 产物如何对齐

- 本文件负责“**dispatch table 组装**”（函数指针数组）。
- `build/irtoc/irtoc_interpreter/irtoc_code.cpp` 负责把 `interpreter.irt.fixed` 里的 `HANDLE_FAST_*` 变成“可编译/可链接”的机器码（`COMPILE(HANDLE_FAST_*)`）。


