# `runtime/interpreter/arch/macros.h`（逐行精读｜dispatch 原语）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 本文件角色：为解释器主循环提供两类“架构相关宏”：
> - `DISPATCH(table, opcode)`：computed-goto 跳转到 handler label
> - `RESTORE_GLOBAL_REGS()`：在支持全局寄存器的架构上恢复寄存器（与 `PANDA_ENABLE_GLOBAL_REGISTER_VARIABLES` 配套）

## 1. ARM64：转发到架构实现（L18–L21）

- **L18–L21**：`PANDA_TARGET_ARM64` 时包含 `aarch64/macros.h`。  
  含义：ARM64 的 dispatch/寄存器恢复可能包含更强的约束或汇编辅助，因此不在通用头中展开。

## 2. 非 ARM64：给出通用实现（L24–L33）

- **L25**：默认 `RESTORE_GLOBAL_REGS()` 为空：多数架构没有全局寄存器恢复的特殊需求。
- **L28–L32**：`DISPATCH` 的核心：
  - 从 `DISPATCH_TABLE[OPCODE]` 取出 label 地址
  - `goto *_label` 直接跳转

> 这是一种经典的“direct threaded code / computed goto”解释器实现方式：  
> 主循环不是 `switch(opcode)`，而是一个 `goto*` 的跳表跳转。  
> 生成的 `ExecuteImpl`（来自 `interpreter-inl_gen.h`）正是围绕该宏组织的。




