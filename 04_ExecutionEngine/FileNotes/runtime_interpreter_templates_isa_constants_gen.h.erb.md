# `runtime/interpreter/templates/isa_constants_gen.h.erb`（逐行精读｜ISA 常量生成）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 本文件角色：生成 `<isa_constants_gen.h>`，为解释器 dispatch table 提供 **编译期常量**（prefix 数量、非 prefix opcode 数量、边界校验）。

## 1. 常量定义（L19–L25）

- **L20**：`NUM_PREFIXED`：ISA 中“prefix 指令”的数量（来自 ISA 描述 `Panda::instructions.select(&:prefix)`）。
- **L21**：`NUM_NON_PREFIXED_OPS`：非 prefix opcode 数量（并 **+1** 给 `EXCEPTION_HANDLER` 预留一个 slot）。
- **L22**：`NUM_PREFIXES`：prefix 的种类数（`Panda::prefixes.size`）。
- **L24**：`static_assert`：限制 first-level dispatch 的 opcode 总数（非 prefix + prefixes）不超过 210。  
  含义：解释器使用“二级 dispatch”（prefix + secondary opcode）的布局；该断言为生成/布局提供上界保证。

## 2. 被谁消费？

- `runtime/interpreter/instruction_handler_base.h` 使用 `NUM_PREFIXED` 来计算异常 opcode 的 extension 值。
- `runtime/interpreter/templates/interpreter-inl_gen.h.erb` 使用 `NUM_PREFIXED` 来计算 `DISPATCH_TABLE_LEN = 256 + NUM_PREFIXED + 1`，并把最后一个 slot 用作 `EXCEPTION_HANDLER`。




