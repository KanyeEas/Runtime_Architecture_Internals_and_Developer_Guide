# `plugins/ets/runtime/external_iface_table.h`（逐行精读｜跨运行时回调表）

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：定义 `ExternalIfaceTable` —— **ETS runtime 与外部 runtime（主要是 JS runtime/JobQueue）之间的接口“插槽表”**。  
> 设计要点：
> - 以 `std::function` 存储回调，允许在启动阶段由外部模块注入实现
> - JS env 以 `void*` 抽象（避免把 N-API 类型渗透到 core runtime）
> - 由 `EtsCoroutine`/ANI attach/detach 在关键时机调用这些回调（见 `ani_vm_api.cpp`）

## 0. includes（L19–L23）

- **L21**：依赖 `runtime/interpreter/frame.h`：`ClearInteropHandleScopesFunction` 需要以 `Frame*` 作为参数（清理 interop handle scopes 以避免跨边界泄漏）。
- **L22**：依赖 `job_queue.h`：JS interop 相关任务队列。

## 1. 类型别名：把 JS runtime 作为黑盒（L32–L38）

- **L32**：`using JSEnv = void*`：对外只暴露句柄，不暴露 JS runtime 具体类型。
- **L33–L38**：五类回调：
  - `ClearInteropHandleScopesFunction(Frame*)`
  - `CreateJSRuntimeFunction() -> JSEnv`
  - `CleanUpJSEnvFunction(JSEnv)`
  - `GetJSEnvFunction() -> JSEnv`
  - `CreateInteropCtxFunction(Coroutine*, JSEnv)`：在某个 coroutine 上绑定/创建 interop context

> 这几类回调恰好覆盖了 `ani_vm_api.cpp` 的 interop attach/detach 需求：  
> attach：创建 js runtime（可选）+ 创建 interop ctx；detach：清理 js env。

## 2. 资源与生命周期：JobQueue + 回调“只设置一次”（L45–L128）

### 2.1 JobQueue（L45–L53）

- `jobQueue_` 存在则可被 `GetJobQueue()` 返回。
- `SetJobQueue()` 用 unique_ptr 设置，所有权归 `ExternalIfaceTable`。

### 2.2 回调设置：ASSERT(!already_set)（L65–L81, L108–L112）

- `SetCreateJSRuntimeFunction/SetCleanUpJSEnvFunction/SetGetJSEnvFunction/SetCreateInteropCtxFunction`
  都会先 `ASSERT(!xxx_)`，表示回调应在初始化阶段只设置一次。

### 2.3 调用回调：全部是“若存在则调用，否则 no-op”（L83–L119）

- `CreateJSRuntime()`：没有回调则返回 nullptr。
- `CleanUpJSEnv(env)`：没有回调则不做任何事。
- `GetJSEnv()`：没有回调则返回 nullptr。
- `CreateInteropCtx(coro, jsEnv)`：没有回调则 no-op。

> 这让 ETS runtime 可以在 **没有 interop_js 编译进来** 的情况下依然工作：  
> 回调为空即表示功能关闭，不需要大量 `#ifdef` 贯穿业务代码。



