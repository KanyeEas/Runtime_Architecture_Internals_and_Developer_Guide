# Flow：FileManager 加载 `.abc` / `.an` → ClassLinker/AotManager

## 0) 在端到端主线图中的位置

- 总入口：[ClassLoading_EndToEnd（Flow）](ClassLoading_EndToEnd.md)（“输入（文件/上下文）”框：.abc/.an 如何进入 runtime）

## 1) `.abc`（panda file）加载

`FileManager::LoadAbcFile(location, openMode)`：
- `OpenPandaFile(location, "", openMode)` 打开 `.abc`
- 若启用 `.an` 且非 ArkAot：
  - 先尝试加载对应 `.an`（AOT 文件）
  - 若找到 AOT panda file，则把 `class hash table` 回填给 panda file（加速查找）
- `Runtime::GetCurrent()->GetClassLinker()->AddPandaFile(std::move(pf))`
  - 触发：pandaFiles 注册、bootPandaFiles、boot bloom filter、notification/debug 注册

## 2) `.an`（AOT）加载

`FileManager::LoadAnFile(anLocation, force)`：
- 计算绝对路径作为 key
- 根据 runtime options + runtime type 推导 `gcType`
- `AotManager::AddFile(path, runtimeIface, gcType, force)` 返回 Expected（含错误字符串）

## 3) 证据链

- [runtime_include_file_manager.h（FileNotes）](../FileNotes/runtime_include_file_manager.h.md)
- [runtime_file_manager.cpp（FileNotes）](../FileNotes/runtime_file_manager.cpp.md)
- [runtime_class_linker.cpp（FileNotes）](../FileNotes/runtime_class_linker.cpp.md)（AddPandaFile）

## 下一步（新人推荐）

- 想看“boot/app 可见域是怎么分的（boot bloom filter 什么时候生效）” → [GetClass_and_LoadClass（Flow）](GetClass_and_LoadClass.md)
- 想看“AOT class context/装载入口（跨章）” → [compiler_aot_aot_manager.cpp（FileNotes）](../../04_ExecutionEngine/FileNotes/compiler_aot_aot_manager.cpp.md) 与 [compiler_aot_aot_file.cpp（FileNotes）](../../04_ExecutionEngine/FileNotes/compiler_aot_aot_file.cpp.md)


