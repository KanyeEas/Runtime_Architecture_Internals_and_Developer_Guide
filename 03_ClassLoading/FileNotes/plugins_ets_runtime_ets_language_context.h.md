# `plugins/ets/runtime/ets_language_context.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：ETS 的 `LanguageContextBase` 声明：提供 descriptor/名称常量、class init 策略、builder 工厂、VM/GC 工厂、verification 初始化信息等。

## 1. 依赖与整体定位（L19–L46）

该头文件把 ETS 与 runtime 的“接口契约”基本一次性列全：
- 继承 `LanguageContextBase`（runtime/include/language_context.h）
- 直接依赖 class linker（`class_linker.h`、`class_linker_extension.h`、`class_initializer.h`）
- 依赖 `ITableBuilder/VTableBuilder`（说明 ETS 会自定义 builder）
- 依赖 GC（`gc.h/gc_types/gc_settings`）与 allocator（表明 LanguageContext 也参与创建 GC）
- ETS 私有依赖：`ets_panda_file_items.h`（descriptor 常量源）、`pt_ets_extension`（调试/工具扩展）、`ets_vm.h`、`ets_class_linker_extension.h`

## 2. 语言身份（L58–L66）

- `GetLanguage()` 固定返回 `SourceLang::ETS`
- `GetLanguageType()` 返回 `EtsLanguageConfig::LANG_TYPE`

> 这是 LanguageContext 与 `extensions_[langIndex]`、以及 runtime 的类型分发的基础。

## 3. Descriptor / 名称常量：把 ETS 的“根类/错误类/特殊名字”映射到字符串（L68–L250）

这一大段基本都是：
- 从 `plugins/ets/runtime/ets_panda_file_items.h` 拿到常量 string
- 通过 `utf::CStringAsMutf8(...)` 转成 MUTF8 指针返回

覆盖范围包括：
- roots：OBJECT、CLASS、NULL_VALUE、CLASS_ARRAY、STRING_ARRAY
- 特殊方法名：`<init>`（CTOR）、`<clinit>`（CCTOR）
- 常见异常/错误类 descriptor：NPE、SOE、AIOOBE、ClassCast、AbstractMethodError、OOM、NoClassDef、Circularity、VerificationError 等

> 这些 descriptor 是 ClassLinker/Verifier/Exception 体系的“统一 key”，用来通过 `GetClass(descriptor)` 取到对应 `Class*`。

## 4. TaggedValue 与调用相关的 override（L252–L292）

多个函数对 ETS 来说是 `UNREACHABLE()`：
- `GetInitialTaggedValue` / `GetEncodedTaggedValue`
- `IsCallableObject` / `GetCallTarget`
- `GetReferenceErrorDescriptor` / `GetTypedErrorDescriptor`

但 `SetExceptionToVReg` 是有实现的（L265–L268）：把异常对象写入 accumulator/vreg 的 reference 槽。

> 解释：ETS 不是动态语言 TaggedValue 调用模型，因此这些动态语言专用接口在 ETS 下被显式禁止。

## 5. 构建器工厂与 class init 策略（L299–L313）

关键点：
- `ThrowException`：统一抛异常入口（实现见 `.cpp`）。
- `CreateITableBuilder(errHandler)`：返回 ETS 的 itable builder（实现见 `.cpp` → `EtsITableBuilder`）。
- `CreateVTableBuilder(errHandler)`：返回 ETS 的 vtable builder（实现见 `.cpp` → `EtsVTableBuilder`）。
- `InitializeClass(classLinker, thread, klass)`：
  - 直接使用 `ClassInitializer<MT_MODE_TASK>::Initialize(...)`（对齐 runtime 的 class state machine）。
- `CreateClassLinkerExtension()`：
  - 返回 `std::make_unique<EtsClassLinkerExtension>()`（ETS 插件扩展点的落地类型）。

> 这段把 03 章“语言侧策略注入点”全部明确化：builder + extension + initializer 都由 LanguageContext 决定。

## 6. VM/GC/StackOverflow/Verification（L315–L352）

- `CreateVM(runtime, options)`：创建 ETS VM（见 `.cpp`）。
- `CreateGC(gcType, objectAllocator, settings)`：创建 ETS GC（见 `.cpp`，通过 `EtsLanguageConfig`）。
- `ThrowStackOverflowException(thread)`：创建并设置 SOE（见 `.cpp`）。
- `GetVerificationInitAPI()`：返回 verification 的 roots/数组元素/合成类需求（见 `.cpp`）。
- `GetVerificationTypeClass/Object/Throwable`：返回验证系统中用于定位核心类型的“类型名字符串”。
- `WrapClassInitializerException`：空实现（ETS 当前不包装 class init 异常）。
- `CreatePtLangExt`：返回 `PtEtsExtension`（调试/工具扩展）。
- `HasValueEqualitySemantic`：true（ETS 值语义相关行为开关）。


