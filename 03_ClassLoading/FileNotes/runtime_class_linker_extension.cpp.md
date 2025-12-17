# `runtime/class_linker_extension.cpp`（逐行精读｜默认 Extension 行为：Boot/App Context + roots + 生命周期容器）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件规模：377 行（实现文件，逐段逐行记录）  
> 目标：补齐 `ClassLinkerExtension` 抽象在 **core runtime 侧的“默认实现行为”**：Boot/App context 的 LoadClass、roots 初始化 helper、context 注册、created/new/obsolete classes 容器语义，以及一个很关键的“异常包装”逻辑。

> 术语速查：见 `FileNotes/_Glossary.md`（同目录）

## 一图读懂：默认 Boot/AppContext 的 LoadClass 与 “created→prepared→newClasses”

```mermaid
flowchart TD
  subgraph LoadClass["默认 LoadClass 策略"]
    A["BootContext::LoadClass"] --> A1["委托 ClassLinker::GetClass(..., bootCtx)"]
    B["AppContext::LoadClass"] --> B1["先探测：extension->GetClass(descriptor, ctx=nullptr)\n(SuppressErrorHandler)"]
    B1 -->|命中| R1["返回 Class*"]
    B1 -->|未命中| B2["遍历本 context 的 pfs_:\nclassId=pf->GetClassId(descriptor)\nLoadClass(*pf,classId,this)"]
    B2 -->|找到| R2["返回 Class*"]
    B2 -->|找不到| R3["OnError(CLASS_NOT_FOUND) / nullptr"]
  end

  subgraph Lifecycle["类对象生命周期容器"]
    C["CreateClass(语言实现)\nAddCreatedClass"] --> D["AddClass: InsertClass 并发去重"]
    D -->|成功| E["OnClassPrepared:\n(recordNewClass_? push newClasses_)\nRemoveCreatedClass"]
    D -->|失败(另线程已插入)| F["FreeClass(语言) + FreeClassData(通用)"]
  end
```

## 0. include 与定位（L16–L24）

- `class_linker_extension.h`：抽象接口与数据成员定义（roots/contexts/new roots 等）。
- `class_linker-inl.h`、`class_linker.h`：具体委托到 `ClassLinker` 的 GetClass/LoadClass/FreeClassData 等。
- `coretypes/class.h`：`FromClassObject` 的实现需要 `coretypes::Class` 的 `GetRuntimeClass()`。

## 1. Extension 析构：释放注册的 contexts（L27–L33）

- **L29–L32**：在 `contextsLock_` 下遍历 `contexts_`，用 `classLinker_->GetAllocator()->Delete(ctx)` 释放。
  - 这说明 `contexts_` 里的 context 对象**由 ClassLinker 的 allocator 分配**，并由 Extension 负责析构回收。

## 2. BootContext：LoadClass/EnumeratePandaFiles 的“委托式实现”（L35–L47）

### 2.1 `BootContext::LoadClass`（L35–L41）
- 断言 extension 已初始化（roots/panda files 结构可用）。
- 直接委托 `classLinker->GetClass(descriptor, needCopyDescriptor, this, errorHandler)`。
  - 关键点：BootContext 的 `LoadClass` 本质上就是“带 boot context 参数调用 ClassLinker::GetClass”。

### 2.2 `BootContext::EnumeratePandaFiles`（L43–L47）
- 直接委托 `ClassLinker::EnumerateBootPandaFiles(cb)`。
  - 与 `ClassLinker` 内部的 `bootPandaFiles_` 对齐（见 `FileNotes/runtime_class_linker.cpp.md` 的 AddPandaFile 段）。

## 3. AppContext：默认应用域的 LoadClass 策略（L49–L78）

### 3.1 `SuppressErrorHandler`（L49–L51）
- 覆盖 `OnError` 为空实现，用于“探测式 GetClass（不要污染 error state）”。

### 3.2 `AppContext::LoadClass`（L53–L78）

