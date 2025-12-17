# `runtime/include/class_helper.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：Class/Descriptor/Type 的辅助工具与 ABI 常量（尤其是 `OBJECT_POINTER_SIZE` / `POINTER_SIZE`）。  
> 与执行/内存的关系：这里的常量会直接影响 `Class::ComputeClassSize` 的布局计算；同时依赖 `runtime/object_header_config.h`（MemoryModelConfig，跨章但在此只解释其对指针大小选择的影响）。

## 1. 文件定位（为什么它属于 03）

类加载/链接阶段需要大量处理：
- 类名 ↔ descriptor 的互转（例如 `Ljava/lang/String;`）
- 数组 descriptor 的 rank/component 提取
- primitive type 的 descriptor 字符
- union descriptor 的解析（本文件声明了 union 相关 API）

此外，本文件用 `MemoryModelConfig` 导出 `OBJECT_POINTER_SIZE`，用于：
- `class-inl.h`：`GetTypeSize(REFERENCE)` 返回 `OBJECT_POINTER_SIZE`
- `ComputeClassSize`：vtable/imt/静态引用字段区域的对齐与大小计算

## 2. 头部与依赖（L1–L25）

- **L15–L16**：include guard：`PANDA_RUNTIME_KLASS_HELPER_H_`。
- **L18**：`<cstdint>`：基本整数类型。
- **L20**：`Span`：用于处理 descriptor 的轻量视图（例如 `IsArrayDescriptor`）。
- **L21**：`file_items.h`：`panda_file::Type` 与 `TypeId`。
- **L22**：`TaggedValue`：用于 tagged 类型大小（与 class object 布局计算一致性）。
- **L23**：`panda_string.h`：`PandaString`（用于构造/存储 descriptor 字符串）。
- **L24**：`object_header_config.h`：导出 `MemoryModelConfig`（决定对象引用大小）。

## 3. `ClassConfig` 与前向声明（L28–L40）

- **L28–L33**：模板 `ClassConfig<Config>`：
  - **L32**：`using ClassWordSize = typename Config::Size;`
  - 目的：把 `MemoryModelConfig::Size` 抽象成一个可复用的 “ClassWordSize”。
- **L35–L40**：前向声明 `Class/ClassLinker/...`：union 相关 API 需要这些类型。

## 4. `ClassHelper`：核心常量与 descriptor 工具（L41–L111）

### 4.1 `OBJECT_POINTER_SIZE` 与 `POINTER_SIZE`（L41–L48）
- **L41**：`ClassHelper : private ClassConfig<MemoryModelConfig>`：把 MemoryModelConfig 注入。
- **L43**：导出 `ClassWordSize`（对外可见）。
- **L45**：`OBJECT_POINTER_SIZE = sizeof(ClassWordSize)`：
  - 表示 **运行时对象引用** 的大小（可能与 `sizeof(void*)` 不同，典型原因是压缩指针/不同内存模型）。
- **L47**：`POINTER_SIZE = sizeof(uintptr_t)`：
  - 表示 **本机指针宽度**（C++ 指针大小）。
- **L46** 注释强调：对任意 `T`，`sizeof(T*)` 不一定等于 `OBJECT_POINTER_SIZE`。

> 这两者的区分是理解 `ComputeClassSize`/对象布局/引用字段大小的关键。

### 4.2 descriptor 生成/解析 API 声明（L49–L71）
本段大多是声明（实现应在 `.cpp` 或其他 inl 中）：
- `GetDescriptor(name, storage, strictPublicDescriptor)`
- `GetTypeDescriptor(name, storage)`
- `GetArrayDescriptor(componentName, rank, storage)`
- `GetPrimitiveTypeDescriptorChar/Str`
- `GetPrimitiveTypeStr`
- `GetPrimitiveDescriptor/GetPrimitiveArrayDescriptor`
- `GetName/GetNameUndecorated`（模板，后面 inline 实现）

### 4.3 数组 descriptor 判断与分解（L72–L94）
- **L72–L76**：`IsArrayDescriptor`：判断首字符是否 `'['`。
- **L78–L83**：`GetComponentDescriptor`：返回 `descriptor + 1`（跳过一个 `'['`）：
  - 注意：这里只剥一层；多维数组需配合 `GetDimensionality`。
- **L85–L94**：`GetDimensionality`：
  - 统计连续 `'['` 的数量（rank）。

### 4.4 union descriptor API（L96–L104）
声明了 union 相关的检查与 LUB（最小上界）求解入口：
- `IsUnionDescriptor/IsUnionOrArrayUnionDescriptor`
- `GetUnionComponent`
- `GetUnionLUBClass(descriptor, classLinker, ctx, ext, handler)`

> union 描述符的加载/组成类型解析已在 `runtime/class_linker.cpp` 的 `LoadUnionClass/LoadConstituentClasses` 等路径逐行确认（见 [FileNotes/runtime_class_linker.cpp](FileNotes/runtime_class_linker.cpp.md) 的 union 段落）。

## 5. `GetName`：descriptor → 人类可读名（L113–L167）

该模板支持 `std::string` 或 `PandaString`：

- **L118–L148**：对单字符 primitive/特殊类型做映射：
  - `V`→`void`，`Z`→`u1`，`B`→`i8`，`H`→`u8`，`S`→`i16`，`C`→`u16`，`I`→`i32`，`U`→`u32`，`J`→`i64`，`Q`→`u64`，`F`→`f32`，`D`→`f64`
  - `A`→`any`（动态/泛型相关语义）
  - `Y/N`：保留字面返回（需要结合语言插件定义其语义）
- **L154**：默认分支把 descriptor 当作 MUTF8 字符串：
  - 若以 `'['` 开头（数组 descriptor），直接返回原串（不去掉装饰）。
  - 否则：
    - 替换 `'/'` 为 `'.'`
    - 去掉前缀 `'L'` 与末尾 `';'`（断言长度 > 2）

## 6. `GetNameUndecorated`：数组用 `[]` 表示（L169–L189）

- **L176–L179**：先统计 rank（连续 `'['` 数）。
- **L181**：`AppendType(descriptor, rank, result)`：把 component 的基础类型写入 result。
- **L183–L186**：再追加 rank 个 `"[]"`。

## 7. `AppendType/AppendNonPrimitiveType`（L191–L255）

### 7.1 `AppendType`（L193–L242）
- 读 `descriptor[rank]`（跳过 `'['`）：
  - primitive 映射同 `GetName`
  - `'L'`：调用 `AppendNonPrimitiveType`

### 7.2 `AppendNonPrimitiveType`（L246–L255）
- 追加 `descriptor + rank + 1` 的字符串（跳过 `'L'`），再 `pop_back()` 去掉 `';'`。
- 替换 `'/'` 为 `'.'`。

## 8. 文件尾（L257–L259）
- 结束命名空间与 include guard。


