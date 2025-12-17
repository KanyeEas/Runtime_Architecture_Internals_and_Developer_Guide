# IRTOC `.irt` DSL 入门（新人可落地的“怎么读/怎么改/怎么验证”）

> 目标：让完全没 IRTOC 背景的新同学，在 **1 小时内**具备三种能力：  
> 1) 看懂 `interpreter.irt` 的大结构（macro/handler/dispatch）  
> 2) 能定位“某个现象对应 .irt 里的哪一段”并做小改动  
> 3) 能用 build 产物把“DSL → IR → 汇编 → 运行时行为”串成证据链闭环

## 0) 在 04 章端到端主线中的位置

- 总入口：[ExecutionEngine_EndToEnd](ExecutionEngine_EndToEnd.md)（“Fast interpreter（IRTOC/LLVM）”相关框）
- 运行时入口与选型：[IRTOC_FastInterpreter](IRTOC_FastInterpreter.md)
- `.irt` 逐行证据（更细）：[irtoc_scripts_interpreter.irt](../FileNotes/irtoc_scripts_interpreter.irt.md)、[irtoc_scripts_common.irt](../FileNotes/irtoc_scripts_common.irt.md)
- `.irt → Graph → 机器码` 的实现源码入口（建议收藏）：
  - Ruby 侧生成器：`irtoc/lang/irtoc.rb`、`irtoc/lang/function.rb`
  - C++ 侧编译器：`irtoc/backend/irtoc.cpp`、`irtoc/backend/compilation.cpp`、`irtoc/backend/function.cpp`
  - Graph 类型与 IR 构造器：`compiler/optimizer/ir/graph.h`、`compiler/optimizer/ir/ir_constructor.h`

## 1) 你首先要形成的 3 个心智模型（非常关键）

### 1.1 `.irt` 不是“解释器源码”，而是“生成器 + IR 构造脚本”

`irtoc/scripts/interpreter.irt` 是一个 Ruby 脚本，它通过 DSL 构造 **IR 图（Graph）**，再由 IRTOC/LLVM backend 生成 `ExecuteImplFast*` 与 `HANDLE_FAST_*` 机器码。

> 也就是说：你改 `.irt`，不会影响 C++ interpreter 的 handler；它影响的是 fast interpreter 的生成物。

### 1.2 `.irt` 的三层结构：Ruby 控制流 / DSL 节点 / Runtime layout 常量

- **Ruby 控制流**：`if Options.arm64?`、`Panda.instructions.each` 等，决定生成哪些代码
- **DSL 节点构造**：`LoadI/AddI/StoreI/Call/Intrinsic/If/Phi/Cast...`（这是“IR 指令”）
- **运行时布局常量**：来自 `include_relative 'common.irt'` 的 `Constants`、regmap（Frame/Thread/Method offset、entrypoint id 等）

### 1.3 fast interpreter 的“内部 ABI”是性能核心

fast interpreter 把解释器核心状态长期放在固定寄存器（`tr/pc/frame/acc/dispatch`），通过 `dispatch_table[opc]` 做 computed-goto（tail-call）。

对应证据链：
- `.irt` 语义：`macro(:dispatch)`（见 [irtoc_scripts_interpreter.irt](../FileNotes/irtoc_scripts_interpreter.irt.md)）
- build 产物：[build_runtime_include_irtoc_interpreter_utils.h](../FileNotes/build_runtime_include_irtoc_interpreter_utils.h.md)
- 汇编证据：[build_irtoc_irtoc_interpreter_disasm.txt](../FileNotes/build_irtoc_irtoc_interpreter_disasm.txt.md)

## 2) `.irt` DSL 的“最小语法集”（够你改 80% 的问题）

### 2.1 定义 macro（可复用片段）

形态：

```ruby
macro(:readbyte) do |pc, offset|
  LoadI(pc).Imm(offset).u8
end
```

要点：
- `macro(:name)` 定义一个可被其他宏/handler 调用的“模板片段”
- 里面的 `LoadI/AddI/...` 是 IR 节点构造器
- 末尾的 `.u8/.i32/.ref/...` 是 **把 IR 节点标注为某种 DataType**

### 2.2 `x := ...`：创建一个 IR 值（SSA 风格）

你会经常看到：