**算法分两步：**
- **Step A（L58–L62）**：先用 Suppress handler 调 `extension_->GetClass(..., nullptr, &handler)`：
  - 这里 `context=nullptr` 会在 `ResolveContext` 里被解析（通常回到 boot context 或 extension 默认上下文），用于快速命中“已加载/可见”的类。
  - 命中则直接返回。
- **Step B（L64–L70）**：遍历 `pfs_`（AppContext 持有的 panda files 指针列表）：
  - `pf->GetClassId(descriptor)` → 过滤 invalid/external → `classLinker->LoadClass(*pf, classId, this, errorHandler)`。
  - 注意：这里走的是 **ClassLinker::LoadClass（直接按 pf+id 加载）**，与 `GetClass(descriptor)` 的 boot filter 分支不同。
- **Step C（L72–L77）**：都找不到时上报 `CLASS_NOT_FOUND`（message 包含 descriptor）。

> 结论：AppContext 默认实现就是“先看全局/boot 可见缓存，再在本 context 的 panda files 里按 classId 加载”。

## 4. roots 初始化 helper：primitive/array/synthetic（L80–L124）

这三个 helper 是 extension 实现里非常高频的自举工具，抽象了 **CreateClass + language-specific InitializeXxxClass + AddClass + SetClassRoot** 的套路。

### 4.1 `InitializeArrayClassRoot`（L80–L96）
- `CreateClass(descriptor, vtableSize, imtSize, size)`（语言实现提供）
- `arrayClass->SetLoadContext(&bootContext_)`
- 取 `componentClass = GetClassRoot(componentRoot)` 并调用 `InitializeArrayClass(arrayClass, componentClass)`（语言实现）
- `AddClass(arrayClass)`：插入到 context（含并发去重与 OnClassPrepared 钩子，见下）
- `SetClassRoot(root, arrayClass)`

### 4.2 `InitializePrimitiveClassRoot`（L98–L111）
- 同样的套路，但额外设置：
  - `primitiveClass->SetType(Type(typeId))`
  - `InitializePrimitiveClass(primitiveClass)`（语言实现）

### 4.3 `InitializeSyntheticClassRoot`（L113–L124）
- synthetic class：`CreateClass(descriptor, 0, 0, size)`
- `synClass->SetType(REFERENCE)` + `InitializeSyntheticClass(synClass)`（语言实现）

## 5. `Initialize` vs `InitializeRoots`：两阶段初始化语义（L126–L169）

### 5.1 `ClassLinkerExtension::Initialize`（L126–L151）
- 记录 `classLinker_` 并调用 `InitializeImpl(compressedStringEnabled)`（语言实现：创建 roots、启用压缩字符串等）。
- 设置 `canInitializeClasses_ = true`，然后从 boot context 枚举出“未 LOADED 的类”复制到 `klasses`。
  - **原因（L132–L134）**：`InitializeClass` 期间可能会加载更多类、修改 boot context；先复制避免迭代器失效/并发修改。
- 对每个未 LOADED 的类调用 `InitializeClass(klass)` 并将其 state 置为 `LOADED`。

### 5.2 `ClassLinkerExtension::InitializeRoots`（L153–L168）
- 遍历 `classRoots_`，对每个 root 调 `classLinker_->InitializeClass(thread, klass)`。
  - 这一步是把 roots 变成“可用的已初始化 Class”，通常发生在 runtime 完成 VM/heap 建立后。

## 6. GetClass / FindLoadedClass：把 context/errorHandler 解析成“真实对象”（L171–L184 + L211–L226）

- `FindLoadedClass`（L171–L174）：委托 `ClassLinker::FindLoadedClass(descriptor, ResolveContext(context))`。
- `GetClass(descriptor)`（L176–L184）：委托 `ClassLinker::GetClass(descriptor, ..., ResolveContext, ResolveErrorHandler)`。
- `GetClass(pf,id)`（L211–L226）：委托 `ClassLinker::GetClass(pf,id, ...)`，并在失败时触发异常包装（见下一节）。

## 7. 关键点：WrapClassNotFoundExceptionIfNeeded（L186–L209）

