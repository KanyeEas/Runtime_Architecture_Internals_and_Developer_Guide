# `bytecode_optimizer/optimize_bytecode.cpp`（逐行精读｜按功能块）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：bytecode optimizer 的核心驱动：把 bytecode 映射为 compiler IR Graph，跑一组优化 pass，然后再生成/回写 bytecode（并维护调试信息映射）。

## 0) 新人先建立“它在链路上的位置”

它不是运行时解释器/JIT 的主循环，而是“执行前/离线变换层”：

- 输入：`.abc` bytecode（panda file）+ debug info
- 中间：`compiler::Graph`（与 JIT 侧复用同一套 IR/Pass 基础设施）
- 输出：优化后的 bytecode（并尽量保持/修复 line/column 等 debug 信息）

## 1) 全局 options：`g_options`（L59）

- `ark::bytecodeopt::Options g_options(\"\");`
- 这是 bytecode optimizer 的全局配置入口（opt level、regex、是否跳过 EH 等），大量分支从这里读取。

## 2) Pass pipeline 的组织方式：`RunOpts` 模板（L61–L89）

- `RunOpts<T>`：对单个 pass 做统一包装（通常先跑 `Cleanup`，某些 pass 需要额外准备/开关）。
- `RunOpts<First, Second, ...>`：用模板递归表达“固定顺序的 pass pipeline”。

> 架构意义：bytecode optimizer 与 JIT 编译器共享 pass 基础设施，这里只是把它组织为“离线/执行前”的固定流水线。

## 3) 核心决策：`RunOptimizations(graph, iface)`（L91–L138）

### 3.1 opt level 分层（L93–L120）

- `OPT_LEVEL_0`：直接返回 false（相当于禁用优化）
- `OPT_LEVEL_1/2`：按不同组合跑 pass

### 3.2 动态方法 special-case（L107–L109）

- `graph->IsDynamicMethod()` 下只跑较保守的一组：`ValNum + Lowering + MoveConstants`
- 这与 04 章执行引擎的总体策略一致：动态语言路径通常约束更多/策略更保守。

### 3.3 Reg/Acc 分配与编码（L122–L137）

- `RegAccAlloc`：决定哪些值进寄存器/acc（为 bytecode 生成做准备）
- `RegAlloc(graph)`：寄存器分配
- `RegEncoder`：把分配结果编码回 bytecode 形式

## 4) Debug info：PC→指令映射与 line/column 修复

### 4.1 `BuildMapFromPcToIns`（L140–L156）

- 用 `compiler::BytecodeInstructions` 迭代原始指令流
- 建立 pc → `pandasm::Ins` 的映射（供 `BytecodeGen` 回写时重建 debug info）

### 4.2 `LineNumberPropagate/ColumnNumberPropagate`（L158–L214）

- 目标：修复“某些指令缺失 line/column”的情况
- 动态方法额外传播 column（L220–L222）

## 5) 单函数闭环：`OptimizeFunction`（约 L262–L333）

这是“bytecode → Graph → pass → bytecode”闭环的核心：

- **Graph 构建**：
  - `CreateBytecodeOptimizerRuntimeAdapter(...)`
  - `graph->RunPass<IrBuilder>()`：把 bytecode 建 IR
- **可优化性过滤**：`SkipFunction`（regex/EH/帧大小上限等）
- **优化流水线**：`RunOptimizations(graph, &irInterface)`
- **回写 bytecode**：`graph->RunPass<BytecodeGen>(&function, &irInterface)`
- **修复 debug info**：`DebugInfoPropagate(function, graph, irInterface)`

## 6) 文件级入口：`OptimizePandaFile` / `OptimizeBytecode`（约 L335–L382）

- 遍历 panda file 的 class/method
- 跳过 external/abstract/native
- 为每个方法调用 `OptimizeFunction`
- `OptimizeBytecode` 负责 PoolManager 初始化/收尾（如果调用方没有 memory pool）

## 7) 排障抓手（新人最常问）

- **为什么某个函数没被优化？**：看 `SkipFunction` 的三个条件：regex / EH / frame size
- **为什么优化失败？**：看 `IrBuilder` 是否失败、`RegAlloc`/`RegEncoder` 是否失败
- **为什么行号乱了？**：看 `BuildMapFromPcToIns` + `LineNumberPropagate/ColumnNumberPropagate`

## 8) 与 04 章执行引擎的边界说明

- runtime 执行：解释器 / fast interpreter / JIT / AOT
- 本文件：执行前/离线工具对 bytecode 做“规整与优化”

> 建议新人把它当作“解释器更快跑”的上游工程，而不是运行时控制流的一部分。

{
  "cells": [],
  "metadata": {
    "language_info": {
      "name": "python"
    }
  },
  "nbformat": 4,
  "nbformat_minor": 2
}