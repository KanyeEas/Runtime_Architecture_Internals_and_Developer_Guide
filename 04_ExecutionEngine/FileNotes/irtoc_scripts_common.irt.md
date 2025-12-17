# `irtoc/scripts/common.irt`（逐行精读｜IRTOC 脚本的“ABI/常量/offset 底座”）

> 章节归属：Stage2 / 04_ExecutionEngine（Execution Engine）  
> 现实意义：`interpreter.irt` 的绝大多数关键语义（Frame/Thread/Method/Acc/VReg 的 offset、tag、以及 entrypoint id）都来自这里的 `Constants` 与 regmap。  
> 你只要把这里看懂，后续读 `interpreter.irt` 才不会在“Imm(cross_values::GetXXXOffset)”里迷路。

## 0. 文件定位（L16–L58）

### 0.1 regmap：把“语义寄存器名字”绑定到“物理寄存器编号”

- **L16–L20**：`$panda_regmap`：定义 thread register（`tr`）在哪个物理寄存器：
  - arm64: 28
  - arm32: 10
  - x86_64: 15
- **L22–L26**：`$arch_regmap`：fp/sp/lr/pc（架构特定）。
- **L28–L32**：`$args_regmap`：ABI 参数寄存器与返回寄存器（`arg0..argN`, `ret`）。
- **L34–L48**：temps/callees/callers regmap：用于 regalloc/临时寄存器规划。
- **L50–L58**：组合成 `$full_regmap`，并派生出 `$default_mask/$panda_mask` 等 regmask。

> 重要：IRTOC 脚本里出现的 `%tr/%pc/%frame/%acc` 等“语义寄存器”，最终会通过 regmap/LiveIn/LiveOut 固化到硬件寄存器；这也是 fast interpreter 的核心性能来源。

### 0.2 mask 约束（L53–L77）

- **L53–L57**：`$default_mask` 默认排除 temp regs 与特殊 arch regs（例如 lr）。
- **L56–L57**：`$panda_mask` 从默认 mask 里再去掉 `:tr`（thread reg）。
- **L71–L77**：arm32 的“偶数寄存器对齐”处理（编译器保守地用两个物理寄存器表示一个虚拟寄存器）。

## 1. `module Constants`：把运行时布局/offset 映射为 IRTOC 可用的 Imm（L79–...）

这一段是 `interpreter.irt` 的“地址计算字典”，核心模式是：

- `cross_values::GetXxxOffset(GetArch())`
- `cross_values::GetEntrypointOffset(GetArch(), EntrypointId::YYY)`
- `sizeof(...)` / `static_cast<uint64_t>(...)`

### 1.1 与解释器帧直接相关的 offset（高频）

- **Frame / VReg / Acc**
  - `VREGISTERS_OFFSET` / `VREGISTER_SIZE` / `VREGISTER_VALUE_OFFSET`
  - `OBJECT_TAG` / `PRIMITIVE_TAG`
  - `GET_ACC_OFFSET` / `GET_ACC_MIRROR_OFFSET`
  - `FRAME_METHOD_OFFSET` / `FRAME_PREV_FRAME_OFFSET` / `FRAME_NEXT_INSTRUCTION_OFFSET`
  - `FRAME_INSTRUCTIONS_OFFSET` / `FRAME_BYTECODE_OFFSET` / `FRAME_FLAGS_OFFSET`
- **Thread**
  - `THREAD_FRAME_OFFSET`（当前解释器帧）
  - `THREAD_EXCEPTION_OFFSET`（pending exception）
  - `THREAD_FLAG_OFFSET`（safepoint/suspend 等 flag）
  - `THREAD_INTERPRETER_CACHE_OFFSET`（解释器 cache）
- **Method**
  - `METHOD_INSTRUCTIONS_OFFSET` / `METHOD_NUM_VREGS_OFFSET` / `METHOD_NUM_ARGS_OFFSET`
  - `METHOD_COMPILED_ENTRY_POINT_OFFSET`
  - `METHOD_NATIVE_POINTER_OFFSET`（profiling 数据等）

### 1.2 解释器/编译器交界（bridge/entrypoints）

典型如：
- `GET_CALLEE_METHOD` / `INITIALIZE_CLASS_BY_ID` / `RESOLVE_CLASS`（direct entrypoints）
- `ANNOTATE_SANITIZERS_*`（sanitizer hook）

> 这解释了 `interpreter.irt` 里大量 `call_runtime("XxxEntrypoint", ...)`：它们不是随便字符串拼接，而是映射到 runtime 的 entrypoints 与 helper。

## 2. 新人排障建议（读 IRTOC handler 之前先看这里）

- **看到 `Imm(cross_values::GetFrameAccOffset(GetArch()))`**：回到本文件的 `Constants::GET_ACC_OFFSET`，确认“它指向 Frame 内哪个字段”。
- **看到 tag 相关 bug（对象/原始值混乱）**：先确认 `OBJECT_TAG/PRIMITIVE_TAG` 是从 `cross_values` 获取，且与 `Frame/VRegister` 的静态语言 mirror 布局一致。
- **看到不同 arch 行为不同**：优先检查 regmap（哪些状态被放到固定寄存器）与 mask（哪些寄存器可能被 regalloc 复用）。


