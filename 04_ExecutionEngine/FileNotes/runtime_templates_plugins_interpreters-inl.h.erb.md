# `runtime/templates/plugins_interpreters-inl.h.erb`（逐行精读｜插件扩展点）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 本文件角色：生成 `plugins_interpreters-inl.h`，用于把“插件提供的解释器扩展 inl”聚合到主解释器生成文件中。  
> 该文件被 `runtime/interpreter/templates/interpreter-inl_gen.h.erb` 直接 `#include`。

## 1. 生成逻辑（L19–L21）

- **L19–L21**：遍历插件选项 `"additional_interpter_inl"`（注意拼写是 `interpter`），对每个条目生成一条 `#include "<path>"`。

含义：
- 插件可以通过构建系统把“额外的 handler/辅助逻辑”以 inl 的形式注入解释器编译单元。
- 这也是为什么 `interpreter-inl_gen.h` 需要包含一个“插件聚合头”：不改 core 代码也能扩展 ISA/行为（比如新增语言/字节码扩展）。




