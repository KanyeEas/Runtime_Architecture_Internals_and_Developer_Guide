# Method（运行时方法元数据对象）

## 0) 在端到端主线图中的位置

- 总入口：[../Flows/ClassLoading_EndToEnd](../Flows/ClassLoading_EndToEnd.md)（“LoadMethods：设置 entrypoint / copied methods”框；以及后续执行入口跨章）

## 它是什么

`Method` 是运行时对“一个方法/函数”的元数据对象，负责承载：
- 签名（Proto/ProtoId/shorty）
- 访问标志位（含 compilation/verification stage 位段）
- 派发索引（vtableIndex）
- 执行入口点（解释器桥接 / JIT/AOT / native / stub）
- 热点计数与 profilingData（union 复用槽）

## 关键字段/不变量

- **签名**：
  - `Proto`：展开 shorty/refTypes
  - `ProtoId`：轻量标识（pf + proto EntityId），用于 override/兼容判断
  - `shorty_`：指向 proto shorty 数据
- **入口点**：
  - `compiledEntryPoint_`（atomic）：默认指向 C2I bridge；native 指向 ANI/critical/async；AOT 可覆盖
  - `SetInterpreterEntryPoint()`：把非 native 方法重置为 C2I bridge
- **状态位段**（都塞进 `accessFlags_`）：
  - `CompilationStage`（NOT_COMPILED/WAITING/COMPILATION/COMPILED/FAILED）
  - `VerificationStage`
  - 访问标志（ACC_*）与运行期标记（DEFAULT_INTERFACE_METHOD/DESTROYED/PROFILING…）
- **派发索引**：
  - `stor16Pair_.vtableIndex`：由 vtable builder 的 `UpdateClass` 写回
- **profilingData vs nativePointer**：
  - union `PointerInMethod`：native/proxy 使用 `nativePointer`，否则使用 `profilingData`

## 谁写它、谁读它（对齐点）

- **创建与入口点设置**：`runtime/class_linker.cpp::LoadMethod/LoadMethods/SetupCopiedMethods`
- **native 入口点策略（ETS）**：`plugins/ets/runtime/ets_class_linker_extension.cpp::GetNativeEntryPointFor`
- **派发索引写回**：`vtableBuilder->UpdateClass`（class_linker.cpp::LinkMethods 调用）
- **调用与 frame 相关入口**：`Method::Invoke/InvokeDyn/InvokeContext`（执行引擎章节 04 详述）

## 证据链

- [FileNotes/runtime_include_method.h](FileNotes/runtime_include_method.h.md)
- [FileNotes/runtime_class_linker.cpp](FileNotes/runtime_class_linker.cpp.md)
- [FileNotes/plugins_ets_runtime_ets_class_linker_extension.cpp](FileNotes/plugins_ets_runtime_ets_class_linker_extension.cpp.md)

## 下一步（新人推荐）

- 想看“entrypoint 在运行期如何影响解释器↔compiled 派发（跨章）” → [04_ExecutionEngine/README](../../04_ExecutionEngine/README.md)
- 想看“LinkMethods 如何写回 vtableIndex/派发结构” → [../Flows/Builders_and_LinkMethods](../Flows/Builders_and_LinkMethods.md)

