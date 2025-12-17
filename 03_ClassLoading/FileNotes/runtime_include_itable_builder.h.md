# `runtime/include/itable_builder.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：`ITableBuilder` 抽象接口（itable 构建/解析/写回）；本文件只定义契约，具体算法在实现类中（动态发现）。

## 1. 依赖与定位（L18–L22）

- **L19**：`class_data_accessor-inl.h`：接口构建可能直接枚举 panda_file 的 interface/method 信息。
- **L20**：`class-inl.h`：构建/写回 itable 时需要 `Class` 的 inline 方法（例如访问接口列表、itable setter 等）。
- **L21**：panda smart pointers：实现可能用 `PandaUniquePtr`。

## 2. `ITableBuilder` 接口契约（L27–L46）

四个核心阶段 + 一个数据出口：
- **Build**（L31–L32）：输入 `ClassLinker*`、`base`、`classInterfaces`、`isInterface`，构建 itable（通常包含继承/合并接口列表、预分配表结构等）。
- **Resolve**（L34）：对已创建的 `klass` 做“解析”步骤（典型：把接口方法映射到实际实现 Method*；可能依赖已建好的 vtable）。
- **UpdateClass**（L36）：把构建/解析结果写回 `Class`（如设置 `klass->SetITable(...)`、修正 interfaces span、标记 flags）。
- **DumpITable**（L38）：调试输出。
- **GetITable**（L40）：导出构建出的 `ITable`（供 `VTableBuilder`/`IMTableBuilder`/ClassLinker 使用）。

约束：
- **L44–L45**：禁止 copy/move（Builder 作为一次性构建对象，持有 arena/中间状态）。

> 与 `class_linker.cpp` 对齐：  
> `SetupClassInfo` 中 `itableBuilder->Build(...)` → `vtableBuilder->Build(..., itable)` → `imtableBuilder->Build(..., itable)`，  
> `LinkMethods` 中 `itableBuilder->Resolve(klass)` → `itableBuilder->UpdateClass(klass)`。

## 3. `DummyITableBuilder`（L48–L69）

提供一个“空实现”用于不需要 itable 的语言/模式：
- Build/Resolve 恒 true
- Update/Dump 空
- `GetITable()` 返回空 `ITable()`

> 这也解释了：itable 在某些语言/运行模式下可以被禁用，但 ClassLinker 管线仍保持统一调用结构。

## 4. 动态发现点（下一步）

本头文件本身不包含实现类，因此需要在仓库里定位：
- 哪些 concrete 类 `: public ITableBuilder`
- `LanguageContext::CreateITableBuilder` 返回的具体实现

这些实现文件会被加入 `03_ClassLoading/Manifests/files.yaml` 并逐行落盘，形成 itable 构建的完整闭环。


