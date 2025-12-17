# Chapter 4：执行引擎（Interpreter / JIT / AOT / Bridge）

> 本章关注“代码怎么跑起来”：解释器如何执行 bytecode、解释器与编译代码如何互相调用（i2c/c2i bridge）、以及 JIT/AOT/IRTOC/quickener 等“性能路径”在工程中的落点。

---

### 1. 执行引擎地图（目录 → 职责）

| 组件 | 目录 | 关键锚点 | 说明 |
|---|---|---|---|
| 解释器 API | `runtime/interpreter/` | `runtime/interpreter/interpreter.h` | `interpreter::Execute(thread, pc, frame)` 是解释器入口 |
| 解释器实现 | `runtime/interpreter/` | `runtime/interpreter/interpreter.cpp`、`runtime/interpreter/interpreter_impl.cpp`、`runtime/interpreter/templates/interpreter-inl_gen.h.erb`、`runtime/interpreter/interpreter-inl.h` | `Execute()` 调 `ExecuteImpl()`；**主循环/dispatch table 在构建期由 `interpreter-inl_gen.h.erb` 生成到 `interpreter-inl_gen.h`**，而 `interpreter-inl.h` 主要是大量 `HandleXxx`（opcode 语义实现） |
| 执行状态（寄存器/帧） | `runtime/interpreter/` | `runtime/interpreter/frame.h`、`runtime/interpreter/vregister.h`、`runtime/interpreter/acc_vregister.h` | vreg-based frame layout；静态语言 mirror vregs 存 tag，动态语言使用 TaggedValue |
| 桥接（i2c/c2i） | `runtime/bridge/` | `runtime/bridge/bridge.h`、`runtime/bridge/bridge.cpp`、`runtime/bridge/arch/*` | 解释器↔编译代码互调；汇编实现按架构分目录 |
| entrypoints（运行时慢路径） | `runtime/entrypoints/` | `runtime/entrypoints/entrypoints.cpp` | 分配、字符串、异常等慢路径/运行时入口（供编译代码调用） |
| JIT 编译与 RuntimeInterface | `runtime/` + `compiler/` | `runtime/compiler.h`、`runtime/compiler.cpp`、`compiler/*` | runtime 侧提供 `PandaRuntimeInterface` 给 compiler 解析类/方法/常量/屏障等 |
| AOT 管理 | `compiler/aot/` | `compiler/aot/aot_manager.h`、`compiler/aot/aot_file.*` | `.an` 文件装载、class context、snapshot index 等 |
| IRTOC（IR→Code 工具） | `irtoc/` | `irtoc/`（工具与脚本） | 工程内置 IRTOC 子项目（README 简略） |
| Quickening / Bytecode 优化 | `quickener/`、`bytecode_optimizer/` | `quickener/quick.cpp`、`bytecode_optimizer/optimize_bytecode.cpp` | 运行前/构建期字节码改写与优化 |

---

### 2. 解释器：vregister-based 的执行模型

#### 2.0 真实默认路径：IRTOC/LLVM fast interpreter（先纠正“只看 C++”的误区）

本仓库支持多种解释器实现（`runtime/options.yaml`）：

- `--interpreter-type=cpp`：C++ interpreter（更适合 debug/断点；且 `--debug-mode=true` 只能配 cpp）
- `--interpreter-type=irtoc`：IRTOC backend 的 fast interpreter
- `--interpreter-type=llvm`：LLVM backend 的 fast interpreter（**默认值**）

运行时选择发生在：`runtime/interpreter/interpreter_impl.cpp::GetInterpreterTypeFromRuntimeOptions/ExecuteImplType`：  
它会在编译配置不支持时做降级（例如未编译 LLVM interpreter 时，默认 `llvm` 会降级到 `irtoc`；未编译 IRTOC 时再降级到 cpp）。

补充几条非常容易踩坑但必须写进脑子的规则（都在 `runtime/interpreter/interpreter_impl.cpp` 里硬编码）：