```ruby
opc := readbyte(pc, 0)
offset := Mul(u8toword(opc), WordSize())
addr := Load(table, offset)
tail_call(addr)
```

直觉理解：
- `:=` 不是 Ruby 的赋值语法，它是 DSL 定义的“创建 SSA 值/节点”的写法
- 这些值会成为后续 IR 节点的输入

### 2.3 `If ... Phi ...`：控制流与合流

典型：

```ruby
res0 := 0
If(arg, 0).NE do
  res1 := 1
end
Phi(res0, res1).i32
```

要点：
- `If(x, y).NE do ... end` 生成分支
- `Phi(a, b)` 在分支汇合点选择值（SSA 合流）

### 2.4 `Intrinsic(...)`：后端专用的“语义指令”

fast interpreter 的两个高频 intrinsic：
- `Intrinsic(:TAIL_CALL)`：实现 computed-goto 的尾跳转（脚本里通常封装成 `tail_call(addr)`）
- `Intrinsic(:INTERPRETER_RETURN)`：从 fast interpreter “返回到 runtime 边界”（用于异常/非 stackless return 等）

### 2.5 `LiveIn/LiveOut`：把语义寄存器绑到硬件寄存器（别忽略它）

你在 `.irt` 里看到的 `%tr/%pc/%frame/%acc` 等语义寄存器，需要通过 LiveIn/LiveOut 固定到硬件寄存器（由 regmap 决定）。

**常见坑**：改了一个宏/handler 后，如果忘了对关键状态做 LiveOut，可能导致后端把寄存器当成可重用临时寄存器，产生“偶现错误/难复现”。

## 3) 你应该从哪里改（按问题类型给“第一落点”）

> 下面每一条都对应 `interpreter.irt` 中一个稳定锚点，建议新人先从锚点开始 grep。

| 你要改的东西 | `.irt` 第一落点（关键词） | 为什么在这里 |
|---|---|---|
| dispatch/跳表 | `macro(:dispatch)` | 决定 opcode→handler 的 computed-goto 语义 |
| decode/取操作数 | `macro(:readbyte)`、`macro(:as_vreg_idx)`、`macro(:as_id)` | 一切 handler 的 operand 都从这里读出来 |
| acc 写回/恢复 | `save_acc` / `restore_acc` 相关宏 | GC/safepoint/桥接/异常都依赖 acc 一致性 |
| 异常入口 | `move_to_exception` / `find_catch_block` | exception slot 与“两段式异常”在这里落地 |
| OSR 触发/回边 | `instrument_branches` / `handle_fake_return` | OSR 最难理解也最常改动的区域 |
| call/return | `generic_call` / `generic_return` | 编译态调用（I2C）与 stackless 调用在这里统一 |
| 单个 opcode 语义 | `handle_xxx` 宏 + `Panda.instructions.each` 生成段 | 大部分 `HANDLE_FAST_*` 都是“宏展开+生成器” |

更细的逐行证据：直接看 [irtoc_scripts_interpreter.irt](../FileNotes/irtoc_scripts_interpreter.irt.md)（里面已经按上述锚点分段）。

## 4) 新人“怎么改”的标准工作流（VM 架构审计级别）

### 4.1 定位：先从运行时现象回到“你到底跑的是 fast interpreter 吗”

- 用 `--log-level=debug --log-components=runtime:interpreter` 看是否出现 `Setting up LLVM Irtoc dispatch table` / `Setting up Irtoc dispatch table`
- 如果你跑的是 cpp interpreter，你改 `.irt` 不会生效

### 4.2 修改：永远改源码 `irtoc/scripts/interpreter.irt`（不要改 build 产物）

你会看到三份相关文件：
- 源码：`irtoc/scripts/interpreter.irt`（改这里）
- 规范化产物：`build/irtoc/irtoc_interpreter/interpreter.irt.fixed`（只读，用于行号与 Loc 对齐）
- 生成 C++：`build/irtoc/irtoc_interpreter/irtoc_code.cpp`（只读，用于 IR 节点定位）

### 4.3 验证（强烈建议按“3 段式证据链”走）

1) **脚本层**：在 `interpreter.irt.fixed` 中确认你的改动确实出现（避免“没触发重新生成”）
2) **IR 层**：在 `irtoc_code.cpp` 找到对应 `Loc(..., <line>)` 与 `INST(id, ...)` 变化
3) **机器码层**：在 `disasm.txt` 找到对应 method 的 `# [inst] <id>`，确认汇编真的变了

