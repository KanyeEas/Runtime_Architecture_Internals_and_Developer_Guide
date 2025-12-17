# `runtime/interpreter/interpreter_impl.cpp`（逐行精读｜按函数簇分段）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：207 行  
> 本文件角色：解释器真实入口：  
> 1) 根据 runtime options/构建配置选择解释器实现（CPP / IRTOC / LLVM）  
> 2) 进入 `ExecuteImplInner<RuntimeInterface,...>` 主循环（在 `interpreter-inl.h` / 生成文件中）

## 1. 解释器“多实现”入口（L18–L35）

- **L19**：包含 `interpreter-inl.h`：主循环与大量 handler 都在 inl 中。
- **L21–L34**：在不同配置下声明 fast path 执行入口：
  - IRTOC：`ExecuteImplFast` / `ExecuteImplFastEH`
  - LLVM：`ExecuteImplFast_LLVM` / `...EH_LLVM`

> 这些函数签名是 `extern "C" void *(void*,void*,void*,void*)` 风格：典型 “汇编/生成代码 ABI”。

## 2. `GetInterpreterTypeFromRuntimeOptions`：运行时选择策略（L42–L77）

- 默认是 `CPP`（L44）。
- **动态语言默认强制 CPP**，除非用户显式设置了 `--interpreter-type`（L46–L48）。  
  这与 “动态语言 GC/Profiler 约束更强” 的逻辑对齐（见 **4.2 非 ARM32 下的选型与约束**：dynamic + fast interpreter 会触发 GC/profiler 的硬限制）。
- 若用户未设置且构建不支持某实现，会做降级：
  - 未启用 LLVM：LLVM → IRTOC（L57–L61）
  - 未启用 IRTOC：IRTOC → CPP（L69–L73）
  - ARK_HYBRID 下：CMC GC 场景对 LLVM 有额外降级/限制（L62–L68）

## 3. `ExecuteImplType`：按类型分流（L81–L118）

- **LLVM 分支**（L84–L95）：
  - Setup LLVM dispatch table
  - jumpToEh 选择 EH 版本
  - 构建未启用 LLVM 时直接 FATAL
- **IRTOC 分支**（L96–L107）：
  - Setup IRTOC dispatch table
  - jumpToEh 选择 EH 版本
  - 构建未启用 IRTOC 时 FATAL
- **CPP 分支**（L108–L117）：
  - 动态语言：根据 `IsBytecodeProfilingEnabled()` 选择模板参数（`ExecuteImplInner<RuntimeInterface,true,profiling>`）
  - 静态语言：`ExecuteImplInner<RuntimeInterface,false>`

> 结论：CPP 解释器的“主循环模板实例化”由 `RuntimeInterface` + 是否 dynamic + 是否 profiling 三元组决定。

## 4. `ExecuteImpl`：执行前置检查与限制（L121–L162）

### 4.1 frame 的 instructions 基址（L123–L124）

- `inst = frame->GetMethod()->GetInstructions()`，`frame->SetInstruction(inst)`：把 method 的 bytecode base 缓存进 frame。

### 4.2 非 ARM32 下的选型与约束（L126–L160）

- ARM32 强制 CPP（注释：IRTOC 不可用）。
- 若选择了非 CPP：
  - debug-mode 只支持 CPP（L129–L132）。
  - 非 ARK_HYBRID 下：
    - 动态语言要求 G1 GC，否则 fatal（L141–L147）。
    - profiler enabled 时提示 dynamic profiling 被禁用（L147–L149）。
  - ARK_HYBRID 下：
    - CMC GC 与 LLVM/IRTOC 的支持矩阵有额外限制（L134–L158）。

### 4.3 真正执行（L161）

- `ExecuteImplType(interpreterType, thread, pc, frame, jumpToEh)`。

## 5. 调试辅助：`InstructionHandlerBase::DebugDump`（L166–L205）

提供在 debug 下打印：
- method 基本信息（nargs/nregs/framesize）
- acc 与每个 vreg 的 DumpVReg
- bytecode 指令流，并标出当前 inst

> 这段对排障很有用：当 opcode 行为异常或 vreg/acc 错乱时，它提供“可见化”的最小工具。



