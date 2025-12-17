# `runtime/arch/x86/osr_x86.S`（现状说明：占位实现）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：x86 下的 OSR 汇编入口文件，但当前实现仍是 **stub/占位**。

## 1) 你需要知道的结论（避免误排障）

本文件当前只定义了一个 `OsrEntry` 符号，并且逻辑是“直接返回 0/false”：

- 注释说明参数：`x0=Frame*`、`x1=bytecode offset`、`x2=osr code ptr`
- 实现：清零返回寄存器后 `ret`

也就是说：**仅凭这个文件无法完成 OSR 的“进入 compiled code 并写回结果”的闭环**。

## 2) 与主线代码的关系（证据链）

- OSR 的 C++ 入口在 `runtime/osr.cpp::OsrEntry`
- 真正用于进入 OSR code 的架构入口在 `OsrEntryAfterIFrame/AfterCFrame/TopFrame`（声明于 `runtime/osr.h`）
- 对非 arm64 平台，这三个入口在 `runtime/arch/asm_support.cpp` 中被定义为 `UNREACHABLE()` stub

> 因此，在 x86 平台上做 OSR 实验/排障前，建议先确认你期待的入口符号是否存在、是否为 stub。


