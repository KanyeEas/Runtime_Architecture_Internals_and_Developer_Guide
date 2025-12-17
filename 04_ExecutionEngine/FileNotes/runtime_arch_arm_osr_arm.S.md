# `runtime/arch/arm/osr_arm.S`（现状说明：暂无实现/仅文件头）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：arm32 下的 OSR 汇编入口文件，但当前仓库版本仅包含文件头部版权声明，**没有任何可执行逻辑**。

## 结论（避免误排障）

- 这意味着在 arm32 平台上，OSR 的“最终进入点”并不在此文件中实现。
- 同时，`runtime/arch/asm_support.cpp` 在非 arm64 平台提供的 `OsrEntryAfter*` 是 `UNREACHABLE()` stub。

> 实战建议：在 arm32 环境中排查 OSR 相关问题时，应首先判断“是否存在可用的 OSR 入口实现”，否则调整 hotness/选项不会产生预期效果。


