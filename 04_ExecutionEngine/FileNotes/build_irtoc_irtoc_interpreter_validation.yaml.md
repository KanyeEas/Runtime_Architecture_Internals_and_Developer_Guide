# `build/irtoc/irtoc_interpreter/validation.yaml`（逐行精读｜生成物的“约束与门禁”）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件属性：build 生成物（本机证据）  
> 本文件角色：IRTOC 解释器生成过程中的 **验证配置**（validation gate），用于限制每个生成函数的资源使用（尤其是 spills）。

## 1) 结构：以函数名为 key 的约束表（L1 起）

YAML 顶层是一个 map，key 是：

- `:ExecuteImplFast`
- `:ExecuteImplFastEH`
- `HANDLE_FAST_NOP`
- `HANDLE_FAST_MOV_V4_V4`
- ...

value 是该函数的验证参数，例如：

- `:spills_count_max: 32`

## 2) spills 上限为什么重要

fast interpreter 的 handler 数量巨大（392 个 slot 对应大量 `HANDLE_FAST_*`），同时它强依赖固定寄存器保存解释器状态。  
一旦某个 handler 的寄存器压力过大导致 spills 爆炸，会带来：

- 性能显著退化（handler 变慢直接放大到整体解释器）
- 更复杂的栈布局与更难的调试
- 在极端情况下可能触发后端的约束失败

因此 build 里用 `validation.yaml` 给每个 handler 上“硬门禁”是合理的工程手段。

## 3) 它与源脚本中的 `InterpreterValidation` 的关系

在 `irtoc/scripts/interpreter.irt` 顶部有：

- `InterpreterValidation = { spills_count_max: 32 }`

并在 `function(..., validate: InterpreterValidation)` 里传入。  
build 时会把它“物化”成每个生成函数的校验项（也就是这里的 `validation.yaml`）。


