# `runtime/arch/amd64/osr_amd64.S`（现状说明：暂无实现/仅文件头）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：amd64 下的 OSR 汇编入口文件，但当前仓库版本仅包含文件头部版权声明，**没有任何可执行逻辑**。

## 结论（避免误排障）

- 这意味着你不能指望在 amd64 上通过该文件进入 OSR compiled code。
- 对比：arm64 有完整 OSR 入口实现（`runtime/arch/aarch64/osr_aarch64.S`）。
- 同时，`runtime/arch/asm_support.cpp` 在非 arm64 平台提供的 `OsrEntryAfter*` 是 `UNREACHABLE()` stub。

> 因此在 amd64 环境中，“OSR 不触发/跑不出来”首先要排除平台入口缺失这一事实，再去看 hotness/选项/编译器状态位。


