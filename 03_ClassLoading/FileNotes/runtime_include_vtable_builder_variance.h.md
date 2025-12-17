# `runtime/include/vtable_builder_variance.h`（逐行精读）

> 章节归属：Stage2 / 03_ClassLoading  
> 文件类型：Variance vtable builder 的声明（把“基础流程骨架”与“覆盖/冲突策略实现”拼装起来）。

## 1. 文件定位（为什么要单独有 variance builder）

`VTableBuilderBase` 的骨架流程通过两个虚函数钩子注入策略：
- `ProcessClassMethod`：本类方法如何覆盖 base 方法、如何处理 final/multiple override。
- `ProcessDefaultMethod`：接口默认方法如何决定是否 copied、如何处理 multiple implement 冲突。

Variance builder 提供了一种具体策略：允许通过 `ProtoCompatibility(ctx)` 判定更宽松的 proto 覆盖关系（例如协变返回类型），并可通过 `OverridePred` 增加额外可覆盖谓词（访问控制/语言规则等）。

## 2. 头部与依赖（L1–L20）

- **L15–L16**：include guard：`PANDA_RUNTIME_VTABLE_BUILDER_VARIANCE_H`。
- **L18**：`runtime/class_linker_context.h`：构造 `ProtoCompatibility(ctx)` 时需要上下文。
- **L19**：`runtime/include/vtable_builder_base.h`：继承基础骨架与 `MethodInfo/VTableInfo` 等定义。

## 3. `VarianceVTableBuilder<ProtoCompatibility, OverridePred>`（L23–L38）

- **L23–L24**：模板参数：
  - `ProtoCompatibility`：可调用对象类型，形如 `ProtoCompatibility(ctx)(baseProto, dervProto)`。
  - `OverridePred`：可调用对象类型，形如 `OverridePred()(baseInfo, dervInfo)`。
- **L24**：继承自 `VTableBuilderBase<false>`：
  - `false` 表示默认方法枚举时 **不遍历 super itable 区间**（见 `vtable_builder_base-inl.h` 的 `traverseUpTo` 逻辑）。
- **L26**：构造函数：仅转发 `ClassLinkerErrorHandler*` 给基类（用于冲突上报）。

私有区（实现都在 `vtable_builder_variance-inl.h`）：
- **L29–L30**：覆盖基类钩子：
  - `ProcessClassMethod`
  - `ProcessDefaultMethod`
- **L32**：`ScanConflictingDefaultMethods`：用于 default 方法冲突扫描（返回 optional 表示 skip/ok/conflict）。
- **L34–L37**：两个静态 helper：
  - `IsOverriddenBy`
  - `IsOverriddenOrOverrides`

## 4. 读者路线（与 inl 文件拼装）

要理解 variance builder 的完整语义，请按以下顺序阅读：
- `runtime/include/vtable_builder_base.h`（骨架+数据结构）
- `runtime/include/vtable_builder_base-inl.h`（Build 顺序与 itable 倒序枚举）
- `runtime/include/vtable_builder_variance.h`（本文件：声明拼装点）
- `runtime/include/vtable_builder_variance-inl.h`（具体覆盖/冲突策略）


