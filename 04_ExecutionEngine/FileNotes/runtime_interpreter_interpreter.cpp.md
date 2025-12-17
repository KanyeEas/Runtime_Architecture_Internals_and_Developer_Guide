# `runtime/interpreter/interpreter.cpp`（逐行精读）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：41 行  
> 本文件角色：解释器入口的“薄封装”：调用 `ExecuteImpl`，并在返回前恢复全局寄存器。

## 0. ABI/寄存器约束（L21–L23）

- **L21–L23**：防止误包含 `arch/global_reg.h`：  
  注释/`#error` 明确指出该头会破坏 ABI。这个约束与 `RESTORE_GLOBAL_REGS()` 的存在是同一类问题：解释器执行过程中可能使用“全局寄存器变量”，必须严格控制 ABI 变化。

## 1. `Execute`：调用实现并恢复寄存器（L27–L31）

- **L29**：`ExecuteImpl(thread, pc, frame, jumpToEh)`：把实际逻辑下沉到 `interpreter_impl.cpp`。
- **L30**：`RESTORE_GLOBAL_REGS()`：恢复全局寄存器变量（若开启）到调用方期望状态。

> 结论：`Execute` 的职责不是执行循环，而是“**跳到真正实现 + 做 ABI 清理**”。

## 2. `Frame::GetInstrOffset` 的内联实现（L35–L40）

- **L36–L39**：`Frame::GetInstrOffset()` 返回 `method_->GetInstructions()`。  
  这在 `compiler_interface.h::ExecState::GetMethodInst()` 与一些桥接/调试路径里会被消费，用来把 frame 的 bytecode 偏移转成真实指令地址。