- **默认值 vs 最终选型**：`runtime/options.yaml` 的默认值是 `llvm`，但最终选型取决于 **frame 是否 dynamic / 是否显式设置 / 构建是否启用 LLVM/IRTOC / 运行时硬限制（debug-mode/GC 等）**。
- **静态语言（非 dynamic frame）**：未显式设置 `--interpreter-type` 时会读取默认值 `llvm`；若该构建未启用 LLVM，则会自动降级到 IRTOC；若也未启用 IRTOC，则继续降级到 cpp。
- **动态语言（dynamic frame）默认总是 cpp**：未显式设置 `--interpreter-type` 时，即便 options 默认是 `llvm`，dynamic frame 仍会强制走 cpp（源码注释原文：`Dynamic languages default is always cpp interpreter (unless option was set)`）。  
  只有当你显式设置 `--interpreter-type=irtoc/llvm` 时，dynamic 才会尝试走 fast interpreter，并触发 GC/Profiler 等约束检查。
- **“自动降级”只对未显式设置生效**：一旦你显式指定 `--interpreter-type=llvm/irtoc`，而当前构建不支持该后端（例如未编进 LLVM/IRTOC），运行时会 `LOG(FATAL)` 直接退出，不会自动降级。
- **ARK_HYBRID 约束是条件成立的**：只有当编译宏 `ARK_HYBRID` 打开时，才会出现 “interpreter-type>cpp 需要 `cmc-gc`、以及 `--interpreter-type=llvm` 直接 FATAL” 这组约束；非 ARK_HYBRID 构建下（例如常见 G1GC）不适用。
- **关于 build/ 目录的提醒**：仓库内 `build/` 产物是“当前这次编译”的输出；本机 linux/amd64 的 `build/` 不能直接推断手机 android/arm64 的运行情况，验证 fast interpreter/dispatch table 时请以 **对应目标平台的构建产物**为准。

> 重要提醒：你在 `runtime/interpreter/interpreter-inl.h` 里读到的大量 C++ handler，更多是“语义对照/调试路径”；生产默认更常走 fast interpreter 的 `HANDLE_FAST_*`（由 `irtoc/scripts/interpreter.irt` 生成）。

#### 2.1 最小调用链

`runtime/interpreter/interpreter.cpp`：
- `interpreter::Execute(...)` → `ExecuteImpl(...)` → `RESTORE_GLOBAL_REGS()`

关键点：
- `ExecuteImpl` 的入口选择与参数检查在 `runtime/interpreter/interpreter_impl.cpp`，并会 `#include "interpreter-inl_gen.h"`（构建时生成）。
- **解释器主循环（dispatch table + `DISPATCH(...)` computed-goto + `EXCEPTION_HANDLER`）来自生成头 `interpreter-inl_gen.h`**：
  - 模板源文件：`runtime/interpreter/templates/interpreter-inl_gen.h.erb`
  - `DISPATCH` 宏：`runtime/interpreter/arch/macros.h`
  - 插件扩展点聚合：`runtime/templates/plugins_interpreters-inl.h.erb` → `plugins_interpreters-inl.h`
- `runtime/interpreter/interpreter-inl.h` 的定位更准确地说是：**大量 opcode 的 `InstructionHandler::HandleXxx` 语义实现 + stackless 调用/返回/找 catch 的 helper**（体量大，建议带着 opcode/handler 名称去 grep）。

#### 2.2 Frame/VRegister/Acc：寄存器与帧的证据

在 `runtime/interpreter/frame.h` 的注释里，frame layout 被明确画出来：
- **静态语言**：payload vregs + mirror vregs（mirror 用于 tag，区分对象/原始值）
- **动态语言**：仅 payload vregs（值本身携带 tag，例如 TaggedValue）

`runtime/interpreter/vregister.h` 进一步提供：
- `VRegister`：纯 64-bit payload
- `StaticVRegisterRef`：payload + mirror（tag 存在 mirror）
- `DynamicVRegisterRef`：payload 里存 TaggedValue raw data，用 `IsHeapObject()` 判定对象

