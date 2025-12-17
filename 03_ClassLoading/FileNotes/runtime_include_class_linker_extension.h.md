# `runtime/include/class_linker_extension.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：语言插件扩展点（ClassLinkerExtension）：定义“语言相关的 class 创建/根类初始化/上下文管理/类初始化策略/GC roots 枚举”。  
> 关键结论：`ClassLinker` 是语言无关管线；**Extension 决定语言相关的创建与初始化**，并且持有 **BootContext/AppContext**（都是 `ClassLinkerContext` 的派生）作为加载域。

## 1. 依赖与定位（L18–L30）

- **L18**：mutex：extension 内部维护多个列表与上下文集合，需要并发保护（多处用 `RecursiveMutex`）。
- **L19–L20**：panda_file File / EntityId：GetClass 等 API 需要文件定位。
- **L21**：`runtime/class_linker_context.h`：上下文本体（descriptor→Class 缓存、per-Class mutex、roots）。
- **L22–L23**：`class_root.h` / `class.h`：class roots 与 Class 元数据对象。
- **L24**：panda 容器。

## 2. 类整体职责（L31–L35）

注释明确：插件必须继承它，以定义语言相关的类操作；实例由 `ClassLinker` 拥有（按语言 one-to-many 关系：ClassLinker 有一个数组，某语言最多一个 extension）。

## 3. 构造/初始化阶段（L38–L47）

- **L38**：构造函数记录 `lang_`，并初始化 `bootContext_(this)`：boot context 总是存在。
- **L42**：`Initialize(ClassLinker*, compressedStringEnabled)`：extension 与 class linker 的绑定入口（实现不在头文件）。
- **L44**：`InitializeFinish()`：二阶段收尾（通常在 roots 完成后）。
- **L46**：`InitializeRoots(thread)`：初始化 class roots（Object/Class/String/Array/Primitive…），并把 roots 插入 boot context（见 `SetClassRoot`）。

> 这与 `ClassLinker::Initialize/InitializeRoots` 的两阶段完全对齐。

## 4. 语言必须实现的核心虚接口（L48–L86）

这些是“语言差异”的主要承载点：
- **类创建/释放**：
  - `CreateClass(descriptor, vtableSize, imtSize, size)`（L72）
  - `FreeClass(Class*)`（L74）
- **类初始化**：
  - `InitializeClass(Class*)`（L76）
  - 还有一个带 errorHandler 的重载默认转发（L78–L81）
- **数组/union/合成类初始化**：
  - `InitializeArrayClass(arrayClass, componentClass)`（纯虚，L48）
  - `InitializeUnionClass` 默认 false（L50–L54），只有支持 union 的语言才 override
  - `InitializeSyntheticClass/InitializePrimitiveClass`（L56–L58）
- **roots 的布局参数**：
  - `GetClassVTableSize/GetClassIMTSize/GetClassSize`（按 ClassRoot，L60–L64）
  - `GetArrayClassVTableSize/GetArrayClassIMTSize/GetArrayClassSize`（L66–L70）
- **native 桥接契约**：
  - `GetNativeEntryPointFor(Method*)`（L83）：native 方法入口点由语言决定（ETS/JS/…）
  - `CanThrowException/IsMethodNativeApi/IsNecessarySwitchThreadState/CanNativeMethodUseObjects`（L85–L100）：native 调用时线程状态切换、对象可用性等策略开关
- **错误处理**：
  - `GetErrorHandler()`（L102）：extension 提供默认错误处理器（ClassLinker 在某些路径会用它兜底）

## 5. Context 管理：BootContext + AppContext（L303–L360）

### 5.1 BootContext（L303–L322）
BootContext 是 `ClassLinkerContext` 的派生类，且与 extension 绑定：
- **L305–L308**：构造时把 SourceLang 设为 extension 语言。
- **L310–L313**：`IsBootContext()` 返回 true（配合 ClassLinker 的 boot fast-path 与 bloom filter）。
- **L315–L316**：`LoadClass(descriptor, needCopyDescriptor, errorHandler)` override：boot 的加载算法由 extension 定义（一般会委托 ClassLinker 在 boot files 中查找/加载）。
- **L318**：`EnumeratePandaFiles(cb)` override：枚举 boot panda files（来源通常是 ClassLinker 注册的 boot files + extension 私有资源）。

### 5.2 AppContext（L324–L360）
AppContext 也是 `ClassLinkerContext` 派生类，持有一组 `pfs_`（该 context 关联的 panda files）：
- **L331–L332**：`LoadClass` override：应用类加载算法（通常只在 pfs_ 内查找，找不到可能走 parent chain 或失败）。
- **L334–L344**：`EnumeratePandaFiles(cb)`：遍历 pfs_ 调 cb。
- **L346–L355**：`GetPandaFilePaths()`：返回 pfs_ 文件名，用于 AOT class context/调试 dump。

> 对齐 `ClassLinker::GetClass`：非 boot context 情况下会直接 `context->LoadClass`，所以 AppContext 的 override 是“应用加载算法”的关键落点。

## 6. roots 与 bootContext 插入（L111–L125）

- **L111–L114**：`GetClassRoot(root)`：从 `classRoots_` 数组取。
- **L116–L119**：`GetBootContext()`：返回 `bootContext_` 地址。
- **L121–L125**：`SetClassRoot(root, klass)`：
  - 写入 `classRoots_[root]`
  - 关键：`bootContext_.InsertClass(klass)`：roots 一定属于 boot context，并且会进入 `loadedClasses_`（descriptor→Class）。

