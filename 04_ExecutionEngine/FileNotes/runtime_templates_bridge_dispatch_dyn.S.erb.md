# `runtime/templates/bridge_dispatch_dyn.S.erb`（I2C dyn dispatch：动态调用约定）

> 章节归属：Stage2 / 04_ExecutionEngine  
> 文件角色：生成 `bridge_dispatch_dyn_<arch>.S` 的模板文件，供 dynamic/TaggedValue 语义的 I2C bridge 使用（把不同 call format 分发到各 `handle_call_<format>_dyn.S` 片段）。

## 1) 为什么需要 dyn dispatch

动态语言/TaggedValue 调用在桥接层通常需要：

- 额外的 tag/value 处理
- 更复杂的参数展开/压栈策略
- 与静态 shorty 调用不同的返回值写回规则

因此 dyn I2C 会使用独立的 dispatch 生成物：`bridge_dispatch_dyn_<arch>.S`。

## 2) 生成链（证据链）

- **GN**：`runtime/BUILD.gn`
  - `bridge_dispatch_dyn_template = "templates/bridge_dispatch_dyn.S.erb"`
  - 生成输出：`bridge_dispatch_dyn_<arch>.S`
- **CMake**：`runtime/CMakeLists.txt`
  - `BRIDGE_DISPATCH_DYN_TEMPLATE=.../templates/bridge_dispatch_dyn.S.erb`
  - 生成输出：`${GEN_INCLUDE_DIR}/bridge_dispatch_dyn_${arch}.S`
- **dyn I2C 汇编使用点**（示例）：
  - `runtime/bridge/arch/aarch64/interpreter_to_compiled_code_bridge_dyn_aarch64.S` 中 `#include "bridge_dispatch_dyn_aarch64.S"`
  - `runtime/bridge/arch/amd64/interpreter_to_compiled_code_bridge_dyn_amd64.S` 中 `#include "bridge_dispatch_dyn_amd64.S"`


