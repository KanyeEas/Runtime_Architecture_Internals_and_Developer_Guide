# `runtime/compiler.cpp`（逐行精读｜按函数簇分段）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：1183 行  
> 本文件角色：实现 `PandaRuntimeInterface` 的大量查询逻辑，以及 `Compiler` 的编译调度/状态机；把 **OSR/deopt/CHA/inline-cache** 等执行引擎关键信号串起来。

## 1. `PandaRuntimeInterface` 的关键实现簇

### 1.1 fast path 与 GC fast path：`IsGcValidForFastPath`（L56–L66）

- Intrinsics fast path 只在 G1 GC 下启用：通过 `Runtime::GetGCType(..., lang)` 判断是否 `G1_GC`。

> 这解释了为什么某些 intrinsic/快路径在不同 GC 下会被禁用：runtime interface 直接卡了开关。

### 1.2 AOT snapshot index：`GetAOTBinaryFileSnapshotIndex*`（L68–L89）

- 把 `panda_file::File` 映射到 AOT manager 的 snapshot index，并加上 `FILE_INDEX_BASE_OFFSET` 形成“对 compiler 暴露的 index 空间”。
- 反向：从 snapshot index 取回 `PandaFile*`（`GetPandaFileBySnapshotIndex`）。

> 这与 03 章的 `.an/AotManager` 闭环一致：编译器侧需要稳定地把 method→panda file→aot snapshot index 绑定起来。

### 1.3 类解析：`PandaRuntimeInterface::GetClass(method, id)`（L159–L171）

实现给出了“编译期解析类”的典型策略：
- **L162–L166**：先走 `ClassLinker::GetLoadedClass(...)`（无锁 fast path）
- miss 后：
  - 创建 `ErrorHandler`
  - `ScopedMutatorLock`（读锁）
  - 调 `ClassLinker::GetClass(..., handler)` 触发加载

> 这直接连接到 03 章的 class loading：编译器解析类型时既能“不意外触发加载”，又能在确实需要时安全加载。

### 1.4 语言/异常/线程状态决策下沉（本文件中多处）

例如 `IsMethodNativeApi/CanThrowException/IsNecessarySwitchThreadState/CanNativeMethodUseObjects`（本文件中对应实现片段）：
- 获取 `LanguageContext`
- 调 `ClassLinkerExtension` 的对应 virtual 方法

> 这是 03→04 的重要边界：编译器需要的“语言特性”由 extension 统一回答。

### 1.5 CHA 与 inline cache：3 个 wrapper 的实现（约 L878–L960）

- **CHA**：`ClassHierarchyAnalysisWrapper::AddDependency`（L878–L882）  
  把 (callee,caller) 依赖写入 `Runtime::GetCurrent()->GetCha()`。
- **Inline cache**：`InlineCachesWrapper::GetClasses`（L911–L937）  
  从 `Method::GetProfilingData()` 查 callsite inline cache，并把 class 列表返回给 compiler；按数量给出 MONO/POLY/MEGA 分类。
- **Unresolved types**：`UnresolvedTypesWrapper::{AddTableSlot,GetTableSlot}`（L939–L960）  
  为 method+typeId+kind 保留一个可写 slot，并把该 slot 的地址返给 compiler（用于生成 lazy resolve/patchpoint）。

## 2. `Compiler`：编译调度与状态机（约 L962–L1183）

### 2.1 `Compiler::CompileMethod`：三段式决策（L962–L1004）

1) 过滤：
- 抽象方法直接拒绝（L964–L966）。

2) OSR 快路径：
- **L968–L972**：若 `osr==true` 且 OSR code 已存在：直接 `OsrEntry(bytecodeOffset, GetOsrCode(method))`。  
  并断言：当前帧 method 就是它、且 method 已有 compiled code（OSR 依赖普通 compiled code 的存在）。

3) 触发编译：
- **L974–L982**：
  - 若非 OSR 且已经 compiled，则退出（避免重复编译）。
  - 根据当前 compiled 状态决定 `ctxOsr`。
  - `AtomicSetCompilationStatus(..., WAITING)` 成功后入队 `CompilerTask(method, ctxOsr, vm)`（`AddTask`）。

4) no-async-jit 同步等待：
- **L983–L1002**：
  - 用 `ScopedChangeThreadStatus` 释放 mutator lock（避免阻塞 JIT 线程的 invalidation/GC）。
  - 轮询 compilation status（WAITING/COMPILATION），若 worker 已被 join 则退出。
  - 通过 `TimedWait` 做轻量等待（10ms）。

> 这解释了一个常见现象：开启 `no-async-jit` 时，“在调用点触发编译并等待”可能导致 safepoint/GC 行为变化（与 `HasSafepointDuringCall` 的注释一致）。

### 2.2 `StartCompileMethod`：分配器与 finalize 规则（L1014–L1061）

关键点：
- **L1020**：重置 hotness counter（避免重复触发）。
- **L1022–L1026**：若编译已“过期”（OSR code 已存在或 method 已 compiled），提前结束任务。
- **L1030–L1039**：为 compiler 创建 arena allocator（可能 background/inplace 模式不同归属）。
- **L1041–L1057**：Finalize 回调负责更新 `Method` 编译状态：
  - 成功：`COMPILATION -> COMPILED`（并强调“检查未被 deopt”）
  - OSR 编译失败且可能被 deopt：回到 `NOT_COMPILED`
  - 其它失败：`FAILED`
- **L1059–L1060**：真正进入编译：`compiler::JITCompileMethod(...)`

### 2.3 `JoinWorker` 与 debug code 清理（L1063–L1073）

- join worker 后，在特定编译 debug 配置下清理 jit debug code（非 AOT 且 emit debug info）。

### 2.4 测试辅助：`CompileMethodImpl`（L1101–L1171，非 product build）

- 通过字符串形式的 full method name 定位 class/method，并触发编译或等待编译完成。  
  这段同时展示了“如何选择 class linker context”：优先从当前栈顶方法的 class 获取 load context，否则退回 boot context。



