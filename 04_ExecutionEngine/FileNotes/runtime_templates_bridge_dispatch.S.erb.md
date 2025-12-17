# `runtime/templates/bridge_dispatch.S.erb`（I2C dispatch：按 call-format 分发到 handler）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：生成 `bridge_dispatch_<arch>.S` 的模板文件，用于 I2C bridge（static shorty calling convention）在汇编里按 “call 指令的 format/分类” 分发到对应的 `handle_call_<format>.S` 片段。

## 1) 这模板解决什么问题

I2C bridge 的核心任务是：把解释器侧的“调用指令 + Frame/Method/Thread”等信息，按目标平台 ABI 组装成调用参数，并调用 `method->compiled_entrypoint`。

但 call 指令存在多种 format（不同操作数布局/传参规则），因此桥接汇编需要先做一次 **按 format 的分发**：

- 识别当前 call opcode 属于哪个 format
- 跳转到该 format 的 handler（`handle_call_<format>.S`）去组装参数并发起调用

## 2) 模板结构（读懂就能读懂生成物）

模板本身很短，但信息密度很高，核心是两段循环：

### 2.1 比较 opcode 并跳转到 `.Lhandle_<fmt>`

- `calls = get_call_insns()`：收集所有 call 类指令（来自 ISA/脚本侧）
- `classified_calls = classify_calls(calls)`：按 format 分类
- 对每个 format，生成一串：
  - `cmp_opcode(insn.opcode_idx)`
  - `jump_eq(".Lhandle_#{fmt}")`

### 2.2 在 `.Lhandle_<fmt>` 中 `#include` 对应 handler

对每个 format 生成一个 label：

- `.Lhandle_<fmt>:` 后紧接 `#include "<%= handler_path(fmt) %>"`

这些被 include 的 `handle_call_<format>.S` 才是“真正组装参数/调用 entrypoint/写回返回值”的实现片段。

## 3) 生成链（模板 → 生成 .S → 被 I2C include）

证据链（从构建系统到最终汇编）：

- **GN**：`runtime/BUILD.gn`
  - `bridge_dispatch_template = "templates/bridge_dispatch.S.erb"`
  - 生成输出：`bridge_dispatch_<arch>.S`
- **CMake**：`runtime/CMakeLists.txt`
  - `BRIDGE_DISPATCH_TEMPLATE=.../templates/bridge_dispatch.S.erb`
  - 生成输出：`${GEN_INCLUDE_DIR}/bridge_dispatch_${arch}.S`
- **I2C 汇编使用点**（示例）：
  - `runtime/bridge/arch/aarch64/interpreter_to_compiled_code_bridge_aarch64.S` 中 `#include "bridge_dispatch_aarch64.S"`
  - `runtime/bridge/arch/amd64/interpreter_to_compiled_code_bridge_amd64.S` 中 `#include "bridge_dispatch_amd64.S"`
  - `runtime/bridge/arch/x86/interpreter_to_compiled_code_bridge_x86.S` 中 `#include "bridge_dispatch_x86.S"`


