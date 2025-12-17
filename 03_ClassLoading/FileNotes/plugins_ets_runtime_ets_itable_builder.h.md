# `plugins/ets/runtime/ets_itable_builder.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：ETS 的 `ITableBuilder` 实现声明：`EtsITableBuilder`。  
> 说明：真正的构建/解析逻辑在 `ets_itable_builder.cpp`，本头文件定义状态与接口。

## 1. 类结构（L32–L52）

`EtsITableBuilder : public ITableBuilder`，核心点：
- 构造注入 `ClassLinkerErrorHandler*`（L34）：
  - ETS 的 itable resolve 在发现冲突/缺失实现时会走 errorHandler（通常最终抛 ETS 异常）。
- override 四个关键方法：
  - `Build(classLinker, base, classInterfaces, isInterface)`
  - `Resolve(klass)`
  - `UpdateClass(klass)`
  - `DumpITable(klass)`
- `GetITable()` 返回内部缓存的 `itable_`（L44–L47）。

## 2. 内部状态（L49–L51）

- `ITable itable_`：构建出来的 itable（表元素为 `ITable::Entry`）。
- `ClassLinkerErrorHandler *errorHandler_`：冲突/错误上报通道。

> 对齐 `class_linker.cpp`：`SetupClassInfo` 会把 builder 存在 `ClassInfo`，随后 `LinkMethods` 调用 `Resolve/UpdateClass` 写回 `Class`。


