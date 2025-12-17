# `runtime/osr.h`（逐行精读）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：74 行  
> 本文件角色：声明 OSR（On-Stack Replacement）入口与 OSR code 缓存：**在解释器执行中途进入编译代码**。

## 0. 关键声明：OSR 入口族（L26–L37）

- **L26–L27**：`PrepareOsrEntry(...)`（extern "C"）  
  - 语义：把解释器 `Frame` 的状态（vregs/acc/env/参数区）搬运进一个 OSR CFrame，并返回“跳转到 OSR code 的目标地址”（native pc）。
  - 需要 `regBuffer/fpRegBuffer`：用于把需要放在寄存器中的值提前写好（汇编入口会把 buffer 填回真实寄存器）。
- **L29**：`OsrEntry(loopHeadBc, osrCode)`  
  - 语义：OSR 总入口（C++），负责定位当前栈与 previous frame kind，并分流到不同汇编入口。
- **L31–L35**：`OsrEntryAfter*CFrame/IFrame/TopFrame`（extern "C"）  
  - 汇编入口：依据“上一帧类型”（解释器/编译/无上一帧）选择不同的栈修补与跳转策略。
- **L37**：`SetOsrResult(frame, uval, fval)`  
  - 语义：OSR 返回到解释器时，把返回值写回解释器 acc（含 tag），并特别处理 void（防止 acc 残留旧对象导致误判为 live）。

## 1. `OsrCodeMap`：method → OSR code 的并发缓存（L39–L70）

- 用 `RWLock` + `PandaMap` 存 `Method* -> void* osrCode`。
- **Get**：读锁；未命中返回 nullptr。
- **Set**：写锁；若 `ptr==nullptr` 视为 remove。
- **Remove**：写锁 erase。

> 这与 `deoptimization.cpp` 的 `RemoveOsrCode(method)` 配合：失效时必须清掉 OSR code，避免进入陈旧 code。




