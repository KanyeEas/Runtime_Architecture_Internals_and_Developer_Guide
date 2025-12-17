# `runtime/bridge/arch/aarch64/proxy_entrypoint_aarch64.S`（逐行精读｜proxy entrypoint / 异常桥）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：aarch64 上的 **proxy entrypoint**：用一个“可被通用方式调用”的桥接入口包裹真实目标 entry（`\entry`），在必要时建立 C2I boundary frame 写 TLS，并在返回路径上处理“native 异常 → ThrowNativeExceptionBridge” 的跳转与寄存器恢复。

## 1) proxy 为什么存在

proxy 解决两个现实问题：

- **统一入口 ABI**：上层可以稳定地以“proxy 约定”调用各种 runtime/slowpath/entrypoint，而 proxy 再转发到真实 `\entry`。
- **异常与栈遍历正确性**：当调用链跨越 compiled/解释器边界时，需要构造可识别的 boundary frame，并在返回时把寄存器恢复到“可继续 unwind/抛异常”的形态。

## 2) 构造 C2I boundary frame + 保存 callee-saved

宏 `PROXY_ENTRYPOINT name, entry, skip_c2i_bridge` 在入口处：

- 保存 `lr` 并把 `lr` 置为 `COMPILED_CODE_TO_INTERPRETER_BRIDGE`
- 建立 `fp`
- `PUSH_CALLEE_REGS sp` 保存 x19-x28 与 d8-d15，并配套 CFI（便于 unwind）

## 3) 何时写 TLS：仅当 caller 是 compiled

关键逻辑：

- 读取 `MANAGED_THREAD_FRAME_KIND_OFFSET`
- 只有当 “caller 为 compiled” 时才 `str fp, [THREAD_REG, #MANAGED_THREAD_FRAME_OFFSET]`

意义：

- 如果 caller 本身就是解释器侧，TLS 已经指向解释器 `Frame*` 链，无需覆盖。
- 如果 caller 是 compiled，proxy 必须把 boundary frame 暴露给 StackWalker/GC（safepoint 可见性）。

## 4) 参数透传：把寄存器参数保存为数组传给 `\entry`

文件会把参数寄存器（x0-x7 / d0-d7）压栈，然后：

- `x1 = sp`：指向“保存的寄存器参数数组”
- `x2 = fp + 24`：指向 caller 的 stack args 区
- `bl \entry`

这与 amd64 版本的注释一致（rsi 指向 pushed args，rdx 指向 stack args）。

## 5) 返回路径：异常检测与 ThrowNativeExceptionBridge

返回前会：

- 恢复 callee-saved（注意注释：“GC may change its values while moving objects.”）
- 恢复 `fp/lr/sp`
- 检查 `MANAGED_THREAD_EXCEPTION_OFFSET`（thread->exception 是否非空）
- 如果存在异常，且 caller 为 compiled，且 prev frame 不是 `BYPASS_BRIDGE`，则：
  - 从 boundary frame 区恢复 caller 的 GPR/FPR（包含是否存在浮点寄存器的 flags）
  - `b ThrowNativeExceptionBridge`

> 这段是“异常从 native/compiled 回到 runtime 抛出路径”的物理证据：它解释了为什么异常路径需要“恢复 caller 寄存器快照”，否则 unwind/抛异常时寄存器状态不完整。

## 6) 与本章其他证据的连接点

- amd64 对照实现：`runtime/bridge/arch/amd64/proxy_entrypoint_amd64.S`
- deopt 与 boundary frame：`runtime/bridge/arch/*/deoptimization_*.S`
- 概念/逻辑：[Bridge_I2C_C2I（Flow）](../Flows/Bridge_I2C_C2I.md) + [Bridge_ABI_and_FrameKind（DataStructure）](../DataStructures/Bridge_ABI_and_FrameKind.md)


