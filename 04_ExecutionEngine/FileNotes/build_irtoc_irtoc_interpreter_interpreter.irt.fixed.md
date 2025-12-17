# `build/irtoc/irtoc_interpreter/interpreter.irt.fixed`（逐行精读｜“展开后的最终脚本”，用于 Loc/调试/对齐）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件属性：build 生成物（本机证据）  
> 本文件角色：它是 `irtoc/scripts/interpreter.irt` 在 build 过程中 **规范化/展开** 后的最终版本：
>
> - 把 `include_relative` 的依赖展开（或按顺序拼接）
> - 把 `include_plugin` 的 handlers 合入
> - 对宏/DSL 结构做“更稳定的输出”（便于后续生成 `irtoc_code.cpp`）
>
> 你在 `irtoc_code.cpp` / `disasm.txt` 里看到的 `Loc(DIR_0, FILE_0, <line>)` 的 `<line>`，指的就是 **本文件的行号**。

---

## 1) 为什么这个文件是“可审计枢纽”

IRTOC 的 3 个层次分别承担不同责任：

- **`irtoc/scripts/interpreter.irt`**：人类可读的解释器语义（宏/生成器/注释密集）
- **`interpreter.irt.fixed`**：给“代码生成器”喂的稳定输入（行号稳定、已展开）
- **`irtoc_code.cpp`**：把 `*.irt.fixed` 的 DSL 语义变成 `Graph` 的 C++ 构造（逐条 `INST(...)`）

所以你要做“逐行证据链”的时候，**固定以 `*.irt.fixed` 行号作为锚点**最稳。

---

## 2) `ExecuteImplFast/ExecuteImplFastEH` 在 fixed 脚本里的真实样子（约 L2740 起）

在本机 build 输出里，可以直接看到（关键点）：

- `function(:ExecuteImplFast, params: { tr/pc/frame/dispatch_table }, mode: [:InterpreterEntry])`
- `LiveOut(tr).DstReg(regmap[:tr])`、`LiveOut(frame).DstReg(regmap[:frame])`
- 初始化 acc/acc_tag（从 frame 的 acc slot load）
- `dispatch(dispatch_table, pc)`（进入 computed-goto/tail-call 的 dispatch）

同一段会被 `irtoc_code.cpp::COMPILE(ExecuteImplFast)` 逐条翻译成 `Opcode::LiveOut/LoadI/AddI/Intrinsic(TAIL_CALL)`。

---

## 3) handler 生成器：`Panda.instructions.each` 会“落地成一批函数文本”

`interpreter.irt` 末尾的 `Panda.instructions.each` 在 fixed 文件里会表现为：

- 大量 `function("HANDLE_FAST_#{handler_name}", ...) do ... end`
- case 分发 + 调用对应 `handle_xxx` 宏

这些函数会在 `irtoc_code.cpp` 里对应 **大量的 `COMPILE(HANDLE_FAST_XXX)`**。

---

## 4) 你如何用它做“行号 → IR → 机器码”的追溯

推荐最短路径（以 `ExecuteImplFast` 为例）：

1. 在本文件找 `function(:ExecuteImplFast` 的行号（例如 2751/2761/2764 等）
2. 去 `irtoc_code.cpp` 搜 `interpreter.irt.fixed:2751`，看对应 `INST(...).Loc(..., 2751)`
3. 去 `disasm.txt` 看同一个 method 的 `[inst] <id> ...` 对应机器码（例如 `jmp %rax`）

这样你可以把一段“脚本语义”严格对齐到“IR 节点序列”和“最终汇编”。


