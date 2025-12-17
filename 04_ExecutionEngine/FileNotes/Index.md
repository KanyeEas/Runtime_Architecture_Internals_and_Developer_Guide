# 04 ExecutionEngine / FileNotes / Index

本目录是 **源码证据链卡片**：每个文件一页，说明“负责什么、关键入口、常见坑、与 Flows/DataStructures 的对应关系”。

## 快速入口

- 术语表：[_Glossary](./_Glossary.md)
- 解释器选型/执行入口（关键）：[runtime_interpreter_interpreter_impl.cpp](./runtime_interpreter_interpreter_impl.cpp.md)
- 解释器模板生成（主循环/异常槽位来源）：[runtime_interpreter_templates_interpreter-inl_gen.h.erb](./runtime_interpreter_templates_interpreter-inl_gen.h.erb.md)
- Bridge 骨架（InvokeInterpreter 等）：[runtime_bridge_bridge.cpp](./runtime_bridge_bridge.cpp.md)
- Entrypoints：[runtime_entrypoints_entrypoints.cpp](./runtime_entrypoints_entrypoints.cpp.md)
- OSR：[runtime_osr.cpp](./runtime_osr.cpp.md)
- StackWalker：[runtime_stack_walker.cpp](./runtime_stack_walker.cpp.md)

## 说明

- 本章文件很多，**完整列表请看**：[All_Pages（全量页面索引）](../../All_Pages.md)（可搜索 `04_ExecutionEngine/FileNotes/`）。






