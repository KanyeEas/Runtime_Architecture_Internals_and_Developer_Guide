# `build/irtoc/irtoc_interpreter/irtoc_code.cpp`（逐行精读｜Graph 构造层：从 *.irt.fixed 到 IR 节点）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件属性：build 生成物（本机证据）  
> 本文件角色：把 `interpreter.irt.fixed` 的 DSL 语义翻译为 **compiler optimizer 的 IR Graph 构造代码**。  
> 你可以把它理解为：IRTOC 后端的“前端输出”——每个 `COMPILE(X)` 都构造一个 `Graph`，随后进入后端生成目标代码（最终落到 `irtoc_interpreter.o`，并在 `disasm.txt` 可见）。

---

## 1) 文件头部：说明这是“为某个 arch 生成的代码”

- **L2**：`// THIS FILE WAS GENERATED FOR X86_64`
- **include**：引入 IR 构造器、relocation、cross_values、runtime 类型等（因为 Graph 构造会用到 offset/常量）。

> 这也是为什么同一份 `interpreter.irt` 在不同 arch build 下会产出不同 `irtoc_code.cpp`：固定寄存器与 offset 都与 `GetArch()` 绑定。

---

## 2) `COMPILE(ExecuteImplFast)`：解释器入口的 Graph 形态（L22–L96）

### 2.1 Graph 配置（“这是 InterpreterEntry”）

在 `COMPILE(ExecuteImplFast)` 的开头你会看到典型配置：

- `SetArgsCount(4)`：对应 runtime 调用 `ExecuteImplFast(thread, pc, frame, dispatch_table)`
- `GetGraph()->SetMode(... | GraphMode::InterpreterEntry(true))`
- `GetGraph()->SetArchUsedRegs(~0x9ff)`：限制可用寄存器集合（与 fixed regmap/ABI 对齐）

### 2.2 参数映射（Parameter）

Graph 里明确声明了 4 个参数：

- `PARAMETER(0,0).ptr()` … `PARAMETER(3,3).ptr()`

在 `disasm.txt` 里能看到它们如何映射到硬件寄存器（x86_64: rdi/rsi/rdx/rcx）。

### 2.3 Loc：脚本行号是如何串起来的

关键证据是每个 `INST(...).Loc(DIR_0, FILE_0, <line>)`：

- `DIR_0` 指向 `build/irtoc/irtoc_interpreter`
- `FILE_0` 是 `"interpreter.irt.fixed"`
- `<line>` 是 **interpreter.irt.fixed 的行号**（例如 2751/2761/2764 等）

这就是“脚本 → IR”最重要的审计锚点。

### 2.4 TAIL_CALL：computed-goto 的 IR 形式

在 `ExecuteImplFast` 的末尾可以看到：

- `Load(dispatch_table, offset)` 取出 handler 地址
- `IntrinsicId::INTRINSIC_TAIL_CALL` 并 `Terminator()`

对应 `interpreter.irt` 的 `dispatch(table, pc)` / `tail_call(addr)` 宏。

在 `disasm.txt` 里最终落成：

- `jmp %rax`

> 这就是 fast interpreter 的“dispatch loop”：不是循环返回，而是尾跳转到下一个 handler。

---

## 3) `COMPILE(ExecuteImplFastEH)`：异常入口的 Graph 形态（L97–L162）

它与 `ExecuteImplFast` 相似，但核心差异是：

- 不是用 opcode 索引 table，而是直接取 `handler_names.size * 8` 的 slot（即 dispatch_table 的最后一项）
- 然后 tail-call 到异常 handler

这与 `interpreter.irt.fixed` 中 `ExecuteImplFastEH` 的 `tail_call(addr)` 对齐，也与 `irtoc_interpreter_utils.h` 把最后一项设为 `HANDLE_FAST_EXCEPTION` 对齐。

---

## 4) `COMPILE(HANDLE_FAST_XXX)`：每条 bytecode 的 handler 都变成一个 Graph

从 `COMPILE(HANDLE_FAST_NOP)` 开始，你会看到模式非常稳定：

- `SetArgsCount(0)`：handler 本身不走 C ABI 参数传递，而是通过 fixed regmap 的 LiveIn/LiveOut 读写状态寄存器
- 一串 `Opcode::LiveIn`：把 `acc/acc_tag/pc/frame/tr/dispatch` 等读进来
- 进行 decode（`LoadI` 从 `%pc` 读 operand，`AndI/ShrI` 做位操作）
- 进行 vreg/acc 操作（`Load/Store` + offset）
- 最终还是以 `Intrinsic(TAIL_CALL)` 跳转到下一个 handler（常见是再次走 `dispatch`）

> 这也解释了为什么 `validation.yaml` 里要对每个 `HANDLE_FAST_*` 做 spills 限制：handler 数量极多，寄存器压力高时必须把 spills 控制在上限内，否则性能/正确性风险上升。

---

## 5) 怎么把它和“机器码”对齐（最实用的审计方法）

以 `ExecuteImplFast` 为例：

1. 在 `irtoc_code.cpp` 找 `COMPILE(ExecuteImplFast)`（你会看到 `INST(...).Loc(..., line)`）
2. 取某个 `INST id`（例如 disasm 里的 `# [inst] 18 Intrinsic.TailCall`）
3. 到 `disasm.txt` 找同一 method 的 `# [inst] 18` 以及它下面的汇编（例如 `jmp %rax`）

这样你就能把 **“脚本行号” ↔ “IR 指令 id” ↔ “最终汇编”** 严格串起来。


