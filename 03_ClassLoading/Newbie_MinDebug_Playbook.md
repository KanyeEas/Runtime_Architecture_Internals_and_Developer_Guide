# 03_ClassLoading：新人最小调试手册（可复现 + 可落地）

> 目标：新人在 **10 分钟内**把“找不到类/接口派发冲突/ETS 两段式加载失败”定位到**第一落点**与**第二落点**，并能用日志/最小实验复现与验证。

## 0) 快速目录（直接点）

- 端到端主线：[Flows/ClassLoading_EndToEnd](Flows/ClassLoading_EndToEnd.md)
- 三大场景决策树（README 里三张）：[README](README.md) 的 场景 A/B/C
- GetClass/LoadClass 主链：[Flows/GetClass_and_LoadClass](Flows/GetClass_and_LoadClass.md)
- ETS 两段式加载：[Flows/ETS_Context_Native_vs_Managed_Load](Flows/ETS_Context_Native_vs_Managed_Load.md)
- `.abc/.an` 装载：[Flows/FileManager_ABC_AN](Flows/FileManager_ABC_AN.md)

## 1) 先把日志开对（90% 的新手问题在这里）

日志选项来自 `libarkbase/utils/logger_options.yaml`（注意：runtime/options.yaml 里旧的 log 选项已不推荐使用）。

### 1.1 常用组合（建议直接复制）

- **只看类加载（最常用）**：
  - `--log-level=debug`
  - `--log-components=classlinker`
- **再加上文件装载（.abc/.an）**：
  - `--log-level=debug`
  - `--log-components=classlinker:pandafile:aot`
- **怀疑与执行引擎/初始化交界（跨章）**：
  - `--log-level=debug`
  - `--log-components=classlinker:interpreter:runtime`

> 证据：源码中类加载相关日志大量使用 `LOG(*, CLASS_LINKER)`（例如 `runtime/class_linker.cpp`、`runtime/class_linker_extension.cpp`），文件装载使用 `LOG(*, PANDAFILE)`（`runtime/file_manager.cpp`）。

## 2) “症状 → 第一落点 → 第二落点”（新人最快路线）

| 症状/日志 | 第一落点（优先看） | 第二落点（需要硬证据时） |
|---|---|---|
| `Cannot find class '<descriptor>'` / `CLASS_NOT_FOUND` | `runtime/class_linker.cpp`（GetClass → FindClassInBootPandaFiles → LoadClass） | [FileNotes/runtime_class_linker.cpp](FileNotes/runtime_class_linker.cpp.md)（boot filter/错误路径/InsertClass 并发去重） |
| CNFE / NCDFE 异常类型不符合预期 | `runtime/class_linker_extension.cpp`（WrapClassNotFoundExceptionIfNeeded） | [FileNotes/runtime_class_linker_extension.cpp](FileNotes/runtime_class_linker_extension.cpp.md)（CNFE→NCDFE 包装策略） |
| boot 启动期类找不到 | [Flows/FileManager_ABC_AN](Flows/FileManager_ABC_AN.md)（boot panda files 注册） | `runtime/file_manager.cpp`（LoadAbcFile）+ `runtime/class_linker.cpp`（boot filter Add/Lookup） |
| `MULTIPLE_IMPLEMENT` / default interface method 冲突 | `plugins/ets/runtime/ets_itable_builder.cpp`（Resolve/冲突判定） | `runtime/include/vtable_builder_*` + `runtime/imtable_builder.cpp`（冲突策略/IMT 行为） |
| IMT 为空 / itable 回退导致性能差 | `runtime/imtable_builder.cpp`（imtSize 策略 + UpdateClass） | [DataStructures/ITable_and_IMT](DataStructures/ITable_and_IMT.md) + [Flows/Builders_and_LinkMethods](Flows/Builders_and_LinkMethods.md) |
| default interface method 看起来“凭空出现一堆 copied methods” | `runtime/include/vtable_builder_base-inl.h`（AddDefaultInterfaceMethods） | [Flows/Builders_and_LinkMethods](Flows/Builders_and_LinkMethods.md)（vtable build 算法图 + copied methods 解释） |
| 调试时 `Class*->GetVTable()`/IMT 读出来像“乱指针/越界” | `runtime/include/coretypes/class.h`（InitClass placement new + GetSize） | [DataStructures/Class](DataStructures/Class.md)（变长对象尾随布局图 + 证据链） |
| 同一类加载“偶现重复创建/重复 FreeClass/prepare 顺序不稳定” | `runtime/class_linker.cpp::LoadClass(... addToRuntime)`（InsertClass 冲突回收） | [Flows/Concurrency_and_ClassLock](Flows/Concurrency_and_ClassLock.md)（并发去重真实模型） |
| 报 `CLASS_CIRCULARITY`（自己的父类/父接口） | `runtime/class_linker.cpp::TryInsertClassLoading` | [Flows/Concurrency_and_ClassLock](Flows/Concurrency_and_ClassLock.md)（thread_local ClassLoadingSet） |
| ETS app context “不允许回退到 managed” | `plugins/ets/runtime/ets_class_linker_context.cpp`（线程状态 gate：coro/managed） | [Flows/ETS_Context_Native_vs_Managed_Load](Flows/ETS_Context_Native_vs_Managed_Load.md)（为什么要禁） |