> 这套设计直接给出结论：解释器以 **虚拟寄存器（vreg）** 为核心，属于 register-based VM（非常接近 ART/dex 的执行风格）。

#### 2.3 异常处理：解释器侧是“两段式”找 catch

当 bytecode handler 触发异常时（例如 NPE/越界/显式 throw），解释器会走统一异常入口：

- **第一段：stackless IFrames 内 unwind**
  - `interpreter-inl.h` 中的 `FindCatchBlockStackless()` 负责在 stackless 解释器帧链上向上找 catch，必要时 `FreeFrame` 并回到 caller frame。
- **第二段：需要时进入 CFrames 搜索并 deopt 回解释器**
  - 生成的 `interpreter-inl_gen.h`（来自 `interpreter-inl_gen.h.erb`）在 `EXCEPTION_HANDLER` 中，若第一段返回 `INVALID_OFFSET`，会（在部分架构上）`return FindCatchBlockInCallStack(thread)`。
  - `runtime/exceptions.cpp` 实现 `FindCatchBlockInCallStack/FindCatchBlockInCFrames`：用 `StackWalker` 遍历编译帧，找到 catch 后调用 `Deoptimize(stack, method->GetInstructions()+pcOffset)` 回到解释器的 catch pc 继续执行。

---

### 3. Bridge：解释器 ↔ 编译代码的双向跳转

#### 3.1 对外可见的桥接符号

`runtime/bridge/bridge.h` 声明了关键 ABI：
- `InterpreterToCompiledCodeBridge(...)` / `InterpreterToCompiledCodeBridgeDyn(...)`
- `CompiledCodeToInterpreterBridge()` / `CompiledCodeToInterpreterBridgeDyn()`
- `InvokeInterpreter(...)`：从特定 pc+frame 调回解释器执行

并在 `runtime/bridge/arch/*` 下按 CPU 架构提供汇编实现（aarch64/amd64/arm/x86）。

#### 3.2 c2i：编译代码回退解释器（deopt/异常路径常用）

`runtime/bridge/bridge.cpp` 的 `InvokeInterpreter(...)` 展示了典型“从编译态回解释器”的骨架：
- 设定 `thread->SetCurrentFrame(frame)` 并标记 `IsCompiled=false`
- `interpreter::Execute(thread, pc, frame, ...)`
- 从 `frame->GetAcc()` 取回返回值（静态/动态分支不同）
- `FreeFrame(frame)` 并恢复 previous frame kind

同时可看到对 `INITOBJ_*` 指令的特殊处理注释：说明编译器可能把某些字节码拆分为多条指令，deopt 时需要保持 acc 语义一致。

#### 3.3 i2c：解释器调用已编译入口

在 `runtime/interpreter/interpreter-inl.h` 中可以直接看到调用桥的符号（通过 grep 可定位）：
- `InterpreterToCompiledCodeBridge(...)`
- `InterpreterToCompiledCodeBridgeDyn(...)`

> 这意味着：解释器执行到某个 call/dispatch 点时，会根据 `Method` 的 compiled entrypoint 决定走解释器内实现还是跳到编译代码。

---

### 4. JIT：runtime/compiler 与 compiler 子项目如何对接

#### 4.1 RuntimeInterface：编译器需要 runtime 提供哪些能力？

`runtime/compiler.h` 定义 `PandaRuntimeInterface : compiler::RuntimeInterface`，提供大量“编译时需要查询”的钩子，例如：
- **方法/类型信息**：`GetMethodCode()`、`GetMethodRegistersCount()`、`ResolveMethodIndex/FieldIndex/TypeIndex`
- **类解析**：`GetClass(...)` 会走 `ClassLinker` 的 loaded class fast path，必要时加锁加载
- **设置编译结果**：`SetCompiledEntryPoint(method, ep)`、`TrySetOsrCode(method, ep)`
- **GC/Barrier 信息**：可见 `gc_barrier_set.h` 被纳入 compiler 侧接口（用于生成 barrier fast path）

