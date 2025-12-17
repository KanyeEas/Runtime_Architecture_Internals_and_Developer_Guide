# 04_ExecutionEngine / Flows

> 本目录用“调用链”组织执行引擎知识：入口是什么、关键分支是什么、出口是什么。  
> 每条 flow 都配 Mermaid 图，并指向对应 `FileNotes/` 作为证据链。

## Flow 清单（建议顺序）

0. `ExecutionEngine_EndToEnd.md`：**端到端主线（新人脊柱图）**：解释器选型→执行→调用/桥接→entrypoints→JIT/OSR→deopt→异常/栈遍历（每个框都可下潜）
1. `Interpreter_Execute.md`：解释器执行主链路（PC/Frame/VReg/Acc）
2. `Bridge_I2C_C2I.md`：解释器↔编译代码桥接（I2C/C2I/InvokeInterpreter）
3. `Entrypoints_and_RuntimeInterface.md`：compiled code 慢路径入口（entrypoints）与 JIT RuntimeInterface
4. `Deopt_and_OSR.md`：deopt/OSR 的触发、安装条件与回退路径
5. `StackWalking.md`：StackWalker 如何统一遍历解释器帧/编译帧（调试/异常/去优化）
6. `IRTOC_FastInterpreter.md`：**fast interpreter 的真实执行链**（选型→dispatch table→ExecuteImplFast）+ build 生成链
6.1 `IRTOC_DSL_Primer.md`：**新人必读：`.irt` DSL 怎么读/怎么改/怎么验证闭环**（从现象→定位→改动→产物证据）
6.2 `IRTOC_DSL_Reference.md`：`.irt` DSL 参考（更“教科书式”的语法/语义说明，按章节查阅）
7. `Opcode_DeepDives_IRTOC.md`：挑选常用 opcode 深入分析（ISA→IRTOC handler→runtime/异常/OSR）
8. （上游工具链）`FileNotes/quickener_quick.cpp.md`、`FileNotes/bytecode_optimizer_optimize_bytecode.cpp.md`：执行前 quickening/bytecode optimization 如何影响运行期输入

> 新人调试入口（不属于 flow，但强烈建议收藏）：`../Newbie_MinDebug_Playbook.md`