这是本文件中最容易被 Stage1/Stage2 忽略但非常重要的语义：
- 仅当当前线程 `HasPendingException()` 才工作。
- 取 `classNotFoundExceptionClass = extension(ctx)->GetClass(ClassNotFoundExceptionDescriptor)`：
  - 若取不到，认为是 OOM 路径（保持原异常）。
- 若当前 pending exception 的类型是 ClassNotFoundException：
  - 取 `name = ClassHelper::GetName(descriptor)`
  - 抛 `NoClassDefFoundError`（`ctx.GetNoClassDefFoundErrorDescriptor()`）并带上类名。

> 结论：**当“按 pf+id 取 class 失败”触发 CNFE 时，extension 会把它升级/转换为 NCDFE**（更贴近链接阶段语义）。

## 8. `AddClass`：context 插入 + 并发去重 + OnClassPrepared（L228–L242）

- 通过 `klass->GetLoadContext()` 取 context，并 `ResolveContext(context)->InsertClass(klass)`：
  - 若返回非空（另线程已插入同名类），释放当前新类：`classLinker_->FreeClass(klass)` 并返回已有类。
- 插入成功则调用 `OnClassPrepared(klass)`（见下：new class recording）。

## 9. Loaded classes 遍历与释放（L244–L289）

- `NumLoadedClasses/VisitLoadedClasses`：boot + 所有 contexts 累加/遍历。
- `FreeLoadedClasses`：
  - 对 boot context 与每个 app context 枚举所有类：
    - 先 `FreeClass(klass)`（语言实现：例如 ETS 会从 created map 移除）
    - 再 `classLinker_->FreeClassData(klass)`（语言无关释放：fields/methods/itable/interfaces 等）

## 10. 创建 AppContext：从路径打开 panda files 并注册到 ClassLinker（L291–L320）

- `CreateApplicationClassLinkerContext(paths)`：
  - `OpenPandaFileOrZip` 打开每个 path，累积 `PandaFilePtr`。
  - 调用重载 `CreateApplicationClassLinkerContext(std::move(appFiles))`。
- `CreateApplicationClassLinkerContext(appFiles)`：
  - 提取 `const panda_file::File*` 列表给 `AppContext` 构造（只存指针）
  - 用 `allocator->New<AppContext>(this, std::move(appFilePtrs))` 分配 context
  - `RegisterContext(...)` 把它挂到 `contexts_`
  - 遍历 `appFiles`，逐个 `classLinker_->AddPandaFile(std::move(pf), ctx)` 注册到 ClassLinker（可触发 AOT snapshot/通知/boot filter 等）

## 11. created/new/obsolete classes：三类容器语义（L322–L375）

- `AddCreatedClass/RemoveCreatedClass`：`createdClasses_` 受 `createdClassesLock_` 保护，用于跟踪“刚创建还未 prepared 的类”。
- `OnClassPrepared`（L337–L347）：
  - 若 `recordNewClass_` 为真（seq_cst），把 klass push 到 `newClasses_`。
  - 然后从 `createdClasses_` 移除（prepared 后不再属于 created）。
  - **seq_cst 注释（L339–L340）**：强调 record_new_class_ 的一致可见性需求。
- `AddObsoleteClass/FreeObsoleteData`：支持 hot reload/obsolete class 数据回收（本章仅需知道它们存在）。

## 12. managed class object 映射（L349–L357）

- `FromClassObject(ObjectHeader*)`：把 managed `coretypes::Class*` 转为 runtime `Class*`。
- `GetClassObjectSizeFromClassSize(size)`：`coretypes::Class::GetSize(size)`（managed class object size 与 runtime class size 的换算）。

## 证据链与关联阅读

- 抽象与数据成员：`FileNotes/runtime_include_class_linker_extension.h.md`
- `ClassLinker` 主管线/FreeClassData：`FileNotes/runtime_class_linker.cpp.md`
- core 语言实现（roots 与 CreateClass）：`runtime/core/core_class_linker_extension.cpp`（将补齐逐行）
- ETS 语言实现：`FileNotes/plugins_ets_runtime_ets_class_linker_extension.cpp.md`