#### 4.2 OSR / Deopt：与桥接联动

`PandaRuntimeInterface::TrySetOsrCode` 显示了典型 OSR 写入流程：
- 获取 `MutatorLock`（读锁）保护
- 若方法已 deopt/无 compiled code，则拒绝 OSR code
- 通过 `CompilerInterface` 设置 OSR code 指针

这与 `bridge.cpp` 的 deoptimization 回退解释器路径形成闭环：**编译→执行→deopt→回解释器→再热→再编译/OSR**。

> ⚠️ 架构现实提醒（避免误排障）：OSR 的“最终进入点”是架构相关汇编入口（`OsrEntryAfter*`）。当前源码中该入口在 **arm64** 有真实实现（`runtime/arch/aarch64/osr_aarch64.S`），而在非 arm64 平台上可能是 `UNREACHABLE()` stub（见 `runtime/arch/asm_support.cpp`）。因此在非 arm64 上“OSR 跑不出来”不一定是选项/热度问题，可能是平台实现缺失/占位。

---

### 5. AOT：.an 文件、snapshot index 与 class context

落点主要有两处：

- `.an` 装载与管理：`compiler/aot/aot_manager.*`（两条真实入口：启动期 `Runtime::HandleAotOptions()`；以及 `enable-an` 下 `FileManager::LoadAbcFile()` 会按 `.abc` 路径尝试 `TryLoadAnFileForLocation()`）
- 编译器侧引用 `.an` 的索引：`runtime/compiler.cpp` 中 `GetAOTBinaryFileSnapshotIndexForMethod(...)` 等接口，把 panda_file 映射到 AOT snapshot index

并且 runtime 在启动时会设置：
- `AotManager::SetBootClassContext(...)`
- `AotManager::SetAppClassContext(...)`

（见 `runtime/runtime.cpp` 的 `CreatePandaVM` 与 `CreateApplicationClassLinkerContext` 段落）

---

### 6. IRTOC / Quickener / Bytecode Optimizer：执行前的“变换层”

#### 6.1 IRTOC

`irtoc/` 子项目在工程中作为独立模块存在（README 简略），用于 IR 到机器码/内建代码的生成管线（常与 intrinsics/模板生成结合）。

#### 6.2 Quickener

`quickener/` 目录提供 quickening 工具（字节码/常量池等预处理），常用于降低运行期解析开销。

#### 6.3 Bytecode Optimizer

`bytecode_optimizer/` 提供更全面的字节码优化（peephole、canonicalization、reg/acc 分配、codegen 等），是“运行前/构建期性能工程”的核心工具箱之一。

---

### 7. 阶段 2（已落地内容 & 仍建议补齐）

#### 7.1 已落地（Stage2 / 04_ExecutionEngine）

- **常用 opcode 的“新人可读索引”**：已补齐（并且以 **IRTOC fast interpreter** 为主线，而非只看 C++ handler）
  - `Runtime_Architecture_Internals_and_Developer_Guide/04_ExecutionEngine/Flows/Opcode_DeepDives_IRTOC.md`
  - `Runtime_Architecture_Internals_and_Developer_Guide/04_ExecutionEngine/DataStructures/ISA_and_OpcodeModel.md`
- **IRTOC/LLVM fast interpreter 的真实执行链 + 生成链**：已补齐
  - `Runtime_Architecture_Internals_and_Developer_Guide/04_ExecutionEngine/Flows/IRTOC_FastInterpreter.md`
  - `Runtime_Architecture_Internals_and_Developer_Guide/04_ExecutionEngine/DataStructures/IRTOC_FastInterpreter.md`
