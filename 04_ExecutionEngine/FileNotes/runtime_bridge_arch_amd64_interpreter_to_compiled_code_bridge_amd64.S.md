# `runtime/bridge/arch/amd64/interpreter_to_compiled_code_bridge_amd64.S`（逐行精读｜I2C 物理落地）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：amd64 上的 **I2C（Interpreter→Compiled）** 桥接：把解释器侧的 `(insn, Frame*, Method*, thread)` 转成 **真实 SysV ABI** 的参数布局并调用 compiled entrypoint，同时构造 I2C boundary frame 供 StackWalker/异常/去优化跨边界识别。

## 1) 你要先记住的“桥接输入/输出”

函数签名（注释）：

- `InterpreterToCompiledCodeBridge(insn, iframe, method, thread)`

桥接的职责：

- **构造 I2C boundary frame**（压入 `INTERPRETER_TO_COMPILED_CODE_BRIDGE` 或 `BYPASS_BRIDGE`）  
  让“解释器栈 → 编译栈”的边界在 unwind 时可见。
- **按 shorty 把参数搬运到 ABI 约定位置**：GPR（`rdi..r9`）、FPR（`xmm0..xmm7`）、以及 stack args。
- **调用 `method->compiled_entrypoint`**，并把返回值按 shorty 写回到解释器帧的 `acc`（含 tagged 的 tag）。

## 2) boundary frame：为什么要 `INTERPRETER_TO_COMPILED_CODE_BRIDGE/BYPASS_BRIDGE`

入口处逻辑：

- 先把 `iframe*` 压栈
- 根据 `MANAGED_THREAD_FRAME_KIND_OFFSET(thread)` 判断当前是否在 compiled 侧，决定压入：
  - `INTERPRETER_TO_COMPILED_CODE_BRIDGE`
  - 或 `BYPASS_BRIDGE`（表示“不是传统跨边界”的语义，StackWalker 需要特殊处理）

这对应 Stage2 文档里的核心不变量：**FrameKind/boundary marker 必须可识别**，否则 StackWalker 会走错解码路径。

## 3) shorty → ABI：参数搬运的核心套路

本文件提供三类关键宏：

- `PREPARE_ARG_STACK`：扫描 shorty，预留 stack/gpr/fpr 三段空间，并保证 16-byte 对齐  
  目标是得到 `%r8` 作为 “reg args base”，以及 `%rsp` 指向 stack args 区域。
- `PUSH_ARG`：对单个参数，根据 shorty 类型写入 gpr/fpr/stack，并处理 `any(tagged)` 的“value+tag 双槽”。
- `LOAD_GPR_ARGS/LOAD_FPR_ARGS`：在 `.Lload_reg_args` 汇总点，把准备好的 args 真正装入寄存器（GPR+XMM）。

重要细节：

- `Method*` 被作为第一个参数固定写进 gpr args 区（最终落到 `%rdi`）。
- instance 方法的 `this` 不在 shorty 中编码，本文件会“hack shorty”：把返回类型位替换成 `REF` 来占位。

## 4) dispatch：为什么这里会 `#include bridge_dispatch_amd64.S`

桥接需要知道“从解释器帧里读哪些 vreg/imm/id16”来组装实参，这与 opcode format 强相关。

- 这里的 dispatch 不是解释器 dispatch，而是 **call 指令/调用格式**的 dispatch。
- `#include "bridge_dispatch_amd64.S"` 来自模板 `runtime/templates/bridge_dispatch.S.erb`，并进一步跳到
  `handle_call_<format>.S` 这些实现文件（本目录下可见）。

> 这也是为什么新引入 call format 时可能编译失败：提示你缺少对应 `handle_call_*` 处理器。

## 5) invoke + 返回值写回

关键点：

- 调用：`mov METHOD_COMPILED_ENTRY_POINT_OFFSET(%rdi), %rax; callq *%rax`
- 返回值：
  - 依据 `shorty[0] & 0xF` 判断返回类型
  - `void`：不写回
  - `float/double`：从 `%xmm0` 获取
  - `tagged(any)`：value 在 `%rax`，tag 在 `%rdx`（或按分支构造），写回 `frame->acc`（以及 mirror/tag）

## 6) 与本章其他证据的连接点

- 概念/逻辑：`Flows/Bridge_I2C_C2I.md`
- FrameKind/边界语义：`DataStructures/Bridge_ABI_and_FrameKind.md`
- C++ 骨架与 acc 写回语义：`FileNotes/runtime_bridge_bridge.cpp.md`
- 相关生成文件（call-format dispatch）：
  - 模板：`runtime/templates/bridge_dispatch.S.erb`
  - 逐行笔记：[FileNotes/runtime_templates_bridge_dispatch.S.erb.md](runtime_templates_bridge_dispatch.S.erb.md)



