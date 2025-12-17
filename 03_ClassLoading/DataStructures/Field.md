# Field（运行时字段元数据对象）

## 0) 在端到端主线图中的位置

- 总入口：`../Flows/ClassLoading_EndToEnd.md`（“LoadFields/LinkFields：LayoutFields 写回 offset”框）

## 它是什么

`Field` 是运行时对“一个字段”的元数据对象。它刻意保持极简：**type 编码进 accessFlags 位段 + offset 单独存储**，以便 class linker 在布局阶段写回 offset。

## 关键字段/不变量

- `accessFlags_`：包含 ACC_PUBLIC/STATIC/VOLATILE/FINAL/READONLY 等，同时还包含 `TypeId` 位段（`ACC_TYPE_SHIFT`）
- `offset_`：字段偏移（static 与 instance 都用同一字段表达，解释由 `klass->GetStaticFieldsOffset` 与 object base 决定）
- `classWord_`：所属 `Class*` 的 word 表示（适配压缩指针模型）
- `fileId_`：panda_file::EntityId（定位字段定义）

## 谁写它、谁读它（对齐点）

- **写入 type/flags**：`runtime/class_linker.cpp::LoadFields`（InitializeMemory(field, ..., TypeFromEncoding)）
- **写入 offset**：`runtime/class_linker.cpp::LayoutFields`（唯一写入点）
- **读取 offset 做访问**：
  - 实际读写由 `Class::GetFieldObject/SetFieldObject` 通过 `ObjectAccessor` 完成（见 `FileNotes/runtime_include_class-inl.h.md`）

## 证据链

- `FileNotes/runtime_include_field.h.md`
- `FileNotes/runtime_class_linker.cpp.md`（LayoutFields 段）

## 下一步（新人推荐）

- 想看“字段布局算法与对齐/基类 padding 回填” → `../Flows/LayoutFields_and_LinkFields.md`
- 想看“Class 的 refFields*/objectSize 等元数据如何被写回” → `Class.md`