- **entrypoints 的“按类别理解”**：已有 Stage2 沉淀入口（可作为新人入口）
  - `Runtime_Architecture_Internals_and_Developer_Guide/04_ExecutionEngine/DataStructures/Entrypoints.md`
  - 逐行证据：`Runtime_Architecture_Internals_and_Developer_Guide/04_ExecutionEngine/FileNotes/runtime_entrypoints_entrypoints.cpp.md`

#### 7.2 i2c/c2i 的栈帧形态（已补齐：含 FrameKind 边界、StackWalker 与 deopt 交界）

- **完整的“逻辑栈形态图 + 切换点清单”**：见
  - `Runtime_Architecture_Internals_and_Developer_Guide/04_ExecutionEngine/Flows/Bridge_I2C_C2I.md`（含 I2C/C2I 的 Top→Bottom 栈形态 + Thread/FrameKind 切换点）
  - `Runtime_Architecture_Internals_and_Developer_Guide/04_ExecutionEngine/DataStructures/Bridge_ABI_and_FrameKind.md`（含 boundary frame、thread 双状态开关、deopt/异常与 StackWalker 的交界）

#### 7.3 物理栈帧/ABI（不再“留作可选”：给你一套能对照汇编的稳定结论）

本节把 **“逻辑边界”如何落到“机器栈上的真实边界帧”** 说清楚：你只要掌握这些不变量，就能把崩溃/缺帧定位到具体桥接点。

##### 7.3.1 Boundary frame 的“落地方式”（汇编直接构造，不是概念）

- **I2C（Interpreter → Compiled）**：进入 compiled 前，会在机器栈上构造一个标记为 `INTERPRETER_TO_COMPILED_CODE_BRIDGE`（或 `BYPASS_BRIDGE`）的边界帧，并把 `THREAD_REG`/`fp` 等关键寄存器状态纳入该帧，供 unwind/StackWalker 识别与还原。
- **C2I（Compiled → Interpreter）**：回解释器前，会构造一个标记为 `COMPILED_CODE_TO_INTERPRETER_BRIDGE` 的边界帧，并 **保存所有 callee-saved 寄存器**，以保证：
  - 异常 unwind / 栈回溯可以读取到 caller 的保存寄存器
  - deopt/OSR/异常路径跨边界时不丢寄存器语义

##### 7.3.2 aarch64 的“可视化物理布局”（关键字段来自汇编注释，适合对照栈）

**aarch64 / I2C 边界帧（来自 `runtime/bridge/arch/aarch64/interpreter_to_compiled_code_bridge_aarch64.S` 的注释与入栈顺序）**：

```mermaid
flowchart TB
  subgraph A["aarch64: I2C bridge frame（高地址 → 低地址）"]
    LR["lr（return addr）"]
    IF["iframe 指针（Frame*）  <— fp 所在语义点附近"]
    TAG["INTERPRETER_TO_COMPILED_CODE_BRIDGE / BYPASS_BRIDGE（桥接类型标记）"]
    FP["saved fp"]
    TH["THREAD_REG（ManagedThread*）"]
    X19["saved x19（callee-saved 示例）"]
  end
  LR --> IF --> TAG --> FP --> TH --> X19
```

**aarch64 / C2I 边界帧（来自 `runtime/bridge/arch/aarch64/compiled_code_to_interpreter_bridge_aarch64.S`）**：

- 该桥会 `PUSH_CALLEE_REGS` 把所有 callee-saved（x19-x28、d8-d15 等）压栈，并在可能进入 safepoint 前把 **C2I 边界帧指针写入 TLS**：
  - `THREAD_REG + MANAGED_THREAD_FRAME_OFFSET = fp`
  - 目的：让 StackWalker 在 safepoint/unwind 期间“看见” caller 的保存寄存器位置

##### 7.3.3 amd64 的 deopt“硬落地”：直接把 CFrame 变形为 C2I 边界帧

在 amd64 上，deopt 返回解释器并不是“另起炉灶建个边界帧”，而是可以直接 **Morph CFrame → C2I boundary frame**（来自 `runtime/bridge/arch/amd64/deoptimization_amd64.S`）：

