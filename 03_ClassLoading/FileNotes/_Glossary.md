# 03_ClassLoading / FileNotes 术语速查（Glossary）

> 用法建议：读任何逐行 FileNote 前，先在这里把不熟的名词扫一遍（建议从 [FileNotes/Index](Index.md) 进入）。  
> 本章原则：尽量在 03 章内闭环解释；涉及其他章节（如 GC/解释器）只给出“是什么/为什么要它”，不强制跳转。

## 核心对象与标识

- **descriptor（类描述符）**：类名的规范编码（多为 MUTF8 字符串）。用于 `descriptor -> Class*` 查找与缓存。  
  - 证据链：[FileNotes/runtime_class_linker.cpp](runtime_class_linker.cpp.md)（GetClass/LoadClass）；[FileNotes/runtime_class_linker_context.h](runtime_class_linker_context.h.md)（loadedClasses_ key）。

- **PandaFile / `.abc`**：Ark/Panda 的字节码文件容器；运行时通过 `panda_file::File`/`OpenPandaFile(OrZip)` 打开并注册到 `ClassLinker`。  
  - 证据链：[FileNotes/runtime_file_manager.cpp](runtime_file_manager.cpp.md)、[FileNotes/runtime_class_linker.cpp](runtime_class_linker.cpp.md)（AddPandaFile）。

- **EntityId（panda_file::File::EntityId）**：PandaFile 内部实体（类/方法/字段/注解等）的索引标识。  
  - 典型用途：`GetClass(pf,id)`、`GetMethod(pf,id)`、`GetField(pf,id)`。

- **ClassDataAccessor / MethodDataAccessor / FieldDataAccessor**：读取 PandaFile 元数据的访问器（不会直接创建 runtime 对象）。  
  - 证据链：[FileNotes/runtime_class_linker.cpp](runtime_class_linker.cpp.md)（LoadClass/LoadMethod/LoadFields）。

## ClassLinker / Extension / Context（谁负责什么）

- **ClassLinker**：语言无关的“加载/链接”主管线（GetClass/LoadClass/BuildClass；派发表 builder、字段布局、缓存/并发、boot filter）。  
  - 证据链：[FileNotes/runtime_include_class_linker.h](runtime_include_class_linker.h.md) + [FileNotes/runtime_class_linker.cpp](runtime_class_linker.cpp.md)。

- **ClassLinkerExtension**：语言扩展点（roots、自定义 CreateClass/FreeClass、native entrypoint、context 管理、错误映射等）。  
  - 抽象与容器：[FileNotes/runtime_include_class_linker_extension.h](runtime_include_class_linker_extension.h.md)  
  - 默认实现（Boot/AppContext LoadClass、new/created/obsolete classes、CNFE→NCDFE 包装）：[FileNotes/runtime_class_linker_extension.cpp](runtime_class_linker_extension.cpp.md)

- **(Boot)Context / AppContext / chained context**：
  - **BootContext**：boot 类加载域；枚举 boot panda files；通常配合 boot bloom filter。  
  - **AppContext**：应用加载域；默认实现会在本域 panda files 中按 classId 加载。  
  - **Chained context**：存在 parent/共享库链的加载域（ETS 强相关）。
  - 证据链：[FileNotes/runtime_class_linker_extension.cpp](runtime_class_linker_extension.cpp.md)（Boot/AppContext 默认）；[FileNotes/runtime_class_linker_context.h](runtime_class_linker_context.h.md)（基类契约）；[FileNotes/plugins_ets_runtime_ets_class_linker_context.cpp](plugins_ets_runtime_ets_class_linker_context.cpp.md)（ETS 链式）。

## roots（根类自举）

- **class roots**：运行时必须最早可用的一组“基础类”（Object/Class/String/Array/primitive 等），由各语言 extension 在初始化阶段创建/注册。  
  - core（PANDA_ASSEMBLY）实现：[FileNotes/runtime_core_core_class_linker_extension.cpp](runtime_core_core_class_linker_extension.cpp.md)  
  - ETS 实现：[FileNotes/plugins_ets_runtime_ets_class_linker_extension.cpp](plugins_ets_runtime_ets_class_linker_extension.cpp.md)

- **NonMovable allocation**：roots/class object 常需要不可移动分配，避免早期阶段对象移动带来额外复杂性。  
  - 证据链：[FileNotes/runtime_core_core_class_linker_extension.cpp](runtime_core_core_class_linker_extension.cpp.md)（CreateClass 使用 AllocateNonMovableObject）。

## 派发表（Dispatch Tables）

- **vtable（虚方法表）**：类虚方法派发表；需要处理 override、final、default interface method（copied methods）等。  
  - 证据链：`FileNotes/runtime_include_vtable_builder_*`（builder 契约/策略）。

- **copied methods（默认接口方法复制体）**：为 default interface method 生成的 `Method` 复制体，挂在 methods 尾部；冲突会用 stub 表达。  
  - 证据链：[FileNotes/runtime_include_vtable_builder_interface.h](runtime_include_vtable_builder_interface.h.md)、[FileNotes/runtime_class_linker.cpp](runtime_class_linker.cpp.md)（SetupCopiedMethods/LoadMethods）。

- **ITable（接口表）**：按 “interface Class* → Method* 映射数组” 存储接口派发信息。  
  - 证据链：[FileNotes/runtime_include_itable.h](runtime_include_itable.h.md)、[FileNotes/plugins_ets_runtime_ets_itable_builder.cpp](plugins_ets_runtime_ets_itable_builder.cpp.md)。

- **IMT（Interface Method Table）**：接口方法快速表（可选加速）；冲突即清空槽，必要时整体禁用（imtSize=0）。  
  - 证据链：[FileNotes/runtime_imtable_builder.cpp](runtime_imtable_builder.cpp.md)。

## 错误与异常（常见缩写）

- **CNFE（ClassNotFoundException）**：类未找到（更偏“查找/加载”）。  
- **NCDFE（NoClassDefFoundError）**：类定义不可用（更偏“链接/解析依赖失败”）。  
  - 本章关键行为：按 `pf,id` 取类失败触发 CNFE 时，Extension 会在必要时包装为 NCDFE。  
  - 证据链：[FileNotes/runtime_class_linker_extension.cpp](runtime_class_linker_extension.cpp.md)（WrapClassNotFoundExceptionIfNeeded）。

## 其它常见名词

- **AOT / `.an`**：提前编译产物；运行时通过 `AotManager` 注册并参与 method entrypoint/linking。  
  - 证据链：[FileNotes/runtime_file_manager.cpp](runtime_file_manager.cpp.md)、[FileNotes/runtime_class_linker.cpp](runtime_class_linker.cpp.md)（AotManager 接入点）。

- **CHA（Class Hierarchy Analysis）**：类层次分析，用于编译/优化；在 runtime 初始化阶段可能触发校验（VerifyClassHierarchy）。  
  - 说明：调用点主要在 `runtime/runtime.cpp`，属于“启动/初始化边界”，本章只解释其与 ClassLinker/AotManager 的接口含义。


