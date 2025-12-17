# `plugins/ets/runtime/ets_native_library_provider.h`（逐行精读）

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：声明 `NativeLibraryProvider` —— ETS 的 native library 装载器与符号解析器：
> - 维护 `libraryPath_` 搜索路径
> - 管理已加载的 `EtsNativeLibrary` 集合
> - 提供 `LoadLibrary`（含权限校验/namespace fallback）与 `ResolveSymbol`

## 0. includes（L19–L24）

- **L20**：`RWLock`：provider 的核心状态（libraries/path）需要并发读写保护。
- **L21**：`ani.h`：`LoadLibrary` 的入口参数是 `ani_env*`（C ABI）。
- **L22**：`ets_native_library.h`：真实的 “dlopen/dlsym 封装对象”。
- **L23**：`panda_containers.h`：`PandaVector/PandaSet/PandaString` 容器体系。

## 1. 类定义（L26–L49）

### 1.1 对外 API（L34–L41）

- **L34–L35**：`LoadLibrary(env, name, shouldVerifyPermission, fileName)`  
  返回 `optional<string>`：空表示成功；非空字符串表示错误信息（人类可读）。  
  这与 `ets_napi_env.cpp` 的 `Expected/Unexpected` 思路一致：优先传递诊断文本。
- **L36**：`ResolveSymbol(name)`：在已加载库集合中查找符号（dlsym 风格）。
- **L38–L41**：library path 的 get/set/add，均需锁保护。

### 1.2 私有实现与并发控制（L42–L48）

- **L43**：`mutable RWLock lock_`：多读少写典型场景（解析符号/获取路径频繁，加载库与修改路径较少）。
- **L44**：`CallAniCtor(env, lib)`：加载后调用 `ANI_Constructor` 进行初始化/版本协商。
- **L45**：`GetCallerClassName(env)`：权限校验/策略分支需要知道调用方（典型在 OHOS 约束下）。
- **L46**：`CheckLibraryPermission(env, fileName)`：平台相关权限检查（OHOS）。
- **L47–L48**：核心状态：
  - `libraries_`：已加载库集合（按 `EtsNativeLibrary` 的比较/哈希策略去重）
  - `libraryPath_`：搜索路径列表



