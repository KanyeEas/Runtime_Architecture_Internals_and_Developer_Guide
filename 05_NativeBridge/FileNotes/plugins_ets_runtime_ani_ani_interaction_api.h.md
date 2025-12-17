# `plugins/ets/runtime/ani/ani_interaction_api.h`（逐行精读）

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：声明 ANI 的“interaction API 表”入口与版本支持检查：
> - `GetInteractionAPI()`：返回 `__ani_interaction_api` 的函数指针表（定义在 `ani_interaction_api.cpp`）
> - `IsVersionSupported(version)`：当前仅支持 `ANI_VERSION_1`
>
> 该表会被 `PandaEtsNapiEnv` 在构造时写入 `ani_env::c_api`（普通模式），或在 verify 模式下被替换为 verify 版本表。

## 1. 外部 ABI 前置声明（L22）

- **L22**：`struct __ani_interaction_api;`  
  同 `__ani_vm_api` 一样，这个类型来自外部 ABI 头；此处只做前置声明。

## 2. 公开函数（L24–L27）

- **L25**：`GetInteractionAPI()`：返回 `&INTERACTION_API`（典型静态表模式，实现在 `.cpp` 末尾）。
- **L26**：`IsVersionSupported(version)`：由 `.cpp` 实现（当前等于 `version == ANI_VERSION_1`）。

## 3. `EnumArrayNames`：内部约定的“枚举辅助数组”命名（L28–L33）

- **L28–L33**：提供几个 `constexpr std::string_view`：
  - `#NamesArray`
  - `#ValuesArray`
  - `#StringValuesArray`
  - `#ItemsArray`

推断用途：
- 这是对 ETS 枚举实现细节的约定：枚举类/模块可能生成这些“伪字段/伪数组”用于反射或 interop。
- interaction API 在 `FindEnum` 或相关访问接口中可能用这些名称做定位（需要结合 `.cpp` 的相应实现段落）。



