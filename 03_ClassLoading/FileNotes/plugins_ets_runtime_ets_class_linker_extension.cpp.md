# `plugins/ets/runtime/ets_class_linker_extension.cpp`（逐行精读｜按功能段落）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：ETS `ClassLinkerExtension` 实现：roots 创建、class object 分配与初始化、native 入口点策略、builtin classes 标记、app context 创建、common-context 推导。  
> 文件规模：约 836 行（按“功能段落”组织逐行笔记）。

## 0. include 与主题（L16–L39）

可以把这些 include 分成三类：
- **ClassLoading 主链**：`ets_class_linker_extension.h`、`ets_class_linker_context.h`、`class_linker-inl.h`、`panda_vm.h`
- **ETS 类型系统**：`ets_method.h`、`ets_platform_types.h`、`ets_panda_file_items.h`
- **ANI/native**：`ani_helpers.h` + native entrypoint 获取

## 1. Native 调用类型：EtsNapiType + 注解识别（L41–L73）

### 1.1 EtsNapiType（L42–L53）
三种 native 模式：
- **GENERIC**：切 coroutine 到 native mode（允许 GC），并在参数前追加 NAPI env + this/class
- **FAST**：保持 managed mode（禁止 GC），仍追加 env+this/class；native 代码禁止触发分配
- **CRITICAL**：保持 managed mode（禁止 GC），参数原样传递（callee 必须 static）；同样禁止分配

### 1.2 GetEtsNapiType（L58–L73）
从 panda_file 的方法注解里识别：
- `ANI_UNSAFE_QUICK` → FAST
- `ANI_UNSAFE_DIRECT` → CRITICAL
否则默认 GENERIC

> 对齐 `Method`：后续 `GetNativeEntryPointFor` 会基于该类型设置 `ACC_FAST_NATIVE/ACC_CRITICAL_NATIVE`。

## 2. ClassLinkerError → ETS 异常（L75–L103）

- `GetClassLinkerErrorDescriptor(error)`（L75–L97）：把 core `ClassLinker::Error` 映射到 ETS 侧错误类 descriptor：
  - CLASS_NOT_FOUND / FIELD_NOT_FOUND / METHOD_NOT_FOUND / NO_CLASS_DEF / CIRCULARITY / METHOD_CONFLICT 等
  - 其它 case 直接 FATAL（要求覆盖完整）
- `ErrorHandler::OnError`（L99–L102）：直接 `ThrowEtsException(currentCoroutine, descriptor, message)`

> 语义：ETS 把 class linker 错误视为“可抛异常”，而不是仅回调错误处理器。

## 3. InitializeClassRoots：primitive/array/synthetic roots（L104–L140）

通过基类提供的 helper：
- `InitializeArrayClassRoot(ClassRoot::ARRAY_CLASS, ClassRoot::CLASS, ClassArrayDescriptor)`（L106–L108）
- `InitializePrimitiveClassRoot(root, typeId, shortDescriptor)`：
  - VOID→"V"、U1→"Z"、I8→"B"、U8→"H"、…、TAGGED→"A"
- 为每个 primitive 创建对应 array root：如 `"[I" "[J" ...`（L123–L134）
- `InitializeArrayClassRoot(ClassRoot::ARRAY_STRING, ClassRoot::STRING, StringArrayDescriptor)`（L135–L136）
- synthetic roots：ANY("Y")、NEVER("N")（L138–L139）

> 这些 roots 最终会通过 `SetClassRoot(root, klass)` 插入到 boot context（基类实现）。

## 4. String class 体系：主类 + 子类 + GC 布局元数据（L142–L235）

### 4.1 CreateStringSubClass（L142–L187）
用 core `ClassLinker::BuildClass` 从 `stringClass` 派生创建子类：
- 继承 `stringClass` 的 accessFlags 并加 `ACC_FINAL`（L147）
- `BuildClass(descriptor, needCopy=true, accessFlags, empty methods/fields/interfaces, base=stringClass, context=stringClass->GetLoadContext())`
- 设置 state：INITIALIZING → 设置 string 类型标志 → 根据子类类型写入 GC 相关元数据：
  - SLICED_STRING：设置 refFieldsNum/refFieldsOffset + objectSize（L164–L169）
  - TREE_STRING：设置 refFieldsNum/refFieldsOffset + objectSize（L172–L178）
