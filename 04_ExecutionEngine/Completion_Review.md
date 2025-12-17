# 04_ExecutionEngine 章节完工审查（VM 架构师验收）

> 审查目标：把 04 章交付为“**新人可直接上手排障** + **架构断言可追溯到源码**”的稳定文档集。  
> 审查方法：逐文档抽取关键断言 → 回到源码/构建规则核验 → 发现不一致则当场修补 → 给出后续可执行优化项。

## 0) 审查范围（Stage1 + Stage2）

- **Stage1（总览）**：[04_Execution_Engine_Interpreter_JIT_AOT](../04_Execution_Engine_Interpreter_JIT_AOT.md)
- **Stage2（入口/学习路径）**：[README](README.md)、[Index](Index.md)、[Flows/Index](Flows/Index.md)、[DataStructures/Index](DataStructures/Index.md)
- **Stage2（Flows）**：
  - [Flows/ExecutionEngine_EndToEnd](Flows/ExecutionEngine_EndToEnd.md)
  - [Flows/Interpreter_Execute](Flows/Interpreter_Execute.md)
  - [Flows/Bridge_I2C_C2I](Flows/Bridge_I2C_C2I.md)
  - [Flows/Entrypoints_and_RuntimeInterface](Flows/Entrypoints_and_RuntimeInterface.md)
  - [Flows/Deopt_and_OSR](Flows/Deopt_and_OSR.md)
  - [Flows/StackWalking](Flows/StackWalking.md)
  - [Flows/IRTOC_FastInterpreter](Flows/IRTOC_FastInterpreter.md)
  - [Flows/IRTOC_DSL_Primer](Flows/IRTOC_DSL_Primer.md)、[Flows/IRTOC_DSL_Reference](Flows/IRTOC_DSL_Reference.md)
- **Stage2（DataStructures）**：[DataStructures/Index](DataStructures/Index.md)（Frame/Acc/VReg、Bridge/FrameKind、StackWalker、OSR/Deopt、Entrypoints、IRTOC、ISA…）
- **新人排障入口**：[Newbie_MinDebug_Playbook](Newbie_MinDebug_Playbook.md)
- **逐行证据链**：[FileNotes/Index](FileNotes/Index.md)（按 [Manifests/files.yaml](Manifests/files.yaml)）

## 1) 结论概览（验收结论）

- **正确性（P0 断言）**：已对以下高风险断言完成源码核验，结论 **与当前文档一致**：
  - **解释器选型/降级/硬限制**：`runtime/interpreter/interpreter_impl.cpp`
  - **主循环/异常两段式（EXCEPTION_HANDLER）**：`runtime/interpreter/templates/interpreter-inl_gen.h.erb`
  - **OSR 触发点（回边/fast interpreter slowpath）**：`runtime/interpreter/instruction_handler_base.h`、`runtime/entrypoints/entrypoints.cpp`
  - **OSR 架构差异（非 arm64 为 UNREACHABLE stub）**：`runtime/arch/asm_support.cpp`
  - **AOT 两条加载入口（HandleAotOptions + enable-an/LoadAbcFile）**：`runtime/runtime.cpp`、`runtime/file_manager.cpp`
  - **C2I 边界帧：callee-saved 保存 + TLS 写入**：`runtime/bridge/arch/aarch64/compiled_code_to_interpreter_bridge_aarch64.S`
  - **IRTOC 管线（.irt→irtoc_code.cpp→Graph→.o/disasm）**：`irtoc/lang/irtoc.rb`、`irtoc/backend/CMakeLists.txt`、`irtoc/backend/function.cpp`

- **一致性/可读性（已修补）**：
  - 统一了 **“392 dispatch table”** 的解释口径（fast interpreter 的真实生成规则 vs C++ label table 的同长度关系）。
  - 移除了一处“若已存在/否则…”的不确定表述，改为直接指向已存在的证据入口。

- **仍可优化（不影响正确性，但能提升“新人可用性/排障效率”）**：
  - 把文档中少量“可能触发/可能是”的表述进一步收敛为 **条件矩阵**（触发条件→第一落点→第二落点→必看日志）。
  - 把 [Newbie_MinDebug_Playbook](Newbie_MinDebug_Playbook.md) 的实验步骤与各 Flow/Primer 的锚点做更细的互链（“排障→学习”闭环）。

