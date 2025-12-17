# `runtime/interpreter/interpreter_impl.h`（逐行精读）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：29 行  
> 本文件角色：声明 `ExecuteImpl(...)`（解释器真实执行入口）。

## 关键点

- **L25**：`ExecuteImpl(thread, pc, frame, jumpToEh=false)`  
  与 `Execute` 同签名；区别在于：
  - `Execute` 是 ABI/寄存器封装层
  - `ExecuteImpl` 才负责选择解释器类型（CPP/IRTOC/LLVM）并进入主循环（见 `interpreter_impl.cpp`）。



