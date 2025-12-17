# `runtime/bridge/arch/amd64/deoptimization_amd64.S`（逐行精读｜deopt 与 boundary frame 变形）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：amd64 上的 **deoptimization 汇编落地**：把“从 compiled 回到解释器”的关键路径做成栈变形与寄存器恢复逻辑。核心入口包括：
> - `DeoptimizeAfterCFrame`：把一个 CFrame **变形（morph）为 C2I boundary frame**，再调用 `InvokeInterpreter`
> - `DeoptimizeAfterIFrame`：在已有 IFrame 语义的场景下恢复寄存器并进入解释器
> - `DropCompiledFrameAndReturn`：丢弃 compiled 帧并安全返回（避免 StackWalker 校验失败）

## 1) `DeoptimizeAfterCFrame`：CFrame → C2I boundary frame（硬证据）

文件注释直接给出变形目标：

- FROM：`lr ; fp <--- ; method`
- TO：`lr ; COMPILED_CODE_TO_INTERPRETER_BRIDGE ; fp <---`

关键实现点：

- 以 `%rcx`（cframe origin）为 CFA，重算 `%rsp` 到 boundary 预留区：  
  `leaq -(((CFRAME_HEADER_SIZE - 2) * 8) + CALLEE_SAVED_SIZE)(%rcx), %rsp`
- 将 `COMPILED_CODE_TO_INTERPRETER_BRIDGE` 写入固定槽位：  
  `movq $COMPILED_CODE_TO_INTERPRETER_BRIDGE, (INT_METHOD_OFFSET * 8)(%rcx)`
- **把 last IFrame 的 `prev_frame` 指向该 boundary**：  
  `movq %rcx, FRAME_PREV_FRAME_OFFSET(%r8)`

> 这条是“逻辑 IFrame 链”与“物理 boundary frame”在 deopt 时如何接起来的根证据。

## 2) boundary slots：从 CFrame 拷贝 callee-saved 到 boundary frame

该函数计算 `BOUNDARY_FRAME_SLOT`，然后：

- 从 cframe 的 callee-saved 区取值
- 写入 boundary frame 固定 slots（并设置 CFI 偏移）

这保证 deopt 后 StackWalker 能在 boundary 上正确读取 caller 的 callee-saved 快照。

## 3) 调用 `InvokeInterpreter`：签名对齐减少参数搬运

文件注释指出：

- `DeoptimizeAfterCFrame` 的参数签名与 `InvokeInterpreter` 相似，因此参数基本已就位。

实现上：

- 保存少量临时寄存器
- `movq %r8, %rcx`（把 last restored IFrame 放到 `InvokeInterpreter` 需要的位置）
- `callq InvokeInterpreter`
- `movq %rax, %xmm0`（解释器返回 int64，但可能是 double：用位模式转移）

## 4) `DeoptimizeAfterIFrame`（简述）

该路径不做“CFrame→boundary 变形”，而是：

- 恢复 `%rsp` 到 cframe 的 `%rbp`
- 恢复 callee-saved
- `callq InvokeInterpreter`
- 返回前同样 `movq %rax, %xmm0` 兼容浮点返回

## 5) `DropCompiledFrameAndReturn`：避免 StackWalker 校验失败

该函数会：

- 从被丢弃的 CFrame 恢复 callee-saved
- **清空 `%rax`**（注释解释：否则垃圾会写到 IFrame.acc，导致 StackWalker verification 失败）
- 返回到上层

## 6) 对照与链接

- aarch64 对照实现：`runtime/bridge/arch/aarch64/deoptimization_aarch64.S`
- `InvokeInterpreter` 语义骨架：`runtime/bridge/bridge.cpp`
- StackWalker/ConvertToIFrame：`runtime/stack_walker.cpp`
- 概念/逻辑：`Flows/Deopt_and_OSR.md` + `Flows/Bridge_I2C_C2I.md`