## 7. GetClass API：extension 作为“语言入口”（L127–L150）

- **L127**：`FindLoadedClass(descriptor, context)`：在指定 context（若为空一般会 resolve 到 boot）里查找 loaded class。
- **L129–L135**：两套 `GetClass` 导出 API：
  - `(descriptor, needCopyDescriptor=true, context=nullptr, errorHandler=nullptr)`
  - `(pf,id, context=nullptr, errorHandler=nullptr)`

这些通常会委托 `classLinker_` 的同名方法；但 extension 可以在其中决定 context 的 resolve（见 `ResolveContext`）。

## 8. GC roots 枚举语义：created/new/boot/app/obsolete（L157–L224）

这是本文件最“容易被忽略但很关键”的部分：**extension 维护了多个 class 列表**，用于不同 GC root 访问策略：

### 8.1 recordNewClass_ 开关（L157–L172）
- `RecordNewRoot(flags)`：处理 `VisitGCRootFlags::{START_RECORDING_NEW_ROOT, END_RECORDING_NEW_ROOT}`：
  - START：`recordNewClass_=true`（seq_cst）
  - END：`recordNewClass_=false`（seq_cst）并清空 `newClasses_`（受 `newClassesLock_`）

用途：GC 可以选择仅访问“自上次记录以来新创建的类”，减少 STW/并发 root 扫描成本。

### 8.2 `EnumerateClasses(cb, flags)`（L174–L224）
按 flags 组合枚举：
- 若 ACCESS_ROOT_ALL 或 ACCESS_ROOT_ONLY_NEW：
  - 先枚举 `createdClasses_`（createdClassesLock_）
- 若 ACCESS_ROOT_ONLY_NEW：
  - 再枚举 `newClasses_`（newClassesLock_）
- 若 ACCESS_ROOT_ALL：
  - 枚举 `bootContext_` 的 loadedClasses_
  - 枚举所有注册的 `contexts_`（contextsLock_），对每个 context 调 `ctx->EnumerateClasses`
- 无论 flags：最后都会枚举 `obsoleteClasses_`（obsoleteClassesLock_）
- 末尾 `RecordNewRoot(flags)`，把 START/END 的语义内聚在同一处

> 结论：ClassLinker 在 GC 时调用 `ext->EnumerateClasses`，可以精确控制“扫全部 / 只扫新类 / 不扫”。

## 9. 上下文注册与枚举（L226–L249）

- `RegisterContext(fn)`：在 `contextsLock_` 下把 fn() 返回的 context push 到 `contexts_`。
- `EnumerateContexts(cb)`：先回调 bootContext_，再在锁下遍历 contexts_。

这与 `ClassLinker::EnumerateContexts`/`EnumerateContextsForDump` 的实现完全对齐：ClassLinker 只是“遍历 extension，再遍历 extension 内部 contexts”。

## 10. ResolveContext 与 OnClassPrepared/obsolete（L255–L269）

- `ResolveContext(context)`：若传入 nullptr，统一回退到 `bootContext_`（L255–L262）。
- `OnClassPrepared(Class*)`：由 ClassLinker 在 class 插入 context 后调用（见 `ClassLinker::RemoveCreatedClassInExtension`），extension 在这里通常会：
  - 把 class 从 `createdClasses_` 移除
  - 如开启 recordNewClass_，把 class 放到 `newClasses_`
  - 以及可能做语言侧的额外 bookkeeping
- `AddObsoleteClass/FreeObsoleteData`：热重载/替换旧类后，把旧数据保留到 `obsoleteClasses_`，确保仍可执行（注释 L266–L268）。

## 11. 保护方法与内部结构（L282–L400）

### 11.1 Root 初始化辅助（L283–L288）
`InitializePrimitiveClassRoot / InitializeArrayClassRoot / InitializeSyntheticClassRoot`：把各种 roots 以统一模式创建并塞到 classRoots_（实现不在头文件）。

### 11.2 created/new/obsolete 的维护（L289–L298）
- `FreeLoadedClasses()`：释放已加载类（通常用于销毁/重置）。
- `AddClass`：把 class 加入到合适集合（并可能插入 context）。
- `AddCreatedClass`：仅加入 created list（“刚创建、未插入 context”阶段）。
- `RemoveCreatedClass`：当 class 已插入 context 后，从 created list 移除。

> 对齐 `ClassLinker::LoadClass`：在 `context->InsertClass` 成功后，会调用 `ext->OnClassPrepared`，这里就是 created→(new?) 的迁移点。

### 11.3 CreateApplicationClassLinkerContext（L299–L301）
两层：
- public `CreateApplicationClassLinkerContext(path)`（L104）返回 `ClassLinkerContext*`
- protected `CreateApplicationClassLinkerContext(PandaVector<PandaFilePtr>&&)`（L300）用于“已打开 panda files”直接构造 AppContext

### 11.4 私有字段（L380–L399）
- `lang_`：语言
- `bootContext_`：boot context（强绑定）
- `classRoots_`：roots 数组（CLASS_ROOT_COUNT）
- `classLinker_`：回指 ClassLinker（Initialize 后置位）
- `contexts_`：已注册的 app contexts
- `createdClasses_`：刚创建/待插入 context 的类
- `recordNewClass_ + newClasses_`：记录“新根类”的增量列表
- `obsoleteClasses_`：热更保留旧类
- `canInitializeClasses_`：是否允许初始化（由 Initialize/InitializeFinish 决定）


