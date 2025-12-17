# `plugins/ets/runtime/ets_class_linker_extension.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：ETS 的 `ClassLinkerExtension` 派生类：定义“ETS 的 class roots / class 创建与释放 / 语言侧初始化 / native 入口点策略 / app context 创建 / common-context 推导”。  
> 注意：实现主体在 `.cpp`，本头文件是 ETS 侧 ClassLoading 的“能力清单”。

## 1. 关键职责一览（L44–L129）

### 1.1 roots 与特殊类初始化
- `InitializeClassRoots()`：创建 primitive/array/synthetic roots（与 `ClassLinkerExtension` 的 root helpers 对齐）。
- String 相关：
  - `InitializeStringClass(classClass)`：创建 String 以及其子类（LineString/SlicedString/TreeString）
  - `CreateStringSubClass(descriptor, stringClass, type)`
  - `GetStringClassDescriptor(ClassRoot strCls)`
- `InitializeBuiltinClasses()` / `InitializeBuiltinSpecialClasses()`：缓存并给某些 builtin class 打 ETS 特定标志（值类型/boxed/bigint/weak ref…）。

### 1.2 class 创建/释放与 managed-object 绑定
- `CreateClass(descriptor, vtableSize, imtSize, size)`：在 ETS heap 上分配 **NonMovable** 的 class object（`EtsClass`），并初始化 runtime `Class`。
- `FreeClass(klass)`：清理 ETS class 的额外数据（如 overload map），并把其从 createdClasses 中移除（对齐基类的 created/new/obsolete 语义）。
- `FromClassObject(obj)`：从 managed class object（`EtsClass*`）反查 runtime `Class*`。
- `GetClassObjectSizeFromClassSize(size)`：Class 对象大小映射（ETS 用 `EtsClass::GetSize(size)`）。

### 1.3 语言侧 InitializeClass
- `InitializeClass(klass)` 与 `InitializeClass(klass, handler)`：
  - 把 core `Class` 的 metadata 同步/映射到 `EtsClass`（ETS 的 `Class` 包装类型），并接入 ETS 的错误处理。

### 1.4 native 入口点策略（ANI / fast / critical / async）
- `IsMethodNativeApi(method)`：区分“真 native API 调用”与“intrinsic/async 伪 native”。
- `GetNativeEntryPointFor(method)`：根据注解与策略返回：
  - generic/fast：ANI 普通入口点
  - critical：ANI critical 入口点
  - async：EtsAsyncEntryPoint
- `IsNecessarySwitchThreadState / CanNativeMethodUseObjects / CanThrowException`：指导 runtime 在 native 调用时是否要切线程态、是否允许触达 managed objects、是否可抛异常。

### 1.5 context 管理与 union/common-context
- `CreateApplicationClassLinkerContext(path)`：由 ETS VM 创建 app runtime linker/context（非 boot）。
- `GetCommonContext(classes)`：给 union 类或跨上下文类型集合找共同 context（沿 parent 逐级向上）。
- `GetParentContext(ctx)`：从 app context 得到父 context（通过 AbcRuntimeLinker parentLinker）。

## 2. 错误处理器（L145–L148）

内部 `ErrorHandler : ClassLinkerErrorHandler`：
- `OnError(error, message)`：将 class linker 错误转换为 ETS 异常（实现见 `.cpp`）。

这解释了为什么 `GetErrorHandler()` 返回 `&errorHandler_`：ETS 把 class linker 错误“语义化”为可捕获异常。

## 3. 私有状态（L150–L155）

- `langCtx_`：ETS 的 `LanguageContext`（用于 descriptor/name/初始化策略等）。
- `heapManager_`：用于分配 NonMovable class object（`EtsClass`）。
- `plaformTypes_`：ETS 平台类型表（提供 `coreRuntimeLinkerLoadClass`、Promise/Job 等核心 class/method 句柄）。


