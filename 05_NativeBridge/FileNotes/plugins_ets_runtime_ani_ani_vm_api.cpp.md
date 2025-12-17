# `plugins/ets/runtime/ani/ani_vm_api.cpp`（逐行精读｜CreateVM/Attach/Detach/GetEnv）

> 章节归属：Stage2 / 05_NativeBridge  
> 文件规模：246 行  
> 本文件角色：实现 ANI 的 VM 级 API（类似 JNI 的 `JNI_CreateJavaVM` + attach/detach/getEnv）：
> - `ANI_CreateVM`：解析 options → 初始化 logger → 创建 Runtime →（可选）创建 main interop context → 返回 `ani_vm*`
> - `ANI_GetCreatedVMs`：返回当前线程关联的 VM（0 或 1）
> - `DestroyVM`：销毁 runtime 或子 VM
> - `GetEnv`：从当前 thread/coroutine 取出 `ani_env*`（即 `PandaEtsNapiEnv`）
> - `AttachCurrentThread/DetachCurrentThread`：把线程 attach 成“exclusive worker coroutine”，并处理 interop JS env 生命周期

## 0. includes：这里把 ANI/Runtime/Interop 三条链串起来（L16–L29）

- **L17–L18**：`ani_options_parser.h` / `ani_options.h`：CreateVM/Attach 解析 ANI options。
- **L19–L21**：compiler/logger options：说明 ANI options 可以影响编译器日志组件（通常用于 JIT/编译路径调试）。
- **L22–L23**：`ani_checkers.h`、`ani_interaction_api.h`：`ANI_CHECK_*` 宏与 version 支持检查来自 interaction api。
- **L24–L25**：`ets_coroutine.h`、`ets_vm.h`：线程 attach 的核心对象。
- **L26**：`interop_context_api.h`：主线程 interop context 创建入口（编译条件 `PANDA_ETS_INTEROP_JS`）。

## 1. C ABI：`ANI_CreateVM`（L31–L74）

- **L33**：参数校验：`result != nullptr`。
- **L34–L36**：版本校验：`ani::IsVersionSupported(version)`。
- **L38–L45**：解析 options + 初始化 logger：
  - `OptionsParser parser; errMsg = parser.Parse(options)`
  - `Logger::Initialize(parser.GetLoggerOptions(), aniOptions.GetLoggerCallback())`
  - 若 parse 出错 → 日志记录并返回 `ANI_ERROR`
- **L46**：同步 compiler logger 组件。
- **L48–L51**：`Runtime::Create(runtimeOptions)`：创建 runtime，失败返回 error。
- **L53–L64**：interop JS（可选编译）：
  - 若 `aniOptions.IsInteropMode()`：调用 `interop::js::CreateMainInteropContext(coroutine, aniOptions.GetInteropEnv())`
  - 失败则 `Runtime::Destroy()` 并返回 error（避免半初始化）
- **L66–L68**：返回 `ani_vm*`：`*result = coroutine->GetPandaVM()`
- **L69–L73**：输出固定日志 `"ani_vm has been created"`（注释指出测试依赖该文本）。

## 2. `ANI_GetCreatedVMs`：当前线程视角的 VM 枚举（L77–L100）

- 若 `Thread::GetCurrent()==nullptr`：说明线程未 attach → 返回 0 个 VM。
- 否则取 `EtsCoroutine::GetCurrent()`：
  - coro 存在：要求 buffer length >= 1，然后写入 `coroutine->GetPandaVM()`，`*result = 1`
  - coro 不存在：返回 0

> 这再次体现“线程 attach”后才允许把 thread 视为在 VM 内。

## 3. `DestroyVM`：销毁 runtime 或子 VM（L104–L124）

- **L109–L113**：没有 current runtime 则无法销毁（返回 ANI_ERROR）。
- **L115–L121**：区分：
  - 若 `pandaVm == runtime->GetPandaVM()`：销毁整个 Runtime（`Runtime::Destroy()`）
  - 否则：销毁该 `PandaEtsVM`（`PandaEtsVM::Destroy(pandaVm)`）

## 4. `GetEnv`：`ani_vm*` → 当前 `ani_env*`（L126–L152）

- 校验 vm/result/version。
- **L136–L140**：`Thread::GetCurrent()` 必须非空（线程已 attach）。
- **L142–L146**：`EtsCoroutine::GetCurrent()` 必须非空（线程 attach 后应有当前 coroutine）。
- **L147–L151**：`env = coro->GetEtsNapiEnv()`，断言非空并返回。  
  对应实现：`PandaEtsNapiEnv`（见 `ets_napi_env.*`）。

## 5. `AttachCurrentThread`：把线程 attach 成 worker coroutine（L154–L201）

### 5.1 线程 attach 前置（L161–L165）

- 若 `Thread::GetCurrent()!=nullptr`：说明已 attach，直接报错。

### 5.2 interop 选项解析（L166–L179）

- 遍历 `options->options`：
  - `"--interop=enable"`：设置 `interopEnabled=true`，并从 `option.extra` 获取 `jsEnv`
  - `"--interop=disable"`：关闭 interop

### 5.3 创建 exclusive worker coroutine（L180–L190）

- 取 `runtime/current etsVM/coroutineManager`
- `CreateExclusiveWorkerForThread(runtime, etsVM)`：为当前 thread 创建专用 worker coroutine
- 失败说明达到 EAWorkers 上限 → 返回 error
- 成功后断言 `exclusiveCoro == Coroutine::GetCurrent()`

### 5.4 interop ctx 创建（L191–L198）

- 从 main thread 的 `ExternalIfaceTable` 取回调表：
  - `ifaceTable = mainThread->GetExternalIfaceTable()`
- 若 `jsEnv==nullptr`：通过 `ifaceTable->CreateJSRuntime()` 创建
- `ifaceTable->CreateInteropCtx(exclusiveCoro, jsEnv)`：把 interop ctx 绑定到该 worker coroutine

### 5.5 返回 `ani_env*`（L199–L200）

- `*result = PandaEtsNapiEnv::GetCurrent()`：env 是 coroutine-local，因此在创建 worker coro 后才可取 current env。

## 6. `DetachCurrentThread`：销毁 worker coroutine + 清理 JS env（L203–L227）

- 要求线程已 attach（`Thread::GetCurrent()!=nullptr`）。
- 先从 main thread 的 `ExternalIfaceTable` 取 `jsEnv = ifaceTable->GetJSEnv()`。
- `coroMan->DestroyExclusiveWorker()`：销毁当前 thread 的 worker coroutine。
- 若 `jsEnv != nullptr`：`ifaceTable->CleanUpJSEnv(jsEnv)`（外部 runtime 清理）。
- 若 destroy 失败 → 返回 error；成功则断言 `Thread::GetCurrent()==nullptr`。

> 注意顺序：先拿到 jsEnv，再 destroy worker。这样不会在 coroutine 已销毁后再通过 coroutine-local 状态取 jsEnv。

## 7. `__ani_vm_api` 表与 `GetVMAPI`（L229–L246）

- **L230–L239**：`VM_API` 的函数指针表把外部 ABI 与本文件的静态函数绑定。
- **L242–L245**：`GetVMAPI()` 返回 `&VM_API`：典型“静态表 + 指针导出”模式。