## 2.1 更强交付标准：症状矩阵（日志关键词 → 第一落点函数 → 必查分支条件 → 第二落点）

> 使用方式：先在日志里**匹配关键词**，然后直接跳到“第一落点函数”里核对“必查分支条件”。  
> 目标：把“猜测式排障”变成“分支驱动排障”。

| 症状/日志关键词（抓关键字即可） | 第一落点函数（源码） | 必查分支条件（你要验证的 if/状态） | 第二落点（证据/图） |
|---|---|---|---|
| `Cannot find class ... in boot class bloom filter` | `runtime/class_linker.cpp::LookupInFilter` | `Runtime::GetOptions().IsUseBootClassFilter()==true` 且 `bootClassFilter_.PossiblyContains(descriptor)==false` 且 `errorHandler!=nullptr` | [Flows/GetClass_and_LoadClass](Flows/GetClass_and_LoadClass.md)（BootFilter 语义）+ [FileNotes/runtime_class_linker.cpp](FileNotes/runtime_class_linker.cpp.md) |
| `Cannot find class ... in boot panda files:` | `runtime/class_linker.cpp::GetClass(descriptor, bootCtx)` | `LookupInFilter!=IMPOSSIBLY_HAS` 且 `FindClassInPandaFiles` 找不到 `classId` | 同上 |
| `Cannot find class ... in all app panda files` | `runtime/class_linker_extension.cpp::AppContext::LoadClass` | 遍历 app panda files 后仍找不到 classId（通常意味着“文件未注册/上下文不对”） | [FileNotes/runtime_class_linker_extension.cpp](FileNotes/runtime_class_linker_extension.cpp.md)（AppContext LoadClass） |
| `Class or interface "<X>" is its own superclass or superinterface` / `CLASS_CIRCULARITY` | `runtime/class_linker.cpp::TryInsertClassLoading` | `threadLocalSet->insert(key).second == false`（同线程递归自指） | [Flows/Concurrency_and_ClassLock](Flows/Concurrency_and_ClassLock.md)（ClassLoadingSet 判定树） |
| `Method overrides final method` / `OVERRIDES_FINAL` | `runtime/include/vtable_builder_*::ProcessClassMethod` | base 槽满足 override 条件且 `itInfo->IsFinal()==true` | [Flows/Builders_and_LinkMethods](Flows/Builders_and_LinkMethods.md)（override 决策树） |
| `MULTIPLE_IMPLEMENT`（或 “Conflicting default implementations”） | `runtime/include/vtable_builder_variance-inl.h` 或 `plugins/ets/runtime/ets_itable_builder.cpp` | vtable/default method 决策树导致冲突，或 ETS resolve 在 vtable 中找到多个实现候选 | [Flows/Builders_and_LinkMethods](Flows/Builders_and_LinkMethods.md)（copied/default 决策树）+ [DataStructures/ITable_and_IMT](DataStructures/ITable_and_IMT.md) |
| `Language specific initialization for class '<descriptor>' failed` | `runtime/class_linker.cpp::LoadClass(... addToRuntime)` | `ext->CanInitializeClasses()==true` 且 `ext->InitializeClass(klass)==false` | [Flows/ClassLoading_EndToEnd](Flows/ClassLoading_EndToEnd.md)（加载↔初始化交界） |
| `Cannot layout static fields ...` / `Cannot layout instance fields ...` | `runtime/class_linker.cpp::LinkFields` → `LayoutFields` | `LayoutFields(..., isStatic)==false` 或 `LayoutFields(..., !isStatic)==false` | [Flows/LayoutFields_and_LinkFields](Flows/LayoutFields_and_LinkFields.md)（布局算法图） |