参考笔记：
- [build_irtoc_irtoc_interpreter_disasm.txt](../FileNotes/build_irtoc_irtoc_interpreter_disasm.txt.md)
- [build_runtime_include_irtoc_interpreter_utils.h](../FileNotes/build_runtime_include_irtoc_interpreter_utils.h.md)

## 5) 两个“新人必踩坑”与架构层 guardrail

- **坑 1：以为改 C++ handler 会影响生产**  
  生产默认往往是 `--interpreter-type=llvm`（fast interpreter），你需要改的是 `.irt` 或生成链，而不是 `interpreter-inl.h`。

- **坑 2：忘记 acc/pc/frame 的一致性不变量**  
  fast interpreter 里大量 `save_acc/restore_acc`、`update_bytecode_offset` 都不是“多余代码”，它们在 GC/safepoint/异常/桥接边界上是硬不变量。  
  改动时优先问自己：**这条路径上 GC/StackWalker/hook 是否还能看到一致的 acc/frame/pc？**

## 6) 你问的核心：谁把 `.irt` 变成 IR 图？IR 图又是谁编译成机器码？

这一节是“架构师视角的全链路分工”，用来消除新人最常见的误解：  
**`.irt` 本身不会直接变成机器码；它先变成“生成的 C++（irtoc_code.cpp）”，再在构建阶段被一个 `irtoc` 可执行程序跑起来，把 Graph 编译成 `.o`。**

### 6.1 第一步：Ruby 生成器执行 `.irt`，并生成 `irtoc_code.cpp`

生成器入口在 `irtoc/lang/irtoc.rb`，它做了三件关键事：

1) **预处理 DSL 语法**（这是你看到 `:=`、`%tr` 等“非 Ruby”语法还能跑的根因）
   - `(\w+) := ...` 会被转成 `let :name, ...`
   - `%tr/%pc/%frame/...` 会被转成 `LiveIn(regmap[:tr])` 之类
