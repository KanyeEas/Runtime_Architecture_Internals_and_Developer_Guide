# IRTOC `.irt` DSL 参考（更“教科书式”的语法/语义说明）

> 目标：比 [IRTOC_DSL_Primer](IRTOC_DSL_Primer.md) 更系统。你可以把它当作“查手册”：  
> - 看到一段 `.irt` 不认识的写法，来这里找“它是什么 / 它等价于什么 / 常见坑是什么”。  
> - 仍然坚持一个原则：每条规则都能回到源码/生成物验证（证据链在每节末尾）。

## 0) 入口与证据链

- 新人先读：[IRTOC_DSL_Primer](IRTOC_DSL_Primer.md)（管线 + 心智模型 + 工作流）
- Ruby 生成器源码：`irtoc/lang/irtoc.rb`、`irtoc/lang/function.rb`
- C++ 编译器源码：`irtoc/backend/compilation.h/.cpp`、`irtoc/backend/function.cpp`
- Graph/IR 定义：`compiler/optimizer/ir/graph.h`、`compiler/optimizer/ir/ir_constructor.h`

## 1) 语言分层：哪些是 Ruby？哪些是 DSL？

在 `.irt` 里你会同时看到两类语法：

- **Ruby 控制流/元编程**（由 Ruby 解释执行）：
  - `if Options.arm64?`
  - `array.each do |x|`
  - `def helper(...) ... end`
- **IRTOC DSL**（最终构造成 compiler IR Graph）：
  - `macro(:name) do |...| ... end`
  - `x := LoadI(...)...`
  - `If(...).NE do ... end`
  - `Phi(a, b).i32`
  - `Intrinsic(:INTERPRETER_RETURN)`

判定方法（实战）：  
**只要它最后会落到 `LoadI/AddI/If/Phi/Intrinsic/Call/...` 这类“节点构造器”，它就在构造 IR。**

## 2) 预处理语法（为什么 `.irt` 看起来不像 Ruby 还能跑）

`irtoc/lang/irtoc.rb` 会对每行做预处理（再 `instance_eval`），常见规则：

- `name := expr` → `let :name, expr`（把“DSL 赋值”变成 Ruby 方法调用）
- `%tr/%pc/%frame/...` → `LiveIn(regmap[:tr])`（把语义寄存器引用变成 LiveIn）
- `} Else` → `}; Else`（修复 Ruby 语法歧义，便于生成器解析）

> 结论：`.irt` 不是纯 Ruby 语法，而是“Ruby + 预处理 DSL”的混合语言。

## 3) 核心概念：Graph / BasicBlock / Inst（你该如何心智化）

### 3.1 Graph 是什么

Graph 是编译器内部 IR（SSA + CFG）。你可以把它理解为：

- 一个控制流图（BasicBlocks 组成）
- 每个 BasicBlock 里是一串 IR 指令（Inst）
- Phi 节点是 SSA 合流

### 3.2 Inst 是什么

每个 `LoadI/AddI/...` 都对应一种 IR 指令类型；后续优化/寄存器分配/指令选择都会以 Inst 为单位工作。

### 3.3 `.irt` 在构造 Graph 时的“隐含上下文”

对解释器 handler（Interpreter/InterpreterEntry 模式）而言，Graph 隐含了：

- arch（目标架构）
- runtime interface（`IrtocRuntimeInterface`）
- 固定寄存器与 LiveIn/LiveOut 的约束
- Frame/Thread/Method 等布局 offset（来自 `common.irt` 的 Constants）

## 4) `macro`：可复用片段（相当于 DSL 的“内联函数”）

### 4.1 `macro(:name) do |args| ... end`

- 定义为 `Function` 类的方法（所以宏本质是 Ruby 的方法）
- 被其他宏/handler 直接调用
- 宏里返回的最后一个 IR 值通常是“该宏的结果”

### 4.2 `scoped_macro`（局部变量/label 作用域更强）

如果你需要在宏内部创建 label/locals，并避免污染外层，使用 `scoped_macro`。

## 5) `x := ...` 与 SSA 值

`x := expr` 是“创建 SSA 值”的语法糖：

- 不要把它理解成 C 的变量赋值
- 更像“把一个 IR 指令的结果绑定到一个名字，供后续 IR 指令引用”

## 6) 类型系统：`.u8/.i32/.ref/.any` 到底在干什么

在 DSL 里，很多节点构造器后面会接 `.u8/.i32/.i64/.ref`：

- 它们给 IR 节点标注 DataType
- 对优化/指令选择/寄存器分配至关重要

实战建议：  
当你看到“对象/primitive 混乱”“tag 错”“32/64 截断错”，优先检查：

- `common.irt` 里的 `Constants::REF_UINT` 等类型定义
- 你改的节点是否误用了 `.u32/.i32` 导致隐式截断

## 7) 控制流：`If` / `Phi` / label（你应该怎么写才不踩坑）

### 7.1 `If(x, y).NE do ... end`

会生成条件分支与两个 basic blocks（概念上），并把 IR 指令放入对应 block。

### 7.2 `Phi(a, b)`

只有在“控制流合流点”才合法；否则会被验证器/构造器认为是无意义的 SSA 合流。

## 8) `Intrinsic(...)`：后端约定的“语义指令”

fast interpreter 最常见的 intrinsic：

- `:TAIL_CALL`：实现 computed-goto（跳到下一 handler）
- `:INTERPRETER_RETURN`：返回到 runtime 边界

> 你改 dispatch/异常/OSR 时，通常绕不开 Intrinsic。

## 9) LiveIn/LiveOut：寄存器约定（fast interpreter 的生命线）

### 9.1 为什么必须显式 LiveOut

fast interpreter 的性能来自固定寄存器，但固定寄存器同时也是“后端可能复用的资源”。  
如果你在关键路径上没把状态 LiveOut，后端可能会把它当临时寄存器覆盖，导致错误。

### 9.2 常见需要 LiveOut 的状态

- `pc/table/frame/tr`（dispatch 需要）
- `acc/acc_tag`（GC/safepoint/异常/桥接需要）

## 10) 建议的学习路径（像学 C 一样学 DSL）

如果你要“系统掌握”：

1) 先把 [IRTOC_DSL_Primer](IRTOC_DSL_Primer.md) 的 **6/7/8/9 节**吃透（管线 + Graph + 性能原因）
1) 先把 [IRTOC_DSL_Primer](IRTOC_DSL_Primer.md) 的 **6/7/8/9 节**吃透（管线 + Graph + 性能原因）
2) 再按 [irtoc_scripts_common.irt](../FileNotes/irtoc_scripts_common.irt.md) 学会读 `Constants/regmap`
3) 最后按 [irtoc_scripts_interpreter.irt](../FileNotes/irtoc_scripts_interpreter.irt.md) 的锚点，把 dispatch/exception/OSR/call-return 逐段读完


