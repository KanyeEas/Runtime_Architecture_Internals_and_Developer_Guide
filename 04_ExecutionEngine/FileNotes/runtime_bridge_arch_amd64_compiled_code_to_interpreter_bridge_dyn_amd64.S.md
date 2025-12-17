# `runtime/bridge/arch/amd64/compiled_code_to_interpreter_bridge_dyn_amd64.S`（逐行精读｜C2I(Dyn) 物理落地）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：amd64 上的 **C2I（Dynamic calling convention）**：为动态语言/TaggedValue 语义提供 compiled→解释器回退路径。整体形态与静态 C2I 相同：先构造 `COMPILED_CODE_TO_INTERPRETER_BRIDGE` boundary frame、保存 callee-saved、写 TLS（保证 safepoint/StackWalker 可见），然后做 `DecrementHotnessCounterDyn` 探测；若仍未编译则创建 `IFrame`（按实际参数个数）并进入 `InterpreterEntryPoint`，最后从 `acc/acc_mirror` 取回 `(value, tag)` 返回给 compiled caller。

## 1) TLS 与 callee-saved：与静态 C2I 相同的硬约束

文件明确包含三件事：

- 保存 return address 到 `MANAGED_THREAD_NATIVE_PC_OFFSET(%THREAD_REG)`
- `pushq $COMPILED_CODE_TO_INTERPRETER_BRIDGE` + `rbp` 建立 boundary frame
- 调 `DecrementHotnessCounterDyn` 前：`movq %rbp, MANAGED_THREAD_FRAME_OFFSET(%THREAD_REG)`

## 2) 编译成功：直接 `jmp entrypoint`

当 `DecrementHotnessCounterDyn` 返回非 0：

- 恢复 TLS：`movq (%rbp), %r8 ; movq %r8, MANAGED_THREAD_FRAME_OFFSET(%THREAD_REG)`
- 拆除 C2I 桥（恢复寄存器/栈）
- `movq METHOD_COMPILED_ENTRY_POINT_OFFSET(%rdi), %rax ; jmp *%rax`

## 3) 未编译：按“实际参数个数”创建 IFrame + 初始化 rest args

dyn 版不会解析 shorty 来搬运参数，而是：

- `CreateFrameForMethodWithActualArgsDyn(actual_num_args, method, prev)`
- `num_iframe_args = max(actual_num_args, method->num_args_)`
- 把 caller stack 上的实参拷贝进 `frame->vregs_` 末尾区域
- 对不足部分用 `TAGGED_VALUE_UNDEFINED` 初始化

并在某些配置下初始化 EcmascriptEnvironment（文件内有条件编译块）。

## 4) 进入解释器与返回值还原

- `InterpreterEntryPoint(method, iframe)`
- 从 `FRAME_ACC_OFFSET` + `FRAME_ACC_MIRROR_OFFSET` 取回 `(value, tag)`，`FreeFrame` 后：
  - `%rax = value`
  - `%rdx = tag`

## 5) 对照与链接

- 静态 C2I（shorty 驱动）对照：`runtime/bridge/arch/amd64/compiled_code_to_interpreter_bridge_amd64.S`
- dyn I2C（配套入口）：`runtime/bridge/arch/amd64/interpreter_to_compiled_code_bridge_dyn_amd64.S`
- 概念/逻辑：`Flows/Bridge_I2C_C2I.md`


