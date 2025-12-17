# `plugins/ets/runtime/ani/ani.h`（逐行精读｜ANI 外部 ABI 契约（聚焦运行时实现相关部分））

> 章节归属：Stage2 / 05_NativeBridge  
> 文件规模：约 8k 行（大量 Doxygen 文档）  
> 本文件角色：定义 ANI 的 **对外 C ABI**：类型系统、返回码、options 结构、以及两张函数指针表：
> - `__ani_vm_api`：VM 级 API（CreateVM/GetEnv/Attach/Detach/Destroy）
> - `__ani_interaction_api`：Interaction API（对象/类/方法/数组/引用/异常/Any 等）
>
> 运行时实现位置：
> - VM API 的实现：`plugins/ets/runtime/ani/ani_vm_api.cpp`
> - Interaction API 的实现：`plugins/ets/runtime/ani/ani_interaction_api.cpp`
> - env 的实例：`plugins/ets/runtime/ets_napi_env.*`（把 `ani_env::c_api` 指向 interaction 表）

## 1. 版本与布尔常量（L30–L34）

- **L30**：`ANI_VERSION_1`
- **L32–L33**：`ANI_FALSE/ANI_TRUE`

`ani_interaction_api.cpp::IsVersionSupported` 目前也只接受 `ANI_VERSION_1`。

## 2. Logger 回调 ABI（L35–L46）

注释给出约定：

- `ani_logger` 签名：`(FILE *stream, int log_level, const char *component, const char *message)`
- 通过 `ani_option`：`option="--logger"`，`extra=ani_logger` 传入
- log level 常量：`ANI_LOGLEVEL_*`

对应实现：
- `ANIOptions` 会强制 `--logger` 的 `extra` 非空（见 `ani_options.cpp`）。

## 3. 基础类型与引用类型模型（L47–L171）

### 3.1 基础类型（L47–L58）

- `ani_size`（size_t）
- 8/16/32/64 位整数与 float/double

### 3.2 引用类型（L59–L135）

该头为了同时支持 C 与 C++，采取两套表示：

- **C++ 模式**（L60–L108）：
  - 用一系列空类 `__ani_object/__ani_string/__ani_class/...` 表达引用类型层级
  - 再 typedef 成指针（例如 `typedef __ani_object* ani_object`）
  - 好处：C++ 编译期能区分 `ani_class` vs `ani_object`，减少误用
- **C 模式**（L109–L134）：
  - 统一为 `struct __ani_ref*` 的不透明指针，并用 typedef “别名化”（`ani_class` 其实还是 `ani_ref`）
  - 好处：纯 C 调用方不需要继承层级

### 3.3 `ani_value` union（L161–L171）

- 用 union 承载所有 primitive/ref 值。  
  `ani_interaction_api.cpp` 会根据方法 shorty 把 varargs/`ani_value[]` 转换成 runtime `Value`。

## 4. `ani_native_function`：native bind 的最小描述（L173–L178）

- (name, signature, pointer) 三元组，用于：
  - `Namespace_BindNativeFunctions`
  - `Module_BindNativeFunctions`
  - `Class_BindNativeMethods`

这些入口在 `ani_interaction_api.cpp` 中实现，并最终汇总进 `INTERACTION_API` 表。

## 5. `ani_vm`/`ani_env` 的“二重语义”（L179–L185）

这里非常关键：同一个概念在 C 与 C++ 下 typedef 不同。

- **C++**（L179–L181）：`ani_vm`/`ani_env` 是不透明 struct（由 runtime 内部实现为“带 c_api 成员的对象”）。
- **C**（L183–L185）：`ani_vm`/`ani_env` 直接 typedef 为 “指向函数指针表的指针”。  
  这意味着纯 C 调用方可能把 `ani_vm` 当作 `vm_api_table*` 来用，而 runtime 内部仍可用 C++ 对象表达 env/vm 并把其 `c_api` 指向表。

> 这也解释了为什么 `PandaEtsNapiEnv` 继承自 `ani_env`：C++ 侧要有一个“持有状态 + c_api”的对象。

## 6. `ani_status`：统一错误码（L187–L203）

典型重要项：

- `ANI_OK`
- `ANI_INVALID_ARGS`
- `ANI_PENDING_ERROR`：表示已有 pending exception（`CHECK_ENV` 宏会直接返回它）
- `ANI_NOT_FOUND` / `ANI_AMBIGUOUS`
- `ANI_INVALID_VERSION`

## 7. `ani_options`：CreateVM/Attach 的 options ABI（L205–L213）

- `ani_option { const char* option; void* extra; }`
- `ani_options { size_t nr_options; const ani_option* options; }`

runtime 解析入口：
- `ani_vm_api.cpp::ANI_CreateVM`：`OptionsParser::Parse(options)`
- `ani_vm_api.cpp::AttachCurrentThread`：直接扫描 `--interop=enable/disable`（这是 attach 专用选项）

## 8. `__ani_vm_api`：VM 级函数指针表（L215–L225）

成员：
- `DestroyVM/GetEnv/AttachCurrentThread/DetachCurrentThread`

真实实现：
- `ani_vm_api.cpp` 末尾定义 `static const __ani_vm_api VM_API = {...}` 并由 `GetVMAPI()` 返回地址。

## 9. 导出符号：CreateVM/GetCreatedVMs/ANI_Constructor（L227–L239）

- `ANI_CreateVM` / `ANI_GetCreatedVMs`：由 runtime 导出（实现见 `ani_vm_api.cpp`）
- `ANI_Constructor` / `ANI_Destructor`：供 “native library so” 导出，类似 JNI_OnLoad/JNI_OnUnload  
  ETS runtime 的 `NativeLibraryProvider` 会强制查找并调用 `ANI_Constructor`（见 `ets_native_library_provider.cpp::CallAniCtor`）。

## 10. `__ani_interaction_api`：超大函数表（L244 起）

这一段包含大量 Doxygen 注释与函数指针字段，是 ANI 的核心 ABI 面。  
注意：
- **ABI 的字段顺序是协议**：`ani_interaction_api.cpp` 必须按同样顺序初始化 `INTERACTION_API = { ... }`。
- runtime 内部最终通过 `PandaEtsNapiEnv::c_api` 间接调用这些函数。

建议阅读策略：
- 先读 `ani_interaction_api.cpp` 的“骨架函数”（`DoGeneralMethodCall/GetArgValues/DoFind/AllocObject`）与末尾 `INTERACTION_API` 初始化，再对照本头查字段含义即可。



