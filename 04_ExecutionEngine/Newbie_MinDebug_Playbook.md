# 04_ExecutionEngine：新人最小调试手册（5 分钟确认“你到底跑的是什么”）

> 目标：新同学不需要读完实现，就能快速确认 **解释器类型/fast interpreter 是否生效/桥接与边界帧是否一致**，并知道遇到问题第一落点在哪。

## 0) 你可以先跳到这里

- **只想确认 interpreter-type**：看 **1)**
- **只想确认 fast interpreter 是否生效（最省时间）**：看 **2)**
- **只想确认 dispatch table/392**：看 **3)**
- **崩在桥接/缺帧/异常跨边界**：看 **4)**
- **OSR/deopt-after 异常或不触发**：看 **5)**
- **看懂异常“两段式”到底哪两段**：看 **6)**
- **想要可复现实验（把现象“做出来”）**：看 **7)**

## 1) 先确认：我现在到底跑的是 cpp / irtoc / llvm？

- **看启动参数**：是否显式传了 `--interpreter-type={cpp|irtoc|llvm}`
  - 默认值在 `runtime/options.yaml`：`interpreter-type` 默认 `llvm`
  - 但 **动态语言有特例**：如果你**没有显式设置** `--interpreter-type`，dynamic frame 会强制走 cpp（源码硬编码）
- **看最终真相（源码入口）**：`runtime/interpreter/interpreter_impl.cpp`
  - `GetInterpreterTypeFromRuntimeOptions(Frame *frame)`
  - `ExecuteImpl(...)`（会做 debug-mode/GC/hybrid 的硬限制）

> 推荐入口文档：`Flows/IRTOC_FastInterpreter.md` 的 **4.1 解释器选型精确规则**（已按源码可复核）。

### 1.1 判定矩阵（最常见的 6 个结论）

- **动态语言 + 未显式设置 `--interpreter-type`** → **强制 cpp**（即使 options 默认值是 llvm）
- **显式设置 `--interpreter-type=llvm` 但构建未启用 LLVM interpreter** → **直接 FATAL**（不是降级）
- **显式设置 `--interpreter-type=irtoc` 但构建未启用 IRTOC** → **直接 FATAL**（不是降级）
- **未显式设置 `--interpreter-type` 且构建不支持 LLVM** → 默认 `llvm` 会 **降级到 irtoc**
- **未显式设置 `--interpreter-type` 且构建不支持 IRTOC** → 会继续 **降级到 cpp**
- **`--debug-mode=true` 且选择 irtoc/llvm** → **直接 FATAL**（debug-mode 只支持 cpp）

## 2) 用日志确认 fast interpreter 是否真的启用了（最快的方法）

当选型为 `irtoc/llvm` 时，`runtime/interpreter/interpreter_impl.cpp::ExecuteImplType` 会打出：

- `Setting up Irtoc dispatch table`
- `Setting up LLVM Irtoc dispatch table`

要看到这些日志，你需要打开 logger（注意：runtime/options.yaml 里的 log 选项已 deprecated）：

- logger 选项定义：`libarkbase/utils/logger_options.yaml`
- 常用组合：
  - `--log-level=debug`
  - `--log-components=runtime:interpreter`

### 2.1 常用“排障日志组合”（建议收藏）

- **只看解释器/桥接**：`--log-level=debug --log-components=runtime:interpreter:interop`
- **再加上编译器（JIT/OSR）**：`--log-level=debug --log-components=runtime:interpreter:compiler:interop`
- **想看 LLVM 侧组件（如果启用）**：`--log-level=debug --log-components=runtime:interpreter:llvm`

> 小技巧：如果你怀疑“日志开了但没打印”，先确认你用的是 `logger::Options`（`libarkbase/utils/logger_options.yaml`），而不是 runtime/options 里已 deprecated 的项。

## 3) dispatch table 从哪里来？为什么是 392？

- dispatch table 的定义与初始化（build 产物，本机证据）：`build/runtime/include/irtoc_interpreter_utils.h`
  - `SetupDispatchTableImpl()`（IRTOC）
  - `SetupLLVMDispatchTableImpl()`（LLVM）
  - `std::array<void (*)(), 392>`：**392 的“真实生成规则”**来自模板 `runtime/interpreter/templates/irtoc_interpreter_utils.h.erb`：
    - `392 = Panda::dispatch_table.handler_names.size() + 1`（`+1` 是 `HANDLE_FAST_EXCEPTION(_LLVM)` 槽位）
  - 同时它与 C++ interpreter 的 label dispatch table **同长度、同 ISA 空间**（便于你心里对齐 opcode 空间）：
    - `392 = 256 + NUM_PREFIXED + 1`（见 `runtime/interpreter/templates/interpreter-inl_gen.h.erb` 与 `isa_constants_gen.h.erb`，`+1` 为 `EXCEPTION_HANDLER` 槽）
- 生成链总览（脚本→机器码）：`Flows/IRTOC_FastInterpreter.md`
  - `irtoc/scripts/interpreter.irt → build/irtoc/.../interpreter.irt.fixed → irtoc_code.cpp → disasm.txt`

### 3.1 你应该如何“证明自己看的是生产路径”

新同学最常犯的错是：“我改了 C++ handler，但运行没变化”。最短自检：

- **如果你看到** `Setting up * dispatch table`：说明你大概率走的是 **fast interpreter（irtoc/llvm）**
- **如果你没看到**，但你以为自己走 fast interpreter：
  - 检查是否其实在跑 **动态语言默认 cpp**（见 1.1 第一条）
  - 或者构建不支持 fast interpreter 导致你被迫走 cpp（见 1.1 的 FATAL/降级规则）

