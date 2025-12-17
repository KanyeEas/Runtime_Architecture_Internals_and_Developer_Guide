# `runtime/interpreter/acc_vregister-inl.h`（逐行精读）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：210 行  
> 本文件角色：在开启 `PANDA_ENABLE_GLOBAL_REGISTER_VARIABLES` 时，把 acc 映射到“全局寄存器变量”，并提供对应的 `AccVRegisterTRef` 语义操作。

## 0. 两种 acc 实现（L23–L27, L203–L207）

- 若启用全局寄存器变量：
  - `AccVRegisterT` 不是内存里的 `AccVRegister`，而是 `arch::regs::{GetAccValue/GetAccTag}` 的视图
- 否则：
  - `using AccVRegisterT = AccVRegister`（直接用内存里的 payload+mirror）

> 这正是 `interpreter.cpp` 里强调“不能随意包含 global_reg.h、并且要 RESTORE_GLOBAL_REGS”的原因：acc 可能不在内存里，而在寄存器里。

## 1. `AccVRegisterT`：从寄存器读写 value/tag（L30–L69）

- **L45–L63**：`GetValue/SetValue/GetTag/SetTag` 全部委托 `arch::regs::*`。
- **L33–L43**：允许从普通 `AccVRegister` 构造（拷贝 value/tag 到寄存器），并可隐式转回 `AccVRegister`（把寄存器快照成内存对象）。

## 2. `AccVRegisterTRef<IS_DYNAMIC>`：统一“对象/原始值”语义（L71–L201）

这是对 `VRegisterRef` 的扩展，最重要的是 `HasObject()`：
- **动态**（L114–L117）：把 payload 当 `TaggedValue`，用 `IsHeapObject()` 判断
- **静态**（L118–L119）：用 tag==GC_OBJECT_TYPE 判断

同时提供：
- `MovePrimitive/MoveReference/Move`：带断言保证类型一致（L121–L145）
- `SetPrimitive` 多重重载（L147–L185）
- `SetReference(ObjectHeader*)`（L187–L193）：静态语言会设置 tag=GC_OBJECT_TYPE；动态语言直接写入 TaggedValue raw data

> 这段是解释器/桥接/OSR/deopt 对 acc 操作的共同语义基础：无论 acc 在内存还是寄存器，都能用同一套 API 做“值/引用”一致性操作。



