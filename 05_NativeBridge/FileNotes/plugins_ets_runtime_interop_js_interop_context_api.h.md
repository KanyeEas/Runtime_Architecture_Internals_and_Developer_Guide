# `plugins/ets/runtime/interop_js/interop_context_api.h`（逐行精读｜对外隔离层）

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：对外提供 **Interop JS 的最小入口**，用于隔离实现细节：
> - `CreateMainInteropContext(EtsCoroutine*, void *napiEnv)`
>
> 设计要求（注释明确写出）：调用方（例如 ANI）应与 interop 实现隔离，因此参数用 `void*` 而不是 `napi_env`。

## 1. 前置声明与命名空间（L21–L40）

- **L23**：`class EtsCoroutine;`：Interop 初始化需要主 coroutine。
- **L25**：嵌套命名空间 `interop::js`：清晰标记属于 JS interop 子系统。

## 2. `CreateMainInteropContext`：ANI 可调用的唯一外部入口（L27–L37）

- **L27–L35（注释）**：说明该函数会：
  - 创建 main interop context
  - 初始化模块、XGC 等
  - 但为了隔离，禁止暴露 `napi_env` 类型
- **L36**：`PANDA_PUBLIC_API bool CreateMainInteropContext(mainCoro, void *napiEnv)`  
  返回 bool：成功/失败；失败时 ANI 侧会销毁 runtime（见 `ani_vm_api.cpp::ANI_CreateVM`）。



