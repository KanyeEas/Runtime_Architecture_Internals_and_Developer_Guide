# `runtime/include/vtable_builder_interface.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：vtable 构建器对外接口契约 + copied default 方法的输出数据结构。

## 1. 文件定位（它在 vtable 构建链路里的位置）

本文件定义两件事：

1. `CopiedMethod`：用于把“接口 default 方法复制体”的输出携带回 ClassLinker（并带冲突/抽象状态）。
2. `VTableBuilder`：vtable/itable/imt 构建器的抽象接口，ClassLinker 可以用不同实现（不同语言/不同覆盖规则）来构建派发表结构。

## 2. 头部与依赖（L1–L25）

- **L1–L14**：License。
- **L15–L16**：include guard：`PANDA_RUNTIME_VTABLE_BUILDER_INTERFACE_H`。
- **L18**：依赖 `runtime/include/method.h`：
  - `CopiedMethod` 直接持有 `Method*`
  - `VTableBuilder::Build` 的第二个重载使用 `Span<Method>`
- **L20**：`namespace ark`。
- **L22–L24**：前向声明 `ClassLinker/ClassLinkerContext/ClassLinkerErrorHandler`（接口参数中会用到这些类型；完整定义在 class_linker 相关文件）。

## 3. `CopiedMethod`：默认方法复制体输出（L26–L54）

### 3.1 构造与持有（L26–L29）
- **L27**：默认构造：允许作为容器元素默认初始化。
- **L28**：显式构造：用 `Method* cpMethod` 初始化 `method_`。

### 3.2 `Status`（L30–L34）
三态用于描述 copied method 的语义结果：
- **ORDINARY**：普通 copied default 方法。
- **ABSTRACT**：default 方法在某些解析规则下等价于 abstract（例如冲突消解或语言规则导致不能作为可调用实现）。
- **CONFLICT**：多个接口默认实现冲突（常见：diamond default methods）。

> 这些状态由具体 vtable builder 策略在构建过程中置位（见 `VTableInfo::CopiedMethodEntry` 与 variance builder）。

### 3.3 访问器（L36–L49）
- `GetMethod()`：返回 `Method*`。
- `GetStatus()/SetStatus()`：读写 status。

### 3.4 私有字段（L51–L54）
- **method_**：指向运行时 `Method` 对象（不是 panda_file accessor）。
- **status_**：默认 `ORDINARY`。

## 4. `VTableBuilder`：构建器接口（L56–L77）

### 4.1 两个 Build 重载（L60–L64）
同一策略需要支持两类输入：
- **L60–L61**：`Build(panda_file::ClassDataAccessor*, Class* baseClass, ITable itable, ClassLinkerContext* ctx)`  
  - 用于“从 panda_file 元数据”构建（典型类加载路径）。
  - `ctx` 影响 proto 兼容性/可见性判定（多语言/多上下文）。
- **L63**：`Build(Span<Method> methods, Class* baseClass, ITable itable, bool isInterface)`  
  - 用于“已有 runtime Method 数组”的构建路径（例如合成类、某些语言的特殊构建流程）。
  - `isInterface` 让 builder 走 interface fast-path（只统计/设置索引等）。

> 两个重载都返回 bool，并用 `[[nodiscard]]` 强制调用方检查失败（避免静默忽略冲突）。

### 4.2 写回与统计接口（L65–L71）
- `UpdateClass(Class*)`：把构建结果写回到 `Class`（vtable/IMT/flags/vtable index 等）。
- `GetNumVirtualMethods()`：本类虚方法数量（接口：非 static 方法数）。
- `GetVTableSize()`：最终 vtable 大小（含新增/覆盖处理后的结果）。
- `GetCopiedMethods()`：输出 copied default methods 的列表（稳定顺序由 builder 定义）。

### 4.3 析构与不可拷贝（L73–L76）
- 虚析构：允许通过基类指针删除实现类。
- 禁止 copy/move：builder 作为状态ful 构建过程对象，不应复制。


