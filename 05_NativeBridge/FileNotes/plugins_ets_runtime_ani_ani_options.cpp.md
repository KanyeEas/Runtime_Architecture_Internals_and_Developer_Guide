# `plugins/ets/runtime/ani/ani_options.cpp`（逐行精读）

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：实现 `ANIOptions` 的 option map 与校验规则：
> - 强制 `--logger` 必须提供 `extra`（callback 指针），且不能有 `=value`
> - `--verify:ani` 不允许 value/extra
> - `--ext:interop`（可选）允许 extra（通常为 JS env 句柄）
> - OHOS 下提供默认 logger callback

## 1. `GetLoggerCallback`：OHOS 默认 logger（L26–L34）

- 从 `OptionKey::LOGGER` 的 `extra` 取出并 reinterpret_cast 为 `LoggerCallback`。
- OHOS 下若 callback 为空，返回 `ohos::DefaultLogger`（保证日志可用）。

## 2. `SetOption`：查 map→调用 handler→存入数组（L36–L51）

- 若 key 不在 map：返回 `false`（表示“不是 ANIOptions 管的 option”）。
- 否则执行 handler：
  - 成功则把 `unique_ptr<OptionValue>` 存入 `optionValues_[optionKey]`
  - 失败则 `Unexpected(error_string)`

> 这与 `OptionsParser` 的两阶段解析对接：  
> 第一阶段先让 `ANIOptions` 吃掉它认识的 key；剩下的再进入 `--ext:` 扩展选项解析（见 `ani_options_parser.cpp`）。

## 3. `GetOptionsMap`：静态表驱动（L54–L112）

### 3.1 `--logger`（L58–L73）

- 不允许 `value`（必须空）。
- 强制 `extra != nullptr`（必须提供 callback）。
- 存储为 `OptionValue { std::string(value), extra }`：value 实际为空字符串，仅用 extra。

### 3.2 `--verify:ani`（L75–L90）

- 不允许 value（必须空）。
- 不允许 extra（必须为 nullptr）。
- 存储为 `OptionValue { true, extra }`：即开启 verify。

### 3.3 `--ext:interop`（L91–L108，可选编译）

- 不允许 value（必须空）。
- 允许 extra（JS env 句柄）并把 bool 置为 true。

> 注意：`ANI_CreateVM` 的 interop 路径使用的是 `aniOptions.IsInteropMode()` 与 `GetInteropEnv()`（见 `ani_vm_api.cpp`）。



