# `runtime/include/field.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：运行时 `Field` 元数据对象（字段名/类型/访问标志/对象布局 offset/所属类指针编码）。  
> 文件特点：实现非常短，但它定义了“字段类型如何编码”“字段 offset 由谁写入”“如何从 Field 反查 type class”的关键契约。

## 1. 文件定位（Field 在 ClassLoading 链路里的作用）

`Class` 聚合 `Field* fields_` 并把字段按静态/实例分区。`Field` 需要提供：
- **身份**：`fileId_`（panda_file::EntityId）
- **访问控制/修饰符**：`accessFlags_`（含 public/private/static/volatile/final/readonly…）
- **字段类型**：通过 `accessFlags_` 的一个位段编码 `TypeId`（而不是单独字段）
- **布局 offset**：`offset_`，用于对象字段访问/静态字段区访问
- **所属类**：`classWord_`（用 `ClassHelper::ClassWordSize` 存储，适配压缩指针模型）

> 交叉引用：  
> - 字段访问实际读写（含屏障/原子）：在 `Class::GetFieldObject/SetFieldObject`（`class-inl.h`）里通过 `ObjectAccessor` 实现（跨章 Memory）。  
> - 字段 offset 的来源：在 `runtime/class_linker.cpp` 的 `LayoutFields/LinkFields` 阶段写入（见 [FileNotes/runtime_class_linker.cpp](FileNotes/runtime_class_linker.cpp.md) 的字段布局段落）。  

## 2. 头部与依赖（L1–L35）

- **L15–L16**：include guard：`PANDA_RUNTIME_FIELD_H_`。
- **L18–L20**：`<cstdint>/<atomic>`：本文件自身字段没有原子，但依赖链中可能需要（以及与 compiler_interface 等交叉）。
- **L21**：`intrinsics_enum.h`：可能用于编译/优化相关的字段处理（本文件未直接使用符号）。
- **L22–L24**：`libarkfile/*`：`File/EntityId/modifiers`（ACC_*、EntityId）。
- **L25**：`compiler_interface.h`：编译器交互（本文件未展开，但属于运行时元数据通用依赖）。
- **L26**：`class_helper.h`：`ClassWordSize` 与 `ToObjPtrType` 的指针模型适配。
- **L27**：`value-inl.h`：值类型工具（本文件未直接使用，但常见于元数据头的通用依赖）。
- **L28**：`macros.h`：`PANDA_PUBLIC_API/MEMBER_OFFSET/NO_COPY_SEMANTIC` 等。
- **L30**：`namespace ark {`。
- **L32–L35**：前向声明 `Class` 与 `ClassLinkerErrorHandler`（ResolveTypeClass 需要）。

## 3. `Field` 类（L36–L166）

### 3.1 构造函数：把 Type 编码进 accessFlags（L40–L44）

```cpp
Field(Class *klass, EntityId fileId, uint32_t accessFlags, panda_file::Type type)
```

- **L41**：`classWord_` 存所属类指针（通过 `ToObjPtrType(klass)` 再 cast 到 `ClassWordSize`）。
- **L41–L42**：保存 `fileId_`。
- **L43**：关键：`accessFlags_ = accessFlags | (type.GetEncoding() << ACC_TYPE_SHIFT)`：
  - `type.GetEncoding()` 产生一个 `TypeId` 的编码值；
  - 通过 `ACC_TYPE_SHIFT` 左移塞入 `accessFlags_` 的“类型位段”；
  - 这解释了为什么 `Field` 没有单独的 `type_` 字段：类型与修饰符共用一个 word。

### 3.2 所属类：Get/Set + offset 暴露（L46–L59）
- **L46–L49**：`GetClass()`：把 `classWord_` reinterpret 成 `Class*`。
- **L51–L54**：`SetClass(Class*)`：按同样方式写入 `classWord_`。
- **L56–L59**：`GetClassOffset()`：暴露 `classWord_` 字段偏移（供快路径/反射）。

### 3.3 panda_file 身份：GetPandaFile / GetFileId（L61–L66）
- **L61**：`GetPandaFile()`：导出 API（实现不在此文件），通常会通过 `GetClass()->GetPandaFile()` 或 ClassLinker 查找。
- **L63–L66**：`GetFileId()`：返回 `fileId_`。

### 3.4 accessFlags 与 offset（L68–L86）
- **L68–L71**：`GetAccessFlags()`：返回 `accessFlags_`（注意：类型位段也包含在其中）。
- **L73–L76**：`GetOffset()`：返回 `offset_`。
- **L78–L81**：`SetOffset(offset)`：写 `offset_`（谁调用？通常是 class linker 在布局计算后写入）。
- **L83–L86**：`GetOffsetOffset()`：暴露 `offset_` 字段偏移。

### 3.5 字段类型解析：ResolveTypeClass / GetTypeId（L88–L99）
- **L88**：`ResolveTypeClass(errorHandler)`：导出 API（实现不在此文件）：
  - 语义：把字段类型（primitive/reference/array/union 等）解析成 `Class*`。
  - 失败时通过 `ClassLinkerErrorHandler` 上报。
- **L90–L93**：`GetType()`：`panda_file::Type(GetTypeId())`。
- **L95–L98**：`GetTypeId()`：从 `accessFlags_` 的类型位段解码：
  - `(accessFlags_ & ACC_TYPE) >> ACC_TYPE_SHIFT`

### 3.6 name 与访问谓词（L100–L140）
- **L100–L103**：`GetAccessFlagsOffset()`：暴露 `accessFlags_` 字段偏移。
- **L105**：`GetName()`：导出 API（实现不在此文件），通常从 panda_file 的 field item 中取字符串。
- **L107–L140**：一组谓词：
  - `IsPublic/IsPrivate/IsProtected/IsStatic/IsVolatile/IsFinal/IsReadonly`
  - 均为 `accessFlags_ & ACC_*` 判定（注意：类型位段共存但不影响这些位）。

### 3.7 唯一 id：`UniqId`（L142–L154）
- **L142–L149**：`CalcUniqId(file, fileId)`：
  - `file->GetFilenameHash()` 左移 32 bit，再 OR `fileId offset`。
- **L151–L154**：`GetUniqId()`：用 `GetPandaFile()` 与 `fileId_` 计算。

### 3.8 生命周期与不可拷贝（L156–L160）
- 默认析构。
- `NO_COPY_SEMANTIC/NO_MOVE_SEMANTIC`：Field 作为元数据对象不允许拷贝/移动（保持地址稳定，供各种缓存/索引引用）。

### 3.9 私有字段布局（L161–L166）
- **classWord_**：所属类指针的 word 表示（与指针模型相关）。
- **fileId_**：panda_file 中的字段实体 id。
- **accessFlags_**：修饰符 + type 位段。
- **offset_**：布局 offset（默认 0，初始化后必须由 linker 写入正确值）。



