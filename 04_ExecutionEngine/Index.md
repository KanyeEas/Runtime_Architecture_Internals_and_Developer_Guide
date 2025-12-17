# 04_ExecutionEngine - Index

## 这份 Index 的用法（面向新同学）

把它当“学习路线图”用：
- **30 分钟**：建立执行引擎整体模型（看图为主）
- **2 小时**：能定位常见问题（按场景选读）
- **1 天**：能读懂实现并改代码（下潜逐行）

建议同时打开：
- [README](README.md)（主线图 + 3 场景排障树）
- [FileNotes/_Glossary](FileNotes/_Glossary.md)（术语速查）
- [Newbie_MinDebug_Playbook](Newbie_MinDebug_Playbook.md)（新人最小调试手册：确认 interpreter-type/fast interpreter/bridge/OSR）

## 30min 路线：建立整体模型（不读逐行）

0. [Flows/ExecutionEngine_EndToEnd](Flows/ExecutionEngine_EndToEnd.md)（端到端脊柱图：先把整条链路串起来）
1. [README](README.md)（3 场景排障树 + 关键现实差异）
2. [Flows/Index](Flows/Index.md)（知道有哪些主调用链，每条链路的入口/出口）
3. [DataStructures/Index](DataStructures/Index.md)（Frame/VReg/Acc/Entrypoint/StackWalker/Deopt/OSR 的卡片）
4. （真实场景补充）[Flows/IRTOC_FastInterpreter](Flows/IRTOC_FastInterpreter.md) + [DataStructures/IRTOC_FastInterpreter](DataStructures/IRTOC_FastInterpreter.md)（理解默认的 llvm/irtoc fast interpreter）
   - 如果你需要“真正改 `.irt`”：[Flows/IRTOC_DSL_Primer](Flows/IRTOC_DSL_Primer.md)（全链路分工 + 怎么改/怎么验）
   - 想更系统学 DSL：[Flows/IRTOC_DSL_Reference](Flows/IRTOC_DSL_Reference.md)（查手册式参考）
5. （新人强烈建议）[Flows/Opcode_DeepDives_IRTOC](Flows/Opcode_DeepDives_IRTOC.md) + [DataStructures/ISA_and_OpcodeModel](DataStructures/ISA_and_OpcodeModel.md)（从常用 opcode 建立直觉）

## 2h 路线：按你遇到的问题选读

### 场景 A：解释器执行异常/语义不对
- [Flows/Interpreter_Execute](Flows/Interpreter_Execute.md)（解释器执行主链路：PC/Frame/Acc/VReg 读写点）
- [DataStructures/Frame_VReg_Acc](DataStructures/Frame_VReg_Acc.md)（Frame/VReg/Acc 的语义与不变量）
- 若你跑的是默认配置（llvm）：[Flows/IRTOC_FastInterpreter](Flows/IRTOC_FastInterpreter.md)（确认实际执行路径/dispatch table/handler 来源）
- 逐行证据入口：[FileNotes/Index](FileNotes/Index.md)（需要时再下潜）

### 场景 B：I2C/C2I 桥接相关问题
- [Flows/Bridge_I2C_C2I](Flows/Bridge_I2C_C2I.md)（桥接的入口、frame kind 切换、返回值语义）
- [FileNotes/runtime_bridge_bridge.cpp](FileNotes/runtime_bridge_bridge.cpp.md)（InvokeInterpreter 与桥接骨架）
- （需要“落到栈/ABI/寄存器”的证据时）见 [Flows/Bridge_I2C_C2I](Flows/Bridge_I2C_C2I.md) 的 **4.1 arch 汇编证据链**：
  - aarch64/amd64：I2C/C2I/proxy/deopt（含 dyn 版本入口）

### 场景 C：deopt/OSR/stack walking
- [Flows/Deopt_and_OSR](Flows/Deopt_and_OSR.md)（deopt/OSR 与桥接/解释器的关系）
- [FileNotes/runtime_deoptimization.cpp](FileNotes/runtime_deoptimization.cpp.md)、[FileNotes/runtime_osr.cpp](FileNotes/runtime_osr.cpp.md)
- [FileNotes/runtime_include_stack_walker.h](FileNotes/runtime_include_stack_walker.h.md)、[FileNotes/runtime_stack_walker.cpp](FileNotes/runtime_stack_walker.cpp.md)
- （deopt-after 的最终落地）`runtime/bridge/arch/*/deoptimization_*.S`（对应 FileNotes 已挂在 [Flows/Bridge_I2C_C2I](Flows/Bridge_I2C_C2I.md) 的 **4.1**）

### 场景 D：编译器接口/entrypoints（compiled code 的慢路径）
- [Flows/Entrypoints_and_RuntimeInterface](Flows/Entrypoints_and_RuntimeInterface.md)
- [FileNotes/runtime_entrypoints_entrypoints.cpp](FileNotes/runtime_entrypoints_entrypoints.cpp.md)
- [FileNotes/runtime_compiler.cpp](FileNotes/runtime_compiler.cpp.md)

## 文件清单
- 见 [Manifests/files.yaml](Manifests/files.yaml)（逐行精读清单）
- 见 [Manifests/tree_inventory.txt](Manifests/tree_inventory.txt)（seed 全量扫描清单）
