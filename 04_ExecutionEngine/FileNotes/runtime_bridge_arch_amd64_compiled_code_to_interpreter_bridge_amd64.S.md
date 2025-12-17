# `runtime/bridge/arch/amd64/compiled_code_to_interpreter_bridge_amd64.S`（逐行精读｜C2I 物理落地）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：amd64 上的 **C2I（Compiled→Interpreter）** 桥接：在 compiled 调用点构造 `COMPILED_CODE_TO_INTERPRETER_BRIDGE` 边界帧，保存 callee-saved（供 StackWalker/GC/异常 unwind），必要时触发（或等待）编译；若仍未编译则创建解释器 `IFrame`、搬运参数并进入 `InterpreterEntryPoint`，最后从 `acc/acc_mirror` 还原返回寄存器并返回给 compiled caller。

## 1) 为什么 C2I 一定要保存 callee-saved 并写 TLS

本文件核心注释非常关键：

- “stack walker will read them during stack unwinding”
- “compilation may fall into safepoint, so we need to make caller's callee registers visible for the stack walker”

对应的汇编证据点（可直接对照 `runtime/bridge/arch/amd64/compiled_code_to_interpreter_bridge_amd64.S`）：

- **保存 return address 到 TLS**：`MANAGED_THREAD_NATIVE_PC_OFFSET(%THREAD_REG)`  
  让 runtime 在 native/compiled 侧能拿到“当前 native PC”（例如异常/采样/诊断）。
- **把 C2I frame 指针写入 TLS**：`movq %rbp, MANAGED_THREAD_FRAME_OFFSET(%THREAD_REG)`  
  发生 safepoint/StackWalker unwind 时，可以从 TLS 找到这条 boundary frame，并读取其保存的 callee-saved。

## 2) 入口：构造 `COMPILED_CODE_TO_INTERPRETER_BRIDGE` boundary frame

关键动作：

- `pushq $COMPILED_CODE_TO_INTERPRETER_BRIDGE`：把 boundary marker 压入栈（StackWalker 的分岔点）
- `pushq %rbp; movq %rsp, %rbp`：建立 frame pointer
- 保存 callee-saved：`r15 r14 r13 r12 rbx`（并配 CFI，便于 unwind）

> 这与本章不变量一致：**边界帧 + callee-saved 可见性**是“跨解释器/编译栈”正确 unwind 的必要条件。

## 3) 热度计数/触发编译：`DecrementHotnessCounter`

### 3.1 为什么“调用 DecrementHotnessCounter 前必须先写 TLS”

本文件在调用 `DecrementHotnessCounter` 前会先：

- `movq %rbp, MANAGED_THREAD_FRAME_OFFSET(%THREAD_REG)`

理由（文件原注释）：编译过程可能进入 safepoint；如果这时 GC/StackWalker 需要遍历栈，必须能看到 caller 的 callee-saved（它们已被 C2I 保存到栈里）。

### 3.2 编译成功：拆除 C2I 并直接跳转到 compiled entrypoint

当 `DecrementHotnessCounter` 返回 `al != 0`：

- 恢复 TLS：`movq (%rbp), %r8; movq %r8, MANAGED_THREAD_FRAME_OFFSET(%THREAD_REG)`  
  （把 thread->frame 指回 caller 的上一帧，C2I 不再是“当前边界”）
- 恢复保存的寄存器（PUSH/POP 宏 + callee-saved）
- **不走 ret**，而是：
  - `movq METHOD_COMPILED_ENTRY_POINT_OFFSET(%rdi), %rax`
  - `jmp *%rax`

> 这一步解释了“为什么 C2I 看起来像一个函数，却常常以 `jmp entrypoint` 的方式离开”：它把控制权直接交给新生成的 compiled code。

## 4) 未编译：创建 `IFrame` + 搬运参数 + 进入解释器

当 `.Lnot_compiled` 分支：

### 4.1 创建解释器帧

- 调 `CreateFrameForMethod(method, prev)`：`prev` 取当前 `%rbp`（也就是 C2I boundary frame）  
  返回的 `Frame*` 保存到寄存器（源码中可见 `%r13`）。

这等价于“在栈上插入一个解释器语义帧 IFrame，并让它的 prev 指向 C2I 边界帧”。

### 4.2 shorty 规则与 instance 方法 “hack”

- shorty 用于描述参数/返回类型，指导“从 ABI 参数位置 → IFrame.vregs”拷贝。
- instance 方法的 `this` 不在 shorty 里编码，所以这里会 **hack shorty**：把 return type nibble 替换为 `REF` 来占位（等价于“把 this 当成第一个参数类型”）。

### 4.3 从 ABI 参数区读参数、写入 `vregs` 与 tag(mirror)

代码会根据 shorty 逐个参数拷贝：

- **来源**：GPR/FPR/stack 三路（通过计数器 `gpr_arg_counter` / `float_arg_counter` 决定取哪一路）
- **目的**：`frame->vregs_` 以及 tag(mirror) 区  
  你能看到“先写 tag 再写 value”的模式（引用类型 tag=1）。

## 5) 进入解释器与返回值还原（返回给 compiled caller）

### 5.1 进入解释器

- `InterpreterEntryPoint(method, iframe)`

解释器执行结束后，返回值会被写入 `iframe->acc_`（以及 mirror/tag）。

### 5.2 从 `acc/acc_mirror` 还原返回寄存器

根据 `shorty[0] & 0xF` 区分返回类型：

- `void`：`FreeFrame` 后不设置返回寄存器
- `reference`：从 `acc` 取 value 放到 `%rax`，tag 放到 `%rdx`（并在 32-bit managed ptr 场景清高 32 位）
- `int/long/tagged(any)`：`acc`→`%rax`，mirror→`%rdx`
- `float/double`：`acc`→`%xmm0`

最后：

- `FreeFrame(iframe)`（释放解释器帧）
- 恢复 callee-saved，ret 回 compiled caller

## 6) 与本章其他证据的连接点

- 概念/逻辑流：`Flows/Bridge_I2C_C2I.md`
- FrameKind/边界语义：[Bridge_ABI_and_FrameKind（DataStructure）](../DataStructures/Bridge_ABI_and_FrameKind.md)
- C++ 骨架（acc 写回、thread 状态位切换点）：`runtime/bridge/bridge.cpp`（本章已有 FileNotes/引用）
- aarch64 对照实现：`runtime/bridge/arch/aarch64/compiled_code_to_interpreter_bridge_aarch64.S`



