# ETS 插件侧闭环（LanguageContext / Extension / Context / ITableBuilder）

## 0) 在端到端主线图中的位置

- 总入口：[../Flows/ClassLoading_EndToEnd](../Flows/ClassLoading_EndToEnd.md)（“ETS：context 的 native→managed 两段式加载”与“Extension 自举/entrypoint”相关框）

## 1) LanguageContext：策略工厂（入口）

`EtsLanguageContext` 负责把 runtime 的“抽象策略点”落到 ETS：
- CreateITableBuilder → `EtsITableBuilder`
- CreateVTableBuilder → `EtsVTableBuilder`
- CreateClassLinkerExtension → `EtsClassLinkerExtension`
- InitializeClass → `ClassInitializer<MT_MODE_TASK>::Initialize`
- CreateVM / CreateGC / ThrowException / ThrowStackOverflow / VerificationInitAPI

证据链：
- [FileNotes/plugins_ets_runtime_ets_language_context.h](FileNotes/plugins_ets_runtime_ets_language_context.h.md)
- [FileNotes/plugins_ets_runtime_ets_language_context.cpp](FileNotes/plugins_ets_runtime_ets_language_context.cpp.md)

## 2) ClassLinkerExtension：自举 + managed<->runtime Class 绑定 + native 入口点

`EtsClassLinkerExtension` 负责：
- boot 自举：OBJECT/CLASS/String 体系与 primitive/array/synthetic roots
- class object 分配：NonMovable `EtsClass` 对象内嵌 runtime `Class`，并通过 `AddCreatedClass/OnClassPrepared` 跟踪生命周期
- native 入口点：按注解选择 GENERIC/FAST/CRITICAL/ASYNC，并写回 Method flags + entrypoint
- app context 创建：`CreateApplicationRuntimeLinker(path)`
- common-context：为 union/跨域类型集合找共同 loadContext

证据链：
- [FileNotes/plugins_ets_runtime_ets_class_linker_extension.h](FileNotes/plugins_ets_runtime_ets_class_linker_extension.h.md)
- [FileNotes/plugins_ets_runtime_ets_class_linker_extension.cpp](FileNotes/plugins_ets_runtime_ets_class_linker_extension.cpp.md)

## 3) ClassLinkerContext：ETS 非 boot 加载域

`EtsClassLinkerContext`：
- native 优先链式解析（parent + shared libs），失败再调用 managed `loadClass(final)`
- 只允许在 managed 线程进入 managed 路径，保护 VM 内部线程（JIT/AOT）不 re-enter managed
- panda files 枚举直接来自 RuntimeLinker 的 AbcFiles 列表

证据链：
- [FileNotes/plugins_ets_runtime_ets_class_linker_context.cpp](FileNotes/plugins_ets_runtime_ets_class_linker_context.cpp.md)

## 4) ITableBuilder：ETS 接口派发 resolve（vtable 驱动）

`EtsITableBuilder`：
- 线性化接口及其父接口，clone base itable
- Resolve 时优先复用 base 的 vtableIndex（派发位置），否则在 vtable 反向匹配 name+proto
- 多实现候选直接 MULTIPLE_IMPLEMENT 报错并失败

证据链：
- [FileNotes/plugins_ets_runtime_ets_itable_builder.cpp](FileNotes/plugins_ets_runtime_ets_itable_builder.cpp.md)

## 下一步（新人推荐）

- 想看“ETS 两段式加载”的决策树与 gate → [../Flows/ETS_Context_Native_vs_Managed_Load](../Flows/ETS_Context_Native_vs_Managed_Load.md)
- 想看“ETS native entrypoint 如何写回 Method 并影响执行入口（跨章）” → [../04_ExecutionEngine/README](../04_ExecutionEngine/README.md)


