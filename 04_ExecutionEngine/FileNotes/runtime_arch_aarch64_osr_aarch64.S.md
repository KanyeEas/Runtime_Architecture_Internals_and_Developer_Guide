# `runtime/arch/aarch64/osr_aarch64.S`（证据链：OSR 的最终落地入口）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：arm64 上 OSR（On-Stack Replacement）的“最终真相层”——实现 `OsrEntryAfterIFrame/OsrEntryAfterCFrame/OsrEntryTopFrame` 三个入口，把解释器帧/边界帧改造为可跳入 OSR code 的 CFrame，并在需要时把返回值写回解释器 accumulator。

## 0) 你读这个文件要带着的问题

- OSR 到底是“怎么从解释器切到 compiled code”的？最后一跳在哪里？
- 为什么 OSR 需要 `PrepareOsrEntry` 的寄存器 buffer？哪些寄存器会被恢复？
- `AfterIFrame/AfterCFrame/TopFrame` 三个入口分别对应什么栈形态？差异在哪？

对应 C++ 入口与协议（先看这个再回来看汇编会更清晰）：

- `runtime/osr.cpp::OsrEntry(...)`：决定走 `AfterIFrame/AfterCFrame/TopFrame`
- `runtime/osr.cpp::PrepareOsrEntry(...)`：把 live vregs/acc/特殊寄存器环境写入 CFrame slot 或 register buffer，并返回“OSR code 的真实 entry PC”
- `runtime/osr.cpp::SetOsrResult(...)`：把 OSR code 返回值按 shorty 写回到解释器 frame 的 accumulator

## 1) 关键结构：`OSR_ENTRY` 宏做了什么

`OSR_ENTRY` 是三个入口都要复用的核心片段，职责可以拆成 4 步：

1) **在栈上准备两个 buffer**  
   - scalar 寄存器 buffer：`REGS_BUFFER_SIZE`
   - vector 寄存器 buffer：`FP_REGS_BUFFER_SIZE`

2) **调用 `PrepareOsrEntry`**（C++）  
   - 入参约定（注释写得很清楚）：  
     `x0=iframe, x1=bytecode offset, x2=osr code ptr, x3=cframe ptr, x4=scalar buf, x5=vector buf`
   - 返回值：`x0` 是“OSR code 的真实 entrypoint（含 native pc 偏移）”，汇编里会暂存到 `x17`，后续用 `blr x17` 跳入。

3) **恢复 `THREAD_REG`**  
   - 宏里会调用 `GetCurrentManagedThread`，并把结果写入 `THREAD_REG`（对后续栈遍历/异常/GC 语义很关键）。

4) **从 buffer 恢复寄存器，再跳入 OSR code**  
   - 恢复一大段 `d0-d31`（vector regs）和 `x0-x27`（注意跳过 `x28`，因为它是 `THREAD_REG`）。
   - 最后 `blr x17` 进入 OSR compiled code。

> 结论：OSR 不是“解释器直接跳到 compiled 入口”那么简单，它必须把“解释器视角的 live 值”按 `CodeInfo::FindOsrStackMap` 的描述映射到 CFrame 的 slot/寄存器状态里，`PrepareOsrEntry` + `OSR_ENTRY` 就是这个映射的落地。

## 2) 三个入口分别解决什么栈形态

### 2.1 `OsrEntryAfterIFrame`：从解释器帧进入 OSR

典型场景：解释器在回边/热度触发处决定 OSR（见 `instruction_handler_base.h::InstrumentBranches` 与 `runtime/osr.cpp::OsrEntry`）。

这个入口会做几件关键事：

- **在进入 OSR 前构造 I2C bridge marker**（`INTERPRETER_TO_COMPILED_CODE_BRIDGE`）  
  这让 StackWalker/unwind 能识别“解释器→编译”的边界。
- **为 stack parameters 预留空间**（`stackParams` 由 `runtime/osr.cpp::GetStackParamsSize` 计算并传入）
- **构造 CFrame header + callee-saved 区**（`PUSH_CALLEE_REGS`），并把 `fp` 切换到新 cframe
- 然后进入 `OSR_ENTRY`，最终跳入 OSR compiled code
- **返回值写回**：调用 `SetOsrResult(frame, result)`，把 OSR code 的返回值写回解释器 frame 的 acc（按 shorty 决定 tag/类型）

### 2.2 `OsrEntryAfterCFrame`：从“compiled 后面”进入 OSR（更复杂）

在 `runtime/osr.cpp::OsrEntry` 里，当 `StackWalker::GetPreviousFrameKind()==FrameKind::COMPILER` 时会走这里。

这个入口的重点是：

- **“替换 C2I frame 为新 cframe”**：它会从边界帧里取回 caller 的 `fp/lr`，并把 boundary frame 上保存的 callee-saved 复制到新 cframe 的对应区域（这能保证 unwind/栈回溯语义正确）。
- 构造完新 cframe 后进入 `OSR_ENTRY`
- 入口尾部有一段专门的 `THREAD_REG` 恢复与 `lr/fp` 保护逻辑（注释解释了 `GetCurrentManagedThread` 可能修改栈内存，需要先保护 cframe 里存的 `lr/fp`）

### 2.3 `OsrEntryTopFrame`：前一帧不存在（FrameKind::NONE）

对应 `runtime/osr.cpp::OsrEntry` 的 `FrameKind::NONE` 分支：栈顶就是当前解释器帧，没有“前一帧 kind”可参考。

整体结构与 `AfterIFrame` 类似：构造必要边界/栈空间 → `OSR_ENTRY` → `SetOsrResult` 写回。

## 3) 排障要点（非常实用）

- **OSR 只在“具备对应 arch 汇编入口”的平台上才可能闭环**：如果你在非 arm64 平台做 OSR 实验，可能直接落入 stub（见 `runtime/arch/asm_support.cpp` 的 `UNREACHABLE()`）。
- **thread/currentFrame 与 frame kind 一致性**：`PrepareOsrEntry` 会 `thread->SetCurrentFrame(cframePtr)` 并标记 compiled，这与 StackWalker/异常/GC 语义强绑定。
- **返回值写回一定要对照 `SetOsrResult`**：如果你看到 OSR 后 acc/tag 异常，第一落点应是 `runtime/osr.cpp::SetOsrResult` 与本文件里调用它的位置。