- 最终置为 INITIALIZED（L185）

> 关键：这里手工写了 `refFieldsNum/refFieldsOffset/objectSize`，说明这些 String 子类的布局是 runtime 约定的（GC 依赖）。

### 4.2 InitializeStringClass（L206–L235）
- 先创建 String 类并塞为 class root：  
  `GetClassLinker()->GetClass(StringDescriptor, false, BootContext)`（L209）  
  然后 `RemoveFinal/SetStringClass/SetClassRoot(STRING, strCls)`（L214–L218）
- 再循环创建 Line/Sliced/Tree 三个子类并各自 SetFinal + SetClassRoot（L220–L232）

## 5. InitializeImpl：boot roots 的最早两类（OBJECT/CLASS）与字符串压缩开关（L237–L280）

核心步骤：
- `langCtx_ = Runtime::GetLanguageContext(ETS)`（L243）
- 从 boot context 获取并设置 OBJECT、CLASS roots（L247–L260）
- 让 managed `EtsClass` 对象的 `Class` 指针指向 classClass（L261–L263）
- `coretypes::String::SetCompressedStringsEnabled(compressedStringEnabled)`（L264）
- 初始化 String 体系（L266–L270）
- 加载 JS_VALUE 类并 `SetXRefClass`（L272–L277）（ETS 与 interop/js 相关）
- `InitializeClassRoots()`（L278）

> 这对应 `ClassLinkerExtension::InitializeImpl` 的“语言自举”：先拿到 OBJECT/CLASS，再逐步补齐其它 roots。

## 6. array/union/primitive/synthetic 的 InitializeXXX（L282–L366）

### 6.1 InitializeArrayClass（L282–L310）
- base 统一设为 OBJECT（并同步 ETS 的 SuperClass）（L289–L292）
- componentType 设为 componentClass（L292）
- accessFlags：从 componentClass 取 file mask，去掉 interface，加上 FINAL|ABSTRACT（L294–L297）
- 复制 OBJECT 的 vtable 到 arrayClass vtable（L300–L304）
- state → INITIALIZED（L306）

### 6.2 InitializeUnionClass（L312–L326）
- base=null、superClass=null
- 记录 constituent types
- state → INITIALIZED

### 6.3 InitializeClass（L328–L345）
`InitializeClass(klass, handler)`：
- 断言已初始化 + 允许访问 managed objects（L335–L336）
- 把 core `Class` 的 base/flags/primitive 属性同步到 `EtsClass::Initialize(...)`（L340–L343）

### 6.4 primitive/synthetic（L347–L366）
统一设 public|final|abstract，并置 INITIALIZED。

## 7. roots 的 vtable/imt/size 计算（L368+，L480–L545）

从我们读到的片段可见：
- primitives/any/never/tagged：vtableSize/imtSize/size 都走 0 或 ComputeClassSize(0,0,...)（L493–L515）
- arrays：走 `GetArrayClass{VTable,IMT,Size}`（L525–L544）
- OBJECT/STRING/Line/Sliced/Tree：走对应 root class 的 vtableSize 或 ComputeClassSize（L509–L515）

> 对齐 `class_linker.cpp::CreateArrayClass`：array class 的 vtable/imt/size 由 extension 决定。

## 8. Class 对象分配与“managed↔runtime”绑定（L546–L616）

### 8.1 InitializeClass(ObjectHeader*, ...)（L546–L559）
- 把 `ObjectHeader*` reinterpret 为 `EtsClass* managedClass`
- `managedClass->InitClass(descriptor, vtableSize, imtSize, size)`：在 managed 对象内部初始化 runtime class 元数据区
- 取出 `klass = managedClass->GetRuntimeClass()` 并：
  - `klass->SetManagedObject(objectHeader)`
  - `klass->SetSourceLang(ETS)`
  - `AddCreatedClass(klass)`（进入 createdClasses_，等待插入 context 后再迁移）