## 4) 桥接/缺帧/异常跨边界：最小排障法

### 4.1 先对齐“三件事”（否则必定缺帧/错帧）

- `thread.currentFrame*`
- `thread.currentFrameIsCompiled`
- 机器栈上的 boundary marker（`*_BRIDGE` 常量）

### 4.2 一键下潜到“汇编证据链”

直接跳：`Flows/Bridge_I2C_C2I.md` → **4.1 arch 汇编证据链**（aarch64/amd64，含 dyn）  
里面把 I2C/C2I/proxy/deopt 的源码路径和对应 FileNotes 都列好了。

### 4.3 症状 → 第一落点 → 第二落点（新人最快路线）

| 你看到的现象 | 第一落点（优先看） | 第二落点（需要硬证据时） |
|---|---|---|
| 跳到 compiled 就崩 | `runtime/bridge/bridge.cpp`（Invoke/Return 语义、frame 切换） | `Flows/Bridge_I2C_C2I.md` 的 arch 汇编证据链（I2C/proxy） |
| 从 compiled 回解释器后返回值/acc 不对 | `runtime/bridge/bridge.cpp` + `runtime/interpreter/*`（acc 写回点） | `runtime/bridge/arch/*/compiled_code_to_interpreter_bridge_*.S`（C2I 写回/FreeFrame） |
| 缺帧/栈遍历崩 | `runtime/stack_walker.cpp`（boundary frame 识别） | `DataStructures/Bridge_ABI_and_FrameKind.md` + arch 汇编（TLS/callee-saved） |
| native 异常无法正确抛出/被吞 | `runtime/exceptions.cpp`（HandlePendingException/FindCatchBlockInCFrames） | `runtime/bridge/arch/*/proxy_entrypoint_*.S`（ThrowNativeExceptionBridge 跳转） |

## 5) OSR 不生效 / deopt-after 异常：第一落点

- **解释器回边触发点**：`runtime/interpreter/instruction_handler_base.h`
  - `InstrumentBranches(int32_t offset)`：只对 back-edge（`offset <= 0`）触发 safepoint/OSR
  - `UpdateHotnessOSR(...)`：`frame->IsDeoptimized()` / `compiler-enable-osr` gating
  - 触发成功后的 **fake-return**：伪造 `RETURN_VOID` 让主循环安全退出并进入 OSR 入口路径
- **fast interpreter 的 OSR entrypoint**：`runtime/entrypoints/entrypoints.cpp::CallCompilerSlowPathOSR`
- 文档入口：`Flows/Deopt_and_OSR.md`

### 5.1 让 OSR 更“容易发生”的三个参数（调试专用）

> 目的：让你在本地更容易把 OSR 路径跑出来（不是性能建议）。

- ⚠️ **先确认架构是否支持**：当前源码里 OSR 的 `OsrEntryAfter*` 真实落地主要在 **arm64**（见 `Flows/Deopt_and_OSR.md` 的 **4.3 架构约束**）；在非 arm64 上这些入口可能是 `UNREACHABLE()` stub，你会“怎么调都跑不出来”。

- `--compiler-enable-jit=true`
- `--compiler-hotness-threshold=1`（更快触发编译请求）
- `--compiler-enable-osr=true`

如果你希望“更可重复”（降低异步编译带来的不确定性），可加：

- `--no-async-jit=true`（让编译更同步、更容易观察调用点行为）

## 6) 异常“两段式”与 catch 搜索（新同学最容易误读）

- 第一段（解释器 stackless）：`EXCEPTION_HANDLER` → `FindCatchBlockStackless()`
  - 源码：`runtime/interpreter/templates/interpreter-inl_gen.h.erb`
- 第二段（进入 CFrames 搜索）：`FindCatchBlockInCallStack(thread)` → `FindCatchBlockInCFrames` → 命中后 `Deoptimize(...)`
  - 源码：`runtime/exceptions.cpp`
- 文档入口：`Flows/StackWalking.md`

## 7) 三个最小实验（把现象“做出来”，你就不再靠猜）

### 实验 1：强制走 cpp（验证你改 C++ handler 是否能生效）

- 运行时显式设置：`--interpreter-type=cpp`
- 你应该观察到：
  - 不会出现 “Setting up * dispatch table” 日志
  - opcode 行为更容易被你在 `runtime/interpreter/interpreter-inl.h` 的 handler 影响

### 实验 2：强制走 llvm/irtoc（验证 fast interpreter 生效）

- 运行时显式设置：`--interpreter-type=llvm`（或 `irtoc`）
- 你应该观察到：
  - 出现 `Setting up LLVM Irtoc dispatch table`（或 `Setting up Irtoc dispatch table`）
  - 如果构建不支持该后端，会直接 FATAL（这也是判断构建能力的最快方法）

### 实验 3：让 OSR 更容易触发并观察“fake-return”

- 运行时建议设置：
  - `--compiler-hotness-threshold=1 --compiler-enable-osr=true --no-async-jit=true`
- 你应该观察到（源码层面）：
  - 回边处走到 `InstrumentBranches(offset<=0)`，并进入 `UpdateHotnessOSR(...)`
  - OSR 发生时会写入 fake `RETURN_VOID`（`GetFakeInstBuf/SetInst`），让解释器主循环走向 OSR 入口

> 备注：这个实验在 **arm64** 上最容易闭环（有 `runtime/arch/aarch64/osr_aarch64.S` 的真实 OSR 入口）；在非 arm64 上请先确认架构实现是否存在，否则可能直接落入 stub/UNREACHABLE。


