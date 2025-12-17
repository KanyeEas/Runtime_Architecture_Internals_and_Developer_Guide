# `runtime/include/compiler_interface.h`（逐行精读）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：241 行  
> 本文件角色：定义 runtime ↔ compiler 的关键 ABI：  
> 1) **CompilerTask**：线程池任务载体（method + OSR 标记 + VM）  
> 2) **CompilerInterface**：编译器侧可替换接口（compile/OSR code 管理）  
> 3) **ExecState**：编译代码调用时的“执行状态结构体”（给 JIT stub/桥接/返回理由使用）

## 0. `CompilerTask`：调度单元（L35–L86）

- 保存 `Method* method_`、`bool isOsr_`、`PandaVM* vm_`。
- 可移动（move ctor / move assign），不可拷贝（NO_COPY_SEMANTIC）。  
  这符合“任务在队列中移动但避免拷贝”的典型线程池模型。

## 1. `CompilerInterface::ReturnReason`（L91）

- `RET_OK`：编译代码正常返回
- `RET_DEOPTIMIZATION`：编译代码请求去优化（返回到解释器/DeoptEntrypoint）

> 这与 04 的 `DeoptimizeEntrypoint` / `Deoptimize` 闭环对齐：编译代码可通过返回理由驱动回退。

## 2. `ExecState`：编译代码执行状态（L93–L208）

`ExecState` 是一个“可被汇编/IRTOC/JIT stub 直接按 offset 访问”的 POD-ish 结构体：
- **L95–L98**：构造：`pc`、`frame`、`calleeMethod`、`numArgs`、`spFlag`。
- **L125–L148**：携带 `acc_` 与可变长 `args_[]`（flexible array）：
  - **L207**：`args_[0]` 是 GNU extension 的 flexible array member。

### 2.1 为什么需要静态 offset（L170–L198）

这些 `GetExecState*Offset()` 用 `MEMBER_OFFSET` 输出字段偏移：
- `acc_` offset
- `args_` offset
- `pc_` offset
- `frame_` offset
- `spFlag_` offset
- `calleeMethod_` offset

用途：
- 汇编桥/compiled stub 能在不理解 C++ 布局细节的情况下取字段（ABI 稳定性依赖这些 offset）。

### 2.2 `GetSize(nargs)`（L165–L168）

按 `sizeof(ExecState) + sizeof(VRegister)*nargs` 计算实际大小。  
这也是“args_ 可变长”的配套机制：调用方先算 size，再分配 ExecState buffer。

## 3. `CompilerInterface` 的核心虚接口（L214–L233）

### 3.1 编译入口（L214）

- `CompileMethod(method, bytecodeOffset, osr, func)`：编译普通/OSR 方法。  
  OSR 在 04 的 `osr.*` 中会消耗 `CompilerInterface::GetOsrCode/SetOsrCode` 的结果。

### 3.2 Worker 生命周期（L216–L223）

- `JoinWorker/FinalizeWorker/PreZygoteFork/PostZygoteFork`：运行时生命周期钩子（多 VM/zygote 场景）。

### 3.3 OSR code 管理（L224–L229）

- `GetOsrCode` / `SetOsrCode` / `RemoveOsrCode`  
  与 04 的：
  - `PandaRuntimeInterface::TrySetOsrCode`（写入 OSR code）
  - `deoptimization.cpp::InvalidateCompiledEntryPoint`（移除 OSR code）
  - `osr.cpp`（OSR entry 时读取 OSR code 并构造 CodeInfo）
  形成闭环。

### 3.4 异步 JIT 开关（L230–L231）

- `SetNoAsyncJit/IsNoAsyncJit`：控制是否禁止异步 JIT（影响编译调度与可预测性）。