### 8.2 CreateClass(descriptor, vtableSize, imtSize, size)（L561–L579）
- 从 heapManager 分配 **NonMovable** 对象（`AllocateNonMovableObject<...>(classClassRoot, EtsClass::GetSize(size))`）
  - 特殊：当 CLASS root 尚未建立时，允许 `classClassRoot==nullptr`（用于自举 OBJECT/CLASS）
- 分配失败返回 nullptr
- 成功后调用上面的 InitializeClass(objectHeader, ...)。

### 8.3 CreateClassRoot（L581–L607）
- root==CLASS 的自举路径：直接分配 nonmovable + InitializeClass + 设置 objectSize + 让自身 class 指向自身（L589–L596）
- 其它 root：走 CreateClass
- 公共收尾：
  - base 设为 OBJECT（L601–L602）
  - state=LOADED、loadContext=BootContext（L603–L604）
  - `GetClassLinker()->AddClassRoot(root, klass)`（L605）

### 8.4 FreeClass / 析构（L609–L624）
- `FreeClass`：`RemoveOverloadMap()` + `RemoveCreatedClass(klass)`（从 createdClasses 迁移/清理）
- 析构：若已初始化则 `FreeLoadedClasses()`（基类 helper）。

## 9. native 入口点选择与 flags 写回（L626–L699）

### 9.1 IsMethodNativeApi（L626–L630）
native 且非 intrinsic 且非 async 注解，才算 native API。

### 9.2 CanThrowException / SwitchThreadState / UseObjects（L632–L660）
全部基于 `EtsMethod` 的 `IsFastNative/IsCriticalNative` 等属性决定：
- critical native：不能抛异常、不能用对象、也不需要切线程态（因为一直在 managed mode 且不能 GC）
- fast native：不切线程态但也不能分配（间接限制）
- generic：需要切线程态（允许 GC）

### 9.3 GetNativeEntryPointFor（L662–L689）
- async 注解 → `EtsAsyncEntryPoint`
- 否则根据 `GetEtsNapiType`：
  - GENERIC：`ani::GetANIEntryPoint()`
  - FAST：给 method 写 `ACC_FAST_NATIVE`，仍用 `GetANIEntryPoint`
  - CRITICAL：写 `ACC_CRITICAL_NATIVE`，用 `ani::GetANICriticalEntryPoint()`

> 对齐 `class_linker.cpp::LoadMethod`：native 方法的 entrypoint 由 extension 决定，并在 Method 上写回 flags/entrypoint。

## 10. builtin classes：CacheClass + PlatformTypes（L701–L789）

- `CacheClass(descriptor, forceInit)`：从 boot context GetClass；可选强制 InitializeClass；失败打印错误。
- `InitializeBuiltinSpecialClasses()`：对 String/NullValue/Boxed/BigInt/Function/Enum/WeakRef 等类设置 ETS 的语义标志。
- `InitializeBuiltinClasses()`：
  - 初始化 special classes
  - 创建 `plaformTypes_`（用 internal allocator new）
  - 把 coroutine 的 pseudo TLS（PromiseClass/JobClass/StringClassPtr/ArrayU16/U8）指向对应 root（L779–L784）

### InitializeFinish（L786–L789）
`plaformTypes_->InitializeClasses(currentCoroutine)`：完成平台类型表的 class 初始化（典型：缓存常用 Method/Class 指针）。

## 11. app context 创建与 common-context（L791–L833）

- `CreateApplicationClassLinkerContext(path)`：调用 `PandaEtsVM::CreateApplicationRuntimeLinker(path)` 返回 context（L793–L795）
- `GetParentContext(ctx)`：从 `EtsClassLinkerContext` 取 runtime linker，要求是 AbcRuntimeLinker，返回 parentLinker->GetClassLinkerContext（L799–L812）
- `GetCommonContext(classes)`：
  - 从第一个 class 的 loadContext 开始
  - while 非 boot：检查该 context 是否包含所有 class descriptor（`FindClass`），否则上移到 parent context
  - 找到则返回；若一路上移到 boot，则返回 boot

> 对齐 `class_linker.cpp::LoadUnionClass`：union class 需要一个 commonContext 作为插入/去重域，这里给出 ETS 的计算方式。