2) **`instance_eval` 执行预处理后的脚本**（这就是“`.irt 是 Ruby 脚本”的现实含义）
3) **把脚本里 `function(...) { ... }` 形成的内容“emit 成 C++ 源码”**（即 `irtoc_code.cpp` / `irtoc_code_llvm.cpp`）

> 你可以把 `.irt` 理解成“用 Ruby 写的代码生成器输入语言”，它的输出是“会构造 Graph 的 C++ 源码”。

### 6.2 第二步：Graph 在哪里生成？是谁生成？

**Graph 不是一个静态文件，它在构建时由 `irtoc` 程序运行时，在内存里创建。**

关键链路是：

- Ruby 生成的 `irtoc_code.cpp` 里会产生很多 `COMPILE(HANDLE_FAST_xxx) { ... }`
- `COMPILE(name)`（定义在 `irtoc/backend/compilation.h`）会把每个函数注册成一个 `Function unit`
- 构建阶段运行 `irtoc` 可执行程序（入口 `irtoc/backend/irtoc.cpp`），它会执行 `Compilation().Run()`
- `Compilation::Compile()` 遍历所有 units，对每个 unit 调 `Function::Compile(...)`
- `Function::Compile` 会 `New<compiler::Graph>(...)` 创建 Graph，并调用 `MakeGraphImpl()` 把 IR 节点塞进 Graph
  - `MakeGraphImpl()` 的主体就是 Ruby 在 `irtoc/lang/function.rb` 里 `emit_ir` 出来的内容
  - IR 节点的构造器是 `compiler::IrConstructor`（见 `compiler/optimizer/ir/ir_constructor.h`）

### 6.3 第三步：谁把 Graph 编译成机器码？机器码生成在哪里？

还是构建阶段的 `irtoc` 可执行程序负责“Graph → 机器码”：

- 对每个 Graph：
  - 先跑 IRTOC 的优化（`RunIrtocInterpreterOptimizations/RunIrtocOptimizations`）
  - 然后进入 codegen，把机器码写入 `graph->GetCode()`（最终会被 `Function::SetCode` 拷贝出来）
- 如果开启了 LLVM IRTOC 路径（`PANDA_LLVM_IRTOC` 等宏），则 `Function::CompileByLLVM()` 会调用 `llvmCompiler_->TryAddGraph(graph)`：
  - **注意**：这是“LLVM 编译 Graph”，不是“clang 编译 C++ interpreter”

构建系统证据（以 CMake 为例）：

- `irtoc/backend/CMakeLists.txt` 的 `irtoc_compile(...)` 会：
  - 先运行 Ruby 生成器产出 `irtoc_code.cpp`（以及可选 `irtoc_code_llvm.cpp`）
  - 编译一个可执行程序 `${TARGET}_exec`（源码包含 `irtoc_code.cpp + irtoc/backend/irtoc.cpp`）
  - 再运行这个可执行程序生成 `${TARGET}.o` / `${TARGET}_llvm.o`，并输出 `disasm.txt`（用于验证机器码）

## 7) IR 图（Graph）到底是什么？怎么理解它？

在本工程里，`compiler::Graph` 是编译器内部的 **SSA/基本块**形式的中间表示（IR）：

- **Graph = BasicBlock 图**（控制流图 CFG）
- **BasicBlock 里是一串 Inst（IR 指令）**（例如 Load/Store/Add/If/Phi/Call/Intrinsic）
- **Phi 节点**表达控制流合流时的 SSA 值选择

你可以把 Graph 理解为“比 C++ 语法更接近 CPU 执行模型、也更利于优化/寄存器分配”的表示形式：  
它能让优化器（CSE/LSE/LICM/RegAlloc/Scheduler…）在“解释器 handler”上做编译器级别的优化，然后再生成机器码。

## 8) fast interpreter 与 C++ interpreter 的关系是什么？

**关系：语义目标相同，落地形态不同。**

- C++ interpreter（`runtime/interpreter/interpreter-inl.h` 等）：
  - 语义实现以 C++ handler 为主
  - dispatch loop/异常入口很多在生成的 `interpreter-inl_gen.h`（模板生成）里
  - 每条 opcode 的执行倾向于“读写 Frame 内存 + 分支/函数调用”

- IRTOC/LLVM fast interpreter（`.irt`）：
  - 仍然以 Frame/VReg/Acc 为语义中心（只是把热点状态缓存到固定寄存器）
  - dispatch 是 computed-goto 的“尾跳转到 handler”（更接近 direct threaded code）
  - handler 是“提前生成的机器码”，而不是运行时频繁经过 C++ 抽象层

> 同一个工程里两条路径并存的意义：  
> C++ interpreter 更适合 debug/可读性；fast interpreter 更适合性能与可控的低层 ABI/寄存器策略。

## 9) 为什么 fast interpreter 更快？（澄清“clang 也会优化”这个误解）

你说的关键疑问是：“C++ interpreter 也是 clang/LLVM 编译的，为什么不一样快？”

要点在于：**是否使用 LLVM 并不是唯一变量，‘程序结构’才是决定解释器性能的核心变量。**

fast interpreter 更快主要来自这些结构性差异：

1) **状态常驻寄存器**：`tr/pc/frame/acc/dispatch` 固定寄存器减少 load/store
2) **direct threaded dispatch**：`dispatch_table[opc]` + `tail_call/jmp`，减少 switch/分支开销
3) **更可控的 ABI 与边界**：acc 写回/恢复、异常入口 slot、OSR fake-return 等都是“写死的协议”，便于全链路优化
4) **编译器 IR 优化适配**：Graph 级优化（CSE/LSE/RegAlloc/Scheduler…）对 handler 这种小热块非常有效

而 C++ interpreter 即便由 clang 编译：

- 也很难自动把它“变形”为同等结构的 direct threaded code（尤其是与 Frame/GC/异常/OSR 协议耦合的部分）
- 大量边界检查、抽象层、以及更保守的别名分析，会限制编译器能做的优化

> 结论：LLVM/clang 能把 C++ 编译成机器码，但不保证它拥有 fast interpreter 那种“为解释器而设计”的执行结构。

## 10) 更详尽的语法参考（教科书式）

如果你希望像 C 语言教科书一样系统学习 DSL（每个构造的语义、类型系统、控制流、LiveIn/LiveOut、常用节点），建议继续读：

- [IRTOC_DSL_Reference](IRTOC_DSL_Reference.md)（更详尽的“语法/语义参考”）


