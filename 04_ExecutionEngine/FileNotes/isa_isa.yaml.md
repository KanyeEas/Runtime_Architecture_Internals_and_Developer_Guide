# `isa/isa.yaml`（逐行精读｜Core ISA：opcode 的“规范源”）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件规模：约 3.4k 行（ISA 规范 + 全量 core 指令表）  
> 本文件角色：定义 **Panda VM 的 core bytecode**：寄存器/acc 模型、calling sequence、prefixes、指令集合、encoding formats、verification 与 exceptions。  
> “执行引擎”章节为什么必须包含它：因为 IRTOC fast interpreter 的 `Panda.instructions` 就是由 ISA 驱动生成的——你想理解 `HANDLE_FAST_CALL_*`、`HANDLE_FAST_JMP_*`、`HANDLE_FAST_RETURN_*` 的语义，必须回到 ISA。

---

## 0) 顶层 `chapters`：解释器模型的“规范文字”（L16–L105）

这一段不是实现，但它是**所有实现必须满足的语义契约**，尤其对新同学非常重要：

- **VM 是 register-based + accumulator**（General Design / Accumulator）
- **Calling Sequence**（最关键）：
  - call 会创建新 frame 并复制参数
  - callee 的 accumulator 视为 **undefined**（verified bytecode 不应读取）
  - return 把结果通过 accumulator 返给 caller；`return.void` 后 caller 的 accumulator 也视为 undefined

> 这直接解释了：为什么 IRTOC 的 `generic_call` 会创建 stackless frame + 设置 next_pc，为什么 `generic_return` 在 stackless 情况下把 acc copy 回 caller frame。

---

## 1) `properties`：指令语义标签（L110–L155）

这里的 tag（如 `call/return/jump/init_obj/any_call`）用于：

- 把指令分组（生成器/优化器/验证器）
- 控制某些生成策略（例如 call/branch 相关插桩）

> 新人常见误区：properties 不是 runtime flag，但它决定“哪些指令需要特别的框架逻辑”（call/return/branch）。

---

## 2) `exceptions` / `verification`：正确性约束的“规范源”（L155–L251）

- `exceptions`：如 `x_null/x_bounds/x_call/x_oom/x_throw`
- `verification`：如 `branch_target/acc_obj_or_null/v1_object/method_id_non_static`

这两部分是：
- 解释器实现异常路径的依据（throw/catch/unwind）
- verify 阶段保证“哪些行为不会发生”的依据（例如 acc undefined 不能读）

---

## 3) `prefixes`：core 前缀 opcode（L252–L268）

core 本身就使用前缀扩展 opcode 空间：

- `bit/unsigned/cast/f32/any`，并各自有 `opcode_idx`

这决定了 encoding 中：
- `pref_op_*` 这种 format 的存在
- 解释器 decode 需要先识别 prefix，再解释后续 operands

---

## 4) `groups` / `instructions`：指令表（核心）

每个 group 通常包含：

- `title/description/pseudo`
- `exceptions/verification/properties`
- `instructions` 列表：每条指令给出：
  - `sig`：语法签名（包含操作数、方向、类型）
  - `acc`：acc 的 in/out/inout 语义
  - `format`：encoding 模板（决定 decode 如何读 operand）
  - `opcode_idx`：实际 opcode 编号（或 prefix 下的索引）

### 4.1 常用 opcode 的“源头位置”（建议新同学先看）

- **branch/jmp**：`jmp`/`jeqz/jnez/...` 这类指令的 pseudo + `branch_target` 验证
- **call/return**：`call.*` / `return.*` / `return.void`
- **throw**：`throw v:in:ref`
- **ldobj/stobj**：field 访问与 `field_id` 语义

它们在 IRTOC 里分别对应：

- `HANDLE_FAST_JMP_IMM*`（并在 backedge 上做 OSR 插桩）
- `HANDLE_FAST_CALL_*` / `HANDLE_FAST_RETURN_*`
- `HANDLE_FAST_THROW_V8`
- `HANDLE_FAST_LDOBJ_*` / `HANDLE_FAST_STOBJ_*`

---

## 5) ISA 如何进入 IRTOC 的生成链（你要记住的桥梁）

在 `irtoc/scripts/interpreter.irt` 末尾：

- `Panda.instructions.each do |i| ... function("HANDLE_FAST_#{handler_name}") ... end`

而 `handler_name` 的命名来自 ISA 生成工具（通常把 mnemonic + operand encoding 形态编码进名字，例如 `CALL_RANGE_V8_ID16`）。  
最终：

- `HANDLE_FAST_*` 进入 `build/runtime/include/irtoc_interpreter_utils.h` 的 392 项 dispatch table


