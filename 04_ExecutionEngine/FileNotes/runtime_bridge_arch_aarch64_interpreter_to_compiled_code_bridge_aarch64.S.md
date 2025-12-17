# `runtime/bridge/arch/aarch64/interpreter_to_compiled_code_bridge_aarch64.S`（逐行精读｜I2C 物理落地）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：aarch64 上的 **I2C（Interpreter→Compiled）** 桥接：从解释器侧输入 `(insn, iframe, method, thread)` 出发，构造 I2C boundary frame（`INTERPRETER_TO_COMPILED_CODE_BRIDGE` 或 `BYPASS_BRIDGE`），按 shorty 把解释器 vregs/acc 拆装到真实 ABI 位置（x0-x7 / d0-d7 / stack），调用 `method->compiled_entrypoint`，并按 shorty 将返回值写回 `frame->acc`（以及 mirror/tag）。

## 1) boundary frame：`INTERPRETER_TO_COMPILED_CODE_BRIDGE` vs `BYPASS_BRIDGE`

文件在入口处明确注释了 bridge frame 的结构（关键在“marker slot”）：

- `lr`
- `iframe <- fp`
- `INTERPRETER_TO_COMPILED_CODE_BRIDGE/BYPASS_BRIDGE`
- `fp`
- `THREAD_REG`
- `x19 <- sp`

随后根据 `MANAGED_THREAD_FRAME_KIND_OFFSET(thread)` 选择 marker：

- 若 caller 在 compiled 侧：写 `BYPASS_BRIDGE`
- 否则：写 `INTERPRETER_TO_COMPILED_CODE_BRIDGE`

> 这就是 StackWalker/FrameKind 的“分岔点”：marker 决定“跨边界”的解码语义。

## 2) shorty 驱动的参数装配：PrepareArgStack + dispatch handlers

### 2.1 shorty 初始化与 instance 方法 hack

- `method.shorty` 来自 `METHOD_SHORTY_OFFSET`，通过 `INIT_SHORTY_REG` 初始化 shorty 状态机。
- instance 方法 `this` 不在 shorty 中编码：这里会 **hack shorty**（把 return nibble 替换成 `REF`）来占位 `this`。

### 2.2 `PrepareArgStack` 预留 ABI 传参空间

调用 `PrepareArgStack` 后，文件把寄存器设置为：

- x9：arg base ptr（GPR/FPR args 的 base）
- x10：GPR arg ptr
- x4：FPR arg ptr
- x3：stack arg ptr

并先把 `Method*` 写入第一个 GPR 参数槽（最终落到 x0）。

### 2.3 `bridge_dispatch_aarch64.S`：按 call-format 组装实参

I2C 需要根据“当前 bytecode 的 call 指令格式”从 `iframe->vregs` 取出实际实参。

这里的分发不是解释器 dispatch，而是 **call-format dispatch**：

- 先读取 opcode（含 prefix opcode）
- 进入 `.Ldispatch` 并 `#include "bridge_dispatch_aarch64.S"`
- 各 handler 负责把“从 vregs/imm 提取的参数”用 shorty/type 规则写入 GPR/FPR/stack 三类参数区
- 最终跳到统一的 `.Lload_reg_args`

> `bridge_dispatch_*.S` 由 `runtime/templates/bridge_dispatch.S.erb` 生成，并进一步依赖各 `handle_call_<format>.S`。

## 3) `.Lload_reg_args`：把准备好的 args 装入 x0-x7 / d0-d7

在 `.Lload_reg_args` 汇总点：

- `LOAD_FPR_ARGS`：把浮点参数从预留区装入 d0-d7
- `LOAD_GPR_ARGS`：把整数/指针参数从预留区装入 x0-x7
- `mov sp, x9`：把 sp 复位到 stack args 区，满足 ABI 调用约定

## 4) 调用 compiled entrypoint

- `ldr lr, [lr, #METHOD_COMPILED_ENTRY_POINT_OFFSET]`
- `blr lr`

其中 `lr` 在前面被复用为 `Method*`（注释中明确）。

## 5) 返回值写回：写回 `acc`（含 tag/mirror）

根据 `shorty[0] & 0xF` 判断返回类型：

- `void`：不写回
- `float/double`：从 d0 取位模式并写回
- 其它（含 `reference` 与 `tagged(any)`）：从 x0/x1 组合写回 `acc` 与 mirror/tag

这保证解释器侧在返回后能继续以 “acc 协议” 工作（并与 GC/异常语义一致）。

## 6) 与本章其他证据的连接点

- 概念/逻辑：[Bridge_I2C_C2I（Flow）](../Flows/Bridge_I2C_C2I.md)
- FrameKind/边界语义：[Bridge_ABI_and_FrameKind（DataStructure）](../DataStructures/Bridge_ABI_and_FrameKind.md)
- amd64 对照实现：`runtime/bridge/arch/amd64/interpreter_to_compiled_code_bridge_amd64.S`（对应 FileNote 已有）


