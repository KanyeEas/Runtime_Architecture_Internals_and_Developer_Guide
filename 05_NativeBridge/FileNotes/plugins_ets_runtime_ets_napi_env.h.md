# `plugins/ets/runtime/ets_napi_env.h`（逐行精读）

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：定义 ETS 侧的 `ani_env` 实例——`PandaEtsNapiEnv`。它是 **native ↔ VM** 的关键“环境对象”，绑定：
> - 当前 `EtsCoroutine`
> - `EtsReferenceStorage`（跨边界引用生命周期）
> - 可选 `EnvANIVerifier`（当启用 VerifyANI 时）

## 0. includes（L19–L22）

- **L19**：`ani.h`：声明 `ani_env` 与 C API 表结构（`ani_env::c_api`）。
- **L20**：`env_ani_verifier.h`：Env 级 verifier，用于在 verify 模式下包装/校验 API 调用。
- **L21**：`ets_reference.h`：引用存储（`EtsReferenceStorage`）与 allocator 相关定义。

## 1. 类型前置与别名（L25–L28）

- **L25–L26**：前置声明 `EtsCoroutine`、`PandaEtsVM`，避免头文件互相 include。
- **L27**：`EtsThrowable = EtsObject`：ETS 侧把 throwable 视为对象（由语言上下文定义真实语义）。

## 2. `PandaEtsNapiEnv`：ani_env 的 C++ 实现（L29–L81）

### 2.1 创建与获取当前 env（L31–L34）

- **L31–L32**：`Create(coroutine, allocator)`：以 `InternalAllocator` 分配 env 与其 `EtsReferenceStorage`；返回 `Expected<*, const char*>` 以携带错误字符串。
- **L33**：`GetCurrent()`：从 TLS/当前 coroutine 获取 env（实现见 `.cpp`）。

### 2.2 生命周期与核心绑定（L35–L48, L77–L81）

- **L35**：构造函数接收 `coroutine` 与 `referenceStorage`（unique_ptr），把 env 与 coroutine 生命周期绑定。
- **L38–L41**：`GetEtsCoroutine()`：显式暴露绑定的 coroutine。
- **L43**：`GetEtsVM()`：通过 coroutine 得到 VM（实现见 `.cpp`）。
- **L45–L48**：`GetEtsReferenceStorage()`：env 暴露引用存储，供 ANI/Interop 逻辑使用。
- **L78–L80**：成员：
  - `coroutine_`
  - `referenceStorage_`
  - `envANIVerifier_`（仅 verify 模式下非空）

### 2.3 `ani_env*` ↔ `PandaEtsNapiEnv*` 的桥（L50–L53）

- **L50–L53**：`FromAniEnv(ani_env*)`：静态 downcast helper。  
  这是整个 native bridge 的常见模式：C ABI 用 `ani_env*`，内部实现需要回到 C++ 类型。

### 2.4 VerifyANI：env 级 verifier（L55–L64）

- **L55–L58**：`IsVerifyANI()`：用 `envANIVerifier_ != nullptr` 判断当前 env 是否处于 verify 模式。
- **L60–L64**：`GetEnvANIVerifier()`：要求非空并返回指针。  
  典型用途：在 verify 代码路径中记录/校验引用、参数、线程状态等。

### 2.5 异常/引用/清理 API（L66–L73）

这些方法是 “native 边界常用能力” 的最小集合：

- **异常桥接**：`SetException/GetThrowable/HasPendingException/ClearException`
- **资源清理**：`FreeInternalMemory/CleanUp/ReInitialize`（主要针对 reference storage 的内存/句柄生命周期）

> 这些 API 的实现都在 `ets_napi_env.cpp`，并且多数会断言处于 managed code（`ASSERT_MANAGED_CODE()`），避免在错误线程/状态下操作 VM 侧异常。



