# `plugins/ets/runtime/ets_class_linker.cpp`（逐行精读｜ETS façade 实现 + async 注解解析）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件规模：94 行  
> 目标：说明 ETS façade 如何把 runtime `ClassLinker`/`ClassLinkerExtension` 的 API 转换为 `EtsClass` 语义，并补充 async 注解到 impl method 的解析链路与异常语义。

## 0. include 与依赖（L16–L24）

- `ets_annotation.h`：查找 async 注解。
- `ets_class_linker.h`：本文件对应头。
- `ets_class_linker_extension.h`：把 core `ClassLinkerExtension*` 转为 ETS 侧类型。
- `ets_coroutine.h` / `ets_exceptions.h` / `ets_panda_file_items.h`：抛 ETS 异常所需。
- `types/ets_class.h`：把 runtime `Class*` 映射回 `EtsClass*`。

## 1. 构造与工厂（L27–L34）

- **L27**：构造仅保存 `classLinker_` 指针（不 owned）。
- **L29–L34**：`Create(classLinker)`：
  - `MakePandaUnique<EtsClassLinker>(classLinker)`，并包装进 `Expected` 返回。

## 2. Initialize：缓存 ETS extension（L36–L41）

- `classLinker_->GetExtension(SourceLang::ETS)` 拿到 core extension 指针。
- `ext_ = EtsClassLinkerExtension::FromCoreType(ext)`：类型安全的 downcast/adapter。

> 这一步让后续 `GetClass`/`GetClassRoot` 都可以通过 `ext_` 完成“runtime Class* ↔ ETS EtsClass*”转换。

## 3. InitializeClass：对外转发（L43–L47）

- 输入是 `EtsClass*`，内部取 `klass->GetRuntimeClass()` 再调用 `classLinker_->InitializeClass(coroutine, runtimeClass)`。

## 4. GetClassRoot / GetClass：把 runtime Class 转为 EtsClass（L49–L67）

- **GetClassRoot**（L49–L52）：
  - `ext_->GetClassRoot(static_cast<ark::ClassRoot>(root))` → runtime `Class*`
  - `EtsClass::FromRuntimeClass(cls)` → `EtsClass*`
- **GetClass(name)**（L54–L60）：
  - `utf::CStringAsMutf8(name)` → descriptor
  - `ext_->GetClass(descriptor, needCopyDescriptor, context, errorHandler)` → runtime `Class*`
  - 非空则转 `EtsClass*` 返回
- **GetClass(pf,id)**（L62–L67）同理。

## 5. GetMethod：直接走 runtime（L69–L73）

- 不做 ETS 包装，直接返回 `Method*`：`classLinker_->GetMethod(pf, id, ctx, errorHandler)`。

## 6. ETS-specific：GetAsyncImplMethod（L75–L92）

### 6.1 注解解析（L78–L83）
- `asyncAnnId = EtsAnnotation::FindAsyncAnnotation(method)`，并断言有效。
- 用 `AnnotationDataAccessor` 读取第 0 个 element 的 scalar value，取出 `implMethodId`（EntityId）。
- `ctx = method->GetClass()->GetLoadContext()`：impl method 按 “当前方法所属类的加载域” 解析。

### 6.2 解析 impl method（L84–L90）
- `result = GetMethod(pf, implMethodId, ctx)`。
- 若为空：
  - 用 `MethodDataAccessor` 拿 `GetFullName()` 拼 message
  - 抛 ETS 异常：`LINKER_UNRESOLVED_METHOD_ERROR`

> 结论：async 注解的语义是“声明式地指向另一个 impl method”，解析失败属于链接错误，并且按 ETS 的异常类型上抛。

## 证据链

- ETS extension 入口点/错误映射：[FileNotes/plugins_ets_runtime_ets_class_linker_extension.cpp](plugins_ets_runtime_ets_class_linker_extension.cpp.md)
- ClassLinker GetMethod：[FileNotes/runtime_class_linker.cpp](runtime_class_linker.cpp.md)
- async 注解数据结构：`plugins/ets/runtime/ets_annotation.h`（若后续需要可纳入 03 动态发现）


