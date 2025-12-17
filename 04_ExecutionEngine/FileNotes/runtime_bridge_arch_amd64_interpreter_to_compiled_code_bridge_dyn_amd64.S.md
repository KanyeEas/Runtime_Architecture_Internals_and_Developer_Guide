# `runtime/bridge/arch/amd64/interpreter_to_compiled_code_bridge_dyn_amd64.S`（逐行精读｜I2C(Dyn) 物理落地）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：amd64 上的 **I2C（Dynamic calling convention）**：为动态语言/TaggedValue 语义提供解释器→编译桥接。入口仍是 `(insn, iframe, method, thread)`，会写入 `INTERPRETER_TO_COMPILED_CODE_BRIDGE/BYPASS_BRIDGE` marker，并通过 `bridge_dispatch_dyn_amd64.S`（模板生成）按 opcode format 组装参数，调用 `method->compiled_entrypoint`，最后把返回值写回 `frame->acc`。

## 1) boundary marker 规则与静态版一致

入口根据 `MANAGED_THREAD_FRAME_KIND_OFFSET(thread)`：

- 默认写 `INTERPRETER_TO_COMPILED_CODE_BRIDGE`
- 若 caller 在 compiled 侧则写 `BYPASS_BRIDGE`

目的：让 StackWalker 能在 IFrame/CFrame 两套解码规则之间正确切换。

## 2) dyn dispatch：`bridge_dispatch_dyn_amd64.S`

该文件读取 opcode（含 prefix opcode）并：

- `#include "bridge_dispatch_dyn_amd64.S"`
- 注释明确：由 `runtime/templates/bridge_dispatch.S.erb` 生成，并依赖 `handle_call_<format>.S`

> 这条证据链很实用：新增 call format 时，缺 handler 会在这里暴露为编译错误。

## 3) 调用 compiled entrypoint 与写回 acc

- 调用：`movq METHOD_COMPILED_ENTRY_POINT_OFFSET(%rdi), %rax ; callq *%rax`
- 写回：`movq %rax, (frame->acc)`（文件中 `movq %rax, (%r12)`）

dyn 版不以 shorty 决定返回类型寄存器（统一走 TaggedValue 语义：value+tag）。

## 4) 对照与链接

- 静态 I2C（shorty 驱动）对照：`runtime/bridge/arch/amd64/interpreter_to_compiled_code_bridge_amd64.S`
- dyn C2I（配套回退路径）：`runtime/bridge/arch/amd64/compiled_code_to_interpreter_bridge_dyn_amd64.S`
- 概念/逻辑：[Bridge_I2C_C2I（Flow）](../Flows/Bridge_I2C_C2I.md)


