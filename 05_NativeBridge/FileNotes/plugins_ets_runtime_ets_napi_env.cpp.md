# `plugins/ets/runtime/ets_napi_env.cpp`（逐行精读）

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：实现 `PandaEtsNapiEnv` 的构建、获取当前 env、引用存储初始化，以及异常桥接与 cleanup。

## 0. includes：为什么这里直接依赖 interaction API（L16–L22）

- **L17**：`ani_interaction_api.h`：普通模式的 ANI C API 表来源（`ani::GetInteractionAPI()`）。
- **L18**：`verify_ani_interaction_api.h`：verify 模式的 C API 表来源（`ani::verify::GetVerifyInteractionAPI()`）。
- **L20–L21**：`ets_coroutine.h` / `ets_vm.h`：env 的核心绑定对象。

> 关键点：`PandaEtsNapiEnv` 的 `ani_env::c_api` 在构造时就被确定（并可能被替换为 verify 表），这是整个 ANI 调用分发的“开关”。

## 1. `Create`：分配 env + reference storage，并初始化底层 ReferenceStorage（L24–L39）

- **L27**：取 VM：`etsVm = coroutine->GetVM()`（注意这是 ETS VM/语言层对象）。
- **L28**：构建 `EtsReferenceStorage`：
  - 参数包含 `etsVm->GetGlobalObjectStorage()`（全局对象存储）与 `allocator`
  - 最后一个 `false`：通常表示“是否为 weak/或某种模式”，需结合 `EtsReferenceStorage` 定义理解
- **L29–L31**：若分配失败或底层 `ReferenceStorage::Init()` 失败 → 返回 `Unexpected("Cannot allocate EtsReferenceStorage")`。
- **L33–L36**：用 allocator `New<PandaEtsNapiEnv>` 分配 env；失败返回错误。
- **L38**：成功返回 `Expected<PandaEtsNapiEnv*, const char*>(ptr)`。

> 这里用 `Expected/Unexpected` 而不是异常/返回码，方便在 `ANI_CreateVM/AttachCurrentThread` 链路中把错误文本一路回传到 C API 层。

## 2. `GetCurrent`：env 的 TLS 语义（L41–L46）

- **L43–L45**：通过 `EtsCoroutine::GetCurrent()` 找到当前 coroutine，然后 `coro->GetEtsNapiEnv()`。  
  结论：在 ETS 设计里，**ani_env 是 coroutine-local**，不是纯 thread-local。

## 3. 构造函数：决定 `c_api` 表（普通 vs verify）（L48–L56）

- **L48–L50**：基类初始化：`ani_env {ani::GetInteractionAPI()}`，默认绑定“普通 interaction API 表”。
- **L51**：若 `coroutine->GetPandaVM()->IsVerifyANI()`：
  - **L52**：取全局 `ANIVerifier`：`GetEtsVM()->GetANIVerifier()`
  - **L53**：创建 `EnvANIVerifier(verifier, c_api)`：把“原始 c_api 表”传入，以便 wrapper 可在校验后转发真实实现
  - **L54**：把 `c_api` 替换成 verify 版本：`ani::verify::GetVerifyInteractionAPI()`

> 这就是 verify 机制的核心：  
> - `EnvANIVerifier` 保存原始表（真实实现）  
> - `c_api` 换成 verify 表（入口变为校验器）  
> 因此后续所有经由 `ani_env*` 的调用都会先进入 verify wrapper，再由 verifier 决定是否/如何调用真实实现。

## 4. VM 访问（L58–L61）

- **L58–L61**：`GetEtsVM()` 从 coroutine 返回 `PandaVM`（ETS VM 的 runtime 容器）。

## 5. 引用存储的生命周期操作（L63–L76）

- **L63–L66**：`FreeInternalMemory()`：直接 `reset()` referenceStorage（释放内部内存）。
- **L68–L71**：`CleanUp()`：调用 `referenceStorage_->CleanUp()`（通常用于 detach/thread exit）。
- **L73–L76**：`ReInitialize()`：`referenceStorage_->ReInitialize()`（通常用于重复 attach/环境复用场景）。

## 6. 异常桥接到 coroutine（L78–L99）

- **SetException/ClearException/GetThrowable** 都会：
  - **ASSERT_MANAGED_CODE()**：要求处于 managed 状态（通常表示当前线程已 attach 且处于允许操作 VM 的状态）。
  - 通过 `coroutine_` 转发到底层异常槽：
    - `SetException(thr->GetCoreType())`
    - `GetException()` 并 reinterpret_cast 回 `EtsThrowable*`
    - `ClearException()`
- **L90–L93**：`HasPendingException()` 不要求 managed assert（可用于快速检查）。



