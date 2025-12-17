# `compiler/aot/compiled_method.h`（逐行精读｜AOT 产物容器）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：`CompiledMethod` 是 AOT 编译阶段生成的“方法级产物容器”：保存机器码与 CodeInfo（以及可选的 CFI debug info），并提供对齐后的 overall size 计算。

## 1) `CompiledMethod` 保存什么

- `code_`：机器码 bytes
- `codeInfo_`：对应的 `CodeInfo` bytes（stack map / vreg info / inline info 等）
- （可选）`CfiInfo`：当 `PANDA_COMPILER_DEBUG_INFO` 开启时，用于生成更准确的 unwind/debug 信息

## 2) 为什么有 `GetOverallSize()`

它按架构对齐约束组合三段大小：

- `CodePrefix`（按 code alignment）
- `code_`（round-up 到 `CodeInfo::ALIGNMENT`）
- `codeInfo_`（round-up 到 `CodeInfo::SIZE_ALIGNMENT`）

> 执行引擎意义：StackWalker/deopt/异常 unwind 依赖 `CodeInfo` 与 code 的相对位置；统一的布局与对齐是“可被可靠解码”的基础。