## 2) P0 断言核验清单（带源码证据点）

### 2.1 解释器选型（cpp/irtoc/llvm）与降级/硬限制

- **证据源**：`runtime/interpreter/interpreter_impl.cpp`
- **核验点**：
  - 动态语言默认 cpp（除非显式设置）：`GetInterpreterTypeFromRuntimeOptions` 的 `if (!frame->IsDynamic() || wasSet)` 分支
  - 默认值读取与“仅未显式设置时降级”：`!wasSet` 下的 `#ifndef PANDA_LLVM_INTERPRETER` / `#ifndef PANDA_WITH_IRTOC` / `#ifdef ARK_HYBRID` 降级逻辑
  - `--debug-mode=true` 强制 cpp：`ExecuteImpl` 中 `Runtime::GetCurrent()->IsDebugMode()` 的 `LOG(FATAL)`
  - 非 ARK_HYBRID 下动态语言 + fast interpreter 的 GC 限制（要求 G1_GC）：`ExecuteImpl` 中 `frame->IsDynamic()` 分支
  - ARK_HYBRID 下组合限制（cmc-gc + 禁止 llvm）：`ExecuteImpl` 中 `#ifdef ARK_HYBRID` 两段约束

### 2.2 dispatch table 的 392（来源与同一性）

- **证据源**：
  - fast interpreter：`runtime/interpreter/templates/irtoc_interpreter_utils.h.erb` → `build/runtime/include/irtoc_interpreter_utils.h`
  - C++ interpreter：`runtime/interpreter/templates/interpreter-inl_gen.h.erb`、`runtime/interpreter/templates/isa_constants_gen.h.erb`
- **核验点**：
  - fast interpreter 表大小来自 `Panda::dispatch_table.handler_names.size() + 1`（`+1` 异常槽位）
  - C++ interpreter 的 label table 长度为 `256 + NUM_PREFIXED + 1`（同 ISA 空间，同长度）

### 2.3 异常“两段式”（stackless IFrames → CFrames → deopt 回 catch pc）

- **证据源**：
  - 第一段入口：`runtime/interpreter/templates/interpreter-inl_gen.h.erb` 的 `EXCEPTION_HANDLER`
  - 第二段：`runtime/exceptions.cpp::FindCatchBlockInCallStack/FindCatchBlockInCFrames`（并在命中后 `Deoptimize(...)`）
- **核验点**：
  - `EXCEPTION_HANDLER` 先 `handler.FindCatchBlockStackless()`，失败后（特定 arch）进入 `FindCatchBlockInCallStack(thread)`

### 2.4 OSR：触发点、slowpath、以及“最后一层”的架构现实

- **证据源**：
  - 解释器回边触发：`runtime/interpreter/instruction_handler_base.h::InstrumentBranches/UpdateHotnessOSR`
  - fast interpreter slowpath：`runtime/entrypoints/entrypoints.cpp::CallCompilerSlowPathOSR`
  - OSR 进入：`runtime/osr.cpp::OsrEntry/PrepareOsrEntry/SetOsrResult`
  - 架构差异：`runtime/arch/asm_support.cpp`（非 arm64 的 `OsrEntryAfter*` 为 `UNREACHABLE()`）
- **核验点**：
  - 仅回边触发：`InstrumentBranches` 的 `if (offset > 0) return false`
  - gating：`frame->IsDeoptimized()` 或 `!compiler-enable-osr` 不尝试 OSR
  - fake-return：触发 OSR 后把 inst 替换成 `RETURN_VOID`（fake buffer）

### 2.5 Bridge：C2I 边界帧的“物理落地”（callee-saved + TLS）

- **证据源**：`runtime/bridge/arch/aarch64/compiled_code_to_interpreter_bridge_aarch64.S`
- **核验点**：
  - `PUSH_CALLEE_REGS` 保存 callee-saved（并给出 CFI）
  - 在可能进入 safepoint 前写 TLS：`str fp, [THREAD_REG, #MANAGED_THREAD_FRAME_OFFSET]`

### 2.6 AOT：两条加载入口与 class context 设置

