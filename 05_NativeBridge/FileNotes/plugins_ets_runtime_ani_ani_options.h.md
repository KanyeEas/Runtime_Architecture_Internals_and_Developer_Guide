# `plugins/ets/runtime/ani/ani_options.h`（逐行精读）

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：定义 ANI 自身可识别的 options 集合 `ANIOptions`：  
> - `--logger`：注入 logger callback（通过 `ani_option.extra`）  
> - `--verify:ani`：开启 VerifyANI（会影响 `PandaEtsNapiEnv` 的 `c_api` 替换）  
> - `--ext:interop`（编译进 interop 时）：开启 interop 模式并保存 `extra`（JS env 句柄）

## 0. includes（L18–L27）

- `Expected`：`SetOption` 返回 `Expected<bool, std::string>`：  
  - `true/false` 表示“是否为已识别的 option key”  
  - error string 表示“识别了但参数/extra 不合法”

## 1. `LoggerCallback` ABI（L30）

- 与 `ani.h` 的注释 ABI 一致：`(FILE*, int, const char*, const char*)`。

## 2. `OptionKey`：编译期固定的 option 枚举（L34–L42）

- `LOGGER`、`VERIFY_ANI`，以及可选 `INTEROP`（`PANDA_ETS_INTEROP_JS`）。
- `NUMBER_OF_ELEMENTS` 用于 `optionValues_` 数组大小。

## 3. `SetOption`：解析并存储到 `optionValues_`（L47）

- 输入：`key/value/extra`
- 输出：
  - `Expected<bool, string>`：  
    - `false`：不认识的 key（交给 `OptionsParser` 当作“扩展 option”继续处理）  
    - `Unexpected(msg)`：认识但参数不合法  
    - `true`：成功保存

## 4. 快速查询接口（L49–L67）

- `GetLoggerCallback()`：返回 logger callback（实现见 `.cpp`，OHOS 下有默认值）。
- `IsVerifyANI()`：读取 `VERIFY_ANI` 的 bool 值（默认 false）。
- interop 分支：
  - `IsInteropMode()`：读取 bool（默认 false）
  - `GetInteropEnv()`：取 `extra`（void*）

## 5. 内部结构：OptionValue/OptionHandler（L71–L81）

- `OptionValue`：
  - `value`：`variant<bool, string>`
  - `extra`：原样保存 `ani_option.extra`
- `OptionHandler`：把字符串 key 映射到 `(OptionKey, parser-fn)`

## 6. 存储布局（L94–L99）

- `optionValues_` 是一个定长数组，按 `OptionKey` 的 underlying 值索引。
- `GetOptionsMap()` 返回静态 map（实现在 `.cpp`）。



