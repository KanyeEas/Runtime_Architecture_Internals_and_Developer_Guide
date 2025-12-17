# `runtime/bridge/arch/aarch64/deoptimization_aarch64.S`（逐行精读｜deopt 与 boundary frame 变形）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：aarch64 上的 **deoptimization 汇编落地**：把“从 compiled 回到解释器”的关键路径做成可执行的栈变形与寄存器恢复逻辑。核心入口包括：
> - `DeoptimizeAfterCFrame`：把一个 CFrame **变形（morph）为 C2I boundary frame**，再调用 `InvokeInterpreter`
> - `DeoptimizeAfterIFrame`：在已有 IFrame 语义的场景下恢复返回地址/寄存器并进入解释器
> - 其它辅助：`DropCompiledFrameAndReturn` 等

## 1) `DeoptimizeAfterCFrame`：CFrame → C2I boundary frame（最关键证据）

文件注释直接给出“变形前后”的栈语义：

- FROM：`lr ; fp <--- ; method`
- TO：`lr ; COMPILED_CODE_TO_INTERPRETER_BRIDGE ; fp <---`

实现要点：

- 基于 `cframe origin`（x3）计算新的 `sp` 位置（为 boundary + callee-saved 区预留空间）
- 把 `COMPILED_CODE_TO_INTERPRETER_BRIDGE` 写入（`stp x7, x8, [x3, #-8]!`）
- **把 last IFrame 的 `prev_frame` 指向这个新 boundary**：`str x3, [x4, #FRAME_PREV_FRAME_OFFSET]`

> 这一条就是“逻辑 IFrame 链如何与物理 boundary frame 串起来”的硬证据：它解释了 StackWalker 为什么能跨过 deopt 边界继续工作。

## 2) boundary slot：从 StackWalker 缓冲区拷贝 callee-saved

`DeoptimizeAfterCFrame` 传入 `x5`（StackWalker 提供的 callee-saved regs buffer）并把它拷贝进 boundary frame 的固定 slots：

- 文件用 `BOUNDARY_FRAME_SLOT` 常量描述布局位置
- 依次 `ldp/stp` 把 x19-x28、d8-d15 等写入 boundary frame
- 同时设置 CFI，确保 unwind 对这些寄存器的偏移是可计算的

这就是 “deopt 后为什么还能正确恢复 caller 的寄存器快照/栈回溯” 的物理依据。

## 3) 调用 `InvokeInterpreter`：签名对齐是为了少搬运参数

文件注释点明：

- `DeoptimizeAfterCFrame` 的参数签名与 `InvokeInterpreter` 类似，所以“参数已经在寄存器里”，只需要把 `last restored IFrame` 传到指定寄存器位置即可。

实现上：

- 保存少量临时寄存器（如 `stp x0, x1` / `stp x2, x3`）
- `mov x3, x4`（把 last IFrame 传给 `InvokeInterpreter` 所需的寄存器位）
- `bl InvokeInterpreter`

## 4) 返回：恢复 callee-saved、恢复 `fp/lr/sp`、并保证返回值形态

- 从 boundary slots 恢复 callee-saved（`RESTORE_CALLEE_REGISTERS`）
- 恢复 `sp/fp/lr`
- `fmov d0, x0`：将解释器返回的 int64 位模式放入浮点返回寄存器（与 amd64 的 `movq %rax, %xmm0` 同理）

## 5) `DeoptimizeAfterIFrame`（简述）

该路径更偏向“已有 IFrame 语义”场景：

- 复制/恢复 LR（OSR 场景下 LR 槽位不同，文件用 `CFRAME_COPY_LR/CFRAME_GET_LR` 宏处理）
- 恢复 callee-saved
- 调 `InvokeInterpreter` 并按约定返回

## 6) 与本章其他证据的连接点

- amd64 对照实现：`runtime/bridge/arch/amd64/deoptimization_amd64.S`
- `InvokeInterpreter` 语义骨架：`runtime/bridge/bridge.cpp`（本章已有 FileNotes/引用）
- StackWalker/ConvertToIFrame：`runtime/stack_walker.cpp` + `runtime/include/stack_walker.h`
- 概念/逻辑：[Deopt_and_OSR（Flow）](../Flows/Deopt_and_OSR.md) + [Bridge_I2C_C2I（Flow）](../Flows/Bridge_I2C_C2I.md)


