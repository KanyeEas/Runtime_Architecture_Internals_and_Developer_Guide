# `plugins/ets/runtime/interop_js/interop_context.cpp`（逐行精读｜对 ANI/ExternalIfaceTable 可见的关键路径）

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：实现 `InteropCtx` 与 `CreateMainInteropContext`。  
> 该文件也非常大；本章以 NativeBridge 视角聚焦两条闭环主线：
>
> 1) **ANI_CreateVM → CreateMainInteropContext**：主线程创建 interop ctx，并把 runtime 生命周期绑定到 JS env cleanup hook（hybrid 模式）。  
> 2) **ExternalIfaceTable 回调注入点**：`InteropCtx::InitExternalInterfaces()` 把 “CreateJSRuntime / GetJSEnv / CleanUpJSEnv / CreateInteropCtx / ClearInteropHandleScopes / JobQueue” 注入，供 `ani_vm_api.cpp::Attach/Detach` 与异常/去优化路径调用。

## 1. `InteropCtx::InitExternalInterfaces`：把 interop 能力以回调表注入（L424–L469）

### 1.1 JobQueue 与“清理 interop handle scopes”（L426–L429）

- **L426**：`interfaceTable_.SetJobQueue(MakePandaUnique<JsJobQueue>())`
- **L427–L429**：注释明确：该清理函数“should be called in the deoptimization and exception handlers”。  
  注入回调：`ClearInteropHandleScopesFunction(Frame*)` → `DestroyLocalScopeForTopFrame(frame)`。

> 对应关系：  
> `ExternalIfaceTable` 里把参数类型固定为 `runtime/interpreter/frame.h::Frame*`，确保执行引擎（解释器/去优化/异常处理）能在边界点清理 interop local scopes。

### 1.2 JS runtime 生命周期（OHOS/hybrid 模式下）（L430–L458）

仅在 `PANDA_TARGET_OHOS || PANDA_JS_ETS_HYBRID_MODE` 下生效：

- **L431–L442**：`CreateJSRuntimeFunction`：
  - 调 `napi_create_runtime(env, &resultJsEnv)`
  - 初始化 global 与 helper（以及可选 Console 模块）
  - 返回新的 `napi_env`（作为 `ExternalIfaceTable::JSEnv` 的 `void*`）
- **L444–L450**：`GetJSEnvFunction`：
  - 取 `InteropCtx::Current()` 并返回其 `GetJSEnv()`（若 ctx 不存在则 nullptr）
- **L452–L456**：`CleanUpJSEnvFunction`：
  - 调 `napi_destroy_runtime(env)` 销毁 js runtime

> 对应 ANI：  
> `ani_vm_api.cpp::AttachCurrentThread` 在 `--interop=enable` 且未提供 `jsEnv` 时，会调用 `ifaceTable->CreateJSRuntime()`；  
> `DetachCurrentThread` 会拿到 `ifaceTable->GetJSEnv()` 并调用 `CleanUpJSEnv(jsEnv)`。

### 1.3 worker 上绑定 interop ctx：`CreateInteropCtxFunction`（L459–L468）

- 把 `void*` 转回 `napi_env`
- 把 `Coroutine*` 转为 `EtsCoroutine*`
- 调 `InteropCtx::Init(etsCoro, env)`：在该 worker 上创建/绑定 ctx
- OHOS + interop 编译时：`TryInitInteropInJsEnv(jsEnv)` 初始化该 JSVM 实例内的 interop

## 2. `CreateMainInteropContext`：ANI 可见的外部入口（L934–L973）

这是 `interop_context_api.h` 声明的函数，在 `ani_vm_api.cpp::ANI_CreateVM` 中被调用。

关键步骤：

- **L936**：断言 `mainCoro` 就是 main thread coroutine。
- **L937–L939**：`CheckRuntimeOptions(mainCoro)`：不满足则失败（运行时选项约束）。
- **L940–L943**：OHOS/hybrid 模式下 `napi_setup_hybrid_environment(env)`。
- **L944**：`AppStateManager::Create()`：创建 app state 监控器。
- **L945–L948**：在 `ScopedManagedCodeThread sm(mainCoro)` 下调用 `InteropCtx::Init(mainCoro, napi_env)`。  
  含义：初始化 interop ctx 需要在 managed code 语境中完成（可能会触发类加载/方法调用/分配等）。
- **L952–L958**：初始化 Timer module + app state callback。
- **L960–L967**：注册 `napi_add_env_cleanup_hook`：在 JS env 生命周期结束时销毁 `AppStateManager` 与 `Runtime`（hybrid leading VM 场景把 ETS VM 生命周期绑定到 JSVM）。
- **L968–L972**：OHOS 下 `TryInitInteropInJsEnv(napiEnv)`，否则直接返回 true。

## 3. 本文件在 05 章闭环中的位置（总结）

你可以把它视为 “interop_js 子系统的 bootstrap + 把能力注入 `ExternalIfaceTable` 的地方”：

```mermaid
flowchart TD
  A[ANI_CreateVM] -->|interop=enable| B[CreateMainInteropContext]
  B --> C[InteropCtx::Init(mainCoro, napi_env)]
  C --> D[InteropCtx::InitExternalInterfaces]
  D --> E[ExternalIfaceTable 回调表就绪]
  E --> F[AttachCurrentThread: CreateJSRuntime/CreateInteropCtx]
  E --> G[DetachCurrentThread: GetJSEnv/CleanUpJSEnv]
  E --> H[Deopt/异常: ClearInteropHandleScopes(Frame*)]
```



