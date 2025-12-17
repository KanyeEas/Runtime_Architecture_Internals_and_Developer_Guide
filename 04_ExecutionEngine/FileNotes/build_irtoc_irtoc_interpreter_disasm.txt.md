# `build/irtoc/irtoc_interpreter/disasm.txt`（审计笔记｜机器码证据：IR 指令 id → 汇编）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件属性：build 生成物（本机证据，体量很大）  
> 本文件角色：展示 IRTOC 后端把 `Graph` 生成的 **最终汇编**，并在注释里保留：
> - `# [inst] <id> ...` 的 IR 指令摘要
> - 对应机器码地址与指令文本
>
> 阅读策略：不要逐行读全文件；只挑“入口 + dispatch + 典型 handler”验证关键约定即可。

---

## 1) `ExecuteImplFast`：入口 + dispatch 的机器码形态（L1–L58）

`METHOD_INFO` 显示：

- mode: `InterpreterEntry`
- spills_count: 0（入口不应产生 spills）

然后你能看到三段最关键的对应关系：

### 1.1 参数寄存器 → 固定寄存器（LiveOut）

反汇编里有：

- `# [inst] 0..3 Parameter arg0..arg3 -> rdi/rsi/rdx/rcx`
- `# [inst] 22 SpillFill rdi -> r15`  
  `mov %rdi, %r15`

这与 `irtoc_code.cpp` / `interpreter.irt.fixed` 的 `LiveOut(tr).DstReg(15)` 对齐：x86_64 上把 `tr` 放进 `r15`（固定寄存器）。

### 1.2 从 frame 初始化 acc/acc_tag（LoadI/AddI/LoadI）

反汇编里有：

- `mov 0x30(%rdx), %rbx`（从 frame 加 offset 取 acc 指针）
- `lea 0x30(%rdx), %rax`
- `mov 0x08(%rax), %r11`（取 acc_tag mirror）

对应 `irtoc_code.cpp` 的：

- `LoadI(frame).Imm(GetFrameAccOffset)`
- `AddI(frame).Imm(GetFrameAccOffset)`
- `LoadI(...).Imm(GetFrameAccMirrorOffset)`

### 1.3 dispatch 的本质：读 table[opc] → `jmp %rax`

反汇编里有：

- `movzxb (%rsi), %eax`：读 opcode（`LoadI.u8(pc, 0)`）
- `mov (%rcx,%rax,8), %rax`：取 `dispatch_table[opc]`
- `jmp %rax`：**尾跳转到 handler**

这就是 `interpreter.irt` 的 `dispatch(table, pc)`：computed-goto 的机器码证据。

---

## 2) `ExecuteImplFastEH`：异常入口取 table 最后一项（L62 起）

你会看到它直接构造常量偏移（例如 `mov $0xC38, %rax`），再：

- `mov (%rcx,%rax,1), %rax`
- `jmp %rax`

其中 `0xC38` = `392 * 8` = `handler_names.size * WordSize()`，即 **dispatch table 的最后一个 slot**。  
这与 `interpreter.irt` 的 `move_to_exception`（load last slot + tail_call）严格对齐。

---

## 3) 你如何把“脚本行号 → IR → 汇编”串起来（建议做一次）

以 `ExecuteImplFast` 为例：

- 在 `interpreter.irt.fixed` 找 `function(:ExecuteImplFast`（例如行号 2751/2761/2764）
- 在 `irtoc_code.cpp` 找 `Loc(..., 2751)`，拿到 `INST id`
- 在本文件找到同一 method 的 `# [inst] <id>`，看其下方汇编

这样就完成了从 DSL 到机器码的“闭环审计”。


