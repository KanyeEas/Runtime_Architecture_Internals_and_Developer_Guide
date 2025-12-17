# `plugins/ets/runtime/ets_native_library_provider.cpp`（逐行精读｜LoadLibrary/ANI_Constructor/namespace fallback）

> 章节归属：Stage2 / 05_NativeBridge  
> 本文件角色：实现 `NativeLibraryProvider`：
> - 从 `libraryPath_` 或绝对路径加载 so
> - 在 system load 失败时（且不要求权限校验）回退到“应用 namespace”加载
> - 加载成功后调用 `ANI_Constructor` 进行初始化与版本协商
> - 提供符号解析与路径管理

## 0. includes：这就是“native bridge 与执行栈/类加载上下文”交汇点（L18–L26）

- **L22**：`ani_interaction_api.h`：表明 native load 与 ANI/异常/线程状态可能有关（日志/错误路径）。
- **L23–L25**：`ets_vm.h`、`ets_method.h`、`ets_namespace_manager_impl.h`：namespace 加载需要 VM/方法/namespace manager 的协作。

## 1. 匿名命名空间 helper：system path 搜索（L31–L46）

### 1.1 `LoadFromPath(pathes, name)`（L31–L46）

- **L33**：若 `name` 不包含 `'/'`，才认为是“库名”而不是路径。
- **L34–L44**：遍历 `pathes`，拼接 `path/name` 并尝试 `EtsNativeLibrary::Load(...)`。
- **L45**：最终 fallback：`EtsNativeLibrary::Load(name)`（可能是绝对路径或系统默认搜索路径）。

> 这个函数把 “库名 + libraryPath_” 的搜索策略集中封装，避免散落在 `LoadLibrary` 主流程里。

## 2. namespace fallback：从执行栈推导 app abcPath（L48–L71）

### 2.1 `LoadNativeLibraryFromNamespace(name)`（L48–L71）

- **L50**：使用 `EtsCoroutine::GetCurrent()` 作为 StackWalker 的入口（再次体现“ETS 以 coroutine 为执行主体”）。
- **L52–L68**：遍历 call stack：
  - **L55–L57**：跳过 `method->GetPandaFile()==nullptr` 的 frame（可能是 native/特殊帧）。
  - **L58–L63**：读取 `method->GetClass()->GetLoadContext()`，并打印是否 boot context。
  - **L63–L66**：找到第一个 **非 boot context** 的 frame，即认为是“应用侧调用点”，取其 panda file 的 `GetFullFileName()` 作为 `abcPath`。
- **L69–L71**：交给 `EtsNamespaceManagerImpl::LoadNativeLibraryFromNs(abcPath, name)`。

> 这是一个非常关键的工程决策：  
> “应用 so 从哪个 namespace 加载”不是纯配置，而是与当前执行栈/类加载上下文绑定。  
> 这使得同名 so 在 system 与 app namespace 之间的选择更贴近真实调用语义。

## 3. `LoadLibrary`：并发去重 + permission + fallback + ctor（L74–L109）

### 3.1 前置检查与去重（L77–L88）

- **L77**：要求 `env != nullptr`。
- **L78–L80**：若 `shouldVerifyPermission` 且 `CheckLibraryPermission` 失败 → 返回错误字符串。
- **L81–L88**：读锁下检查 `libraries_` 是否已存在同名库，存在则直接成功返回（重复 load 是幂等的）。

### 3.2 加载与 fallback（L89–L97）

- **L89**：尝试 system/path load：`LoadFromPath(GetLibraryPath(), name)`。
- **L90–L94**：若 `!shouldVerifyPermission` 且加载失败：  
  打 warning，并尝试 `LoadNativeLibraryFromNamespace(name.c_str())`（应用库）。
- **L95–L97**：仍失败则返回 `os::Error::ToString()`。

### 3.3 写锁插入与 ctor（L98–L109）

- **L100–L106**：写锁下 `libraries_.emplace(std::move(loadRes.Value()))`：
  - 若未插入（已存在），直接成功返回
  - 记录 `lib` 指针用于后续 ctor
- **L108**：`return CallAniCtor(env, lib)`：加载成功后必须跑 `ANI_Constructor`（除非库缺符号则返回错误）。

## 4. `CallAniCtor`：JNI_OnLoad 风格的版本协商（L111–L131）

- **L113**：查找符号 `"ANI_Constructor"`：
  - 找到则按签名调用：`ani_status (*)(ani_vm*, uint32_t*)`
  - `vm` 从 env 转回：`PandaEnv::FromAniEnv(env)->GetEtsVM()`（env→VM 的标准桥）
  - status 非 OK → 返回错误
  - version 不支持（`ani::IsVersionSupported(version)`）→ 返回错误
- **L125–L129**：找不到符号也视为错误（强制要求 ctor 存在），并记录日志。

> 结论：ETS native library 的约定比 JNI 更“硬”：缺少 ctor 直接失败，而不是可选。

## 5. OHOS 权限校验：需要调用方 className（L133–L183）

### 5.1 `GetCallerClassName`（L133–L157）

- 通过 `env->GetEtsCoroutine()` 与 `StackWalker::Create(coro)` 找到当前方法帧。
- 要求调用点来自 boot context（**L151–L155**）：否则报错。  
  直觉：只有 “系统 API” 或“受信任调用点” 才被允许触发某些库加载策略。

### 5.2 `CheckLibraryPermission`（L159–L183）

- 仅在 `PANDA_TARGET_OHOS` 下生效。
- 通过 `EtsNamespaceManagerImpl::GetExtensionApiCheckCallback()` 获取回调：
  - 未注册 → 失败
  - 回调返回 false → 失败并打印 className/fileName
- 否则通过。

## 6. `ResolveSymbol` 与路径管理（L185–L216）

- `ResolveSymbol`：读锁下遍历所有已加载库，返回第一个命中的符号地址。
- `GetLibraryPath/SetLibraryPath/AddLibraryPath`：读写锁保护 `libraryPath_`。



