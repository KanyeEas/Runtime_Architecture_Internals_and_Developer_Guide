# `plugins/ets/runtime/ani/ani_options_parser.h`（逐行精读）

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：声明 `OptionsParser`，用于 `ANI_CreateVM` 解析 `ani_options` 并产出三类结果：
> - `ANIOptions`（ANI 自身的开关：logger/verify/interop）
> - `logger::Options`（日志系统）
> - `RuntimeOptions`（运行时配置，且默认设为 ets runtime）
> - 以及 compiler options parser（通过 `compiler::g_options`）

## 1. 产物 getter（L37–L50）

- `GetANIOptions()`：给 `ani_vm_api.cpp` 决定 interop/verify 分支。
- `GetLoggerOptions()`：用于 `Logger::Initialize(...)`
- `GetRuntimeOptions()`：用于 `Runtime::Create(...)`

## 2. 解析流程的关键内部类型（L53–L70）

### 2.1 `Option`：扩展 option 的拆解结果（L53–L58）

- `fullName`：原始字符串（如 `--ext:foo=bar`）
- `name`：去掉 prefix 的名字（如 `foo`）
- `value`：`bar`
- `opt`：指向原始 `ani_option`，以便检查 `extra` 语义

### 2.2 `OptionsMap`（L60–L60）

- `map<name, unique_ptr<Option>>`：用于把 ext options 暂存并分派给 logger/runtime/compiler 三个 parser。

### 2.3 三个 parser（L74–L81）

- `loggerOptionsParser_` + `loggerOptions_`
- `runtimeOptionsParser_` + `runtimeOptions_`
- `compilerOptionsParser_`

> `PrepareEtsVmOptions()` 会把 ETS VM 特有的 options 写回 `RuntimeOptions`（实现见 `.cpp`）。



