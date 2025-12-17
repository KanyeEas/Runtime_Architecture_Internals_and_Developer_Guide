# `runtime/bridge/arch/amd64/proxy_entrypoint_amd64.S`（逐行精读｜proxy entrypoint / 异常桥）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：amd64 上的 **proxy entrypoint**：以统一 ABI 包裹真实 `\entry`，必要时构造 `COMPILED_CODE_TO_INTERPRETER_BRIDGE` boundary frame 并写 TLS；返回路径负责“native 异常 → ThrowNativeExceptionBridge”的寄存器恢复与跳转。

## 1) proxy 的核心价值

- **统一入口 ABI**：上层可稳定调用 proxy，proxy 再调用真实 `\entry`（第二阶段/slowpath 入口点常见）
- **异常/栈遍历正确性**：跨边界时需要 boundary frame + callee-saved 可见，且异常路径必须恢复 caller 的寄存器快照

## 2) 构造 boundary frame + 保存 callee-saved

宏 `PROXY_ENTRYPOINT name, entry` 做了典型 C2I frame 形态：

- `pushq $COMPILED_CODE_TO_INTERPRETER_BRIDGE`
- `pushq %rbp ; movq %rsp, %rbp`
- 保存 callee-saved：`r15 r14 r13 r12 rbx`（配 CFI）

## 3) 仅当 caller 为 compiled 时写 TLS

关键逻辑：

- 读 `MANAGED_THREAD_FRAME_KIND_OFFSET(%THREAD_REG)` 到 `%r12b`
- 若为 compiled（非 0），才 `movq %rbp, MANAGED_THREAD_FRAME_OFFSET(%THREAD_REG)`

意义：避免在解释器调用 proxy 时破坏 “thread->currentFrame 指向 Frame* 链” 的语义。

## 4) 参数透传：把寄存器参数变成数组传给 `\entry`

该文件先执行：

- `PUSH_FP_REGS`、`PUSH_GENERAL_REGS`

随后约定：

- `%rsi = %rsp`：指向“已保存的寄存器参数数组”
- `%rdx = rbp + 24`：指向 stack args 区（由 i2c 先压栈的 stack args）
- `callq \entry`

这允许 `\entry` 以统一方式读取“寄存器参数 + 栈参数”。

## 5) 返回路径：异常检测与 ThrowNativeExceptionBridge

返回前会恢复 callee-saved（注释强调：GC 可能移动对象导致寄存器内容变化，所以要从栈恢复）。

随后执行异常分支判断：

- `thread->exception != 0`（`MANAGED_THREAD_EXCEPTION_OFFSET`）
- `caller is compiled`（`%r10b`）
- `prev frame 不是 BYPASS`（检查 `COMP_METHOD_OFFSET` 槽）

如果满足：

- 从 boundary frame 区恢复 caller 的 GPR（以及在 flags 指示下恢复 caller 的 XMM0-XMM15）
- `jmp ThrowNativeExceptionBridge`

> 这是“native 异常向上抛出”路径的硬证据：没有这一段，异常 unwind 会因寄存器/栈状态不完整而失败。

## 6) 对照与链接

- aarch64 对照实现：`runtime/bridge/arch/aarch64/proxy_entrypoint_aarch64.S`
- deopt 变形与 boundary slots：`runtime/bridge/arch/*/deoptimization_*.S`
- 概念/逻辑：`Flows/Bridge_I2C_C2I.md` + `DataStructures/Bridge_ABI_and_FrameKind.md`


