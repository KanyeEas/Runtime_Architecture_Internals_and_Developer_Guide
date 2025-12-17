# `runtime/bridge/arch/aarch64/interpreter_to_compiled_code_bridge_dyn_aarch64.S`（逐行精读｜I2C(Dyn) 物理落地）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：aarch64 上的 **I2C（Dynamic calling convention）**：服务于动态语言/TaggedValue 语义的解释器→编译桥接。它与静态版本最大的不同点是：**参数来源不再是 shorty，而是“实际参数个数 + TaggedValue 数组/栈布局”**；dispatch 逻辑仍由模板生成，并最终调用 compiled entrypoint，再把结果写回 `frame->acc`。

## 1) boundary marker 的选择规则与静态版一致

入口处同样根据 `MANAGED_THREAD_FRAME_KIND_OFFSET(thread)` 在栈上写入：

- `INTERPRETER_TO_COMPILED_CODE_BRIDGE`
- 或 `BYPASS_BRIDGE`

这保证 StackWalker 能在 IFrame/CFrame 两套解码规则之间正确切换。

## 2) dyn dispatch：`bridge_dispatch_dyn_aarch64.S`

该文件读取 opcode（含 prefix opcode），进入 `.Ldispatch`：

- `#include "bridge_dispatch_dyn_aarch64.S"`
- 注释明确指出：该文件由 `runtime/templates/bridge_dispatch.S.erb` 生成，并进一步依赖 `handle_call_<format>.S`

> 这部分的“证据链价值”在于：当新增 call format 时，这里会提示缺少对应 handler（编译报错路径清晰）。

## 3) 调用 compiled entrypoint 与返回值写回

关键动作：

- 调用：`ldr lr, [x0, METHOD_COMPILED_ENTRY_POINT_OFFSET] ; blr lr`（x0 为 `Method*`）
- 写回：把返回值写入 `FRAME_ACC_OFFSET(frame)`（该文件明确 `str x0, [frame.acc]`）

## 4) 与静态 I2C 的关系

- 静态 I2C（shorty 驱动）详见：`runtime/bridge/arch/aarch64/interpreter_to_compiled_code_bridge_aarch64.S`
- dyn I2C 的核心差异是“参数装配规则”：
  - 静态：shorty 决定 GPR/FPR/stack 的布局与 tag(mirror)
  - dyn：以 TaggedValue/实际参数个数为中心，按动态调用约定组织参数