- 写入边界帧标记：把 `COMPILED_CODE_TO_INTERPRETER_BRIDGE` 写到边界帧的 method/tag slot
- 串起 IFrame 链：把 “最后恢复的 IFrame” 的 `prev_frame` 指向这个 C2I 边界帧
- 复制 callee-saved：把 CFrame 的 callee-saved 拷贝进 boundary frame，供后续 unwind/恢复使用

这解释了一个常见现象：**你在 deopt 之后看到的“上一帧”可能是 boundary frame（不是 IFrame/CFrame），但它必须存在且可识别**，否则 StackWalker 会在跨边界时走错解码路径。

##### 7.3.4 你做 crash/缺帧排障时的最小对照清单

- **先对齐三个维度是否一致**：
  - thread 的 `currentFrame*`
  - thread 的 `currentFrameIsCompiled`
  - 机器栈上的 boundary frame 标记（`*_BRIDGE` 常量）
- **证据定位（源码路径）**：
  - I2C：`runtime/bridge/arch/*/interpreter_to_compiled_code_bridge_*.S`
  - C2I：`runtime/bridge/arch/*/compiled_code_to_interpreter_bridge_*.S`
  - deopt-after：`runtime/bridge/arch/*/deoptimization_*.S`（会显式处理 C2I boundary 与寄存器可见性）

- **证据定位（本章 FileNotes 直达）**：
  - `Flows/Bridge_I2C_C2I.md` 的 “arch 汇编证据链” 小节（集中入口）
  - aarch64：I2C/C2I/proxy/deopt
    - I2C：[04_ExecutionEngine/FileNotes/runtime_bridge_arch_aarch64_interpreter_to_compiled_code_bridge_aarch64.S.md](04_ExecutionEngine/FileNotes/runtime_bridge_arch_aarch64_interpreter_to_compiled_code_bridge_aarch64.S.md)
    - C2I：[04_ExecutionEngine/FileNotes/runtime_bridge_arch_aarch64_compiled_code_to_interpreter_bridge_aarch64.S.md](04_ExecutionEngine/FileNotes/runtime_bridge_arch_aarch64_compiled_code_to_interpreter_bridge_aarch64.S.md)
    - proxy：[04_ExecutionEngine/FileNotes/runtime_bridge_arch_aarch64_proxy_entrypoint_aarch64.S.md](04_ExecutionEngine/FileNotes/runtime_bridge_arch_aarch64_proxy_entrypoint_aarch64.S.md)
    - deopt：[04_ExecutionEngine/FileNotes/runtime_bridge_arch_aarch64_deoptimization_aarch64.S.md](04_ExecutionEngine/FileNotes/runtime_bridge_arch_aarch64_deoptimization_aarch64.S.md)
  - amd64：I2C/C2I/proxy/deopt
    - I2C：[04_ExecutionEngine/FileNotes/runtime_bridge_arch_amd64_interpreter_to_compiled_code_bridge_amd64.S.md](04_ExecutionEngine/FileNotes/runtime_bridge_arch_amd64_interpreter_to_compiled_code_bridge_amd64.S.md)
    - C2I：[04_ExecutionEngine/FileNotes/runtime_bridge_arch_amd64_compiled_code_to_interpreter_bridge_amd64.S.md](04_ExecutionEngine/FileNotes/runtime_bridge_arch_amd64_compiled_code_to_interpreter_bridge_amd64.S.md)
    - proxy：[04_ExecutionEngine/FileNotes/runtime_bridge_arch_amd64_proxy_entrypoint_amd64.S.md](04_ExecutionEngine/FileNotes/runtime_bridge_arch_amd64_proxy_entrypoint_amd64.S.md)
    - deopt：[04_ExecutionEngine/FileNotes/runtime_bridge_arch_amd64_deoptimization_amd64.S.md](04_ExecutionEngine/FileNotes/runtime_bridge_arch_amd64_deoptimization_amd64.S.md)