## 3) 三个最小实验（强烈建议新人做一遍）

### 实验 1：复现“找不到类”（验证你走到的是 boot 还是 app）

- **操作**：选择一个你确信存在/不存在的 descriptor，分别在 boot 与 app 情况下触发一次 `GetClass`。
- **日志**：
  - `--log-level=debug --log-components=classlinker:pandafile`
- **观测点**：
  - 是否走 `BootContext` 分支（boot filter / boot panda files）
  - 是否走 `AppContext::LoadClass`（或 ETS context 的 `LoadClass`）
- **关键日志关键词**（用于快速判分支）：
  - boot filter 快速否定：`Cannot find class ... in boot class bloom filter`
  - boot files 查不到：`Cannot find class ... in boot panda files:`
  - app files 查不到：`Cannot find class ... in all app panda files`
- **关键函数**：
  - boot：`ClassLinker::GetClass` → `LookupInFilter` → `FindClassInPandaFiles`
  - app：`AppContext::LoadClass`（默认实现）/ `EtsClassLinkerContext::LoadClass`（ETS 特化）
- **第一落点**：[Flows/GetClass_and_LoadClass](Flows/GetClass_and_LoadClass.md)
- **第二落点**：[FileNotes/runtime_class_linker.cpp](FileNotes/runtime_class_linker.cpp.md)、[FileNotes/runtime_class_linker_extension.cpp](FileNotes/runtime_class_linker_extension.cpp.md)

### 实验 2：复现 ETS 两段式加载 gate（验证“为什么不能回退”）

- **操作**：在 ETS app context 下触发一次 class load：
  - 在“非 managed 线程/无 coroutine”触发（应禁止 managed 回退）
  - 在“managed 线程（有 coroutine）”触发（允许 managed 回退）
- **日志**：
  - `--log-level=debug --log-components=classlinker`
- **观测点**：
  - native 链式查找是否遍历 parent/shared-libs
  - 是否进入 `RuntimeLinker.loadClass(final)` managed 回退
- **关键函数/条件**：
  - gate：`EtsCoroutine::GetCurrent()==nullptr || !coro->IsManagedCode()` → 禁止回退
  - 白名单 linker：`coreAbcRuntimeLinker/coreMemoryRuntimeLinker`（否则直接要求走 managed）
- **第一落点**：[Flows/ETS_Context_Native_vs_Managed_Load](Flows/ETS_Context_Native_vs_Managed_Load.md)
- **第二落点**：[FileNotes/plugins_ets_runtime_ets_class_linker_context.cpp](FileNotes/plugins_ets_runtime_ets_class_linker_context.cpp.md)

### 实验 3：复现接口派发冲突（MULTIPLE_IMPLEMENT / IMT 冲突）

- **操作**：构造一个最小用例：
  - 两个 interface 产生同名同签名默认方法 / 多实现冲突（或让接口方法总数超过 IMT 策略阈值）
- **日志**：
  - `--log-level=debug --log-components=classlinker`
- **观测点**：
  - vtable/itable/imt 的 build/resolve/update 顺序
  - 冲突策略是否“清空 IMT 槽/禁用 IMT”
- **关键落地效果**：
  - copied default method 的 `Status` 会在 `ClassLinker::SetupCopiedMethods` 转为不同 stub entrypoint（ABSTRACT/CONFLICT）
- **第一落点**：[Flows/Builders_and_LinkMethods](Flows/Builders_and_LinkMethods.md)
- **第二落点**：[FileNotes/runtime_imtable_builder.cpp](FileNotes/runtime_imtable_builder.cpp.md)、[FileNotes/plugins_ets_runtime_ets_itable_builder.cpp](FileNotes/plugins_ets_runtime_ets_itable_builder.cpp.md)



