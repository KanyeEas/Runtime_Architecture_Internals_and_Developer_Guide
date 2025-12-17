# `plugins/ets/runtime/interop_js/interop_context.h`（逐行精读｜InteropCtx 对象模型（聚焦对外边界））

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：声明 JS interop 的核心对象 `InteropCtx`（以及若干辅助缓存/存储）。  
> 注意：该头非常大，且包含大量 interop 细节；本章在“NativeBridge”语境下重点关注 **对外边界与生命周期钩子**：
>
> - `InteropCtx::Init(EtsCoroutine*, napi_env)`：为某个 coroutine 绑定 interop ctx
> - `InteropCtx::Current(...)`：从 coroutine/worker 获取当前 ctx
> - `InteropCtx::GetJSEnv()`：获取 JS runtime env（napi_env）
> - `InteropCtx::InitExternalInterfaces()`：把 `ExternalIfaceTable` 回调注入 ETS VM（实现见 `.cpp`）
> - `DestroyLocalScopeForTopFrame(Frame*)`：用于异常/去优化时清理 interop handle scopes（通过 ExternalIfaceTable 暴露）

## 1. “不要在 NativeBridge 章节里陷入 interop 细节”的原因（L19–L41）

该头直接 include 了大量 interop 子系统组件（job queue、refconvert、intrinsics、xgc、napi、hybrid vm interface 等）。  
这意味着：
- 任何引入该头的文件都会把 interop 的大部分实现细节带进编译单元；
- 为了隔离，ANI 等模块应优先 include `interop_context_api.h`（void* 参数）而不是直接 include 本头。

## 2. `InteropCtx` 的关键对外方法（L156–L240）

### 2.1 初始化与销毁（L161–L165）

- **L161**：`static void Init(EtsCoroutine *coro, napi_env env)`：将 interop ctx 与某个 coroutine 绑定。  
  这会在：
  - main 线程：`CreateMainInteropContext` 内调用
  - worker 线程 attach：`ExternalIfaceTable::CreateInteropCtx` 回调内调用（见 `interop_context.cpp::InitExternalInterfaces`）
- **L162**：析构函数负责释放 interop 相关 GC references 等资源。
- **L164–L165**：`Destroy(void*)`：典型“以 void* 存在 worker 上”的销毁入口。

### 2.2 当前 ctx 的获取（L166–L179）

- **L166–L174**：`Current(Coroutine*)`：通过 `coro->GetWorker()` 再取 `Current(worker)`。  
  注释提示未来可能优化为从 coroutine 缓存 pointer，但需要保证 worker 状态一致。
- **L176–L179**：`Current()`：取当前 coroutine 的 ctx。

### 2.3 JS env 与 interop local scopes（L186–L221）

- **L186–L190**：`GetJSEnv()`：返回 napi_env（断言非空）。
- **L213–L221**：`DestroyLocalScopeForTopFrame(Frame*)`：对 interop local scopes 的关键清理入口。  
  它在 `.cpp` 中会被注入为 `ExternalIfaceTable::ClearInteropHandleScopesFunction`，并被注明“应在去优化与异常 handler 中调用”。

## 3. 本章“NativeBridge”与 InteropCtx 的连接方式（总结）

NativeBridge 不直接依赖 interop 的内部实现，而是通过两条“窄接口”连接：

- **启动阶段（main thread）**：`interop_context_api.h::CreateMainInteropContext(mainCoro, void* jsEnv)`
- **运行阶段（worker attach/detach 与异常/去优化清理）**：`ExternalIfaceTable` 回调集合  
  回调的注入发生在 `InteropCtx::InitExternalInterfaces()`（实现见 `interop_context.cpp`）。



