# `runtime/interpreter/state.h`（逐行精读）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：249 行  
> 本文件角色：定义解释器执行的“寄存器化状态”：PC/Frame/Thread/DispatchTable/Acc 的统一访问接口；在开启全局寄存器变量时，把这些状态映射到 `arch::regs`。

## 1. StateIface：统一接口层（L29–L86）

`StateIface<T>` 持有一个 `AccVRegisterT acc_`（构造时从 `frame->GetAcc()` 拿到初始值），并把关键操作（GetInst/SetInst/GetFrame/SetFrame/GetThread/SetThread/SaveState/RestoreState）下发到派生类实现。

> 这是一种 CRTP 模式：用静态多态把“有无全局寄存器变量”的差异消化掉，调用点保持一致。

## 2. 有全局寄存器变量的 `State`（L88–L173）

关键差异：
- **L107–L115**：PC（inst）实际存放在 `arch::regs::Pc`
- **L117–L127**：Frame 指针存放在 `arch::regs::Frame`，并且会额外设置 `MirrorFp`：
  - `MirrorFp = frame + Frame::GetVregsOffset() + frame->GetSize()`（L125–L127）  
    这是静态语言“payload + mirror vregs”布局的关键：mirror 起点=payload 起点+size。
- **L129–L137**：dispatch table 存放在 `arch::regs::DispatchTable`（用于快速 opcode 分派）。
- **L149–L165**：SaveState/RestoreState 会把 inst/acc/fp/mirrorFp/thread spill 出来再恢复  
  - 典型用途：跨 runtime call/慢路径时保护解释器寄存器状态。

## 3. 无全局寄存器变量的 `State`（L175–L243）

- PC/Frame/Thread/DispatchTable 都是普通成员变量，Save/Restore 为空实现。
- 这是一种“纯 C++ 状态机”实现：更简单但可能慢（取决于平台/优化）。

> 结论：`State` 是解释器主循环的“核心上下文”，它把 **PC/Frame/Thread/Acc/dispatch-table** 聚合起来，并在性能敏感配置下映射到寄存器变量。



