# `runtime/interpreter/interpreter.h`（逐行精读）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：29 行  
> 本文件角色：声明解释器入口 `interpreter::Execute(...)`。

## 关键点

- **L20–L22**：依赖 `thread.h` 与 `frame.h`：解释器入口以 `ManagedThread*` 与 `Frame*` 为基本上下文。
- **L25**：`Execute(thread, pc, frame, jumpToEh=false)`：
  - `pc`：本次解释执行的起始字节码地址
  - `frame`：解释器帧（承载 vregs/acc/prev 链）
  - `jumpToEh`：用于“直接跳入异常处理路径”的控制位（在 deopt/异常 unwind 场景中会用到，详见 `interpreter_impl.cpp` 的调用链）。



