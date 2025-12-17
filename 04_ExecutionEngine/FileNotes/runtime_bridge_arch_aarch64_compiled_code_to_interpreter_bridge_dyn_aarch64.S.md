# `runtime/bridge/arch/aarch64/compiled_code_to_interpreter_bridge_dyn_aarch64.S`（逐行精读｜C2I(Dyn) 物理落地）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：aarch64 上的 **C2I（Dynamic calling convention）**：为动态语言/TaggedValue 语义提供 compiled→解释器回退路径。整体形态与静态 `C2I` 相同：先构造 `COMPILED_CODE_TO_INTERPRETER_BRIDGE` boundary frame 并写 TLS，随后做 hotness/编译探测；若仍未编译则创建 `IFrame`（按“实际参数个数”）并进入 `InterpreterEntryPoint`，最后从 `acc/acc_mirror` 还原返回寄存器并返回给 compiled caller。

## 1) 入口与 TLS：与静态 C2I 完全一致的关键不变量

你能在文件开头直接看到与静态版相同的三件事：

- 构造 `COMPILED_CODE_TO_INTERPRETER_BRIDGE` boundary frame（`lr + marker + fp`）
- `PUSH_CALLEE_REGS` 保存 callee-saved（供 StackWalker/GC/unwind）
- `str fp, [THREAD_REG, #MANAGED_THREAD_FRAME_OFFSET]` 在调用 `DecrementHotnessCounterDyn` 前写 TLS（保障 safepoint 可遍历）

## 2) 编译成功：直接 `br entrypoint`

当 `DecrementHotnessCounterDyn` 返回非 0：

- 恢复 TLS：`ldr lr, [fp] ; str lr, [THREAD_REG, #MANAGED_THREAD_FRAME_OFFSET]`
- 恢复 `fp/lr/sp` 后 `br METHOD_COMPILED_ENTRY_POINT`

## 3) 未编译：按“实际参数个数”创建 IFrame 并初始化 rest args

与静态 shorty 不同，dyn 版会：

- 调 `CreateFrameForMethodWithActualArgsDyn(actual_num_args, method, prev)`
- 计算 `num_iframe_args = max(actual_num_args, method->num_args_)`
- 将实参从 caller 栈拷贝到 `frame->vregs_` 末尾对应区域
- 对不足部分用 `TAGGED_VALUE_UNDEFINED` 初始化（“rest args”）

## 4) 进入解释器与返回值还原

- `InterpreterEntryPoint(method, iframe)`
- 从 `FRAME_ACC_OFFSET` 与 `FRAME_ACC_MIRROR_OFFSET` 取 `(value, tag)`，`FreeFrame` 后：
  - `x0 = value`
  - `x1 = tag`

## 5) 与本章其他证据的连接点

- 静态 C2I（shorty 驱动）对照：`runtime/bridge/arch/aarch64/compiled_code_to_interpreter_bridge_aarch64.S`
- dyn I2C 对照：`runtime/bridge/arch/aarch64/interpreter_to_compiled_code_bridge_dyn_aarch64.S`
- 概念/逻辑：`Flows/Bridge_I2C_C2I.md` + `DataStructures/Bridge_ABI_and_FrameKind.md`


