# Opcode Deep Dives（面向新同学｜从 ISA → IRTOC handler → runtime 交互）

> 目标：你不需要先读完整 `interpreter.irt`/`isa.yaml`，但读完这篇应该能“看懂并定位”最常见的执行路径。  
> 每个 opcode 都按固定模板展开：**ISA 语义 → fast interpreter 关键宏 → runtime slowpath/异常/OSR**。

## 0) 你需要先知道的背景（1 分钟）

- **ISA 是唯一事实来源**：core 在 `isa/isa.yaml`，ETS 扩展在 `plugins/ets/isa/isa.yaml`。
- **IRTOC handler 自动生成**：`irtoc/scripts/interpreter.irt` 里 `Panda.instructions.each` 为每条指令生成 `HANDLE_FAST_*`。
- **fast interpreter 的执行形态是 tail-call dispatch**：每个 handler 最终会 `tail_call(next_handler)`，机器码里就是 `jmp %reg`。

## 1) `call.*`：调用的两条路（I2C vs stackless interpreter call）

### 1.1 ISA 语义（核心要点）

来自 `isa/isa.yaml` 的 Calling Sequence：
- call 会创建新 frame，复制参数
- callee 的 acc 被认为是 **undefined**（verified bytecode 不可读）
- return 通过 acc 把结果返给 caller

### 1.2 IRTOC 实现抓手

在 `interpreter.irt`，调用核心收敛到：

- `get_callee(...)`：解析 method +（virt call 时）解析 receiver + `ResolveVirtualMethod`
- `generic_call(...)`：两条路径
  - **已编译**：`InterpreterToCompiledCodeBridge(pc, frame, callee, tr)`（I2C）
  - **未编译**：创建新 frame，标记 `Frame::IS_STACKLESS`，把 `THREAD_FRAME_OFFSET` 指到新 frame

#### 1.2.1 工程锚点：对应的 fast handler 名称（你 grep 时用这个）

- core（静态 call）：
  - `HANDLE_FAST_CALL_SHORT_V4_V4_ID16`
  - `HANDLE_FAST_CALL_V4_V4_V4_V4_ID16`
  - `HANDLE_FAST_CALL_RANGE_V8_ID16`
- 相关变体（同一机制不同入口）：
  - virt：`HANDLE_FAST_CALL_VIRT_*`
  - call.acc：`HANDLE_FAST_CALL_ACC_*` / `HANDLE_FAST_CALL_VIRT_ACC_*`

### 1.3 新人排障 checklist

- “call 后直接崩溃”：
  - 先确认走的是 I2C 还是 stackless（callee 是否 compiled）
  - 检查 call 前是否正确 `save_acc`（GC/hook/safepoint 需要）
- “返回值不对”：
  - 看 `restore_acc/restore_acc_tag` 与 caller `Frame::acc` 的一致性

## 2) `return.* / return.void`：stackless 弹栈 vs runtime 边界返回

### 2.1 IRTOC 的统一出口：`generic_return`

- 若 `Frame::IS_STACKLESS`：
  - 取 `prev_frame/next_pc`
  - 把返回值 copy 到 caller 的 acc slot
  - `THREAD_FRAME_OFFSET=prev_frame`，free 当前 frame
  - 继续执行 caller（pc=next_pc）
- 否则：
  - `save_acc()` 后 `Intrinsic(:INTERPRETER_RETURN)`（回到 runtime 边界）

#### 2.1.1 工程锚点：对应的 fast handler 名称

- `HANDLE_FAST_RETURN`
- `HANDLE_FAST_RETURN_64`
- `HANDLE_FAST_RETURN_OBJ`
- `HANDLE_FAST_RETURN_VOID`

### 2.2 为什么这很重要

这决定了：
- 为什么 fast interpreter 里“看不到一个大 while loop”：它靠 tail-call 让 handler 串成一条执行链
- 为什么很多返回路径需要写回 frame：否则 runtime 看不到正确 acc

## 3) `jmp.*` 与 OSR：回边插桩 + fake-return

### 3.1 ISA 语义：`pc += imm`（branch_target 约束）

### 3.2 IRTOC 关键机制：`instrument_branches`

当 `imm <= 0`（回边）：
- 做 `safepoint` 检查
- hotness<=0 时调用 `CallCompilerSlowPathOSR`
- OSR 成功时触发 `handle_fake_return()`：
  - 强制从当前 stackless frame 退出到 caller，给 OSR 一个稳定切换点

> 这就是“OSR 触发点在回边”的现实来源：不是编译器想当然，而是解释器实现里明确做了插桩。

#### 3.2.1 工程锚点：对应的 fast handler 名称

- 无条件跳转：`HANDLE_FAST_JMP_IMM8` / `HANDLE_FAST_JMP_IMM16` / `HANDLE_FAST_JMP_IMM32`
- 常见条件跳转（示例）：`HANDLE_FAST_JEQZ_IMM8/IMM16`、`HANDLE_FAST_JNEZ_IMM8/IMM16`

## 4) `throw`：异常两段式（stackless IFrames → CFrames）

### 4.1 IRTOC handler 的基本结构

- null check（必要时抛 NPE）
- `ThrowExceptionFromInterpreter(tr, exc, frame, pc)`
- `find_catch_block()`：
  - `FindCatchBlockInIFrames(tr, frame, pc)`
  - 找不到则 `Intrinsic(:INTERPRETER_RETURN)` 交给 runtime（随后可能走 `FindCatchBlockInCallStack` 并触发 deopt）
- 找到则切换到 EH frame + 取回 EH acc + 继续执行 handler_pc

## 5) `ldobj/stobj`（core）与 `ets.ldobj.name/ets.call.name`（ETS 扩展）

这一组是“最能体现语言扩展 + slowpath + cache”的指令族：

- core `ldobj/stobj`：field_id 解析（cache_entry + ResolveFieldById 等）
- ETS `ets.ldobj.name*`：name-based resolution（field/getter）并在失败时抛 ETS 专用异常
- ETS `ets.call.name*`：name-based method lookup + `generic_call`

#### 5.1 工程锚点：ETS handler 名称（dispatch table 里能直接看到）

- `HANDLE_FAST_ETS_LDOBJ_NAME_PREF_V8_ID32`
- `HANDLE_FAST_ETS_LDOBJ_NAME_64_PREF_V8_ID32`
- `HANDLE_FAST_ETS_LDOBJ_NAME_OBJ_PREF_V8_ID32`
- `HANDLE_FAST_ETS_CALL_NAME_SHORT_PREF_V4_V4_ID16`
- `HANDLE_FAST_ETS_CALL_NAME_PREF_V4_V4_V4_V4_ID16`
- `HANDLE_FAST_ETS_CALL_NAME_RANGE_PREF_V8_ID16`

建议读者接下来：
- 对照 `plugins/ets/isa/isa.yaml` 的 pseudo code
- 再看 `interpreter.irt` 里的 `handle_ets_ldobj_name_* / handle_ets_call_name_*` 宏

## 证据链（本章）

- ISA core：`isa/isa.yaml`
- ISA ETS：`plugins/ets/isa/isa.yaml`
- IRTOC 语义：`irtoc/scripts/interpreter.irt`（见对应 FileNotes）
- dispatch table：`build/runtime/include/irtoc_interpreter_utils.h`
- 机器码证据：`build/irtoc/irtoc_interpreter/disasm.txt`


