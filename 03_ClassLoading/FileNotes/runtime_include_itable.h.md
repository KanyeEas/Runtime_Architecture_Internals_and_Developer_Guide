# `runtime/include/itable.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：接口派发表（ITable）——“接口 -> 方法数组”的映射容器。  
> 使用位置：`Class::ResolveVirtualMethod` 的 itable 分支、vtable builder 的 default 方法遍历（`AddDefaultInterfaceMethods`）等。

## 1. 文件定位（ITable 在派发链路里的职责）

当 `Class::ResolveVirtualMethod` 解析“接口方法在当前类的实现”时：

- 首先尝试 **IMT**（`GetIMT()`，槽位命中则直接返回）。
- 若 IMT miss，则进入 **ITable**：
  - 在 `ITable` 中找到目标接口 `Entry`（按 `entry.GetInterface()` 匹配）
  - 再用 `method->GetVTableIndex()` 在 `entry.GetMethods()` 中索引到该接口方法对应的实现。

因此 ITable 的核心契约是：
- `Entry.interface_`：指向接口 `Class*`
- `Entry.methods_`：一个 `Span<Method*>`，长度至少覆盖接口的“虚方法槽位数”（即接口中 non-static 方法被赋予的 vtable_index）。

## 2. 头部与依赖（L1–L25）

- **L1–L14**：License。
- **L15–L16**：include guard：`PANDA_RUNTIME_ITABLE_H_`。
- **L18**：`span.h`：`Span<T>` 容器（`methods_` 与 `elements_` 都是 Span）。
- **L19**：`allocator.h`：`mem::InternalAllocatorPtr`（用于 Entry::Copy 分配 method 数组）。
- **L21**：`namespace ark {`。
- **L23–L24**：前向声明 `Class` 与 `Method`（Entry/ITable 都只持指针或 span）。

## 3. `ITable::Entry`（L26–L71）

### 3.1 Set/Get：interface 与 methods（L30–L48）
- **L30–L33**：`SetInterface(Class*)`：写入 `interface_`。
- **L35–L38**：`GetInterface()`：返回 `interface_`。
- **L40–L43**：`SetMethods(Span<Method*>)`：写入 `methods_`（不拷贝）。
- **L45–L48**：`GetMethods()`：返回 `methods_`（span 视图）。

### 3.2 深拷贝：`Entry Copy(InternalAllocatorPtr)`（L50–L61）
该函数定义了 **Entry 的深拷贝语义**：
- **L52–L53**：新建局部 `Entry entry`，复制 `interface_`。
- **L54–L59**：若 `methods_.data() != nullptr`：
  - **L55**：为 `methods_.size()` 分配 `Method*` 数组：`allocator->AllocArray<Method*>(n)`
  - 构造 span：`{ptr, size}`
  - **L56–L58**：逐项复制指针。
- **L60**：返回新 entry（拥有独立的 `methods_` 数组）。

> 注意：这意味着 ITable 的 elements_ 可能被复制（例如类复制/镜像/特殊 runtime 行为），且 methods span 的 ownership 由 allocator 提供的内存管理。

### 3.3 偏移暴露：`GetInterfaceOffset`（L63–L66）
- 用 `MEMBER_OFFSET(Entry, interface_)` 暴露字段偏移：
  - 用途：汇编快路径/反射/调试工具直接访问 layout。

### 3.4 Entry 字段（L68–L71）
- **L69**：`interface_`：接口类指针。
- **L70**：`methods_`：`Span<Method*>`，默认 `{nullptr, nullptr}`（空 span）。

## 4. `ITable`（L73–L126）

### 4.1 构造与基本访问（L73–L100）
- **L73**：默认构造：elements_ 为空。
- **L75**：`ITable(Span<Entry> elements)`：保存 span（不拷贝）。
- **L77–L85**：`Get()`：
  - 非 const：返回 `Span<Entry>`（可修改 entries）。
  - const：返回 `Span<const Entry>`（只读视图）。
- **L87–L90**：`Size()`：entries 数量。
- **L92–L100**：`operator[]`：按下标访问 entry（const/非 const）。

### 4.2 拷贝/移动语义（L102–L105）
- 默认析构。
- `DEFAULT_COPY_SEMANTIC/DEFAULT_MOVE_SEMANTIC`：
  - 这意味着 ITable 本身是“轻量 span 包装”，复制只复制 span 指针与 size；
  - 真正的深拷贝只发生在 `Entry::Copy` 被显式调用时。

### 4.3 layout 偏移暴露（L107–L118）
这组静态 constexpr 用于“从 ITable 对象地址，直接定位 entries 的 data/size”：

- **L107–L110**：`GetEntriesDataOffset()`：
  - `GetElementsOffset()`（itable.elements_ 字段偏移）
  - + `Span<Entry>::GetDataOffset()`（span 内 data 指针偏移）
- **L111–L114**：`GetEntriesSizeOffset()`：
  - `GetElementsOffset()` + `Span<Entry>::GetSizeOffset()`
- **L115–L118**：`GetEntrySize()`：`sizeof(Entry)`（便于遍历/序列化/调试）。

### 4.4 私有实现（L120–L126）
- **L121–L124**：`GetElementsOffset()`：`MEMBER_OFFSET(ITable, elements_)`。
- **L125**：`elements_`：`Span<Entry>`，承载所有 entries。

## 5. 与 `ResolveVirtualMethod` 的对齐点（关键契约复述）

`Class::ResolveVirtualMethod` 的 itable 路径（见 `class-inl.h`）对 ITable 的依赖如下：
- `for (size_t i = 0; i < itable.Size(); i++)`
- `auto &entry = itable[i]`
- `entry.GetInterface() == iface`
- `entry.GetMethods()[method->GetVTableIndex()]`

因此构建时必须保证：
- 对每个实现接口的类，`itable_` entries 覆盖所有接口；
- `entry.methods_` 的长度与索引规则与“接口方法的 vtable_index 分配规则”一致（由 vtable builder 的 `UpdateClass` 对接口方法写回 vtable_index 来保证）。


