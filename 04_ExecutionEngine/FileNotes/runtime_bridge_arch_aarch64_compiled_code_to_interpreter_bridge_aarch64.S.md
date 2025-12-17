# `runtime/bridge/arch/aarch64/compiled_code_to_interpreter_bridge_aarch64.S`（逐行精读｜C2I 物理落地）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：aarch64 上的 **C2I（Compiled→Interpreter）** 桥接：构造 `COMPILED_CODE_TO_INTERPRETER_BRIDGE` boundary frame、保存 callee-saved 并把 boundary 写入 TLS（保障 safepoint/StackWalker 可见），随后走 “编译成功直跳 / 未编译创建 IFrame + 进入 InterpreterEntryPoint” 两分支，最后从 `acc/acc_mirror` 还原返回寄存器并返回给 compiled caller。

## 1) 入口：构造 `COMPILED_CODE_TO_INTERPRETER_BRIDGE` boundary frame

文件内直接给出了 bridge frame 形态：

- `lr`
- `COMPILED_CODE_TO_INTERPRETER_BRIDGE`
- `fp  <- fp`
- `==  <- sp`

对应实现（可对照源文件顶部 `CompiledCodeToInterpreterBridge:`）：

- `sub sp, sp, #32` + `str lr, [sp, #24]`
- `mov lr, #COMPILED_CODE_TO_INTERPRETER_BRIDGE`
- `stp fp, lr, [sp, #8]`，并 `add fp, sp, #8` 建立 frame pointer

## 2) 保存 callee-saved + 写 TLS（关键不变量）

### 2.1 保存 callee-saved 的原因

注释与 amd64 版本一致：**StackWalker unwind 会读取这些寄存器保存区**。本文件用 `PUSH_CALLEE_REGS sp` 保存了 x19-x28 与 d8-d15，并配套 CFI。

### 2.2 调用 `DecrementHotnessCounter` 前写 TLS

关键证据点：

- `str fp, [THREAD_REG, #MANAGED_THREAD_FRAME_OFFSET]`

理由（文件注释）：编译过程可能进入 safepoint；如果这时 GC/StackWalker 需要遍历栈，必须能看到 caller 的 callee-saved（它们已被 C2I 保存到栈里）。

## 3) 热度计数/触发编译：成功则直接 `br entrypoint`

当 `DecrementHotnessCounter` 返回非 0：

- 恢复 TLS：`ldr lr, [fp] ; str lr, [THREAD_REG, #MANAGED_THREAD_FRAME_OFFSET]`
- 恢复寄存器与栈：`POP_ARGS_VREGS/POP_CALLER_REGS` + 恢复 `fp/lr` + `add sp, sp, #32`
- 直接跳转到 compiled：`ldr x16, [x0, #METHOD_COMPILED_ENTRY_POINT_OFFSET] ; br x16`

> 这解释了“为什么 C2I 看起来像一个函数，却常常以 `br entrypoint` 的方式离开”：桥内把控制权直接交给最新的 compiled entrypoint。

## 4) 未编译：创建 `IFrame` 并按 shorty 搬运参数

在 `.Lnot_compiled` 分支：

- 先把参数寄存器（x0-x7 / d0-d7）保存到栈，作为后续“ABI 参数区”的稳定来源。
- 调 `CreateFrameForMethod(method, prev)` 创建解释器 `Frame*`：
  - `prev` 取当前 `fp`（即 C2I boundary frame）
- 初始化 shorty（`METHOD_SHORTY_OFFSET` + `INIT_SHORTY_REG`），并按 shorty 逐个参数把值写入 `frame->vregs_`：
  - 参数来源：GPR/FPR/stack 三路（由计数器 w6/w7 决定）
  - 引用参数会写入 tag（通过对比 `SHORTY_REFERENCE` 产生 tag=1）
  - instance 方法会 “hack shorty”：把 return type nibble 替换为 `REF` 来占位 `this`

## 5) 进入解释器与返回值还原（返回给 compiled caller）

- 进入解释器：`InterpreterEntryPoint(method, iframe)`
- 返回值还原：从 `iframe->acc_`（以及 mirror/tag）读取，并按 `shorty[0] & 0xF`：
  - `void`：`FreeFrame` 后直接返回
  - `reference`：返回 `(x0=value, x1=tag)`（32-bit managed ptr 下清高 32 位）
  - `int/long/tagged(any)`：返回 `(x0=value, x1=tag)`
  - `float/double`：`fmov d0, x19`（把 acc 的位模式搬到浮点返回寄存器）
- 最后恢复 callee-saved 与 `fp/lr`，`ret`

## 6) 与本章其他证据的连接点

- 概念/逻辑流：`Flows/Bridge_I2C_C2I.md`
- FrameKind/边界语义：`DataStructures/Bridge_ABI_and_FrameKind.md`
- amd64 对照实现：`runtime/bridge/arch/amd64/compiled_code_to_interpreter_bridge_amd64.S`


