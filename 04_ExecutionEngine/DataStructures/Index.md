# 04_ExecutionEngine / DataStructures

> 本目录是“结构卡片”：**它是什么**、**关键不变量**、**谁写谁读**、**常见坑**（可用于 code review/排障）。

## 卡片清单（建议顺序）

1. [Frame_VReg_Acc](Frame_VReg_Acc.md)：Frame/VRegister/Acc 的语义与布局（静态/动态语言差异）
2. [Entrypoint_and_MethodDispatch](Entrypoint_and_MethodDispatch.md)：Method 的 entrypoint/compiled code/OSR code 与 dispatch 决策
3. [Bridge_ABI_and_FrameKind](Bridge_ABI_and_FrameKind.md)：I2C/C2I 桥接边界、FrameKind 切换、返回值/异常语义
4. [StackWalker](StackWalker.md)：栈遍历抽象（解释器帧/编译帧统一视图）
5. [Deopt_and_OSR](Deopt_and_OSR.md)：去优化与 OSR 的核心概念与不变量
6. [Entrypoints](Entrypoints.md)：运行时入口（慢路径）的分类与调用约定（高层概念）
7. [IRTOC_FastInterpreter](IRTOC_FastInterpreter.md)：**真实场景默认的解释器实现**（IRTOC/LLVM fast interpreter）与 build 生成链
   - 新人改 IRTOC 必读：[Flows/IRTOC_DSL_Primer](../Flows/IRTOC_DSL_Primer.md)（`.irt` 语法/落点/验证闭环）
8. [ISA_and_OpcodeModel](ISA_and_OpcodeModel.md)：ISA（core+ETS）如何定义 opcode，以及如何驱动 IRTOC/编译器生成