- **证据源**：
  - 启动期：`runtime/runtime.cpp::HandleAotOptions`（LoadAnFile）
  - `enable-an`：`runtime/file_manager.cpp::LoadAbcFile`（TryLoadAnFileForLocation）
  - class context：`runtime/runtime.cpp` 中对 `AotManager::SetBootClassContext/SetAppClassContext` 的设置

## 3) 逐文档验收（摘要）

> 说明：这里是“交付验收视角”的摘要；更细的逐行证据在 `FileNotes/*`。

### 3.1 Stage1：[04_Execution_Engine_Interpreter_JIT_AOT](../04_Execution_Engine_Interpreter_JIT_AOT.md)

- **正确性**：P0 断言（选型/异常两段式/OSR 架构差异/AOT 两入口/桥接 ABI）已能回到源码核验；表述总体准确。
- **建议优化**：
  - AOT 段建议补一句：`HandleAotOptions` 在 OHOS 与非 OHOS 的失败处理（ERROR vs FATAL）不同（避免新人误判“为何同配置不同平台行为不一致”）。

### 3.2 Stage2 入口：[README](README.md) / [Index](Index.md) / [Flows/Index](Flows/Index.md) / [DataStructures/Index](DataStructures/Index.md)

- **正确性**：学习路径与“现实差异”口径与源码一致。
- **已优化**：IRTOC 的 primer/reference 已在入口层显性挂出，避免新人只读 C++ handler。
- **建议优化**：在 [Index](Index.md) 的 2h/1d 路线中增加“最小跑通实验”（直接复用 playbook 的 3 个实验链接）。

### 3.3 Flows（调用链）

- **[ExecutionEngine_EndToEnd](Flows/ExecutionEngine_EndToEnd.md)**：主线图与各下潜链接一致；作为“唯一脊柱入口”合格。
- **[Interpreter_Execute](Flows/Interpreter_Execute.md)**：正确；明确主循环来自生成模板（避免错读）。
- **[Bridge_I2C_C2I](Flows/Bridge_I2C_C2I.md)**：正确；并提供 arch 汇编证据链入口（对排障极有价值）。
- **[Entrypoints_and_RuntimeInterface](Flows/Entrypoints_and_RuntimeInterface.md)**：正确；建议后续补一个“entrypoints 分类→常见崩溃 first-contact”表格（提升排障效率）。
- **[Deopt_and_OSR](Flows/Deopt_and_OSR.md)**：与源码一致；对“非 arm64 stub/UNREACHABLE”提醒非常关键，建议保留在所有 OSR 实验入口处（已基本做到）。
- **[StackWalking](Flows/StackWalking.md)**：正确；突出异常两段式交界，方向对。
- **[IRTOC_FastInterpreter](Flows/IRTOC_FastInterpreter.md) / [IRTOC_DSL_Primer](Flows/IRTOC_DSL_Primer.md) / [IRTOC_DSL_Reference](Flows/IRTOC_DSL_Reference.md)**：管线解释与证据链齐全；属于本章最核心内容之一，现已具备“新人可改可验”的闭环。

### 3.4 DataStructures（结构卡片）

- **总体评价**：卡片的“不变量/谁写谁读/常见坑”结构正确，能支撑 code review 与新人排障。
- **建议优化**：对 [Entrypoint_and_MethodDispatch](DataStructures/Entrypoint_and_MethodDispatch.md) 建议补一个“entrypoint 状态机（interp/compiled/osr）”图（如果该卡片里还未覆盖）。

### 3.5 新人最小排障：[Newbie_MinDebug_Playbook](Newbie_MinDebug_Playbook.md)

- **正确性**：关键日志/选项/入口与源码一致。
- **已优化**：统一了 392 的解释口径，避免误导。
- **建议优化**：把每个实验步骤的“预期观测点”再加一列“失败时的第二落点”（比如直接指向 `interpreter_impl.cpp` 的具体 `LOG(FATAL)` 语句类别）。

## 4) 后续可执行优化清单（不改变事实，只提升交付质量）

- **把“可能触发”收敛为条件矩阵**：优先改以下几处的表述风格：
  - entrypoints 异常边界、deopt-after、stackwalking 的交界描述
- **补 1 张 entrypoint/dispatch 状态机图**：帮助新人理解“Method 的入口为什么会变”
- **把 playbook 的实验与 Flow/Primer 做锚点互链**：形成“排障→理解→改动→验证”的闭环导航



