# `plugins/ets/runtime/ets_language_context.cpp`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：ETS 的 `LanguageContextBase` 实现：把“语言策略”落到具体 builder / VM / GC / 异常机制。  
> 文件规模：约 108 行（实现集中，主要是工厂方法与异常桥接）。

## 1. include 与依赖定位（L16–L26）

该 `.cpp` 明确揭示 ETS 在 03 章的关键实现点：
- **L16**：`ets_itable_builder.h`：ETS 的 ITableBuilder 实现（已逐行：见 [plugins_ets_runtime_ets_itable_builder.h](plugins_ets_runtime_ets_itable_builder.h.md) / [plugins_ets_runtime_ets_itable_builder.cpp](plugins_ets_runtime_ets_itable_builder.cpp.md)）。
- **L18**：`ets_vtable_builder.h`：ETS 的 VTableBuilder 实现（本章目前以 `EtsVTableBuilder` 为“存在点”说明；其逐行可在后续按动态发现纳入，若你希望把 ETS vtable override 规则也完全闭环到代码）。
- **L19–L24**：ETS 的方法/字符串/异常/handle scope：用于异常创建与 ThrowStackOverflow。

## 2. ThrowException（L29–L33）

- 把 `ManagedThread*` cast 成 `EtsCoroutine*`（ETS 的线程/协程模型）。
- 调用 `ThrowEtsException(coroutine, name, msg)`，把 MUTF8 descriptor 转为 C string。

> 语义：LanguageContext 负责“抛异常的统一入口”，但具体异常对象创建在 ETS runtime 子系统中完成。

## 3. CreateITableBuilder / CreateVTableBuilder（L35–L43）

- **L35–L38**：`CreateITableBuilder(errHandler)` → `MakePandaUnique<EtsITableBuilder>(errHandler)`  
  结论：ETS 的 itable 构建算法在 `EtsITableBuilder`，与 core 的空实现不同。
- **L40–L43**：`CreateVTableBuilder(errHandler)` → `MakePandaUnique<EtsVTableBuilder>(errHandler)`  
  结论：ETS 也有自己的 vtable builder（可能在 override/接口默认方法策略上做 ETS 特化）。

> 与 `class_linker.cpp` 对齐：`SetupClassInfo` 正是通过 `LanguageContext::Create*Builder` 注入这两个 builder。

## 4. CreateVM（L45–L56）

调用 `ets::PandaEtsVM::Create(runtime, options)`：
- 失败：打印错误并返回 nullptr
- 成功：返回 VM 指针

> 这把“RuntimeOptions → 具体语言 VM” 的构建权交给 LanguageContext。

## 5. CreateGC（L58–L62）

`mem::CreateGC<EtsLanguageConfig>(gcType, objectAllocator, settings)`：
- ETS 的 GC 配置通过 `EtsLanguageConfig` 参与选择/实例化（不同语言可能影响 barrier/对象模型）。

## 6. ThrowStackOverflowException（L64–L77）

关键链路：
- `EtsCoroutine::CastFromThread(thread)` 获取协程
- 取 `EtsClassLinker*`（通过 VM）
- `GetStackOverflowErrorClassDescriptor()` 得到异常类 descriptor
- `classLinker->GetClass(descriptor, true)` 获取 `EtsClass*`
- 创建异常对象 `EtsObject::Create(cls)` 并设置到 coroutine exception

> 这对应 core 语言里用 `ObjectHeader::Create(cls)` 创建异常对象的路径，但 ETS 使用 ETS 类型系统包装。

## 7. GetVerificationInitAPI（L79–L105）

返回 verification 初始化数据：
- **primitiveRootsForVerification**：包含 TAGGED/VOID/U1..F64 等类型集合
- **arrayElementsForVerification**：`[Z [B [S [C [I [J [F [D`（布尔/字节/短/char/int/long/float/double）
- **isNeed*SyntheticClass**：
  - need Class synthetic：true
  - need Object/String synthetic：false

> 这直接影响 verification 章节（06）的“基础类型 roots 与合成类需求”。


