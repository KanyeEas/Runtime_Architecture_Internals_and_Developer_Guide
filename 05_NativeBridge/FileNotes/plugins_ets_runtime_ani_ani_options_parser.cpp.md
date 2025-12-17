# `plugins/ets/runtime/ani/ani_options_parser.cpp`（逐行精读｜ANI_CreateVM options 解析）

> 章节归属：Stage2 / 05_NativeBridge  
> 文件规模：248 行  
> 本文件角色：实现 `OptionsParser` 的两阶段解析：
> 1) 先让 `ANIOptions` 解析它认识的 option（`--logger`、`--verify:ani`、`--ext:interop`）
> 2) 其余参数若符合 `--ext:` 前缀，则作为“扩展 option”分派给 logger/runtime/compiler 的 PandArgParser
>
> 最终产出：`logger::Options`、`RuntimeOptions`（默认 ETS runtime）、compiler options，并写回 ETS VM options。

## 1. product build 约束（L25–L29）

- `PANDA_PRODUCT_BUILD` 下：`ANI_SUPPORTS_ONLY_PRODUCT_OPTIONS=true`  
  作用：仅允许 product allowlist 中的参数被解析/透传，其他参数会被静默跳过或判为不支持（见 `GetParserDependentArgs`）。

## 2. 构造：注册三套 options，并设置 ETS runtime 默认值（L38–L49）

- **L40–L42**：把 logger/runtime/compiler 的 options 注册到各自 parser。
- **L44–L49**：强制设置 runtime options 的 ETS 默认：
  - boot intrinsic/class spaces = {"ets"}
  - runtimeType = "ets"
  - loadRuntimes = {"ets"}

> 这保证 `ANI_CreateVM` 创建的 runtime 是 ETS runtime，而不是依赖外部传参决定。

## 3. `Parse`：第一阶段（ANIOptions）+ 第二阶段（ext options）+ 写回 ETS VM options（L83–L132）

### 3.1 遍历 `ani_options`（L95–L114）

- 对每个 `ani_option`：
  - 拆 `name/value`（按 `=` 分割）
  - `aniOptions_.SetOption(name, value, opt.extra)`：
    - `HasValue()==false`：表示参数有错误，直接返回错误字符串
    - `Value()==true`：ANIOptions 识别并消费掉该 option
    - `Value()==false`：不是 ANIOptions 管的，收集到 `extOptions`

### 3.2 解析扩展 option 前缀（L116–L125, L174–L187）

- 只接受两种前缀：
  - deprecated：`--ext:--`
  - 新版：`--ext:`
- 解析后构造 `Option{fullName, name, value, opt}`，并放入 `extOptionsMap[name]`。
- 若前缀不匹配则返回空（随后报 “option is not supported”）。

### 3.3 `ParseExtOptions`：把 ext options 分派给 3 个 parser（L134–L172）

- `GetParserDependentArgs(parser, productOptions, extOptionsMap, outArgs)`：
  - 读取 parser 已解析过的 arg name 集合
  - 若 product build 且 name 不在 allowlist：跳过
  - 若 ext option 被该 parser 识别：
    - 强制 `opt->extra == nullptr`（扩展 option 不支持 extra）
    - 组装成 `--name=value` 形式加入 outArgs
    - 从 map 中删除该项
- 依次对 logger/runtime/compiler 三个 parser 做该过程；最后要求 extOptionsMap 为空，否则报“不支持”。
- 运行各 parser 并 Validate：
  - logger validate 失败会回退默认 logger options（见 `RunLoggerOptionsParser`）

### 3.4 `PrepareEtsVmOptions`（L243–L246）

- 调 `SetEtsVmOptions(runtimeOptions_, make_unique<EtsVmOptions>(aniOptions_.IsVerifyANI()))`：  
  把 verifyANI 开关写进 ETS VM options（后续 env 构造时会用到）。

> 这条链路最终影响 `PandaEtsNapiEnv` 是否把 `c_api` 替换为 verify 表（见 `ets_napi_env.cpp`）。



