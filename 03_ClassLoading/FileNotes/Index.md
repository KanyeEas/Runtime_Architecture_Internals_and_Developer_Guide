# 03 ClassLoading / FileNotes / Index

本目录是 **源码证据链卡片**：每个文件一页，解释“这个文件负责什么、关键入口函数、常见坑、以及与 Flows/DataStructures 的对应关系”。

## 快速入口

- 术语表：[_Glossary](./_Glossary.md)
- ClassLinker 主逻辑：[runtime_class_linker.cpp](./runtime_class_linker.cpp.md)
- ClassLock / ClassMutexHandler：[runtime_class_lock.h](./runtime_class_lock.h.md) / [runtime_class_lock.cpp](./runtime_class_lock.cpp.md)
- FileManager（.abc/.an）：[runtime_file_manager.cpp](./runtime_file_manager.cpp.md)

## 文件列表（手工维护索引，完整列表可看 All Pages）

- [runtime_class_linker.cpp](./runtime_class_linker.cpp.md)
- [runtime_class_linker_context.h](./runtime_class_linker_context.h.md)
- [runtime_class_linker_extension.cpp](./runtime_class_linker_extension.cpp.md)
- [runtime_class_lock.h](./runtime_class_lock.h.md)
- [runtime_class_lock.cpp](./runtime_class_lock.cpp.md)
- [runtime_file_manager.cpp](./runtime_file_manager.cpp.md)
- [runtime_imtable_builder.cpp](./runtime_imtable_builder.cpp.md)
- [runtime_include_class.h](./runtime_include_class.h.md)
- [runtime_include_class-inl.h](./runtime_include_class-inl.h.md)
- [runtime_include_vtable_builder_base.h](./runtime_include_vtable_builder_base.h.md)
- [runtime_include_vtable_builder_base-inl.h](./runtime_include_vtable_builder_base-inl.h.md)
- [runtime_include_vtable_builder_interface.h](./runtime_include_vtable_builder_interface.h.md)
- [runtime_include_vtable_builder_variance.h](./runtime_include_vtable_builder_variance.h.md)
- [runtime_include_vtable_builder_variance-inl.h](./runtime_include_vtable_builder_variance-inl.h.md)
- [runtime_include_itable.h](./runtime_include_itable.h.md)
- [runtime_include_itable_builder.h](./runtime_include_itable_builder.h.md)
- [runtime_include_imtable_builder.h](./runtime_include_imtable_builder.h.md)
- [runtime_include_method.h](./runtime_include_method.h.md)
- [runtime_include_field.h](./runtime_include_field.h.md)
- [runtime_include_file_manager.h](./runtime_include_file_manager.h.md)
- [runtime_include_class_linker.h](./runtime_include_class_linker.h.md)
- [runtime_include_class_linker_extension.h](./runtime_include_class_linker_extension.h.md)
- [runtime_include_class_helper.h](./runtime_include_class_helper.h.md)
- ETS 插件相关：见 [All_Pages](../../All_Pages.md) 中的 `plugins_ets_runtime_ets_*`


