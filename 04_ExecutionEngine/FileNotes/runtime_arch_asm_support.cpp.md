# `runtime/arch/asm_support.cpp`（汇编/架构 glue：常量校验 + OSR stub）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：为汇编提供“可被编译器校验的常量/offset”（通过 `static_assert`），并提供少量 `extern "C"` glue（如 `GetCurrentManagedThread`）。**对 OSR 来说，它还定义了非 arm64 平台的 `OsrEntryAfter*` stub 行为。**

## 1) 这个文件为什么重要

很多执行引擎的关键路径最终会落到汇编（bridge/deopt/osr）。一旦 C++ 的结构体 layout / 常量值 与汇编假设不一致，后果通常是：

- 边界帧识别失败（StackWalker 缺帧/错帧）
- TLS/thread 寄存器恢复错位
- deopt/OSR 写回错误（acc/vreg/pc 恢复错）

这个文件用 `static_assert` 把“C++ 的真实 layout”钉死，确保汇编里使用的 offset/常量是可审计且可验证的。

## 2) 关键点：Frame offset 的硬校验

文件里对 `Frame` 的字段 offset 做了人工校验（`FRAME_METHOD_OFFSET/FRAME_PREV_FRAME_OFFSET/FRAME_SLOT_OFFSET`），理由也写得很直白：Frame 本身不是天然 aligned storage，所以要显式检查。

> 这类 assert 一旦触发，通常意味着你改了 `Frame` 的结构体布局，却没同步更新汇编侧的 offset（或生成的 asm_defines）。

## 3) 关键 glue：`GetCurrentManagedThread`

`extern "C" ManagedThread *GetCurrentManagedThread()` 只是一个薄封装：返回 `ManagedThread::GetCurrent()`。

它的意义在于：

- 汇编侧（bridge/osr/deopt）可以在不引入复杂 C++ ABI 的前提下拿到 `ManagedThread*`
- aarch64 OSR 入口会用它恢复 `THREAD_REG`（见 `runtime/arch/aarch64/osr_aarch64.S`）

## 4) 非 arm64 的 OSR 入口：明确是 `UNREACHABLE()`

文件末尾有非常关键的一段：

- 在 `#if !defined(PANDA_TARGET_ARM64)` 下，提供
  - `OsrEntryAfterCFrame(...)`
  - `OsrEntryAfterIFrame(...)`
  - `OsrEntryTopFrame(...)`
- 三个函数体都是 `UNREACHABLE()`（不是返回 false，也不是降级）

> 结论：当你在非 arm64 平台排查“OSR 不触发”时，必须先确认你走到的是不是这组 stub。否则你可能会把时间浪费在 hotness/选项/编译器上，但根因其实是“平台根本没有 OSR 入口实现”。


